"""Offline tests for src/ask.py: router wiring, contract enforcement, evidence lookup. No API, no database."""
import json
import sys
import unittest
from pathlib import Path

FA26 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FA26 / "src"))
try:
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    import langgraph  # noqa: F401
    HAVE_LANGGRAPH = True
except ImportError:  # the engine needs langgraph; skip cleanly where it is not installed
    HAVE_LANGGRAPH = False
from ask import build_system, parse_plan, rows_to_facts, REASON_CODES  # noqa: E402


class PromptTests(unittest.TestCase):
    def test_system_lists_every_tool_and_the_v2_vocabulary(self):
        s = build_system()
        for t in ("count_activities(", "transaction_total(", "rt_top_funders(", "date_extreme("):
            self.assertIn(t, s)
        self.assertIn("organisation_scope", s)
        self.assertIn("EXACTLY ONE reason code", s)

    def test_parse_plan_filters_unknown_reasons(self):
        st, reasons, expl, tool, args, cy = parse_plan('{"status":"clarify","reasons":["organisation_scope","MADE_UP"],"explanation":"x","tool":null}')
        self.assertEqual((st, reasons, tool), ("clarify", ["organisation_scope"], None))
        self.assertIn("funding_scope", REASON_CODES)

    def test_rows_to_facts_formats_money(self):
        f = rows_to_facts([{"key": "total", "value": 19149380438.35998, "evidence": ["nodes_transactions.csv:row:1"]}])
        self.assertEqual(f["total"]["value"], "19149380438.36")


@unittest.skipUnless(HAVE_LANGGRAPH, "langgraph not installed")
class EngineTests(unittest.TestCase):
    def make(self, responses, rows):
        from ask import Engine
        calls = []
        def fake_cypher(q, params=None):
            calls.append((q, params)); return rows
        eng = Engine(llm=FakeListChatModel(responses=responses), run_cypher=fake_cypher, snapshot_dir=FA26 / "benchmark" / "snapshot")
        return eng, calls

    def test_template_path_returns_contract_and_provenance(self):
        plan = json.dumps({"status": "answer", "tool": "count_activities", "args": {"publisher": "wfp", "country_code": "YE"}, "explanation": "count"})
        eng, calls = self.make([plan], [{"key": "count", "value": 4, "evidence": ["nodes_activities.csv:row:2", "rel_targets_country.csv:row:2"]}])
        out = eng.ask("How many WFP activities target Yemen?")
        self.assertEqual(out["status"], "answer")
        self.assertEqual(out["facts"]["count"]["value"], "4")
        self.assertEqual(out["tool"], "count_activities")
        self.assertEqual(out["args"]["country_code"], "YE")
        self.assertEqual(len(calls), 1)
        ev = eng.evidence_rows(out)
        self.assertEqual([e["id"] for e in ev], ["nodes_activities.csv:row:2", "rel_targets_country.csv:row:2"])
        self.assertIn("iati_identifier", ev[0])

    def test_free_cypher_with_bad_evidence_is_retried_then_cleaned(self):
        bad = json.dumps({"status": "answer", "tool": "free_cypher", "cypher": "MATCH (a:Activity) RETURN 'count' AS key, count(a) AS value, collect(a.iati_identifier) AS evidence"})
        eng, calls = self.make([bad, bad, bad], [{"key": "count", "value": 505, "evidence": ["GB-CHC-202918-X"]}])
        out = eng.ask("How many activities are recorded?")
        self.assertEqual(out["retries"], 2)                      # contract check sent it back twice
        self.assertIn("source_id", out["error"] or "")           # and the last error names the rule
        self.assertEqual(out["facts"], {})                       # no invalid evidence leaks out

    def test_clarify_keeps_one_reason(self):
        plan = json.dumps({"status": "clarify", "reasons": ["organisation_scope", "funding_scope"], "explanation": "Oxfam GB or America?", "tool": None})
        eng, _ = self.make([plan], [])
        out = eng.ask("How much did Oxfam give?")
        self.assertEqual((out["status"], out["reasons"], out["facts"]), ("clarify", ["organisation_scope"], {}))


if __name__ == "__main__":
    unittest.main(verbosity=1)
