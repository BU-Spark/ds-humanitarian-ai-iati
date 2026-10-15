"""Tier 1 #1c: hunger words inside organisation names (World Food
Programme, Welthungerhilfe) should not count as a hunger signal."""
import pytest

from parse_filter import hunger_match


@pytest.mark.xfail(strict=True, reason="org names are matched as keywords")
@pytest.mark.parametrize("title", [
    "Joint logistics hub with the World Food Programme",
    "WASH rehabilitation in partnership with Welthungerhilfe",
])
def test_org_name_alone_does_not_keep(make_rec, title):
    assert hunger_match(make_rec(title))[0] is False


def test_real_hunger_work_with_wfp_is_kept(make_rec):
    # guard: stripping org names must not drop genuine hunger activities
    rec = make_rec("Food distribution with the World Food Programme")
    assert hunger_match(rec)[0] is True
