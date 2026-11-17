"""
validate_graph.py -- Check a graph loaded by load_neo4j.py against its CSVs.

load_neo4j.py already compares per-label / per-type counts. This adds the
checks a count can hide:

  * every constraint and index in the schema module exists and is ONLINE
  * the PARTICIPATES_IN shortfall equals the exact-duplicate rows in the CSV
  * no orphan nodes (Organisation, Country, Sector, ... with no relationship)
  * every Activity has one REPORTS and at least one TARGETS
  * required properties are present (filter provenance, transaction value/date)
  * per-publisher activity counts, optionally against a baseline graph dir

    python retrieval/validate_graph.py --env PATH --graph-dir DIR [--baseline-dir DIR]

Read-only: every query runs in a read transaction. Exit code 1 on any FAIL.
"""
import argparse
import csv
import importlib
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_neo4j import DEFAULT_GRAPH_DIR, connect, load_env  # noqa: E402

# labels whose nodes must each have at least one relationship
NO_ORPHANS = ["Activity", "Organisation", "Country", "Sector", "Transaction", "Budget", "Location", "SDG"]
REQUIRED_PROPS = {
    "Activity": ["iati_identifier", "publisher", "title", "match_basis", "start_date"],
    "Transaction": ["tx_id", "type", "value", "currency", "date"],
    "Organisation": ["ref"],
}


