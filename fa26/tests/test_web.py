"""Offline tests for the web service (fa26/web): API contract, locked routes and models, dashboard views. No API keys, no database."""
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

FA26 = Path(__file__).resolve().parents[1]
for p in (FA26 / "web", FA26 / "src"):
    sys.path.insert(0, str(p))
try:
    from fastapi.testclient import TestClient
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    import langgraph  # noqa: F401
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False

SNAP = FA26 / "benchmark" / "snapshot"


def q12_rows():
    """Snapshot rows the transaction_total template cites for benchmark Q12 (Oxfam America, expenditure, USD)."""
    import csv
    acts = {r["iati_identifier"]: (i, r) for i, r in enumerate(csv.DictReader((SNAP / "nodes_activities.csv").open(encoding="utf-8")), 1)}
    ev, total = set(), Decimal(0)
    for i, t in enumerate(csv.DictReader((SNAP / "nodes_transactions.csv").open(encoding="utf-8")), 1):
        a = acts.get(t["iati_identifier"])
        if a and a[1]["publisher"] == "oxfamus" and t["type"] == "4" and t["currency"] == "USD":
            ev.add(f"nodes_transactions.csv:row:{i}"); ev.add(f"nodes_activities.csv:row:{a[0]}"); total += Decimal(t["value"])
    return sorted(ev), total


@unittest.skipUnless(HAVE_DEPS, "fastapi / langgraph not installed")
class WebTests(unittest.TestCase):
    def setUp(self):
        import server
        from ask import Engine
        self.server = server
        ev, self.total = q12_rows()
        plan = json.dumps({"status": "answer", "tool": "transaction_total",
                           "args": {"publisher": "oxfamus", "type_code": "4", "currency": "USD"}})
        rows = [{"key": "total", "value": float(self.total), "evidence": ev}]
        server._engine = Engine(llm=FakeListChatModel(responses=[plan] * 5), run_cypher=lambda q, p=None: rows, snapshot_dir=SNAP)
        self.client = TestClient(server.app)

    def tearDown(self):
        self.server._engine = None

    def test_ask_returns_answer_views_and_timings(self):
        r = self.client.post("/api/ask", json={"question": "What is the net sum of Oxfam America expenditure in USD?"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        a, v = body["answer"], body["views"]
        self.assertEqual(a["facts"]["total"]["value"], "3781832.44")
        self.assertEqual(a["facts"]["total"]["evidence_n"], 31)
        for k in ("plan_ms", "query_ms", "format_ms", "total_ms"):
            self.assertIn(k, a["timings"])
        self.assertEqual(v["kpis"]["transactions"], 20)
        self.assertEqual(v["kpis"]["activities"], 11)
        self.assertTrue(v["reconcile"]["match"])
        self.assertAlmostEqual(sum(c["value"] for c in v["breakdowns"]["country"]), float(self.total), places=2)
        self.assertNotIn("evidence", a["facts"]["total"])     # ids stay server-side; the page gets rows

    def test_locked_model_and_route(self):
        r = self.client.post("/api/ask", json={"question": "How many activities?", "model": "zai/glm-5.3"})
        self.assertEqual(r.status_code, 423)
        r = self.client.post("/api/ask", json={"question": "How many activities?", "route": "template_only"})
        self.assertEqual(r.status_code, 423)

    def test_meta_reports_dataset_and_lock(self):
        m = self.client.get("/api/meta").json()
        self.assertEqual(m["routes"], ["auto"])
        self.assertEqual(m["models"], ["default"])
        self.assertTrue(m["compare"]["locked"])
        self.assertEqual(m["dataset"]["activities"], 505)

    def test_basic_auth_when_configured(self):
        import base64
        self.server._AUTH = "team:secret"
        try:
            self.assertEqual(self.client.get("/api/meta").status_code, 401)
            self.assertEqual(self.client.get("/api/health").status_code, 200)
            ok = {"Authorization": "Basic " + base64.b64encode(b"team:secret").decode()}
            self.assertEqual(self.client.get("/api/meta", headers=ok).status_code, 200)
        finally:
            self.server._AUTH = ""

    def test_question_length_is_bounded(self):
        self.assertEqual(self.client.post("/api/ask", json={"question": "x" * 501}).status_code, 422)


class ViewTests(unittest.TestCase):
    def test_count_answer_uses_activity_rows(self):
        import csv
        from views import build_views
        tables = {}

        def table(name):
            if name not in tables:
                tables[name] = list(csv.DictReader((SNAP / name).open(encoding="utf-8")))
            return tables[name]
        acts = table("nodes_activities.csv")
        wfp = [i for i, a in enumerate(acts, 1) if a["publisher"] == "wfp"]
        ev = [{"id": f"nodes_activities.csv:row:{i}", "table": "nodes_activities.csv", "row": i, **acts[i - 1]} for i in wfp]
        ans = {"status": "answer", "facts": {"count": {"value": str(len(wfp)), "evidence": [e["id"] for e in ev]}}}
        v = build_views(ans, ev, table)
        self.assertEqual(v["measure"], "count")
        self.assertEqual(v["kpis"]["activities"], len(wfp))
        self.assertEqual(sum(c["value"] for c in v["breakdowns"]["country"]), len(wfp))
        self.assertEqual(v["breakdowns"]["publisher"], [{"key": "WFP", "value": len(wfp)}])

    def test_layout_poster_for_single_numbers_and_dashboard_otherwise(self):
        import csv
        from views import build_views
        tables = {}

        def table(name):
            if name not in tables:
                tables[name] = list(csv.DictReader((SNAP / name).open(encoding="utf-8")))
            return tables[name]
        zero = {"status": "answer", "facts": {"total": {"value": "0.00", "evidence": ["manifest:nodes_transactions.csv"]}}}
        v = build_views(zero, [], table)
        self.assertEqual((v["layout"], v["manifest_scope"]), ("poster", ["nodes_transactions.csv"]))
        clarify = {"status": "clarify", "facts": {}, "reasons": ["organisation_scope"]}
        self.assertEqual(build_views(clarify, [], table)["layout"], "poster")
        multi = {"status": "answer", "facts": {"GBP": {"value": "1", "evidence": []}, "USD": {"value": "2", "evidence": []}}}
        self.assertEqual(build_views(multi, [], table)["layout"], "dashboard")

if __name__ == "__main__":
    unittest.main(verbosity=1)
