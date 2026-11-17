"""Each tool against answers recomputed from the CSVs with pandas.

The pandas side re-implements the tool's definition independently of
Cypher: same filters, same SAME_AS canonicalisation, same self-exclusion.
If a test fails, either the Cypher or the definition drifted. Expected
values come from the CSVs the graph was loaded from (RETRIEVAL_GRAPH_DIR),
so the suite runs on the summer graph and on the cleaned one."""
import pytest

import entities as E
from tools import activities, shared_partners, top_funders, funding_over_time, transaction_totals, for_model, PUBLISHER_LABELS

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
    assert {x["iati_identifier"] for x in r["rows"]} == set(exp.iati_identifier) and len(exp) > 0


def test_activities_match_type(csv):
    act = csv["act"]
    r = activities(match_type="sector", limit=500)
    assert len(r["rows"]) == (act.match_basis == "sector").sum() > 0
    assert {x["publisher"] for x in r["rows"]} == {"wfp"}
    assert "sector codes" in r["coverage_note"]
    for mt in ("keyword", "keyword_weak", "sdg"):
        r = activities(match_type=mt, limit=500)
        assert len(r["rows"]) == (act.match_basis == mt).sum()
    assert activities(match_type="fuzzy")["status"] == "error"


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
    g = prov.groupby(["org", "currency"]).agg(amount=("value", lambda s: s[s > 0].sum()),
                                              adjustments=("value", lambda s: s[s < 0].sum()),
                                              net=("value", "sum"), n=("tx_id", "count"),
                                              n_neg=("value", lambda s: (s < 0).sum())).reset_index()
    return g.sort_values("amount", ascending=False)


def test_top_funder_somalia_usd(csv):
    exp = pandas_funders(csv, "SO")
    exp = exp[exp.currency == "USD"].iloc[0]
    r = top_funders("Somalia", limit=1)
    got = next(x for x in r["rows"] if x["currency"] == "USD")
    assert got["funder_id"] == exp.org == "XM-DAC-302"
    assert got["amount"] == pytest.approx(exp.amount, abs=0.01) and got["n_transactions"] == exp.n
    assert got["adjustments"] == pytest.approx(exp.adjustments, abs=0.01) and got["n_adjustments"] == exp.n_neg
    assert got["net"] == pytest.approx(exp.net, abs=0.01)
    assert got["amount"] + got["adjustments"] == pytest.approx(got["net"], abs=0.01)


def test_adjustments_are_their_own_category(csv):
    r = top_funders("Yemen", limit=500)
    assert all(x["amount"] >= 0 and x["adjustments"] <= 0 for x in r["rows"])
    assert any(x["n_adjustments"] > 0 for x in r["rows"])
    for cur in {x["currency"] for x in r["rows"]}:          # ranked by amount, not net
        amounts = [x["amount"] for x in r["rows"] if x["currency"] == cur]
        assert amounts == sorted(amounts, reverse=True)
    assert "adjustments" in r["coverage_note"]


def test_top_funder_south_sudan_gbp_is_wfp_canonicalised(csv):
    exp = pandas_funders(csv, "SS")
    exp = exp[exp.currency == "GBP"].iloc[0]
    r = top_funders("South Sudan", limit=1)
    got = next(x for x in r["rows"] if x["currency"] == "GBP")
    assert exp.org == got["funder_id"] == "XM-DAC-41140"      # the name: pseudo-ref merged in
    assert got["amount"] == pytest.approx(exp.amount, abs=0.01) and got["n_transactions"] == exp.n
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
    assert got["funder_id"] == exp.org and got["amount"] == pytest.approx(exp.amount, abs=0.01)


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
    t = tx[(tx.publisher == "wfp") & (tx.type == "1")]
    exp = t[t.value > 0].groupby(["year", "currency"]).value.sum()
    exp_adj = t[t.value < 0].groupby(["year", "currency"]).value.sum()
    r = funding_over_time(publisher="WFP")
    assert r["status"] == "ok"
    got = {(int(x["period"]), x["currency"]): x for x in r["rows"]}
    assert set(got) == set(exp.index)
    for k, v in exp.items():
        assert got[k]["amount"] == pytest.approx(v, abs=0.01)
        assert got[k]["adjustments"] == pytest.approx(exp_adj.get(k, 0), abs=0.01)
    assert min(y for y, _ in got) == 2021
    assert "2021" in r["coverage_note"]