def rows(graph_dir, fname):
    with open(graph_dir / fname, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def publisher_counts(graph_dir):
    return Counter(r["publisher"] for r in rows(graph_dir, "nodes_activities.csv"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", help="path to .env")
    ap.add_argument("--graph-dir", default=str(DEFAULT_GRAPH_DIR))
    ap.add_argument("--baseline-dir", help="graph CSVs to compare activity counts against")
    ap.add_argument("--schema", default="schema_prototype")
    args = ap.parse_args()
    schema = importlib.import_module(args.schema)
    graph_dir = Path(args.graph_dir)

    load_env(args.env)
    driver, database = connect()
    print(f"validating {os.environ['NEO4J_URI']} against {graph_dir}\n")
    failures = []

    def check(name, ok, detail=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  -- ' + detail if detail else ''}")
        if not ok:
            failures.append(name)

    def q(cypher, **params):
        return s.execute_read(lambda tx: list(tx.run(cypher, **params)))

    with driver, driver.session(database=database) as s:
        print("constraints and indexes")
        cons = {r["name"] for r in q("SHOW CONSTRAINTS YIELD name")}
        want = {c.split()[2] for c in schema.CONSTRAINTS}
        check("all schema constraints exist", want <= cons, f"missing {sorted(want - cons)}" if want - cons else f"{len(want)}")
        idx = {r["name"]: r["state"] for r in q("SHOW INDEXES YIELD name, state")}
        want_idx = {c.split()[2] for c in schema.INDEXES}
        missing = sorted(want_idx - idx.keys())
        offline = sorted(n for n, st in idx.items() if st != "ONLINE")
        check("all schema indexes exist and are ONLINE", not missing and not offline,
              f"missing {missing}, offline {offline}" if missing or offline else f"{len(want_idx)}")

        print("\nrelationship deviations")
        part = rows(graph_dir, "rel_participates.csv")
        distinct = len({(r["org_ref"], r["iati_identifier"], r["role"]) for r in part})
        got = q("MATCH ()-[p:PARTICIPATES_IN]->() RETURN count(p) AS c")[0]["c"]
        check("PARTICIPATES_IN = distinct (org, activity, role) CSV rows", got == distinct,
              f"{len(part)} CSV rows, {distinct} distinct, {got} in db")

        print("\nsource ids (benchmark evidence)")
        n = q("MATCH (n) WHERE NOT n:LoadMeta AND n.source_id IS NULL RETURN count(n) AS c")[0]["c"]
        check("every node has a source_id", n == 0, f"{n} without" if n else "")
        n = q("MATCH ()-[r]->() WHERE r.source_ids IS NULL RETURN count(r) AS c")[0]["c"]
        check("every relationship has source_ids", n == 0, f"{n} without" if n else "")
        got = q("MATCH ()-[p:PARTICIPATES_IN]->() RETURN sum(size(p.source_ids)) AS c")[0]["c"]
        check("collapsed PARTICIPATES_IN edges keep every CSV row", got == len(part), f"{got} of {len(part)} rows")

        print("\nexact money (value_cents)")
        for label, fname in (("Transaction", "nodes_transactions.csv"), ("Budget", "nodes_budgets.csv")):
            want = sum(schema._cents(r["value"]) or 0 for r in rows(graph_dir, fname))
            got = q(f"MATCH (n:{label}) RETURN sum(n.value_cents) AS c, "
                    f"count(n.value) - count(n.value_cents) AS missing")[0]
            check(f"{label}.value_cents sums to the exact CSV total", got["c"] == want and got["missing"] == 0,
                  f"db {got['c']} vs csv {want}, {got['missing']} rows without value_cents")

        print("\norphans and structure")
        for label in NO_ORPHANS:
            n = q(f"MATCH (n:{label}) WHERE NOT (n)--() RETURN count(n) AS c")[0]["c"]
            check(f"no orphan {label} nodes", n == 0, f"{n} orphans" if n else "")
        bad = q("MATCH (a:Activity) WITH a, COUNT { (:Organisation)-[:REPORTS]->(a) } AS r "
                "WHERE r <> 1 RETURN count(a) AS c")[0]["c"]
        check("every Activity has exactly one reporting org", bad == 0, f"{bad} activities" if bad else "")
        bad = q("MATCH (a:Activity) WHERE NOT (a)-[:TARGETS]->(:Country) RETURN count(a) AS c")[0]["c"]
        check("every Activity targets a country", bad == 0, f"{bad} activities" if bad else "")
        bad = q("MATCH (a:Activity) WHERE any(c IN a.hotspot_countries WHERE NOT (a)-[:TARGETS]->(:Country {code: c})) "
                "RETURN count(a) AS c")[0]["c"]
        check("hotspot_countries agrees with TARGETS", bad == 0, f"{bad} activities" if bad else "")

        print("\nrequired properties")
        act_cols = rows(graph_dir, "nodes_activities.csv")[0].keys()
        # hunger-filter provenance columns exist only in the Fall 2026 pipeline output
        REQUIRED_PROPS["Activity"] += [c for c in ("confidence", "review_status") if c in act_cols]
        for label, props in REQUIRED_PROPS.items():
            for p in props:
                n = q(f"MATCH (n:{label}) WHERE n.{p} IS NULL RETURN count(n) AS c")[0]["c"]
                check(f"{label}.{p} never null", n == 0, f"{n} nulls" if n else "")

        print("\nfilter provenance (from the hunger filter)")
        for prop in ("match_basis", "confidence", "review_status"):
            dist = {r["v"]: r["c"] for r in q(f"MATCH (a:Activity) RETURN a.{prop} AS v, count(*) AS c ORDER BY c DESC")}
            print(f"  {prop:<14} {dist}")

        print("\nnegative transactions")
        for r in q("MATCH (a:Activity)-[:HAS_TRANSACTION]->(t:Transaction) "
                   "RETURN a.publisher AS pub, count(t) AS n, sum(CASE WHEN t.value < 0 THEN 1 ELSE 0 END) AS neg "
                   "ORDER BY pub"):
            print(f"  {r['pub']:<8} {r['neg']:>6} of {r['n']:>6} rows negative ({r['neg'] / r['n']:.0%})")

        print("\nactivities per publisher")
        db_counts = {r["p"]: r["c"] for r in q("MATCH (a:Activity) RETURN a.publisher AS p, count(*) AS c")}
        csv_counts = publisher_counts(graph_dir)
        check("per-publisher counts match CSV", db_counts == dict(csv_counts))
        base = publisher_counts(Path(args.baseline_dir)) if args.baseline_dir else None
        print(f"  {'publisher':<10} {'baseline':>9} {'now':>6}" if base else f"  {'publisher':<10} {'now':>6}")
        for p in sorted(set(csv_counts) | set(base or {})):
            print(f"  {p:<10} {base.get(p, 0):>9} {csv_counts.get(p, 0):>6}" if base else f"  {p:<10} {csv_counts[p]:>6}")
        if base:
            print(f"  {'total':<10} {sum(base.values()):>9} {sum(csv_counts.values()):>6}")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} FAILED: {failures}'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
