"""Offline tests for src/tools/contract.py (benchmark output contract)."""
import sys
import unittest
from pathlib import Path

FA26 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FA26 / "src"))
from tools.contract import (clean_evidence, evidence_error, invalid_reasons, normalise_facts,  # noqa: E402
                            scalar_kind, single_v2_reason, valid_evidence_id)


class EvidenceTests(unittest.TestCase):
    def test_row_and_manifest_ids(self):
        self.assertTrue(valid_evidence_id("nodes_activities.csv:row:1"))
        self.assertTrue(valid_evidence_id("rel_transaction_edges.csv:row:17570"))
        self.assertTrue(valid_evidence_id("manifest:nodes_transactions.csv"))

    def test_identifiers_and_unknown_tables_are_rejected(self):
        for bad in ("GB-CHC-202918-AFHA25", "XM-DAC-41140", "manifest:transactions.csv", "activities.csv:row:3",
                    "nodes_activities.csv:row:0", "", None, 12):
            self.assertFalse(valid_evidence_id(bad), bad)

    def test_clean_keeps_valid_sorted_unique_and_reports_dropped(self):
        kept, dropped = clean_evidence(["nodes_activities.csv:row:2", "GB-CHC-202918-X", "nodes_activities.csv:row:1",
                                        "nodes_activities.csv:row:2"])
        self.assertEqual(kept, ["nodes_activities.csv:row:1", "nodes_activities.csv:row:2"])
        self.assertEqual(dropped, ["GB-CHC-202918-X"])

    def test_bare_string_is_one_id_not_characters(self):
        kept, dropped = clean_evidence("nodes_activities.csv:row:7")
        self.assertEqual((kept, dropped), (["nodes_activities.csv:row:7"], []))
        self.assertEqual(clean_evidence("A")[1], ["A"])

    def test_evidence_error_names_examples(self):
        self.assertIsNone(evidence_error([{"evidence": ["nodes_activities.csv:row:1"]}]))
        msg = evidence_error([{"evidence": ["GB-CHC-202918-AFHA25", "nodes_activities.csv:row:1"]}])
        self.assertIn("source_id", msg)
        self.assertIn("GB-CHC-202918-AFHA25", msg)


class KeyTests(unittest.TestCase):
    def test_scalar_kind(self):
        self.assertEqual(scalar_kind("How many activities are recorded as completed?"), "count")
        self.assertEqual(scalar_kind("What is the total of positive WFP incoming-fund transactions in USD?"), "total")
        self.assertEqual(scalar_kind("What is the earliest recorded actual activity start date?"), "date")
        self.assertIsNone(scalar_kind("Which organisations work with both publishers?"))

    def test_single_fact_renamed_only_when_scalar(self):
        f = {"wfp": {"value": "82", "evidence": []}}
        self.assertEqual(normalise_facts(f, "How many activities does the World Food Programme report?"),
                         {"count": {"value": "82", "evidence": []}})
        self.assertEqual(normalise_facts({"count": {"value": "1"}}, "How many?"), {"count": {"value": "1"}})
        self.assertEqual(normalise_facts({"USD": {"value": "1"}}, "How much by currency?"), {"USD": {"value": "1"}})
        multi = {"wfp": {"value": "82"}, "oxfamgb": {"value": "412"}}
        self.assertEqual(normalise_facts(multi, "How many activities per publisher?"), multi)
        self.assertEqual(normalise_facts(f, "How many activities?", legacy=True), f)   # Q01-Q20 untouched


class ReasonTests(unittest.TestCase):
    def test_single_v2_reason(self):
        self.assertEqual(single_v2_reason(["organisation_scope", "FUNDING_DEFINITION_REQUIRED", "PERIOD_REQUIRED"]), ["organisation_scope"])
        self.assertEqual(single_v2_reason(["funding_scope", "organisation_scope"]), ["organisation_scope"])
        self.assertEqual(single_v2_reason(["country_scope", "organisation_scope"]), ["country_scope"])
        self.assertEqual(single_v2_reason(["country_scope", "funding_scope"]), ["country_scope"])
        self.assertEqual(single_v2_reason(["outcomes_unavailable", "coverage_unavailable"], status="abstain"), ["outcomes_unavailable"])
        legacy = ["FUNDING_DEFINITION_REQUIRED", "CURRENCY_BASIS_REQUIRED", "PERIOD_REQUIRED"]
        self.assertEqual(single_v2_reason(legacy), legacy)      # Q01-Q20 style lists untouched

    def test_invalid_reasons(self):
        vocab = ["organisation_scope", "funding_scope", "NEEDS_DATA_MISSING"]
        self.assertEqual(invalid_reasons(["organisation_scope", "ORG_AMBIGUOUS"], vocab), ["ORG_AMBIGUOUS"])
        self.assertEqual(invalid_reasons([], vocab), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
