"""Build web/static/data.json from the repository, so the page always shows the code and data as committed.

    python fa26/web/build_site.py            # writes fa26/web/static/data.json

What it reads (nothing is typed by hand):
  src/tools/templates.py, src/tools/adapter.py, src/tools/resolver.py, src/tools/contract.py  -> libraries
  retrieval/schema_prototype.py + benchmark/snapshot/*.csv                                     -> graph schema and counts
  scripts/smoke_templates.py (v1) and scripts/smoke_v2_development.py (development)            -> benchmark coverage
  benchmark/questions.json, benchmark/v2/questions.json + splits.json                         -> question text
Only regression (v1) and development questions are used; heldout questions are never read into the page.
Example results are recomputed from the snapshot CSVs with each template's rule (Decimal sums).
"""
from __future__ import annotations

import ast
import csv
import json
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

FA26 = Path(__file__).resolve().parents[1]
SNAP = FA26 / "benchmark" / "snapshot"
OUT = FA26 / "web" / "static" / "data.json"
for p in (FA26 / "web", FA26 / "src"):
    sys.path.insert(0, str(p))
sys.path.append(str(FA26 / "retrieval"))  # after src: retrieval/tools.py must not shadow the src/tools package

from tools import templates as T, adapter as AD, contract as CT  # noqa: E402
from tools.resolver import OrgResolver, ALIAS_GROUPS  # noqa: E402
import schema_prototype as SP  # noqa: E402
from views import build_views  # noqa: E402

csv.field_size_limit(10_000_000)
_TABLES: dict[str, list[dict]] = {}


def table(name: str) -> list[dict]:
    if name not in _TABLES:
        with (SNAP / name).open(encoding="utf-8", newline="") as fh:
            _TABLES[name] = list(csv.DictReader(fh))
    return _TABLES[name]


def routes(path: Path, var: str | None = None) -> dict:
    tree = ast.parse(path.read_text())
    alias = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
             if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict) and n.value.keys \
                and isinstance(n.value.keys[0], ast.Constant) and re.match(r"V?2?Q\d", str(n.value.keys[0].value)) \
                and (var is None or n.targets[0].id == var):
            out = {}
            for k, v in zip(n.value.keys, n.value.values):
                if not isinstance(v, ast.Tuple):
                    continue
                name = v.elts[0]
                name = alias.get(name.id) if isinstance(name, ast.Name) else ast.literal_eval(name)
                out[ast.literal_eval(k)] = (name, ast.literal_eval(v.elts[1]))
            if out:
                return out
    return {}


def category(src: str, name: str) -> str:
    secs = [(m.start(), m.group(1).strip()) for m in re.finditer(r"# -+ ([a-z ()0-9]+)\n", src)]
    pos, cat = src.find(f'"{name}": {{'), None
    for p, s in secs:
        if p < pos:
            cat = s
    return cat or "other"


# ------------------------------------------------------------------ offline template rules (examples only)
def ev_id(tbl: str, i: int) -> str:
    return f"{tbl}:row:{i}"


def tx_total(publisher: str, type_code: str, currency: str, measure: str = "net", date_from=None, date_to=None):
    acts = {r["iati_identifier"]: (i, r) for i, r in enumerate(table("nodes_activities.csv"), 1)}
    total, ev, act_ev = Decimal(0), [], set()
    for i, t in enumerate(table("nodes_transactions.csv"), 1):
        a = acts.get(t["iati_identifier"])
        if not a or a[1]["publisher"] != publisher or t["type"] != type_code or t["currency"] != currency:
            continue
        if date_from and not (t["date"] and t["date"] >= date_from):
            continue
        if date_to and not (t["date"] and t["date"] < date_to):
            continue
        v = Decimal(t["value"])
        if (measure == "amount" and v <= 0) or (measure == "adjustments" and v >= 0):
            continue
        total += v; ev.append(ev_id("nodes_transactions.csv", i)); act_ev.add(ev_id("nodes_activities.csv", a[0]))
    return {"total": {"value": f"{total:.2f}", "evidence": sorted(ev + sorted(act_ev))}}


