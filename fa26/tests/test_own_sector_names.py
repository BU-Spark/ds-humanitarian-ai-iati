"""Tier 1 #1a: Oxfam GB's own sector vocabulary (99) names should not, on
their own, make an activity hunger-related. ~122 kept activities match only
because the sector name "A Sustainable Livelihood" contains "livelihood"."""
import pytest

from parse_filter import hunger_match

SUSTAINABLE_LIVELIHOOD = ("1", "99", "A Sustainable Livelihood")
LIFE_AND_SECURITY = ("3", "99", "Life and Security")


@pytest.mark.xfail(strict=True, reason="own-vocab sector name alone triggers keep")
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
