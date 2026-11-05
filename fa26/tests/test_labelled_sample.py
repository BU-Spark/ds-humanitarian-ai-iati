"""Score hunger_match() against hand-labelled samples in data/:

- hunger_filter_sample_50.csv: John's 50, used to tune the filter
- hunger_filter_sample_devansh_50.csv: Devansh's 50, held out for testing
  (labels drafted by Claude, confirmed by Devansh, 29 Oct 2026)

Floors are the scores on each sample when its test was written. Raise them
when the filter improves; lowering them should be a deliberate decision.
Recall matters most: a missed hunger activity is worse than an extra one.
"keyword_weak" activities are kept by the pipeline, so the first test counts
them as yes. The second scores the confident view: strong matches only."""
from pathlib import Path

import pytest

import evaluate_filter as ev

DATA = Path(__file__).parents[1] / "data"
JOHN = DATA / "hunger_filter_sample_50.csv"
HELD_OUT = DATA / "hunger_filter_sample_devansh_50.csv"


def _rates(path, weak_as_yes):
    labelled = ev.load_labelled(path)
    if not labelled:
        pytest.skip(f"{path.name} has no labels yet")
    tp, fp, tn, fn, _ = ev.confusion(labelled, weak_as_yes)
    return tp / (tp + fp), tp / (tp + fn)


@pytest.mark.skipif(not JOHN.exists(), reason="labelled sample not present")
def test_pipeline_view_floors():
    precision, recall = _rates(JOHN, weak_as_yes=True)
    assert precision >= 0.70 and recall >= 1.0, (precision, recall)


@pytest.mark.skipif(not JOHN.exists(), reason="labelled sample not present")
def test_strong_only_view_floors():
    precision, recall = _rates(JOHN, weak_as_yes=False)
    assert precision >= 0.85 and recall >= 0.95, (precision, recall)


# Held-out floors are lower: this sample was not used for tuning, so it
# shows how the filter does on activities it has not seen. Don't tune the
# filter to raise these; that would stop the sample being held out.
@pytest.mark.skipif(not HELD_OUT.exists(), reason="held-out sample not present")
def test_held_out_pipeline_view_floors():
    precision, recall = _rates(HELD_OUT, weak_as_yes=True)
    assert precision >= 0.65 and recall >= 0.85, (precision, recall)


@pytest.mark.skipif(not HELD_OUT.exists(), reason="held-out sample not present")
def test_held_out_strong_only_view_floors():
    precision, recall = _rates(HELD_OUT, weak_as_yes=False)
    assert precision >= 0.90 and recall >= 0.65, (precision, recall)
