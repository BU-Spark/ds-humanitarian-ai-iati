"""End-to-end: run the parser on the 7 labelled fixture activities and check
which are kept, and why. Writes to a temp dir, never to data/graph/."""
import csv
import json
import shutil
from pathlib import Path

import parse_filter

FIXTURE = Path(__file__).parent / "fixture_iati_2.03.xml"


def test_fixture_outcomes(tmp_path, monkeypatch):
    raw, graph = tmp_path / "raw", tmp_path / "graph"
    (raw / "oxfamgb").mkdir(parents=True)
    shutil.copy(FIXTURE, raw / "oxfamgb" / FIXTURE.name)
    monkeypatch.setattr(parse_filter, "RAW_DIR", raw)
    monkeypatch.setattr(parse_filter, "GRAPH_DIR", graph)

    parse_filter.run("oxfamgb")

    with open(graph / "nodes_activities.csv", encoding="utf-8") as f:
        kept = {r["iati_identifier"]: r["match_basis"] for r in csv.DictReader(f)}
    assert kept == {
        "GB-CHC-202918-TEST001": "sector",        # DAC 72040
        "US-EIN-237069110-TEST004": "keyword",    # hunger + malnutrition
        "XM-DAC-41140-TEST005": "sector",         # food security cluster
        "GB-CHC-202918-TEST006": "keyword_weak",  # "livelihoods" only
    }
    # 2 dropped by theme (WASH code), 3 by geography (Kenya), 7 no signal
    counts = json.loads((graph / "coverage_report.json").read_text())["counts"]
    assert counts["dropped_geography"] == 1
    assert counts["dropped_theme_sector_no_match"] == 1
    assert counts["dropped_theme_no_signal"] == 1
