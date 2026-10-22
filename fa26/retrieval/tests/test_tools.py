"""Each tool against answers recomputed from the CSVs with pandas.

The pandas side re-implements the tool's definition independently of
Cypher: same filters, same SAME_AS canonicalisation, same self-exclusion.
If a test fails, either the Cypher or the definition drifted."""
import pytest

import entities as E
from tools import activities, shared_partners, top_funders, funding_over_time, PUBLISHER_LABELS

pytestmark = pytest.mark.usefixtures("graph_db")
CANON = {v: c for c, vs in E.SAME_AS.items() for v in vs}
KEYS = {"status", "rows", "cypher", "params", "coverage_note"}


def canon(ref):
    return CANON.get(ref, ref)


# ------------------------------------------------------------ shape --
def test_return_shape_ok_and_error():
    ok = activities(country="Somalia", limit=3)
    assert KEYS <= set(ok) and ok["status"] == "ok" and 0 < len(ok["rows"]) <= 3
    assert "LIMIT" in ok["cypher"] and ok["params"]["country"] == "SO"
    assert {"iati_identifier", "publisher"} <= set(ok["rows"][0])
    err = activities(country="Kenya")
    assert KEYS <= set(err) and err["status"] == "error" and err["rows"] == [] and err["cypher"] == ""
    amb = activities(publisher="Oxfam")
    assert amb["status"] == "error" and amb["candidates"]


def test_bad_inputs_are_errors_not_empty():
    assert activities(year_from="twenty")["status"] == "error"
    assert top_funders("Somalia", transaction_types=("Grant",))["status"] == "error"
    assert funding_over_time(by="week")["status"] == "error"
    assert shared_partners(["WFP"])["status"] == "error"


def test_read_query_requires_limit(graph_db):
    with pytest.raises(ValueError):
        graph_db.read_query("MATCH (n) RETURN count(n)")


# ------------------------------------------------------- activities --
@pytest.mark.parametrize("country,publisher", [("Yemen", "Oxfam GB"), ("Sudan", "WFP"), ("Haiti", None)])
def test_activities_counts(csv, country, publisher):
    code = {"Yemen": "YE", "Sudan": "SD", "Haiti": "HT"}[country]
    act = csv["act"]
    exp = act[act.countries.apply(lambda cc: code in cc)]
    if publisher:
        exp = exp[exp.publisher == {v: k for k, v in PUBLISHER_LABELS.items()}[
            "World Food Programme" if publisher == "WFP" else publisher]]
    r = activities(country=country, publisher=publisher, limit=500)
    assert r["status"] == "ok"
    assert {x["iati_identifier"] for x in r["rows"]} == set(exp.iati_identifier)


def test_activities_year_window_means_active_during(csv):
    act = csv["act"]
    exp = act[(act.countries.apply(lambda cc: "YE" in cc)) & (act.publisher == "oxfamgb")
              & (act.start_year <= 2020) & (act.end_year >= 2018)]
    r = activities(country="Yemen", publisher="Oxfam GB", year_from=2018, year_to="2020", limit=500)
    assert {x["iati_identifier"] for x in r["rows"]} == set(exp.iati_identifier)
    assert len(exp) == 30


def test_activities_match_type(csv):
    act = csv["act"]
    r = activities(match_type="sector", limit=500)
    assert len(r["rows"]) == (act.match_basis == "sector").sum() == 75
    assert {x["publisher"] for x in r["rows"]} == {"wfp"}
    assert "sector codes" in r["coverage_note"]


# ------------------------------------------------------ top_funders --
def pandas_funders(csv, code, types=("1",), exclude_self=True, year_from=None):
    act, tx, txe, rep = csv["act"], csv["tx"], csv["txe"], csv["rep"]
    ids = set(act[act.countries.apply(lambda cc: code in cc)].iati_identifier)
    t = tx[tx.iati_identifier.isin(ids) & tx.type.isin(types)]
    if year_from:
        t = t[t.year >= year_from]
    prov = txe[txe.edge == "PROVIDED_BY"].merge(t, on="tx_id")
    prov["org"] = prov.org_ref.map(canon)
    reporter = rep.set_index("iati_identifier").org_ref.map(canon)
    if exclude_self:
        prov = prov[prov.org != prov.iati_identifier.map(reporter)]
    g = prov.groupby(["org", "currency"]).agg(net=("value", "sum"), n=("tx_id", "count"),
                                              n_neg=("value", lambda s: (s < 0).sum())).reset_index()
    return g.sort_values("net", ascending=False)


def test_top_funder_somalia_usd(csv):
    exp = pandas_funders(csv, "SO")
    exp = exp[exp.currency == "USD"].iloc[0]
    r = top_funders("Somalia", limit=1)
    got = next(x for x in r["rows"] if x["currency"] == "USD")
    assert got["funder_id"] == exp.org == "XM-DAC-302"
    assert got["net"] == round(exp.net) == 1203270484 and got["n_transactions"] == exp.n == 44
    assert got["n_negative"] == exp.n_neg
    assert got["positive_total"] + got["negative_total"] == got["net"]


def test_top_funder_south_sudan_gbp_is_wfp_canonicalised(csv):
    exp = pandas_funders(csv, "SS")
    exp = exp[exp.currency == "GBP"].iloc[0]
    r = top_funders("South Sudan", limit=1)
    got = next(x for x in r["rows"] if x["currency"] == "GBP")
    assert exp.org == got["funder_id"] == "XM-DAC-41140"      # the name: pseudo-ref merged in
    assert got["net"] == round(exp.net) and got["n_transactions"] == exp.n == 162
    assert "name:UN World Food Programme (WFP)" in got["all_refs"]


