"""
load_neo4j.py -- Load the prototype graph CSVs (data/graph/*.csv) into Neo4j.

Generic loader: all Cypher, casts and derived columns live in a schema
module (default: schema_prototype.py). Connection details come from a .env
file; nothing is hard-coded.

    python retrieval/load_neo4j.py              # load into an EMPTY database
    python retrieval/load_neo4j.py --reset      # wipe a DB this loader filled, then load
    python retrieval/load_neo4j.py --reset --force   # wipe even if someone else filled it
    python retrieval/load_neo4j.py --dry-run    # cast + count rows, no DB writes

.env keys: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE (optional)
"""
import argparse
import csv
import importlib
import json
import logging
import os
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, unit_of_work

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_GRAPH_DIR = ROOT / "data" / "graph"
BATCH = 2000
TX_TIMEOUT_S = 120


# ------------------------------------------------------------------ env --
def load_env(explicit=None):
    """Search .env in: --env path, prototype root, its parent."""
    candidates = [explicit] if explicit else [ROOT / ".env", ROOT.parent / ".env"]
    for p in candidates:
        if p and Path(p).exists():
            logging.getLogger("dotenv").setLevel(logging.ERROR)  # bare-URL line in .env
            load_dotenv(p, override=False)
            return Path(p)
    sys.exit("no .env found; pass --env PATH")


