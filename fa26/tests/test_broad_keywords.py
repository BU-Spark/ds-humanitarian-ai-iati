"""Tier 1 #1b: broad single keywords ("food", "agriculture", "livelihood")
are kept but labelled "keyword_weak" for review, separately from strong
hunger terms."""
import pytest

from parse_filter import hunger_match


def test_strong_keyword_is_kept(make_rec):
    assert hunger_match(make_rec("Treating acute malnutrition in Somalia")) \
        == (True, "keyword")


def test_plural_still_matches(make_rec):
    # guard: a word-boundary "fix" would wrongly drop these
    assert hunger_match(make_rec("Restoring livelihoods after floods"))[0] is True


@pytest.mark.parametrize("title", [
    "Food for thought: civic education for youth",
    "Women's cooperatives in agriculture value chains",
    "Livelihood diversification and governance",
    "Drought response in Badakshan",
    "Empowering smallholder farmers against disaster",
])
def test_broad_keyword_only_is_flagged_weak(make_rec, title):
    assert hunger_match(make_rec(title)) == (True, "keyword_weak")


def test_strong_wins_over_weak(make_rec):
    rec = make_rec("Agriculture and nutrition support for farmers")
    assert hunger_match(rec) == (True, "keyword")


@pytest.mark.parametrize("title", [
    "Cash Voucher (for food) Distribution",
    "Livelihood recovery and food production support",
    "Drought response: cash transfers to food-poor households",
])
def test_context_term_next_to_food_is_strong(make_rec, title):
    # John's context rule: livelihood/cash/agriculture terms + a food word
    assert hunger_match(make_rec(title)) == (True, "keyword")


def test_food_alone_without_context_stays_weak(make_rec):
    assert hunger_match(make_rec("Food for thought: civic education")) \
        == (True, "keyword_weak")


def test_oxfam_food_security_acronym_is_strong(make_rec):
    # EFSVL = Emergency Food Security and Vulnerable Livelihoods
    rec = make_rec("EFSVL and WASH support to vulnerable communities in Melut")
    assert hunger_match(rec) == (True, "keyword")


def test_keyword_past_2000_chars_is_seen(make_rec):
    # descriptions used to be truncated before matching
    rec = make_rec("Community programme", description="x " * 1200 + "famine relief")
    assert hunger_match(rec) == (True, "keyword")
