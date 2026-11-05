"""Offline tests for the deterministic query tools and the entity resolver (no database, no API)."""
import re
import sys
import unittest
from pathlib import Path

FA26 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FA26 / "src"))
from tools import TOOLS, validate_args, run_tool, OrgResolver  # noqa: E402
from text2cypher_eval import guard_query  # noqa: E402


class TemplateTests(unittest.TestCase):
    def test_every_template_passes_the_read_only_guard(self):
        for name, t in TOOLS.items():
            with self.subTest(tool=name):
                guard_query(t["cypher"].strip())

    def test_declared_params_match_cypher_placeholders(self):
        for name, t in TOOLS.items():
            with self.subTest(tool=name):
                self.assertEqual(set(re.findall(r"\$(\w+)", t["cypher"])), set(t["params"]))

    def test_every_template_returns_key_value_evidence(self):
        for name, t in TOOLS.items():
            with self.subTest(tool=name):
                for col in ("AS key", "AS value", "AS evidence"):
                    self.assertIn(col, t["cypher"])

    def test_required_and_enum_validation(self):
        with self.assertRaisesRegex(ValueError, "required"):
            validate_args("transaction_total", {"publisher": "wfp", "type_code": "1"})
        with self.assertRaisesRegex(ValueError, "not in"):
            validate_args("transaction_total", {"publisher": "wfp", "type_code": "9", "currency": "USD"})
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            validate_args("activities_per_publisher", {"start_from": "2020"})
        with self.assertRaisesRegex(ValueError, "unknown parameters"):
            validate_args("participants_by_role", {"role": "1"})

    def test_injection_cannot_reach_cypher(self):
        with self.assertRaises(ValueError):
            validate_args("count_activities_by_sector", {"publisher": "wfp", "sector_key": "1:72040' OR 1=1 //"})
        with self.assertRaises(ValueError):
            validate_args("activities_per_publisher_by_country", {"country_code": "SO RETURN 1"})

    def test_defaults_and_manifest_fallback(self):
        calls = []
        def fake_run(q, p):
            calls.append((q, p))
            return [{"key": "total", "value": 0, "evidence": [None]}]
        out = run_tool(fake_run, "transaction_total", {"publisher": "wfp", "type_code": "1", "currency": "USD"})
        self.assertEqual(calls[0][1]["date_from"], None)
        self.assertEqual(out["rows"][0]["evidence"], ["manifest:nodes_activities.csv", "manifest:nodes_transactions.csv"])
        out = run_tool(fake_run, "multi_publisher_participants", {})
        self.assertEqual(out["params"], {"min_publishers": 2})


class ResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = OrgResolver.from_csv(FA26 / "benchmark" / "snapshot" / "nodes_organisations.csv")

    def test_alias_groups_return_every_identifier(self):
        self.assertEqual(self.r.resolve("UK government")["refs"], ["XM-DAC-12", "XM-DAC-12-1"])
        self.assertEqual(set(self.r.resolve("WFP")["refs"]), {"XM-DAC-41140", "name:UN World Food Programme (WFP)"})
        self.assertEqual(len(self.r.resolve("ECHO")["refs"]), 2)

    def test_exact_name_beats_contained_alias(self):
        self.assertEqual(self.r.resolve("Oxfam Novib")["refs"], ["NL-KVK-27108436"])

    def test_countries(self):
        self.assertEqual(self.r.resolve("DRC")["refs"], ["CD"])
        self.assertEqual(self.r.resolve("South Sudan")["kind"], "country")

    def test_placeholders_are_not_organisations(self):
        self.assertNotIn("MU", self.r.resolve("Multilateral")["refs"])

    def test_duplicate_groups_cover_known_pairs(self):
        groups = {g["group"]: g["n"] for g in self.r.duplicate_groups()}
        for g in ("WFP", "UK_GOV", "US_GOV", "EU_ECHO", "UNICEF"):
            self.assertGreaterEqual(groups.get(g, 0), 2, g)


class CrosscheckTests(unittest.TestCase):
    """Independent pandas/Decimal references used by notebook 07, pinned to the snapshot."""
    @classmethod
    def setUpClass(cls):
        from tools import crosscheck as cc
        cls.cc = cc; cls.t = cc.load(FA26 / "benchmark" / "snapshot")

    def test_participation_duplicates_explain_relationship_counts(self):
        self.assertEqual(self.cc.participation_duplicates(self.t), 210)   # 59,121 - 210 = 58,911

    def test_wfp_commitments_mirror_expenditure(self):
        m = self.cc.wfp_mirror(self.t)
        self.assertEqual(m["2"], m["4"])
        self.assertEqual(str(m["2"]["positive"]), "18037403740.15")

    def test_shared_partners_zero_on_raw_refs(self):
        self.assertEqual(self.cc.shared_partners(self.t, "oxfamgb", "wfp"), {})
        self.assertEqual(self.cc.shared_partners(self.t, "oxfamgb", "oxfamus"), {"US-EIN-23-7069110": 49})

    def test_somalia_top_funder_matches_published_number(self):
        top = self.cc.country_top_funders(self.t, "SO", ("1",), "USD", True, 1)
        self.assertEqual(list(top), ["XM-DAC-302 [USD]"])
        self.assertEqual(str(top["XM-DAC-302 [USD]"]), "1203270484.23")


if __name__ == "__main__":
    unittest.main(verbosity=1)