def test_funding_over_time_quarters_sum_to_year(csv):
    y = funding_over_time(publisher="WFP", country="Sudan", transaction_type="Expenditure", year_from=2023, year_to=2023)
    q = funding_over_time(publisher="WFP", country="Sudan", transaction_type="Expenditure", by="quarter",
                          year_from=2023, year_to=2023)
    assert len(y["rows"]) == 1 and len(q["rows"]) == 4
    assert sum(x["net"] for x in q["rows"]) == pytest.approx(y["rows"][0]["net"], abs=0.01)
    assert "mirrors" in y["coverage_note"]


def test_funding_over_time_oxfam_america_only_expenditure(csv):
    assert funding_over_time(publisher="Oxfam America")["status"] == "no_results"
    tx = csv["tx"]
    exp = tx[(tx.publisher == "oxfamus") & (tx.type == "4")].value.sum()
    r = funding_over_time(publisher="Oxfam America", transaction_type="Expenditure")
    assert sum(x["net"] for x in r["rows"]) == pytest.approx(exp, abs=0.01)


# ---------------------------------------------- transaction_totals --
def pandas_totals(csv, type_code, publisher=None, currency=None, country=None, year=None):
    act, tx = csv["act"], csv["tx"]
    t = tx[tx.type == type_code]
    if publisher:
        t = t[t.publisher == publisher]
    if currency:
        t = t[t.currency == currency]
    if year:
        t = t[t.date.str[:4] == str(year)]
    links = {}
    if country:
        tc = csv["tc"][csv["tc"].country_code == country]
        t = t[t.iati_identifier.isin(set(tc.iati_identifier))]
        links = tc.groupby("iati_identifier").source_id.apply(set).to_dict()
    act_src = act.set_index("iati_identifier").source_id

    def evidence(rows):
        ids = set(rows.source_id) | set(rows.iati_identifier.map(act_src))
        for a in set(rows.iati_identifier):
            ids |= links.get(a, set())
        return sorted(ids)
    return t, evidence


@pytest.mark.parametrize("type_code,type_name,publisher,currency", [
    ("1", "Incoming Funds", "wfp", "USD"),
    ("4", "Expenditure", "oxfamgb", "GBP"),
    ("3", "Disbursement", "oxfamgb", "GBP"),
])
def test_transaction_totals_values_and_evidence(csv, type_code, type_name, publisher, currency):
    t, evidence = pandas_totals(csv, type_code, publisher, currency)
    r = transaction_totals(type_name, publisher=publisher, currency=currency)
    assert r["status"] == "ok" and len(r["rows"]) == 1
    got = r["rows"][0]
    pos, neg = t[t.value > 0], t[t.value < 0]
    assert got["amount"] == pytest.approx(pos.value.sum(), abs=0.01)
    assert got["adjustments"] == pytest.approx(neg.value.sum(), abs=0.01)
    assert got["net"] == pytest.approx(t.value.sum(), abs=0.01)
    assert got["n_transactions"] == len(t) and got["n_adjustments"] == len(neg)
    # complete lineage per figure: the sign's transaction rows plus their activity rows
    assert got["evidence_amount"] == evidence(pos)
    assert got["evidence_adjustments"] == evidence(neg)
    assert got["evidence_net"] == evidence(t)


def test_money_sums_are_exact_cents(csv):
    """value_cents sums reproduce the Decimal total of the raw strings to the cent
    (a float sum is off by ~2e-5 on this group)."""
    from decimal import Decimal
    tx = csv["tx"]
    t = tx[(tx.publisher == "wfp") & (tx.type == "1") & (tx.currency == "USD")]
    row = transaction_totals("Incoming Funds", publisher="WFP", currency="USD")["rows"][0]
    for got, rows in ((row["amount"], t[t.value > 0]), (row["adjustments"], t[t.value < 0]), (row["net"], t)):
        exact = sum((Decimal(v) for v in rows.value_raw), Decimal(0)).quantize(Decimal("0.01"))
        assert Decimal(repr(got)) == exact


