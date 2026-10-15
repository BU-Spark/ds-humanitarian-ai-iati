"""Tier 1 #1b: broad single keywords ("food", "agriculture", "livelihood")
should be distinguishable from strong hunger terms. The proposed label
"keyword_weak" is a spec for the fix, not something the code has yet."""
import pytest

from parse_filter import hunger_match


def test_strong_keyword_is_kept(make_rec):
    assert hunger_match(make_rec("Treating acute malnutrition in Somalia")) \
        == (True, "keyword")


def test_plural_still_matches(make_rec):
    # guard: a word-boundary "fix" would wrongly drop these
    assert hunger_match(make_rec("Restoring livelihoods after floods"))[0] is True


@pytest.mark.xfail(strict=True, reason="no weak/strong keyword tiers yet")
@pytest.mark.parametrize("title", [
    "Food for thought: civic education for youth",
    "Women's cooperatives in agriculture value chains",
    "Livelihood diversification and governance",
])
def test_broad_keyword_only_is_flagged_weak(make_rec, title):
    assert hunger_match(make_rec(title)) == (True, "keyword_weak")
