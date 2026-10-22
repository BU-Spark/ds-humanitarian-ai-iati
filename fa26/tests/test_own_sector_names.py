"""Tier 1 #1a: Oxfam GB's own sector vocabulary (99) names should not, on
their own, make an activity hunger-related. ~122 kept activities matched only
because the sector name "A Sustainable Livelihood" contains "livelihood"."""
from parse_filter import hunger_match

SUSTAINABLE_LIVELIHOOD = ("1", "99", "A Sustainable Livelihood")
LIFE_AND_SECURITY = ("3", "99", "Life and Security")


def test_sector_name_alone_does_not_keep(make_rec):
    rec = make_rec("Strengthening local governance in Yemen",
                   sectors=[SUSTAINABLE_LIVELIHOOD])
    assert hunger_match(rec)[0] is False


def test_hunger_title_with_own_sector_is_kept(make_rec):
    rec = make_rec("Emergency food assistance in Jonglei",
                   sectors=[SUSTAINABLE_LIVELIHOOD])
    assert hunger_match(rec) == (True, "keyword")


def test_non_hunger_own_sector_is_dropped(make_rec):
    rec = make_rec("Strengthening local governance in Yemen",
                   sectors=[LIFE_AND_SECURITY])
    assert hunger_match(rec) == (False, "no_signal")


def test_sdg2_sector_tag_is_kept(make_rec):
    # SDG vocabularies are official: goal 2 / target 2.x is a hunger signal
    # even when the title has no keyword
    assert hunger_match(make_rec("Resilience programme",
                                 sectors=[("2", "7", "Zero hunger")])) \
        == (True, "sdg")
    assert hunger_match(make_rec("Resilience programme",
                                 sectors=[("2.1", "8", "End hunger")])) \
        == (True, "sdg")


def test_other_sdg_tag_is_not_a_signal(make_rec):
    # goal 5 (gender) and target 12.1 must not match via the "2" prefix
    rec = make_rec("Women's rights programme",
                   sectors=[("5", "7", "Gender equality"),
                            ("12.1", "8", "Sustainable consumption")])
    assert hunger_match(rec) == (False, "no_signal")