def per_publisher_count():
    by = {}
    for i, a in enumerate(table("nodes_activities.csv"), 1):
        by.setdefault(a["publisher"], []).append(ev_id("nodes_activities.csv", i))
    return {k: {"value": str(len(v)), "evidence": v} for k, v in sorted(by.items())}


def count_all():
    ids = [ev_id("nodes_activities.csv", i) for i in range(1, len(table("nodes_activities.csv")) + 1)]
    return {"count": {"value": str(len(ids)), "evidence": ids}}


# Map positions for the globe. Not in the IATI data: publisher head offices and the capital of each hotspot country.
HQ = {"Oxfam GB": [51.75, -1.26], "Oxfam America": [42.36, -71.06], "WFP": [41.90, 12.50]}
CAPITALS = {"SD": [15.50, 32.56], "SS": [4.85, 31.58], "YE": [15.37, 44.19], "PS": [31.50, 34.47], "NG": [9.06, 7.49],
            "SO": [2.05, 45.32], "AF": [34.53, 69.17], "CD": [-4.32, 15.31], "HT": [18.59, -72.31], "LB": [33.89, 35.50],
            "MG": [-18.88, 47.51], "MM": [19.76, 96.08], "ML": [12.64, -8.00]}
PUB = {"oxfamgb": "Oxfam GB", "oxfamus": "Oxfam America", "wfp": "WFP"}


def globe():
    names = {r["code"]: r["name"] for r in table("nodes_countries.csv")}
    pairs, per_c = Counter(), Counter()
    for a in table("nodes_activities.csv"):
        c = a["hotspot_countries"]
        if c in CAPITALS:
            pairs[(PUB.get(a["publisher"], a["publisher"]), names.get(c, c))] += 1
            per_c[names.get(c, c)] += 1
    return {"hq": HQ, "countries": {names.get(c, c): v for c, v in CAPITALS.items()}, "activities": dict(per_c),
            "links": [{"publisher": p, "country": c, "activities": n} for (p, c), n in sorted(pairs.items(), key=lambda kv: -kv[1])]}


EXAMPLES = {  # benchmark question -> offline rule with the template's arguments
    "Q12": lambda a: tx_total(**a),
    "Q10": lambda a: tx_total(**a),
    "V2Q059": lambda a: tx_total(**a),
    "Q01": lambda a: per_publisher_count(),
    "V2Q001": lambda a: count_all(),
}


def evidence_rows(facts: dict) -> list[dict]:
    ids = sorted({e for f in facts.values() for e in f["evidence"] if not e.startswith("manifest:")})
    out = []
    for e in ids:
        t, _, n = e.partition(":row:")
        out.append({"id": e, "table": t, "row": int(n), **table(t)[int(n) - 1]})
    return out


