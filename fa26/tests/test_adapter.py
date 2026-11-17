"""Offline tests for src/tools/adapter.py: retrieval results -> (key, value, evidence) facts. No database."""
import sys
import unittest
from pathlib import Path

FA26 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FA26 / "src"))
from tools import TOOLS  # noqa: E402
from tools.adapter import (RETRIEVAL_TOOLS, ToolClarification, ToolError, catalog_all, retrieval_catalog,  # noqa: E402
                           rows_to_facts, run_any, run_retrieval, validate_retrieval_args, for_model)

INDEX = {"GB-CHC-202918-A1": "nodes_activities.csv:row:1", "XM-DAC-41140-B2": "nodes_activities.csv:row:2"}


def ok(rows, **extra):
    return {"status": "ok", "rows": rows, "cypher": "MATCH ...", "params": {}, "coverage_note": "", **extra}


FAKE = {
    "activities": lambda **kw: ok([{"iati_identifier": "GB-CHC-202918-A1", "publisher": "oxfamgb"},
                                   {"iati_identifier": "XM-DAC-41140-B2", "publisher": "wfp"}]),
    "shared_partners": lambda **kw: ok([{"organisation_id": "US-EIN-23-7069110", "n_activities": 49,
                                         "activity_ids": ["GB-CHC-202918-A1", "XM-DAC-41140-B2", "UNKNOWN"]}]),
    "top_funders": lambda **kw: (
        {"status": "error", "rows": [], "cypher": "", "params": kw, "coverage_note": "ambiguous country",
         "candidates": [{"id": "SD", "name": "Sudan"}, {"id": "SS", "name": "South Sudan"}]}
        if kw.get("country") == "Sudan?" else
        ok([{"funder_id": "XM-DAC-302", "currency": "USD", "amount": 1203270484.23, "adjustments": -5.0, "net": 1203270479.23,
             "evidence_amount": ["nodes_transactions.csv:row:9", "nodes_activities.csv:row:3"],
             "evidence_adjustments": ["nodes_transactions.csv:row:10"], "evidence_net": ["nodes_transactions.csv:row:9", "nodes_transactions.csv:row:10"]}])),
    "funding_over_time": lambda **kw: ok([
        {"period": "2020", "publisher": "wfp", "currency": "USD", "amount": 10.0, "adjustments": -1.0, "net": 9.0,
         "evidence_amount": ["nodes_transactions.csv:row:1"], "evidence_adjustments": ["nodes_transactions.csv:row:2"], "evidence_net": ["nodes_transactions.csv:row:1", "nodes_transactions.csv:row:2"]},
        {"period": "2021", "publisher": "wfp", "currency": "USD", "amount": 20.0, "adjustments": 0.0, "net": 20.0,
         "evidence_amount": ["nodes_transactions.csv:row:3"], "evidence_adjustments": ["manifest:nodes_transactions.csv"], "evidence_net": ["nodes_transactions.csv:row:3"]}]),
    "transaction_totals": lambda **kw: (
        {"status": "no_results", "rows": [], "cypher": "MATCH ...", "params": kw, "coverage_note": "no rows",
         "evidence": ["manifest:nodes_transactions.csv", "manifest:nodes_activities.csv"]}
        if kw.get("currency") == "EUR" else
        ok([{"publisher": None, "currency": "GBP", "amount": 600.0, "adjustments": 0.0, "net": 600.0,
             "evidence_amount": ["nodes_transactions.csv:row:5"], "evidence_adjustments": ["manifest:nodes_transactions.csv"], "evidence_net": ["nodes_transactions.csv:row:5"]},
            {"publisher": None, "currency": "USD", "amount": 100.0, "adjustments": -30.0, "net": 70.0,
             "evidence_amount": ["nodes_transactions.csv:row:6"], "evidence_adjustments": ["nodes_transactions.csv:row:7"], "evidence_net": ["nodes_transactions.csv:row:6", "nodes_transactions.csv:row:7"]}])),
}