def test_transaction_totals_country_cites_targeting_rows(csv):
    t, evidence = pandas_totals(csv, "4", "wfp", "USD", country="SD", year=2023)
    r = transaction_totals("Expenditure", publisher="WFP", currency="USD", country="Sudan",
                           year_from=2023, year_to=2023)
    got = r["rows"][0]
    assert got["net"] == pytest.approx(t.value.sum(), abs=0.01)
    assert got["evidence_net"] == evidence(t)
    assert any(e.startswith("rel_targets_country.csv:") for e in got["evidence_net"])


def test_transaction_totals_by_currency_and_publisher(csv):
    tx = csv["tx"]
    t = tx[tx.type == "1"]
    r = transaction_totals()
    assert {x["currency"]: x["net"] for x in r["rows"]} == pytest.approx(t.groupby("currency").value.sum().to_dict(), abs=0.01)
    assert all(x["publisher"] is None for x in r["rows"])
    r = transaction_totals(by_publisher=True)
    exp = t.groupby(["publisher", "currency"]).value.sum().to_dict()
    assert {(x["publisher"], x["currency"]): x["net"] for x in r["rows"]} == pytest.approx(exp, abs=0.01)


def test_funding_over_time_country_matches_pandas(csv):
    t, evidence = pandas_totals(csv, "4", "wfp", "USD", country="SD", year=2023)
    rows = funding_over_time(publisher="WFP", country="Sudan", transaction_type="Expenditure",
                             year_from=2023, year_to=2023)["rows"]
    assert len(rows) == 1 and rows[0]["n_transactions"] == len(t)      # no row multiplication
    assert rows[0]["net"] == pytest.approx(t.value.sum(), abs=0.01)
    assert rows[0]["evidence_net"] == evidence(t)
    assert rows[0]["evidence_adjustments"] == evidence(t[t.value < 0])


def test_zero_figure_cites_searched_tables():
    row = transaction_totals("Expenditure", publisher="Oxfam America", currency="USD")["rows"][0]
    assert row["adjustments"] == 0 and row["n_adjustments"] == 0
    assert row["evidence_adjustments"] == ["manifest:nodes_activities.csv", "manifest:nodes_transactions.csv"]


def test_for_model_strips_evidence():
    full = transaction_totals()
    slim = for_model(full)
    assert slim["rows"] and not any(k.startswith("evidence") for r in slim["rows"] for k in r)
    assert full["rows"][0]["evidence_net"]                      # original untouched
    assert "evidence" not in for_model(transaction_totals(currency="EUR"))


def test_transaction_totals_empty_cites_searched_tables():
    r = transaction_totals(publisher="WFP", currency="USD", year_from=1990, year_to=1990)
    assert r["status"] == "no_results" and r["rows"] == []
    assert r["evidence"] == ["manifest:nodes_activities.csv", "manifest:nodes_transactions.csv"]
    r = transaction_totals("Expenditure", currency="EUR")
    assert r["evidence"] == ["manifest:nodes_transactions.csv"]


def test_transaction_totals_rejects_mixed_types():
    r = transaction_totals(("Outgoing Commitment", "Expenditure"))
    assert r["status"] == "error" and "one transaction type" in r["coverage_note"]
    assert transaction_totals(currency=["USD"])["status"] == "error"


def test_money_tools_carry_evidence(csv):
    r = top_funders("Somalia", limit=1)
    row = next(x for x in r["rows"] if x["currency"] == "USD")
    assert row["n_adjustments"] > 0
    assert len([e for e in row["evidence_adjustments"] if e.startswith("nodes_transactions.csv")]) == row["n_adjustments"]
    assert {e.split(":row:")[0] for e in row["evidence_net"]} == {
        "nodes_transactions.csv", "nodes_activities.csv", "rel_targets_country.csv", "rel_transaction_edges.csv"}
    f = funding_over_time(publisher="WFP", year_from=2023, year_to=2023)["rows"][0]
    assert len([e for e in f["evidence_net"] if e.startswith("nodes_transactions.csv")]) == f["n_transactions"]


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
