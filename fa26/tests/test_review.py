"""Manual review layer: dropped activities that might be hunger-related are
queued for a person instead of being lost, kept ones carry a confidence
tier, and a reviewer's decision overrides the filter (client meeting,
23 Oct 2026)."""
import csv

import pytest

import parse_filter
import review
from parse_filter import hunger_match, matched_terms, review_reasons


def _reasons(rec):
    return review_reasons(rec, *hunger_match(rec))


@pytest.mark.parametrize("title, sectors, expected", [
    # dropped, but mentions a term deliberately left out of the filter
    ("Cash for work: rehabilitating roads", (), ["near_miss_term"]),
    ("Purchase for Progress (P4P) pilot", (), ["near_miss_term"]),
    ("Civic participation and governance", (), []),
    # kept activities are never queued, however doubtful: a wrong keep is
    # the cheaper error, and confidence "low" already marks them
    ("Restoring livelihoods after floods", (), []),
    ("Strengthening local institutions", (("2", "7", ""),), []),
    ("Water and food security for IDPs", (("14030", "1", ""),), []),
])
def test_review_reasons(make_rec, title, sectors, expected):
    assert _reasons(make_rec(title, sectors=sectors)) == expected


def test_matched_terms_explain_the_match(make_rec):
    terms = matched_terms(make_rec("Cash transfer for food in drought areas"))
    assert "context: cash transfer, drought" in terms
    assert "food: food" in terms


def test_matched_terms_ignore_org_names(make_rec):
    assert matched_terms(make_rec("Logistics support with World Food Programme")) == ""


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _activities(env):
    return {r["iati_identifier"]: r
            for r in _rows(env / "graph" / "nodes_activities.csv")}


def test_text_overrules_non_hunger_sector(make_rec):
    # missing a hunger activity is worse than keeping an extra one
    assert hunger_match(make_rec("Water and food security for IDPs",
                                 sectors=[("14030", "1", "")])) \
        == (True, "keyword_over_sector")
    # weak words alone don't overrule the publisher's coding
    assert hunger_match(make_rec("Drought-resilient water supply",
                                 sectors=[("14030", "1", "")])) \
        == (False, "sector_no_match")


def test_french_strong_terms(make_rec):
    # the one miss on John's sample: WFP Haiti, DAC 73010, French text
    rec = make_rec("Fournir une assistance alimentaire aux ménages vulnérables",
                   sectors=[("73010", "1", "")])
    assert hunger_match(rec) == (True, "keyword_over_sector")


def test_kept_activities_carry_confidence(fixture_env):
    parse_filter.run("oxfamgb")
    assert _rows(review.QUEUE) == []  # nothing in the fixture is a near miss
    acts = _activities(fixture_env)
    assert acts["GB-CHC-202918-TEST001"]["confidence"] == "high"      # sector
    assert acts["US-EIN-237069110-TEST004"]["confidence"] == "medium"  # keyword
    assert acts["GB-CHC-202918-TEST006"]["confidence"] == "low"       # weak
    assert {a["review_status"] for a in acts.values()} == {"not_flagged"}


def _queue_row(iid, **kw):
    return {"iati_identifier": iid, "publisher": "oxfamgb", "title": "t",
            "description": "", "filter_decision": "dropped",
            "match_basis": "no_signal", **kw}


def test_decisions_override_filter_and_survive_requeue(fixture_env):
    # a reviewer includes a dropped activity from the queue...
    review._write(review.QUEUE, [_queue_row(
        "GB-CHC-202918-TEST007", decision="include", reviewer="DV",
        notes="test")], review.QUEUE_FIELDS)
    # ...and excludes a kept weak match directly in the decisions file
    review._write(review.DECISIONS, [{
        "iati_identifier": "GB-CHC-202918-TEST006", "decision": "exclude",
    }], review.DECISION_FIELDS)

    parse_filter.run("oxfamgb")

    acts = _activities(fixture_env)
    assert "GB-CHC-202918-TEST006" not in acts
    assert acts["GB-CHC-202918-TEST007"]["review_status"] == "include"
    assert acts["GB-CHC-202918-TEST007"]["match_basis"] == "no_signal"
    assert _rows(review.QUEUE) == []  # the rewritten queue drops decided rows
    saved = {d["iati_identifier"]: d for d in _rows(review.DECISIONS)}
    assert saved["GB-CHC-202918-TEST007"]["decision"] == "include"
    assert saved["GB-CHC-202918-TEST007"]["reviewer"] == "DV"
    assert saved["GB-CHC-202918-TEST006"]["decision"] == "exclude"


def test_bad_decision_value_is_ignored_not_lost(fixture_env):
    review._write(review.QUEUE, [_queue_row("X-1", decision="maybe")],
                  review.QUEUE_FIELDS)
    assert review.harvest() == 0
    assert review.load_decisions() == {}