def test_top_funders_self_exclusion_and_year(csv):
    with_self = pandas_funders(csv, "YE", exclude_self=False)
    assert "GB-CHC-202918" in set(with_self.org)
    r = top_funders("Yemen", limit=500)
    assert "GB-CHC-202918" not in {x["funder_id"] for x in r["rows"]}
    r2 = top_funders("Yemen", limit=500, exclude_self=False)
    assert "GB-CHC-202918" in {x["funder_id"] for x in r2["rows"]}
    exp = pandas_funders(csv, "SO", year_from=2024)
    exp = exp[exp.currency == "USD"].iloc[0]
    got = next(x for x in top_funders("Somalia", year_from="2024", limit=1)["rows"] if x["currency"] == "USD")
    assert got["funder_id"] == exp.org and got["net"] == round(exp.net)


def test_top_funders_limit_is_per_currency(csv):
    r = top_funders("Yemen", limit=3)
    from collections import Counter
    assert all(n <= 3 for n in Counter(x["currency"] for x in r["rows"]).values())
    assert len(r["rows"]) == 6
    # rows never interleave currencies
    cur = [x["currency"] for x in r["rows"]]
    assert cur == sorted(cur)


def test_disbursement_default_from_brief_explains_itself():
    r = top_funders("Yemen", transaction_types=("Disbursement",))
    assert r["status"] == "no_results" and "exclude_self" in r["coverage_note"]


# ------------------------------------------------ funding_over_time --
def test_funding_over_time_wfp_yearly(csv):
    tx = csv["tx"]
    exp = tx[(tx.publisher == "wfp") & (tx.type == "1")].groupby(["year", "currency"]).value.sum()
    r = funding_over_time(publisher="WFP")
    assert r["status"] == "ok"
    got = {(int(x["period"]), x["currency"]): x["net"] for x in r["rows"]}
    assert set(got) == set(exp.index)
    for k, v in exp.items():
        assert got[k] == round(v)
    assert min(y for y, _ in got) == 2021
    assert "2021" in r["coverage_note"]


def test_funding_over_time_quarters_sum_to_year(csv):
    y = funding_over_time(publisher="WFP", country="Sudan", transaction_type="Expenditure", year_from=2023, year_to=2023)
    q = funding_over_time(publisher="WFP", country="Sudan", transaction_type="Expenditure", by="quarter",
                          year_from=2023, year_to=2023)
    assert len(y["rows"]) == 1 and len(q["rows"]) == 4
    assert abs(sum(x["net"] for x in q["rows"]) - y["rows"][0]["net"]) <= 2   # per-row rounding
    assert "mirrors" in y["coverage_note"]


def test_funding_over_time_oxfam_america_only_expenditure(csv):
    assert funding_over_time(publisher="Oxfam America")["status"] == "no_results"
    tx = csv["tx"]
    exp = tx[(tx.publisher == "oxfamus") & (tx.type == "4")].value.sum()
    r = funding_over_time(publisher="Oxfam America", transaction_type="Expenditure")
    assert abs(round(exp) - sum(x["net"] for x in r["rows"])) <= len(r["rows"])   # per-row rounding


# -------------------------------------------------- shared_partners --
def pandas_shared(csv, slugs, code=None):
    act, part, txe, tx, rep = csv["act"], csv["part"], csv["txe"], csv["tx"], csv["rep"]
    pub = act.set_index("iati_identifier").publisher
    links = part[["org_ref", "iati_identifier"]].copy()
    te = txe.merge(tx[["tx_id", "iati_identifier"]], on="tx_id")[["org_ref", "iati_identifier"]]
    links = __import__("pandas").concat([links, te])
    links["publisher"] = links.iati_identifier.map(pub)
    links = links[links.publisher.isin(slugs)]
    if code:
        keep = set(act[act.countries.apply(lambda cc: code in cc)].iati_identifier)
        links = links[links.iati_identifier.isin(keep)]
    links["org"] = links.org_ref.map(canon)
    excl = set(E.PLACEHOLDERS)
    for s in slugs:
        ref = rep[rep.iati_identifier.isin(act[act.publisher == s].iati_identifier)].org_ref.iloc[0]
        excl |= {ref, *E.SAME_AS.get(ref, [])}
    links = links[~links.org.isin(excl) & ~links.org_ref.isin(excl)]
    g = links.groupby("org").agg(pubs=("publisher", lambda s: set(s)), n=("iati_identifier", "nunique"))
    return g[g.pubs.apply(len) == len(slugs)]


def test_shared_partners_oxfamgb_wfp(csv):
    exp = pandas_shared(csv, ["oxfamgb", "wfp"])
    r = shared_partners(["Oxfam GB", "WFP"], limit=500)
    got = {x["organisation_id"]: x["n_activities"] for x in r["rows"]}
    assert set(got) == set(exp.index)
    assert got == exp.n.to_dict()
    assert "XI-IATI-EC_ECHO" in got and "XM-DAC-41122" in got     # ECHO, UNICEF: invisible in the prototype
    assert "XM-DAC-41140" not in got and "GB-CHC-202918" not in got
    assert "MU" not in got


def test_shared_partners_with_country(csv):
    exp = pandas_shared(csv, ["oxfamgb", "wfp"], "SS")
    r = shared_partners(["Oxfam GB", "WFP"], country="South Sudan", limit=500)
    assert {x["organisation_id"] for x in r["rows"]} == set(exp.index)


def test_shared_partners_oxfam_america_has_none():
    r = shared_partners(["Oxfam GB", "Oxfam America"])
    assert r["status"] == "no_results" and "Oxfam America" in r["coverage_note"]
