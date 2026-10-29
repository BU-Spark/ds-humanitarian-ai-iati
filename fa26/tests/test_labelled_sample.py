"""Score hunger_match() against hand-labelled samples in data/:

- hunger_filter_sample_50.csv: John's 50, used to tune the filter
- hunger_filter_sample_devansh_50.csv: Devansh's 50, held out for testing
  (skipped until labelled)

Floors are the scores on John's sample when the test was written. Raise them
when the filter improves; lowering them should be a deliberate decision.
"keyword_weak" activities are kept by the pipeline, so the first test counts
them as yes. The second scores the confident view: strong matches only."""
from pathlib import Path

import pytest

import evaluate_filter as ev

DATA = Path(__file__).parents[1] / "data"
JOHN = DATA / "hunger_filter_sample_50.csv"


def _rates(path, weak_as_yes):
    labelled = ev.load_labelled(path)
    if not labelled:
        pytest.skip(f"{path.name} has no labels yet")
    tp, fp, tn, fn, _ = ev.confusion(labelled, weak_as_yes)
    return tp / (tp + fp), tp / (tp + fn)


@pytest.mark.skipif(not JOHN.exists(), reason="labelled sample not present")
def test_pipeline_view_floors():
    precision, recall = _rates(JOHN, weak_as_yes=True)
    assert precision >= 0.70 and recall >= 0.95, (precision, recall)


@pytest.mark.skipif(not JOHN.exists(), reason="labelled sample not present")
def test_strong_only_view_floors():
    precision, recall = _rates(JOHN, weak_as_yes=False)
    assert precision >= 0.85 and recall >= 0.90, (precision, recall)
