"""Independent pandas implementations of the overlapping tool questions, computed from the pinned snapshot CSVs.

Used by notebook 07 to cross-check the Cypher templates (src/tools/templates.py) and Alex's retrieval
tools (fa26/retrieval/tools.py) against a third implementation that never touches Neo4j, in the same
spirit as the benchmark's SQL baseline. Values are Decimal sums of the exported strings.
"""
from __future__ import annotations
import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

PUBLISHER_REF = {"oxfamgb": "GB-CHC-202918", "oxfamus": "US-EIN-23-7069110", "wfp": "XM-DAC-41140"}


def load(snapshot_dir: str | Path) -> dict:
    csv.field_size_limit(10_000_000)
    t = {}
    for p in sorted(Path(snapshot_dir).glob("*.csv")):
        with p.open(encoding="utf-8", newline="") as fh:
            t[p.stem] = list(csv.DictReader(fh))
    t["_act"] = {a["iati_identifier"]: a for a in t["nodes_activities"]}
    return t


def top_funders(t, publisher, type_code="1", currency=None, limit=10):
    """Provider ref -> net sum of transactions of type_code on the publisher's activities (per currency)."""
    tx = {r["tx_id"]: r for r in t["nodes_transactions"]}
    out = defaultdict(Decimal)
    for e in t["rel_transaction_edges"]:
        if e["edge"] != "PROVIDED_BY":
            continue
        r = tx[e["tx_id"]]
        if r["type"] != type_code or t["_act"][r["iati_identifier"]]["publisher"] != publisher:
            continue
        if currency and r["currency"] != currency:
            continue
        out[(e["org_ref"], r["currency"])] += Decimal(r["value"])
    rows = sorted(out.items(), key=lambda kv: -kv[1])[:limit]
    return {f"{ref} [{cur}]": v for (ref, cur), v in rows}


def shared_partners(t, pub_a, pub_b):
    """Org ref -> distinct activities across both publishers, for orgs participating in both."""
    pubs, acts = defaultdict(set), defaultdict(set)
    for r in t["rel_participates"]:
        p = t["_act"][r["iati_identifier"]]["publisher"]
        if p in (pub_a, pub_b):
            pubs[r["org_ref"]].add(p)
            acts[r["org_ref"]].add(r["iati_identifier"])
    return {ref: len(acts[ref]) for ref in acts if {pub_a, pub_b} <= pubs[ref]}


def funding_over_time(t, publisher, type_code, currency):
    """Year -> net sum for one publisher, type and currency (transaction-date year)."""
    out = defaultdict(Decimal)
    for r in t["nodes_transactions"]:
        if r["type"] == type_code and r["currency"] == currency and r["date"] and \
                t["_act"][r["iati_identifier"]]["publisher"] == publisher:
            out[r["date"][:4]] += Decimal(r["value"])
    return dict(sorted(out.items()))


def country_top_funders(t, country_code, type_codes=("1",), currency=None, exclude_self=True, limit=10):
    """Alex's definition: providers of transactions on activities targeting a country, optionally excluding
    the activity's own reporting organisation. Returns (ref, currency) -> net."""
    target = {r["iati_identifier"] for r in t["rel_targets_country"] if r["country_code"] == country_code}
    reporter = {r["iati_identifier"]: r["org_ref"] for r in t["rel_reports"]}
    tx = {r["tx_id"]: r for r in t["nodes_transactions"]}
    out = defaultdict(Decimal)
    for e in t["rel_transaction_edges"]:
        if e["edge"] != "PROVIDED_BY":
            continue
        r = tx[e["tx_id"]]
        a = r["iati_identifier"]
        if a not in target or r["type"] not in type_codes:
            continue
        if currency and r["currency"] != currency:
            continue
        if exclude_self and e["org_ref"] == reporter.get(a):
            continue
        out[(e["org_ref"], r["currency"])] += Decimal(r["value"])
    rows = sorted(out.items(), key=lambda kv: -kv[1])[:limit]
    return {f"{ref} [{cur}]": v for (ref, cur), v in rows}


def wfp_mirror(t):
    """Alex's finding: WFP type 2 (commitment) and type 4 (expenditure) totals are identical."""
    out = {}
    for code in ("2", "4"):
        rows = [r for r in t["nodes_transactions"] if r["type"] == code and t["_act"][r["iati_identifier"]]["publisher"] == "wfp"]
        out[code] = {"n": len(rows), "positive": sum((Decimal(r["value"]) for r in rows if Decimal(r["value"]) > 0), Decimal(0)),
                     "negative": sum((Decimal(r["value"]) for r in rows if Decimal(r["value"]) < 0), Decimal(0))}
    return out


def participation_duplicates(t):
    """Exact duplicate rows in rel_participates (same org, activity, role): the 59,121 vs 58,911 difference."""
    seen, dup = set(), 0
    for r in t["rel_participates"]:
        k = (r["org_ref"], r["iati_identifier"], r["role"])
        dup += k in seen
        seen.add(k)
    return dup