def main():
    src = (FA26 / "src" / "tools" / "templates.py").read_text()
    splits = json.loads((FA26 / "benchmark" / "v2" / "splits.json").read_text())
    dev = set(splits["development"])
    v1q = {q["id"]: q["question"] for q in json.loads((FA26 / "benchmark" / "questions.json").read_text())}
    v2q = {q["id"]: q["question"] for q in json.loads((FA26 / "benchmark" / "v2" / "questions.json").read_text()) if q["id"] in dev}
    r1 = routes(FA26 / "scripts" / "smoke_templates.py", "ROUTE")
    r2 = routes(FA26 / "scripts" / "smoke_v2_development.py")
    bench = {}
    for qid, (tool, args) in list(r1.items()) + list(r2.items()):
        text = v1q.get(qid) if qid.startswith("Q") else v2q.get(qid)
        if tool in T.TOOLS and text:
            bench.setdefault(tool, []).append({"id": qid, "split": "regression (v1)" if qid.startswith("Q") else "development", "q": text, "args": args})

    results, examples = {}, {}
    for qid, rule in EXAMPLES.items():
        hit = next(((t, b) for t, bs in bench.items() for b in bs if b["id"] == qid), None)
        if not hit:
            continue
        tool, b = hit
        facts = rule(b["args"])
        for f in facts.values():  # zero result: cite the searched tables, as tools.templates.run_tool does
            if not f["evidence"] and Decimal(f["value"]) == 0 and tool in T.MANIFEST_SCOPE:
                f["evidence"] = sorted(f"manifest:{m}" for m in T.MANIFEST_SCOPE[tool])
        ans = {"id": qid, "question": b["q"], "status": "answer", "facts": facts, "tool": tool, "args": b["args"],
               "cypher": T.TOOLS[tool]["cypher"].strip(), "reasons": [], "timings": None}
        results[qid] = {"rows": [{"key": k, "value": f["value"], "evidence": len(f["evidence"])} for k, f in facts.items()]}
        views = build_views(ans, evidence_rows(facts), table)
        ans["facts"] = {k: {"value": f["value"], "evidence_n": len(f["evidence"])} for k, f in facts.items()}  # same shape as /api/ask
        examples[qid] = {"answer": ans, "views": views}

    R = OrgResolver.from_csv(SNAP / "nodes_organisations.csv")
    demos = {}
    for q in ["Oxfam", "the UK government", "WFP", "US-EIN-23-7069110", "Congo", "Oxfam Novib"]:
        o = R.resolve(q)
        demos[q] = {"kind": o["kind"], "group": o["group"], "n": len(o["refs"]), "note": o["note"],
                    "via": o["candidates"][0]["via"] if o["candidates"] else None,
                    "cands": [{"ref": c.get("ref", c.get("code")), "name": c["name"], "via": c["via"]} for c in o["candidates"][:6]]}

    edges = Counter(r["edge"] for r in table("rel_transaction_edges.csv"))
    rel_rows = {}
    for k, (f, flt) in SP.REL_COUNTS.items():
        rel_rows[k] = edges.get(flt["edge"], 0) if flt else len(table(f))
    manifest = json.loads((FA26 / "benchmark" / "manifest.json").read_text())

    data = {
        "templates": [{"name": k, "cat": category(src, k), "description": v["description"], "params": v["params"],
                       "cypher": v["cypher"].strip(), "coverage": v["coverage"], "bench": bench.get(k, [])} for k, v in T.TOOLS.items()],
        "tools": [{"name": k, "fn": v["fn"], "description": v["description"], "params": v["params"], "money": k in AD.MONEY_TOOLS}
                  for k, v in AD.RETRIEVAL_TOOLS.items()],
        "groups": [{"group": g, "aliases": al, "patterns": pats, "members": [{"ref": o["ref"], "name": o["name"]} for o in R.group_members(g)]}
                   for g, (al, pats) in ALIAS_GROUPS.items()],
        "demos": demos,
        "reasons": {"v1": CT.V1_REASONS, "v2": [r for r in __import__("ask").REASON_CODES if r.islower()]},
        "schema": {"nodes": {k: len(table(v)) for k, v in SP.NODE_COUNTS.items()}, "rels": rel_rows, "deviations": SP.EXPECTED_DEVIATIONS},
        "manifest": sorted(manifest["files"]) if isinstance(manifest["files"], list) else sorted(manifest["files"]),
        "results": results,
        "examples": examples,
        "dataset": {"name": "benchmark snapshot", "activities": len(table("nodes_activities.csv"))},
        "globe": globe(),
        "expected_counts": {"nodes": sum(len(table(v)) for v in SP.NODE_COUNTS.values()),
                            "relationships": sum(rel_rows.values()) - len(table("rel_participates.csv"))
                            + len({tuple(r.values()) for r in table("rel_participates.csv")})},  # duplicate participation rows merge on load
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(FA26)}: {len(data['templates'])} templates, {len(data['tools'])} tools, "
          f"{len(data['groups'])} alias groups, {len(examples)} examples")


if __name__ == "__main__":
    main()