class CatalogTests(unittest.TestCase):
    def test_names_do_not_collide_with_templates(self):
        self.assertFalse(set(RETRIEVAL_TOOLS) & set(TOOLS))
        self.assertTrue(all(n.startswith("rt_") for n in RETRIEVAL_TOOLS))

    def test_catalog_lists_every_tool_once(self):
        cat = catalog_all()
        for n in list(TOOLS) + list(RETRIEVAL_TOOLS):
            self.assertEqual(cat.count(f"- {n}("), 1, n)
        self.assertIn("measure?: enum=amount|adjustments|net", retrieval_catalog())


class ArgTests(unittest.TestCase):
    def test_defaults_and_measure_are_separated(self):
        kw, m = validate_retrieval_args("rt_transaction_totals", {"publisher": "WFP", "currency": "USD"})
        self.assertEqual(m, "amount")
        self.assertNotIn("measure", kw)
        self.assertEqual(kw["transaction_type"], "Incoming Funds")
        self.assertFalse(kw["by_publisher"])

    def test_strings_from_the_router_are_coerced(self):
        kw, m = validate_retrieval_args("rt_funding_over_time", {"year_from": "2020", "measure": "net"})
        self.assertEqual((kw["year_from"], m), (2020, "net"))
        kw, _ = validate_retrieval_args("rt_shared_partners", {"publishers": "Oxfam GB, WFP"})
        self.assertEqual(kw["publishers"], ["Oxfam GB", "WFP"])
        kw, _ = validate_retrieval_args("rt_top_funders", {"country": "SO", "exclude_self": "false"})
        self.assertFalse(kw["exclude_self"])

    def test_transaction_types_are_alexs_exact_names(self):
        # Alex's tools reject any name not in TRANSACTION_TYPE_NAMES ("Commitment" used to fail)
        sys.path.insert(0, str(FA26 / "retrieval"))
        from schema_prototype import TRANSACTION_TYPES
        from tools.adapter import TX_TYPES
        self.assertLessEqual(set(TX_TYPES), set(TRANSACTION_TYPES.values()))

    def test_rejections(self):
        with self.assertRaisesRegex(ToolError, "required"):
            validate_retrieval_args("rt_top_funders", {})
        with self.assertRaisesRegex(ToolError, "not in"):
            validate_retrieval_args("rt_transaction_totals", {"measure": "gross"})
        with self.assertRaisesRegex(ToolError, "unknown parameters"):
            validate_retrieval_args("rt_activities", {"sector": "x"})
        with self.assertRaisesRegex(ToolError, "integer"):
            validate_retrieval_args("rt_activities", {"year_from": "last year"})