def connect():
    missing = [k for k in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD") if not os.environ.get(k)]
    if missing:
        sys.exit(f".env is missing {missing}")
    driver = GraphDatabase.driver(os.environ["NEO4J_URI"],
                                  auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
                                  connection_timeout=30)
    driver.verify_connectivity()
    return driver, os.environ.get("NEO4J_DATABASE") or None


# -------------------------------------------------------------- casting --
def cast(value, kind, anomalies, where):
    """Empty -> None. Bad values -> None and counted, never raise."""
    if value is None or value == "":
        return None
    try:
        if kind == "float":
            return float(value)
        if kind == "int":
            return int(value)
        if kind == "bool":
            return value.strip().lower() in ("true", "1", "yes")
        if kind == "date":
            return date.fromisoformat(value[:10])
        if kind == "datetime":
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:          # IATI times are naive; store one type
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except (ValueError, TypeError):
        anomalies[f"{where}: {kind} {value!r}"] += 1
        return None
    return value


def read_rows(graph_dir, schema, fname, where=None, columns=None, anomalies=None):
    """CSV -> list of dicts with casts + derived columns applied."""
    casts = schema.CASTS.get(fname, {})
    derive = schema.DERIVE.get(fname)
    anomalies = anomalies if anomalies is not None else Counter()
    rows = []
    with open(graph_dir / fname, newline="", encoding="utf-8") as f:
        for i, raw in enumerate(csv.DictReader(f), 1):    # numbered before filtering
            if where and any(raw.get(k) != v for k, v in where.items()):
                continue
            row = {k: cast(v, casts.get(k), anomalies, f"{fname}.{k}") if k in casts
                   else (v if v != "" else None) for k, v in raw.items()}
            row["source_id"] = f"{fname}:row:{i}"
            if derive:
                row.update(derive(row))
            if columns:
                row = {k: row[k] for k in columns}
            rows.append(row)
    return rows


def csv_count(graph_dir, fname, where=None):
    with open(graph_dir / fname, newline="", encoding="utf-8") as f:
        return sum(1 for r in csv.DictReader(f)
                   if not where or all(r.get(k) == v for k, v in where.items()))


# ----------------------------------------------------------------- neo4j --
@unit_of_work(timeout=TX_TIMEOUT_S)
def _run_batch(tx, cypher, rows):
    return tx.run(cypher, rows=rows).consume()


def run_batched(session, cypher, rows):
    for i in range(0, len(rows), BATCH):
        session.execute_write(_run_batch, cypher, rows[i:i + BATCH])


def db_is_empty(session):
    return session.run("MATCH (n) RETURN count(n) AS c").single()["c"] == 0


def loader_owns_db(session):
    return session.run("MATCH (m:LoadMeta {name: 'retrieval-loader'}) RETURN count(m) AS c").single()["c"] > 0


def wipe(session):
    # auto-commit transaction so CALL ... IN TRANSACTIONS is allowed
    session.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS").consume()
    for r in list(session.run("SHOW CONSTRAINTS YIELD name")):
        session.run(f"DROP CONSTRAINT `{r['name']}` IF EXISTS").consume()
    for r in list(session.run("SHOW INDEXES YIELD name, type WHERE type <> 'LOOKUP'")):
        session.run(f"DROP INDEX `{r['name']}` IF EXISTS").consume()


def counts(session):
    nodes = {r["label"]: r["c"] for r in session.run(
        "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS c")}
    rels = {r["t"]: r["c"] for r in session.run(
        "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c")}
    return nodes, rels


# ------------------------------------------------------------------ main --
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", help="path to .env")
    ap.add_argument("--graph-dir", default=str(DEFAULT_GRAPH_DIR))
    ap.add_argument("--schema", default="schema_prototype", help="schema module name in retrieval/")
    ap.add_argument("--reset", action="store_true", help="wipe the database first")
    ap.add_argument("--force", action="store_true", help="allow --reset on a DB this loader did not fill")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, str(HERE))
    schema = importlib.import_module(args.schema)
    graph_dir = Path(args.graph_dir)
    anomalies = Counter()
    t0 = time.time()

    # ---- read + cast everything up front so a bad CSV fails before any write
    node_batches = [(f, cy, read_rows(graph_dir, schema, f, w, cols, anomalies))
                    for f, cy, w, cols in schema.NODE_LOADS]
    rel_batches = [(f, cy, read_rows(graph_dir, schema, f, w, cols, anomalies))
                   for f, cy, w, cols in schema.REL_LOADS]
    print(f"schema {schema.NAME}: read {sum(len(r) for _, _, r in node_batches)} node rows, "
          f"{sum(len(r) for _, _, r in rel_batches)} relationship rows from {graph_dir}")
    if anomalies:
        print("cast anomalies (stored as null):")
        for k, n in anomalies.most_common():
            print(f"  {n:>6}  {k}")
    if args.dry_run:
        return

    env_path = load_env(args.env)
    driver, database = connect()
    print(f"connected to {os.environ['NEO4J_URI']} (from {env_path})")
    with driver, driver.session(database=database) as s:
        if not db_is_empty(s):
            if not args.reset:
                sys.exit("database is not empty; use --reset (and --force if it was not filled by this loader)")
            if not loader_owns_db(s) and not args.force:
                sys.exit("database has data not written by this loader; add --force to wipe it anyway")
            print("wiping existing data, constraints and indexes ...")
            wipe(s)

        for cy in schema.CONSTRAINTS + schema.INDEXES:
            s.run(cy).consume()
        print(f"created {len(schema.CONSTRAINTS)} constraints, {len(schema.INDEXES)} indexes")

        for fname, cy, rows in node_batches:
            t = time.time(); run_batched(s, cy, rows)
            print(f"  nodes  {fname:<28} {len(rows):>7} rows  {time.time() - t:5.1f}s")
        for fname, cy, rows in rel_batches:
            t = time.time(); run_batched(s, cy, rows)
            print(f"  rels   {fname:<28} {len(rows):>7} rows  {time.time() - t:5.1f}s")
        for cy in schema.POST_LOAD:
            s.run(cy).consume()

        # ---- counts vs CSV
        nodes, rels = counts(s)
        print(f"\n{'label / type':<18} {'csv rows':>9} {'in db':>9}  note")
        ok = True
        for label, fname in schema.NODE_COUNTS.items():
            exp, got = csv_count(graph_dir, fname), nodes.get(label, 0)
            flag = "" if exp == got else "MISMATCH"; ok &= exp == got
            print(f"{label:<18} {exp:>9} {got:>9}  {flag}")
        for rtype, (fname, where) in schema.REL_COUNTS.items():
            exp, got = csv_count(graph_dir, fname, where), rels.get(rtype, 0)
            note = ""
            if exp != got:
                note = schema.EXPECTED_DEVIATIONS.get(rtype, "MISMATCH")
                ok &= rtype in schema.EXPECTED_DEVIATIONS
            print(f"{rtype:<18} {exp:>9} {got:>9}  {note}")
        print(f"total nodes {sum(nodes.values())}, relationships {sum(rels.values())}, "
              f"{time.time() - t0:.0f}s; counts {'OK' if ok else 'HAVE UNEXPLAINED MISMATCHES'}")

        # ---- semantic spot check: Cypher vs CSV for one country
        country = "SO"
        db_top = [(r["org_ref"], r["total"], r["n"]) for r in s.run(schema.SPOT_CHECK_CYPHER, country=country)]
        acts = {r["iati_identifier"] for r in read_rows(graph_dir, schema, "nodes_activities.csv")
                if country in (r["hotspot_countries"] or [])}
        tx = {r["tx_id"]: r for r in read_rows(graph_dir, schema, "nodes_transactions.csv")
              if r["iati_identifier"] in acts and r["type"] == "1" and r["currency"] == "USD"}
        agg = {}
        for e in read_rows(graph_dir, schema, "rel_transaction_edges.csv", {"edge": "PROVIDED_BY"}):
            if e["tx_id"] in tx:
                tot, n = agg.get(e["org_ref"], (0.0, 0)); agg[e["org_ref"]] = (tot + tx[e["tx_id"]]["value"], n + 1)
        csv_top = sorted(((o, float(round(v)), n) for o, (v, n) in agg.items()), key=lambda x: -x[1])[:3]
        print(f"\nspot check: top USD incoming-funds providers into {country}")
        print(f"  cypher: {db_top}\n  csv:    {csv_top}\n  {'MATCH' if db_top == csv_top else 'DIFFER'}")

        s.run("MERGE (m:LoadMeta {name: 'retrieval-loader'}) SET m.schema = $schema, m.loaded_at = datetime(), "
              "m.source = $src, m.node_count = $n, m.rel_count = $r",
              schema=schema.NAME, src=str(graph_dir), n=sum(nodes.values()), r=sum(rels.values())).consume()


if __name__ == "__main__":
    main()
