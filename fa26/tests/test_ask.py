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

    def test_answer_reports_stage_timings_and_calls(self):
        plan = json.dumps({"status": "answer", "tool": "count_activities", "args": {"publisher": "wfp"}})
        eng, _ = self.make([plan], [{"key": "count", "value": 82, "evidence": ["nodes_activities.csv:row:2"]}])
        out = eng.ask("How many WFP activities are there?")
        self.assertEqual((out["route"], out["model_calls"]), ("auto", 1))
        for k in ("plan_ms", "query_ms", "format_ms", "total_ms"):
            self.assertIn(k, out["timings"])
            self.assertGreaterEqual(out["timings"][k], 0)

    def test_retries_add_up_in_plan_time_and_calls(self):
        bad = json.dumps({"status": "answer", "tool": "free_cypher", "cypher": "MATCH (a:Activity) RETURN 'count' AS key, count(a) AS value, collect(a.iati_identifier) AS evidence"})
        eng, _ = self.make([bad, bad, bad], [{"key": "count", "value": 505, "evidence": ["GB-CHC-202918-X"]}])
        out = eng.ask("How many activities are recorded?")
        self.assertEqual(out["model_calls"], 3)

    def test_only_auto_route_is_open(self):
        eng, calls = self.make([], [])
        with self.assertRaises(ValueError):
            eng.ask("How many activities?", route="template_only")
        self.assertEqual(calls, [])

    def test_clarify_keeps_one_reason(self):
        plan = json.dumps({"status": "clarify", "reasons": ["organisation_scope", "funding_scope"], "explanation": "Oxfam GB or America?", "tool": None})
        eng, _ = self.make([plan], [])
        out = eng.ask("How much did Oxfam give?")
        self.assertEqual((out["status"], out["reasons"], out["facts"]), ("clarify", ["organisation_scope"], {}))



class CacheAndUsageTests(unittest.TestCase):
    """Ablation experiment 1 (plan/result cache) and the token log; both are off or zero by default."""
    PLAN = json.dumps({"status": "answer", "tool": "count_activities", "args": {"publisher": "wfp"}, "explanation": "count"})
    ROWS = [{"key": "count", "value": 82, "evidence": ["nodes_activities.csv:row:2"]}]

    def make(self, cache, llm=None):
        from ask import Engine
        calls = []
        def fake_cypher(q, params=None):
            calls.append(q); return [dict(r) for r in self.ROWS]
        llm = llm or FakeListChatModel(responses=[self.PLAN] * 3)
        return Engine(llm=llm, run_cypher=fake_cypher, snapshot_dir=FA26 / "benchmark" / "snapshot", cache=cache), calls

    def test_cache_off_by_default_calls_model_every_time(self):
        eng, calls = self.make(cache=False)
        a, b = eng.ask("How many WFP activities?"), eng.ask("How many WFP activities?")
        self.assertEqual((a["model_calls"], b["model_calls"]), (1, 1))
        self.assertEqual(len(calls), 2)
        self.assertEqual(b["cache"], {"plan": False, "result": False})

    def test_cache_replays_plan_and_rows_with_same_answer(self):
        eng, calls = self.make(cache=True)
        a, b = eng.ask("How many WFP activities?"), eng.ask("How many WFP activities?")
        self.assertEqual(a["facts"], b["facts"])
        self.assertEqual(b["model_calls"], 0)
        self.assertEqual(b["cache"], {"plan": True, "result": True})
        self.assertEqual(len(calls), 1)
        self.assertEqual(b["path"], "tool")

    def test_cache_key_is_exact_question_text(self):
        eng, _ = self.make(cache=True)
        eng.ask("How many WFP activities?")
        c = eng.ask("How many activities does WFP have?")
        self.assertEqual(c["model_calls"], 1)
        self.assertFalse(c["cache"]["plan"])
        self.assertTrue(c["cache"]["result"])      # same tool and args, so the rows are reused

    def test_failed_plan_is_not_cached(self):
        bad = json.dumps({"status": "answer", "tool": None})
        eng, _ = self.make(cache=True, llm=FakeListChatModel(responses=[bad] * 6))
        eng.ask("How many WFP activities?")
        self.assertEqual(eng.cache["plan"], {})

    def test_tokens_come_from_usage_metadata(self):
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage
        msg = AIMessage(content=self.PLAN, usage_metadata={"input_tokens": 1200, "output_tokens": 80, "total_tokens": 1280})
        eng, _ = self.make(cache=False, llm=GenericFakeChatModel(messages=iter([msg])))
        out = eng.ask("How many WFP activities?")
        self.assertEqual(out["tokens"], {"in": 1200, "out": 80})


if __name__ == "__main__":
    unittest.main(verbosity=1)
