"""Live check of the composable templates on benchmark v2's DEVELOPMENT split with hand-written routes.

Scores a 'templates_manual' submission with score_v2.py, which tells us the ceiling the LLM router can
reach with these templates and where a template itself is wrong. Development only: never route the
held-out split by hand (Deniz's rule: first held-out run is frozen).

    IATI_BENCHMARK_BUNDLE=/path/to/exported/development/bundle python fa26/scripts/smoke_v2_development.py
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
from common import verify_snapshot, save_json                      # noqa: E402
from benchmark_bundle import load_bundle, submission, score_command  # noqa: E402
from text2cypher_eval import guard_query                            # noqa: E402
from tools import run_tool                                          # noqa: E402
from tools.contract import clean_evidence                           # noqa: E402
from dotenv import load_dotenv                                      # noqa: E402
from neo4j import GraphDatabase, Query, READ_ACCESS                 # noqa: E402

A = "count_activities"
ROUTE = {
    "V2Q001": (A, {}), "V2Q002": (A, {"humanitarian": "1"}), "V2Q003": (A, {"status": "3"}),
    "V2Q004": (A, {"has_actual_start": False}), "V2Q005": (A, {"has_actual_end": False}),
    "V2Q006": (A, {"has_planned_start": True}), "V2Q007": (A, {"has_planned_end": True}),
    "V2Q008": (A, {"default_currency": "GBP"}), "V2Q009": ("count_organisations", {}), "V2Q010": ("count_locations", {}),
    "V2Q021": (A, {"publisher": "oxfamgb", "country_code": "SO", "status": "3"}),
    "V2Q022": (A, {"publisher": "wfp", "country_code": "YE", "status": "2"}),
    "V2Q023": (A, {"country_code": "AF", "has_location": True}),
    "V2Q024": (A, {"country_code": "SS", "participant_role": "1"}),
    "V2Q025": (A, {"publisher": "wfp", "has_sector": True, "participant_role": "4"}),
    "V2Q026": (A, {"publisher": "oxfamgb", "has_location": True, "participant_role": "4"}),
    "V2Q027": (A, {"country_code": "YE", "has_sdg": True}),
    "V2Q028": (A, {"country_code": "SO", "actual_start_before": "2020-01-01"}),
    "V2Q029": (A, {"participant_role": "1", "actual_end_before": "2022-01-01"}),
    "V2Q030": (A, {"publisher": "oxfamus", "has_transaction": True, "has_budget": True}),
    "V2Q049": (A, {"publisher": "wfp"}), "V2Q050": (A, {"publisher": "oxfamus"}), "V2Q051": (A, {"publisher": "oxfamgb"}),
    "V2Q056": ("transaction_total", {"publisher": "wfp", "type_code": "1", "currency": "USD", "measure": "adjustments"}),
    "V2Q057": ("transaction_total", {"publisher": "wfp", "type_code": "1", "currency": "USD", "measure": "amount"}),
    "V2Q058": ("count_transactions", {"sign": "zero"}),
    "V2Q059": ("transaction_total", {"publisher": "oxfamgb", "type_code": "4", "currency": "GBP"}),
    "V2Q060": ("transaction_total", {"publisher": "wfp", "type_code": "2", "currency": "USD"}),
    "V2Q061": ("transaction_total", {"publisher": "wfp", "type_code": "4", "currency": "USD"}),
    "V2Q062": ("count_transactions", {"publisher": "oxfamgb", "type_code": "3", "sign": "negative"}),
}
POLICY = {"V2Q041": ("clarify", ["funding_scope"]), "V2Q042": ("clarify", ["organisation_scope"]),
          "V2Q043": ("clarify", ["organisation_scope"]), "V2Q044": ("clarify", ["country_scope"]),
          "V2Q045": ("clarify", ["organisation_scope"]),
          "V2Q071": ("abstain", ["outcomes_unavailable"]), "V2Q072": ("abstain", ["outcomes_unavailable"]),
          "V2Q073": ("abstain", ["misuse_unavailable"]), "V2Q074": ("abstain", ["balances_unavailable"]),
          "V2Q075": ("abstain", ["identity_unavailable"])}


def fmt(v):
    if isinstance(v, float) and not v.is_integer(): return str(Decimal(str(v)).quantize(Decimal("0.01")))
    if isinstance(v, (int, float)): return str(int(v))
    return str(v)


def main():
    load_dotenv(FA26 / ".env", override=False)
    snapshot_id = verify_snapshot()["snapshot_id"]
    bundle = load_bundle(os.environ["IATI_BENCHMARK_BUNDLE"], snapshot_id)
    assert bundle["template"]["split"] == "development", "hand routes are for the development split only"
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]))
    driver.verify_connectivity(); db = os.environ.get("NEO4J_DATABASE") or "neo4j"

    def run_cypher(q, params=None):
        guard_query(q)
        with driver.session(database=db, default_access_mode=READ_ACCESS) as s:
            return [dict(r) for r in s.run(Query(q, timeout=120), **(params or {}))]

    answers, failed = [], []
    for q in bundle["questions"]:
        qid, t0 = q["id"], time.time()
        if qid in ROUTE:
            name, args = ROUTE[qid]
            try:
                rows = run_tool(run_cypher, name, args)["rows"]
                facts = {str(r["key"]): {"value": fmt(r["value"]), "evidence": clean_evidence(r.get("evidence"))[0]} for r in rows}
                answers.append({"id": qid, "status": "answer", "facts": facts, "reasons": [], "latency_ms": round((time.time() - t0) * 1000, 1)})
                print(f"{qid} {name:<22} {json.dumps({k: v['value'] for k, v in facts.items()})}  ev={sum(len(v['evidence']) for v in facts.values())}  {(time.time() - t0):.1f}s")
            except Exception as e:
                failed.append(qid); print(f"{qid} ERROR {name}: {type(e).__name__}: {str(e)[:300]}")
                answers.append({"id": qid, "status": "answer", "facts": {}, "reasons": [], "latency_ms": None})
        elif qid in POLICY:
            st, reasons = POLICY[qid]
            answers.append({"id": qid, "status": st, "facts": {}, "reasons": reasons, "latency_ms": round((time.time() - t0) * 1000, 1)})
        else:
            print(qid, "NO ROUTE"); answers.append({"id": qid, "status": "abstain", "facts": {}, "reasons": ["NEEDS_DATA_MISSING"], "latency_ms": None})
    driver.close()
    out = FA26 / "data" / "processed" / f"06_submission_templates_manual_v2dev_{run_id}.json"
    save_json(out, submission(bundle, f"templates_manual_v2dev__{run_id}", snapshot_id, answers))
    results = FA26 / "benchmark" / "v2" / "results" / "live" / f"templates_manual_development_{run_id}"
    proc = subprocess.run(score_command(sys.executable, FA26, [out], results, bundle), capture_output=True, text=True, cwd=FA26.parent)
    print(proc.stdout[-3000:], proc.stderr[-1500:])
    if proc.returncode == 0:
        runs = json.loads((results / "comparison.json").read_text())
        runs = runs["runs"] if isinstance(runs, dict) else runs
        for r in runs:
            s = r.get("summary", r); print("OVERALL", s.get("overall_pct"), "correct", s.get("correctness_pct"), "evidence", s.get("evidence_f1_pct"), "behaviour", s.get("behavior_pct"))
            for cat, v in (r.get("by_category") or {}).items(): print(f"   {cat:<13} overall {v['overall_pct']:>6}  correct {v['correctness_pct']:>6}  evidence {v.get('evidence_f1_pct')}")
    if failed: print("FAILED:", failed)


if __name__ == "__main__":
    main()