class MappingTests(unittest.TestCase):
    def test_activities_and_shared_partners_cite_snapshot_rows(self):
        r = run_retrieval("rt_activities", {}, impl=FAKE, index=INDEX)
        self.assertEqual(r["rows"][0], {"key": "GB-CHC-202918-A1", "value": "oxfamgb", "evidence": ["nodes_activities.csv:row:1"]})
        r = run_retrieval("rt_shared_partners", {"publishers": ["Oxfam GB", "Oxfam America"]}, impl=FAKE, index=INDEX)
        self.assertEqual(r["rows"][0]["key"], "US-EIN-23-7069110")
        self.assertEqual(r["rows"][0]["value"], 49)
        self.assertEqual(r["rows"][0]["evidence"], ["nodes_activities.csv:row:1", "nodes_activities.csv:row:2"])  # unknown id dropped
        self.assertIn("first 20 activities", r["coverage"])

    def test_measure_selects_value_and_evidence(self):
        a = run_retrieval("rt_top_funders", {"country": "Somalia"}, impl=FAKE, index=INDEX)["rows"][0]
        self.assertEqual((a["key"], a["value"], a["evidence"]),
                         ("XM-DAC-302 [USD]", 1203270484.23, ["nodes_activities.csv:row:3", "nodes_transactions.csv:row:9"]))
        n = run_retrieval("rt_top_funders", {"country": "Somalia", "measure": "net"}, impl=FAKE, index=INDEX)["rows"][0]
        self.assertEqual((n["value"], n["evidence"]), (1203270479.23, ["nodes_transactions.csv:row:10", "nodes_transactions.csv:row:9"]))
        adj = run_retrieval("rt_top_funders", {"country": "Somalia", "measure": "adjustments"}, impl=FAKE, index=INDEX)["rows"][0]
        self.assertEqual((adj["value"], adj["evidence"]), (-5.0, ["nodes_transactions.csv:row:10"]))

    def test_period_keys_single_currency_single_publisher(self):
        rows = run_retrieval("rt_funding_over_time", {"publisher": "WFP", "measure": "net"}, impl=FAKE, index=INDEX)["rows"]
        self.assertEqual([r["key"] for r in rows], ["2020", "2021"])
        self.assertEqual([r["value"] for r in rows], [9.0, 20.0])

    def test_totals_keys_follow_benchmark_style(self):
        rows = run_retrieval("rt_transaction_totals", {"measure": "net"}, impl=FAKE, index=INDEX)["rows"]
        self.assertEqual({r["key"]: r["value"] for r in rows}, {"GBP": 600.0, "USD": 70.0})   # multi-currency -> currency keys
        single = rows_to_facts("rt_transaction_totals", {"rows": [FAKE["transaction_totals"]()["rows"][1]]}, "amount", INDEX)
        self.assertEqual(single, [{"key": "total", "value": 100.0, "evidence": ["nodes_transactions.csv:row:6"]}])
        zero_adj = rows_to_facts("rt_transaction_totals", {"rows": [FAKE["transaction_totals"]()["rows"][0]]}, "adjustments", INDEX)
        self.assertEqual(zero_adj[0]["evidence"], ["manifest:nodes_transactions.csv"])        # a zero cites the manifest

    def test_no_results_money_becomes_manifest_cited_zero(self):
        r = run_retrieval("rt_transaction_totals", {"currency": "EUR"}, impl=FAKE, index=INDEX)
        self.assertEqual(r["rows"], [{"key": "total", "value": 0, "evidence": ["manifest:nodes_activities.csv", "manifest:nodes_transactions.csv"]}])

    def test_ambiguous_entity_raises_clarification_with_candidates(self):
        with self.assertRaises(ToolClarification) as cm:
            run_retrieval("rt_top_funders", {"country": "Sudan?"}, impl=FAKE, index=INDEX)
        self.assertEqual([c["id"] for c in cm.exception.candidates], ["SD", "SS"])

    def test_for_model_strips_evidence(self):
        res = FAKE["top_funders"](country="Somalia")
        slim = for_model(res)
        self.assertNotIn("evidence_amount", slim["rows"][0])
        self.assertIn("evidence_amount", res["rows"][0])     # original untouched


class DispatchTests(unittest.TestCase):
    def test_run_any_routes_to_templates_or_retrieval(self):
        calls = []
        def fake_cypher(q, p):
            calls.append(q)
            return [{"key": "wfp", "value": 3, "evidence": ["nodes_activities.csv:row:7"]}]
        t = run_any(fake_cypher, "activities_per_publisher", {})
        self.assertEqual(t["rows"][0]["key"], "wfp")
        self.assertEqual(len(calls), 1)
        r = run_any(fake_cypher, "rt_activities", {}, impl=FAKE, index=INDEX)
        self.assertEqual(len(calls), 1)                    # retrieval path never runs our Cypher
        self.assertEqual(r["tool"], "rt_activities")
        with self.assertRaises(ToolError):
            run_any(fake_cypher, "nope", {})


if __name__ == "__main__":
    unittest.main(verbosity=1)
