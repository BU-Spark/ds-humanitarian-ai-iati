"""resolve_entity: the examples from the brief plus the ambiguity rules."""
import pytest

from resolve_entity import resolve_entity, get_catalog

pytestmark = pytest.mark.usefixtures("graph_db")


@pytest.fixture(scope="module")
def cat():
    return get_catalog()


@pytest.mark.parametrize("text,expected_id,expected_ids", [
    ("WFP", "XM-DAC-41140", {"XM-DAC-41140", "name:UN World Food Programme (WFP)"}),
    ("World Food Program", "XM-DAC-41140", None),
    ("Oxfam America", "US-EIN-23-7069110", {"US-EIN-23-7069110"}),
    ("UK government", "XM-DAC-12", None),
    ("FCDO", "XM-DAC-12-1", {"XM-DAC-12-1"}),
    ("unicef", "XM-DAC-41122", None),
])
def test_organisation_ok(cat, text, expected_id, expected_ids):
    r = resolve_entity(text, "organisation", cat)
    assert r["status"] == "ok", r
    assert r["match"]["id"] == expected_id
    assert r["match"]["confidence"] >= 0.9
    if expected_ids is not None:
        assert set(r["match"]["ids"]) == expected_ids
    assert expected_id in r["match"]["ids"]


def test_uk_group_includes_fcdo(cat):
    r = resolve_entity("UK government", "organisation", cat)
    assert "XM-DAC-12-1" in r["match"]["ids"]
    assert r["match"]["relation"] == "agency_of"


def test_fcdo_reports_parent(cat):
    assert resolve_entity("FCDO", "organisation", cat)["match"]["parent"] == "XM-DAC-12"


def test_publisher_slug_on_match(cat):
    assert resolve_entity("Oxfam GB", "organisation", cat)["match"]["publisher"] == "oxfamgb"
    assert resolve_entity("WFP", "organisation", cat)["match"]["publisher"] == "wfp"


def test_oxfam_is_ambiguous_with_publishers_first(cat):
    r = resolve_entity("Oxfam", "organisation", cat)
    assert r["status"] == "ambiguous" and r["match"] is None
    first_two = {c["id"] for c in r["candidates"][:2]}
    assert first_two == {"GB-CHC-202918", "US-EIN-23-7069110"}


def test_save_the_children_is_ambiguous(cat):
    r = resolve_entity("Save the Children", "organisation", cat)
    assert r["status"] == "ambiguous" and len(r["candidates"]) == 2


def test_typo_resolves_via_fuzzy(cat):
    r = resolve_entity("Oxfam Amerika", "organisation", cat)
    assert r["status"] == "ok" and r["match"]["id"] == "US-EIN-23-7069110" and r["match"]["method"] == "fuzzy"


def test_partial_name_is_not_a_confident_match(cat):
    r = resolve_entity("Red Cross", "organisation", cat)
    assert r["status"] == "ambiguous"
    assert r["candidates"][0]["id"] == "name:British Red Cross"


def test_placeholder_carries_warning(cat):
    r = resolve_entity("Multilateral", "organisation", cat)
    assert r["status"] == "ok" and "placeholder" in r["note"]


def test_short_unknown_input_is_not_fuzzed(cat):
    assert resolve_entity("XQ", "organisation", cat)["status"] == "no_results"


@pytest.mark.parametrize("text,code", [
    ("Somalia", "SO"), ("SO", "SO"), ("SOM", "SO"), ("DRC", "CD"), ("COD", "CD"),
    ("Democratic Republic of the Congo", "CD"), ("Palestine", "PS"), ("Burma", "MM"), ("sudan", "SD"),
])
def test_country_ok(cat, text, code):
    r = resolve_entity(text, "country", cat)
    assert r["status"] == "ok" and r["match"]["id"] == code and r["match"]["ids"] == [code]


def test_non_hotspot_country(cat):
    r = resolve_entity("Kenya", "country", cat)
    assert r["status"] == "no_results" and "13 hotspot" in r["note"]


def test_kind_separation(cat):
    assert resolve_entity("Somalia", "organisation", cat)["match"]["id"] == "XM-DAC-273"
    assert resolve_entity("Somalia", "country", cat)["match"]["id"] == "SO"


def test_bad_kind(cat):
    assert resolve_entity("Somalia", "planet", cat)["status"] == "error"
