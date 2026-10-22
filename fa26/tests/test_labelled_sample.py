"""Score hunger_match() against the 50 hand-labelled activities in
data/hunger_filter_sample_50.csv (labelled by John, sampled from hotspot
activities, about half kept and half dropped by the original filter).

Each row carries the parsed activity as record_json, so no raw XML is needed.
The floors below are the scores when this test was added. Raise them when the
filter improves; a change that lowers them should be a deliberate decision."""
import csv
import json
from pathlib import Path

import pytest

from parse_filter import hunger_match

SAMPLE = Path(__file__).parents[1] / "data" / "hunger_filter_sample_50.csv"
MIN_PRECISION = 0.70   # 19 / 27
MIN_RECALL = 0.95      # 19 / 20


def _score():
    csv.field_size_limit(10_000_000)  # record_json fields are large
    with open(SAMPLE, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    tp = fp = fn = 0
    for r in rows:
        actual = r["manual_label"].strip().lower() == "yes"
        # keyword_weak activities are kept by the pipeline, so they count as yes
        predicted = hunger_match(json.loads(r["record_json"]))[0]
        tp += predicted and actual
        fp += predicted and not actual
        fn += actual and not predicted
    return tp, fp, fn


@pytest.mark.skipif(not SAMPLE.exists(), reason="labelled sample not present")
def test_filter_meets_labelled_sample_floors():
    tp, fp, fn = _score()
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    assert precision >= MIN_PRECISION, f"precision {precision:.0%} (TP={tp}, FP={fp})"
    assert recall >= MIN_RECALL, f"recall {recall:.0%} (TP={tp}, FN={fn})"
