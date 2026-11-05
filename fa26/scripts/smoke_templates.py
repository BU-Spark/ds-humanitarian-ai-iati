"""Live smoke test: run the 16 templates on the graph in .env with notebook 06's manual routes (Q01-Q16)
and score the result against the v1 answer key. Use after reloading the graph.

    conda activate iati
    python fa26/scripts/smoke_templates.py            # writes data/processed/06_submission_templates_manual_<run>.json
                                                      # and benchmark/results/live_<run>_smoke/comparison.md
Exit code 1 when any template errors or the overall score is below 100.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

FA26 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FA26 / "benchmark")); sys.path.insert(0, str(FA26 / "src"))
from common import verify_snapshot, load_json, save_json          # noqa: E402
from text2cypher_eval import guard_query                            # noqa: E402
from tools import run_tool                                          # noqa: E402
from dotenv import load_dotenv                                      # noqa: E402
from neo4j import GraphDatabase, Query, READ_ACCESS                 # noqa: E402

ROUTE = {
    "Q01": ("activities_per_publisher", {}),
    "Q02": ("hotspot_countries_per_publisher", {}),
    "Q03": ("activities_per_publisher_by_country", {"country_code": "SO"}),
    "Q04": ("multi_publisher_participants", {"min_publishers": 2}),
    "Q05": ("participants_by_role", {}),
    "Q06": ("activities_by_match_basis", {}),
    "Q07": ("count_activities_by_sector", {"publisher": "wfp", "sector_key": "1:72040"}),
    "Q08": ("activities_per_publisher", {"start_from": "2020-01-01", "start_to": "2026-01-01"}),
    "Q09": ("latest_update_per_publisher", {}),
    "Q10": ("transaction_total", {"publisher": "wfp", "type_code": "1", "currency": "USD", "date_from": "2020-01-01", "date_to": "2021-01-01"}),
    "Q11": ("transaction_total", {"publisher": "oxfamgb", "type_code": "3", "currency": "GBP", "date_from": "2020-01-01", "date_to": "2021-01-01"}),
    "Q12": ("transaction_total", {"publisher": "oxfamus", "type_code": "4", "currency": "USD"}),
    "Q13": ("negative_transactions_per_publisher", {}),
    "Q14": ("budget_total", {"type_code": "1", "status_code": "2", "currency": "USD"}),
    "Q15": ("activities_per_sdg", {}),
    "Q16": ("activities_with_location_per_publisher", {}),
}
POLICY = {"Q17": ("abstain", ["NEEDS_DATA_MISSING"]), "Q18": ("abstain", ["HISTORY_UNAVAILABLE"]),
          "Q19": ("clarify", ["FUNDING_DEFINITION_REQUIRED", "CURRENCY_BASIS_REQUIRED", "PERIOD_REQUIRED"]),
          "Q20": ("abstain", ["RAW_XML_UNAVAILABLE"])}


def fmt_value(v, kind):
    if kind == "integer": return str(int(round(float(v))))
    if kind == "decimal": return str(Decimal(str(v)).quantize(Decimal("0.01")))
    if kind == "date": return str(v)[:10]
    if isinstance(v, float) and not v.is_integer(): return str(Decimal(str(v)).quantize(Decimal("0.01")))
    if isinstance(v, (int, float)): return str(int(v))
    return str(v)


def main():
    load_dotenv(FA26 / ".env", override=False)
    snapshot_id = verify_snapshot()["snapshot_id"]
    questions = load_json(FA26 / "benchmark" / "questions.json")
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]))
    driver.verify_connectivity()
    db = os.environ.get("NEO4J_DATABASE") or "neo4j"

    def run_cypher(q, params=None):
        guard_query(q)
        with driver.session(database=db, default_access_mode=READ_ACCESS) as s:
            return [dict(r) for r in s.run(Query(q, timeout=60), **(params or {}))]

    print("graph nodes:", run_cypher("MATCH (n) RETURN count(n) AS c")[0]["c"],
          "| loader:", run_cypher("MATCH (m:LoadMeta) RETURN m.name AS n, m.schema AS s LIMIT 1") or "no LoadMeta (notebook 04 load)")
    answers, failed = [], []
    for q in questions:
        t0 = time.time()
        if q["id"] in ROUTE:
            name, args = ROUTE[q["id"]]
            try:
                res = run_tool(run_cypher, name, args)
                facts = {str(r["key"]): {"value": fmt_value(r["value"], q.get("value_type", "auto")),
                                         "evidence": sorted({str(e) for e in (r.get("evidence") or []) if e})} for r in res["rows"]}
                answers.append({"id": q["id"], "status": "answer", "facts": facts, "reasons": [], "latency_ms": round((time.time() - t0) * 1000, 1)})
                print(f"{q['id']} answer   facts={len(facts):<3} {name}")
            except Exception as e:
                failed.append(q["id"]); print(f"{q['id']} ERROR    {name}: {type(e).__name__}: {str(e)[:200]}")
                answers.append({"id": q["id"], "status": "answer", "facts": {}, "reasons": [], "latency_ms": None})
        else:
            status, reasons = POLICY[q["id"]]
            answers.append({"id": q["id"], "status": status, "facts": {}, "reasons": reasons, "explanation": "policy rule",
                            "latency_ms": round((time.time() - t0) * 1000, 1)})
    driver.close()
    out = FA26 / "data" / "processed" / f"06_submission_templates_manual_{run_id}.json"
    save_json(out, {"run_name": f"templates_manual__neo4j_templates__{run_id}", "snapshot_id": snapshot_id, "answers": answers})
    results = FA26 / "benchmark" / "results" / f"live_{run_id}_smoke"
    subprocess.run([sys.executable, str(FA26 / "benchmark" / "score.py"), str(out),
                    str(FA26 / "benchmark" / "runs" / "sqlite_baseline.json"), "--output", str(results)], check=True)
    print((results / "comparison.md").read_text())
    runs = json.loads((results / "details.json").read_text())["runs"]
    ours = [r for r in runs if r["summary"]["run_name"].startswith("templates_manual")]
    overall = ours[0]["summary"]["overall_pct"] if ours else None
    if failed or (overall is not None and overall < 100):
        print("SMOKE FAILED", {"errors": failed, "overall": overall}); sys.exit(1)
    print("SMOKE OK")


if __name__ == "__main__":
    main()
