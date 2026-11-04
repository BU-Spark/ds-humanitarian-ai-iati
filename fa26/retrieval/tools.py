"""
tools.py -- parameterised Cypher tools for the Graph RAG orchestrator.

Plain Python functions, no LangChain. Every tool returns the same dict:

    {
      "status": "ok" | "no_results" | "error",
      "rows": [...],            # activity rows carry iati_identifier + publisher;
                                # aggregate rows carry activity_ids + publishers
      "cypher": "...",          # the exact query that ran ("" on resolver errors)
      "params": {...},          # the exact parameters passed
      "coverage_note": "...",   # what the answer does NOT cover
    }

Money tools (top_funders, funding_over_time, transaction_totals) also put
three evidence lists on every row: `evidence_amount`, `evidence_adjustments`
and `evidence_net`. Each is the complete, untruncated set of source CSV rows
("nodes_transactions.csv:row:12") behind that figure: the transaction rows,
their activity rows, and the link rows a filter used (country targeting,
provider edge). This is the citation format Deniz's benchmark scores. When a
money tool finds nothing it returns top-level `evidence` naming the tables
searched ("manifest:nodes_transactions.csv"), as the benchmark expects.
Amounts are unrounded floats; format them at the presentation layer.

Inputs are free text: `country` and `publisher` go through resolve_entity,
so "Somalia", "SO", "SOM", "Oxfam", "WFP" all work. If resolution is
ambiguous the tool returns status "error" with the candidates so the caller
can ask the user instead of silently guessing.

All queries run read-only with a timeout and a LIMIT (see db.py). Values are
never formatted into Cypher; everything is a $parameter.

Facts about this graph that shape the defaults (verified 2026-10-21, see
findings.md): funders appear as the provider of "Incoming Funds"
transactions; "Disbursement" rows exist only for Oxfam GB with Oxfam GB
itself as provider, so it is NOT the default here. Money is never
currency-converted. About 23% of transactions are negative; per the client
(meeting 2026-10-23) they are reported as their own "adjustments" category,
never netted into the headline `amount`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db                                   # noqa: E402
import entities as E                        # noqa: E402
from resolve_entity import resolve_entity   # noqa: E402
from schema_prototype import TRANSACTION_TYPES   # noqa: E402  (code -> name)

MAX_LIMIT = 500
MAX_IDS_PER_ROW = 20
PUBLISHER_LABELS = {"oxfamgb": "Oxfam GB", "oxfamus": "Oxfam America", "wfp": "World Food Programme"}
TRANSACTION_TYPE_NAMES = sorted(set(TRANSACTION_TYPES.values()))
MATCH_TYPES = ("sector", "sdg", "keyword", "keyword_over_sector", "keyword_weak")

# variant ref -> canonical ref, so one funder is one row
CANON = {v: canon for canon, vs in E.SAME_AS.items() for v in vs}


# ---------------------------------------------------------------- helpers --
def _result(status, rows, cypher, params, note):
    return {"status": status, "rows": rows, "cypher": cypher, "params": params, "coverage_note": note}


def _error(message, params, candidates=None):
    out = _result("error", [], "", params, message)
    if candidates:
        out["candidates"] = candidates
    return out


def _year(v, name):
    """-> (int_or_None, error). LLM callers often pass years as strings."""
    if v is None or v == "":
        return None, None
    try:
        return int(v), None
    except (TypeError, ValueError):
        return None, f"{name} must be an integer year, got {v!r}"


def _limit(n):
    try:
        return max(1, min(int(n), MAX_LIMIT))
    except (TypeError, ValueError):
        return 50


def _country(text):
    """-> (code, error_dict_or_None)"""
    if text is None or text == "":
        return None, None
    r = resolve_entity(text, "country")
    if r["status"] != "ok":
        return None, (r["note"], r.get("candidates"))
    return r["match"]["id"], None


def _publisher(text):
    """-> (slug, org_ref, error) ; accepts slug, label, org name, or ref"""
    if text is None or text == "":
        return None, None, None
    t = str(text).strip().lower()
    for slug, label in PUBLISHER_LABELS.items():
        if t in (slug, label.lower()):
            return slug, _publisher_ref(slug), None
    r = resolve_entity(text, "organisation")
    if r["status"] != "ok":
        return None, None, (r["note"], r.get("candidates"))
    slug = r["match"].get("publisher")
    if not slug:
        return None, None, (f"'{text}' resolved to {r['match']['name']} ({r['match']['id']}), which is not one of "
                            f"the three publishers ({', '.join(PUBLISHER_LABELS.values())})", None)
    return slug, r["match"]["id"], None


_PUB_REFS = {}
_CANON_NAMES = {}


def _canon_names():
    """canonical ref -> display name, so a merged row is labelled by its
    canonical organisation even when only a variant ref had transactions."""
    if not _CANON_NAMES:
        from resolve_entity import get_catalog
        cat = get_catalog()
        for canon in E.SAME_AS:
            if canon in cat.orgs and cat.orgs[canon]["name"]:
                _CANON_NAMES[canon] = cat.orgs[canon]["name"]
    return _CANON_NAMES


def _publisher_ref(slug):
    if not _PUB_REFS:
        for row in db.read_query("MATCH (o:Organisation) WHERE o.publisher IS NOT NULL "
                                 "RETURN o.publisher AS slug, o.ref AS ref LIMIT 10"):
            _PUB_REFS[row["slug"]] = row["ref"]
    return _PUB_REFS.get(slug)


def _self_refs(slugs, placeholders=True):
    """Each publisher's own ref plus its SAME_AS variants (and placeholders)."""
    refs = set(E.PLACEHOLDERS) if placeholders else set()
    for s in slugs:
        ref = _publisher_ref(s)
        if ref:
            refs.add(ref)
            refs |= set(E.SAME_AS.get(ref, []))
    return sorted(refs)


def _types(transaction_types):
    if isinstance(transaction_types, str):
        transaction_types = (transaction_types,)
    names = []
    for t in transaction_types or ():
        t = str(t).strip()
        match = next((n for n in TRANSACTION_TYPE_NAMES if n.lower() == t.lower()), None)
        if match is None:
            code_name = TRANSACTION_TYPES.get(t)
            if code_name is None:
                return None, f"unknown transaction type '{t}'; use one of {TRANSACTION_TYPE_NAMES}"
            match = code_name
        names.append(match)
    return names, None


def _note(parts):
    return " ".join(p for p in parts if p)


def _coverage(publishers=None, year_from=None, money=False, types=(), sectors=False):
    """Conditional coverage notes from the Phase 1 findings."""
    pubs = set(publishers or PUBLISHER_LABELS)
    parts = []
    if money:
        parts.append("Amounts are summed per currency with no conversion. `amount` counts positive "
                     "transactions only; negative transactions (about 23% of rows) are reported separately "
                     "as `adjustments`, and `net` = amount + adjustments.")
    if "oxfamus" in pubs:
        parts.append("Oxfam America publishes 11 activities (2017-2018) with no funders, partners or "
                     "sector codes, so it contributes little or nothing here.")
    if "wfp" in pubs and money and (year_from is None or year_from < 2021):
        parts.append("WFP activities start in 2018 but WFP transactions only begin in 2021.")
    if "wfp" in pubs and money and any(t in ("Outgoing Commitment", "Expenditure") for t in types):
        parts.append("WFP mirrors every commitment as an identical expenditure; do not add those two types.")
    if "oxfamgb" in pubs and "Disbursement" in types:
        parts.append("Disbursement rows exist only for Oxfam GB and name Oxfam GB itself as provider.")
    if sectors:
        parts.append("Oxfam GB and Oxfam America have no standard sector codes, so their activities are "
                     "kept by keyword match. match_basis and confidence say why each activity is included; "
                     "keyword_weak and low-confidence ones are the least certain.")
    return _note(parts)


def _run(cypher, params, note, empty_note=""):
    try:
        rows = db.read_query(cypher, params)
    except Exception as e:  # driver/timeout/syntax: report, never raise into the agent loop
        return _result("error", [], cypher, params, f"query failed: {type(e).__name__}: {e}")
    if not rows:
        return _result("no_results", [], cypher, params, _note([empty_note, note]))
    return _result("ok", rows, cypher, params, note)


# Collected per group by every money query: one [tx row, activity row, link rows...]
# list per transaction, split by sign. `ev_links` must be bound before this runs.
MONEY_AGG = """
     sum(CASE WHEN t.value > 0 THEN t.value ELSE 0 END) AS amount,
     sum(CASE WHEN t.value < 0 THEN t.value ELSE 0 END) AS adjustments,
     sum(t.value) AS net,
     count(t) AS n_transactions, sum(CASE WHEN t.value < 0 THEN 1 ELSE 0 END) AS n_adjustments,
     collect(DISTINCT a.iati_identifier) AS acts,
     collect(CASE WHEN t.value > 0 THEN [t.source_id, a.source_id] + ev_links END) AS ev_amount,
     collect(CASE WHEN t.value < 0 THEN [t.source_id, a.source_id] + ev_links END) AS ev_adjustments,
     collect([t.source_id, a.source_id] + ev_links) AS ev_net"""


def _money(out, tables):
    """Flatten the ev_* columns into sorted, de-duplicated evidence lists. A figure
    with no contributing rows (e.g. adjustments of 0) cites the searched tables,
    the way the benchmark cites an empty match; so does a no_results answer."""
    manifest = sorted(f"manifest:{t}" for t in tables)
    for r in out["rows"]:
        for k in ("amount", "adjustments", "net"):
            r[f"evidence_{k}"] = sorted({x for ids in r.pop(f"ev_{k}") for x in ids if x}) or manifest
    if out["status"] == "no_results":
        out["evidence"] = manifest
    return out


def for_model(result):
    """Copy of a tool result without evidence lists, for the LLM's context.

    Evidence can run to tens of thousands of row ids (about 1 MB for
    transaction_totals() over all publishers). Give the model this copy and
    keep the full result in code to attach citations to the final answer."""
    out = {k: v for k, v in result.items() if k != "evidence"}
    out["rows"] = [{k: v for k, v in r.items() if not k.startswith("evidence_")} for r in result["rows"]]
    return out


def _searched(*tables, publisher=None, country=None):
    """Tables an empty money answer searched (benchmark manifest rule)."""
    return {"nodes_transactions.csv", *tables,
            *(["nodes_activities.csv"] if publisher else []),
            *(["rel_targets_country.csv"] if country else [])}


# ------------------------------------------------------------------ tools --
ACTIVITIES_CYPHER = """
MATCH (a:Activity)
WHERE ($country IS NULL OR EXISTS { MATCH (a)-[:TARGETS]->(:Country {code: $country}) })
  AND ($publisher IS NULL OR a.publisher = $publisher)
  AND ($match_type IS NULL OR a.match_basis = $match_type)
  AND ($year_from IS NULL OR coalesce(a.end_date, a.start_date).year >= $year_from)
  AND ($year_to IS NULL OR a.start_date.year <= $year_to)
RETURN a.iati_identifier AS iati_identifier, a.publisher AS publisher, a.title AS title,
       a.status_name AS status, toString(a.start_date) AS start_date, toString(a.end_date) AS end_date,
       a.hotspot_countries AS countries, a.match_basis AS match_basis, a.confidence AS confidence,
       a.humanitarian AS humanitarian
ORDER BY a.start_date DESC, a.iati_identifier
LIMIT $limit
"""


def activities(country=None, publisher=None, year_from=None, year_to=None, match_type=None, limit=50):
    """List hunger-related activities in the graph.

    Args:
        country: hotspot country name or ISO code ("Somalia", "SO", "SOM", "DRC"). None = all 13.
        publisher: "Oxfam GB" | "Oxfam America" | "WFP" (or slug / org name). None = all.
        year_from, year_to: ints. An activity matches if it was ACTIVE in the
            range: start year <= year_to and end year (or start year if no end) >= year_from.
        match_type: why the hunger filter kept the activity: "sector" (standard DAC/cluster code),
            "sdg" (SDG 2 tag), "keyword" (strong term), "keyword_over_sector" (strong term despite
            non-hunger codes) or "keyword_weak" (weak terms only). None = all.
        limit: max rows (<= 500).
    Returns: rows of iati_identifier, publisher, title, status, start_date, end_date,
        countries, match_basis, confidence (high/medium/low), humanitarian.
    Example: activities(country="Yemen", publisher="Oxfam GB", year_from=2020)
    """
    raw = {"country": country, "publisher": publisher, "year_from": year_from, "year_to": year_to,
           "match_type": match_type, "limit": limit}
    code, err = _country(country)
    if err:
        return _error(err[0], raw, err[1])
    slug, _, err = _publisher(publisher)
    if err:
        return _error(err[0], raw, err[1])
    if match_type not in (None, *MATCH_TYPES):
        return _error(f"match_type must be one of {list(MATCH_TYPES)} or None", raw)
    year_from, err = _year(year_from, "year_from")
    if err:
        return _error(err, raw)
    year_to, err = _year(year_to, "year_to")
    if err:
        return _error(err, raw)
    params = {"country": code, "publisher": slug, "year_from": year_from, "year_to": year_to,
              "match_type": match_type, "limit": _limit(limit)}
    note = _coverage([slug] if slug else None, sectors=True)
    return _run(ACTIVITIES_CYPHER, params, note, "No activities match these filters.")


SHARED_PARTNERS_CYPHER = """
CALL () {
  MATCH (o:Organisation)-[p:PARTICIPATES_IN]->(a:Activity)
  RETURN o, a, 'participation' AS via, p.role_name AS role
  UNION ALL
  MATCH (o:Organisation)-[:PROVIDES]->(:Transaction)<-[:HAS_TRANSACTION]-(a:Activity)
  RETURN o, a, 'funder' AS via, null AS role
  UNION ALL
  MATCH (o:Organisation)<-[:RECEIVED_BY]-(:Transaction)<-[:HAS_TRANSACTION]-(a:Activity)
  RETURN o, a, 'recipient' AS via, null AS role
}
WITH coalesce($canon[o.ref], o.ref) AS org, o, a, via, role
WHERE a.publisher IN $publishers
  AND NOT org IN $exclude AND NOT o.ref IN $exclude
  AND ($country IS NULL OR EXISTS { MATCH (a)-[:TARGETS]->(:Country {code: $country}) })
WITH org, collect(DISTINCT a.publisher) AS publishers, collect(DISTINCT via) AS via,
     collect(DISTINCT role) AS roles, collect(DISTINCT a.iati_identifier) AS acts,
     collect(DISTINCT {ref: o.ref, name: o.name}) AS orgs
WHERE size(publishers) = size($publishers)
RETURN org AS organisation_id,
       coalesce($names[org], head([x IN orgs WHERE x.ref = org | x.name]), head([x IN orgs | x.name]), org) AS organisation,
       [x IN orgs | x.ref] AS all_refs,
       publishers, via, [r IN roles WHERE r IS NOT NULL] AS roles,
       size(acts) AS n_activities, acts[0..$max_ids] AS activity_ids
ORDER BY n_activities DESC, organisation
LIMIT $limit
"""


def shared_partners(publishers, country=None, limit=50):
    """Organisations that work with EVERY one of the given publishers.

    "Work with" means any of: listed as a participating org on an activity,
    provider of a transaction (funder), or receiver of a transaction
    (recipient). The publishers themselves, their duplicate refs and
    placeholder refs ("Multilateral", "Oxfam Partner(s)") are excluded.
    Organisations published under several refs are merged with the SAME_AS
    table; a government and its agencies (US vs USAID) stay separate.

    Args:
        publishers: list of 2+ publisher names ["Oxfam GB", "WFP"].
        country: optional hotspot country to restrict activities to.
        limit: max rows (<= 500).
    Returns: rows of organisation_id, organisation, all_refs, publishers, via
        (participation/funder/recipient), roles, n_activities, activity_ids.
    Example: shared_partners(["Oxfam GB", "WFP"], country="South Sudan")
    """
    raw = {"publishers": publishers, "country": country, "limit": limit}
    if isinstance(publishers, str):
        publishers = [publishers]
    if not publishers or len(publishers) < 2:
        return _error("give at least two publishers, e.g. ['Oxfam GB', 'WFP']", raw)
    slugs = []
    for p in publishers:
        slug, _, err = _publisher(p)
        if err:
            return _error(err[0], raw, err[1])
        slugs.append(slug)
    slugs = sorted(set(slugs))
    code, err = _country(country)
    if err:
        return _error(err[0], raw, err[1])
    params = {"publishers": slugs, "country": code, "exclude": _self_refs(slugs), "canon": CANON,
              "names": _canon_names(), "limit": _limit(limit), "max_ids": MAX_IDS_PER_ROW}
    note = _note([_coverage(slugs),
                  "Agencies are not rolled up into their government (USAID and United States, FCDO and "
                  "United Kingdom are separate rows). Oxfam GB names most funders without an IATI ref, so "
                  "matches depend on the curated SAME_AS table in entities.py."])
    return _run(SHARED_PARTNERS_CYPHER, params, note,
                f"No organisation is linked to all of {slugs} here.")


TOP_FUNDERS_CYPHER = """
MATCH (a:Activity)-[tr:TARGETS]->(:Country {code: $country}),
      (a)-[:HAS_TRANSACTION]->(t:Transaction)<-[pv:PROVIDES]-(o:Organisation),
      (rep:Organisation)-[:REPORTS]->(a)
WHERE t.type_name IN $types
  AND ($year_from IS NULL OR t.date.year >= $year_from)
  AND ($year_to IS NULL OR t.date.year <= $year_to)
  AND ($publisher IS NULL OR a.publisher = $publisher)
WITH coalesce($canon[o.ref], o.ref) AS org, coalesce($canon[rep.ref], rep.ref) AS reporter, o, a, t,
     coalesce(tr.source_ids, []) + coalesce(pv.source_ids, []) AS ev_links
WHERE NOT $exclude_self OR org <> reporter
WITH org, t.currency AS currency,
     collect(DISTINCT {ref: o.ref, name: o.name}) AS orgs,""" + MONEY_AGG + """,
     collect(DISTINCT a.publisher) AS publishers,
     min(t.date) AS first_date, max(t.date) AS last_date
ORDER BY amount DESC
WITH currency, collect({
       funder_id: org,
       funder: coalesce($names[org], head([x IN orgs WHERE x.ref = org | x.name]), head([x IN orgs | x.name]), org),
       all_refs: [x IN orgs | x.ref], currency: currency,
       amount: amount, adjustments: adjustments, net: net,
       n_transactions: n_transactions, n_adjustments: n_adjustments,
       ev_amount: ev_amount, ev_adjustments: ev_adjustments, ev_net: ev_net,
       first_date: toString(first_date), last_date: toString(last_date),
       publishers: publishers, n_activities: size(acts), activity_ids: acts[0..$max_ids]}) AS rows
ORDER BY currency
UNWIND rows[0..$limit] AS r
RETURN r.funder_id AS funder_id, r.funder AS funder, r.all_refs AS all_refs, r.currency AS currency,
       r.amount AS amount, r.adjustments AS adjustments, r.net AS net,
       r.n_transactions AS n_transactions, r.n_adjustments AS n_adjustments, r.first_date AS first_date,
       r.last_date AS last_date, r.publishers AS publishers, r.n_activities AS n_activities,
       r.activity_ids AS activity_ids, r.ev_amount AS ev_amount, r.ev_adjustments AS ev_adjustments,
       r.ev_net AS ev_net
LIMIT $max_rows
"""


def top_funders(country, transaction_types=("Incoming Funds",), year_from=None, year_to=None,
                limit=10, publisher=None, exclude_self=True):
    """Organisations providing the most money into a hotspot country.

    Sums the `value` of transactions of the given type(s) on activities that
    target the country, grouped by provider organisation and currency.
    Currencies are never converted: a funder active in USD and GBP appears
    once per currency, and rows are ordered by currency then `amount`.
    `amount` sums positive transactions only; negative ones are kept as their
    own `adjustments` category (client decision 2026-10-23), and `net` is
    amount + adjustments.

    Args:
        country: hotspot country name or code (required).
        transaction_types: tuple of IATI transaction type names. Default
            ("Incoming Funds",) because in this graph external funders appear
            only as providers of Incoming Funds; "Disbursement" rows exist only
            for Oxfam GB with Oxfam GB itself as provider. Accepted names:
            Incoming Funds, Outgoing Commitment, Disbursement, Expenditure,
            Incoming Commitment, ... (codes "1".."13" also accepted).
        year_from, year_to: ints, applied to the transaction date.
        limit: max rows PER CURRENCY (<= 500).
        publisher: restrict to one publisher's activities.
        exclude_self: drop rows where the provider is the activity's own
            reporting organisation (a publisher paying itself). Other
            publishers still count: WFP funding an Oxfam GB activity is a
            funder. Default True.
    Returns: rows of funder_id, funder, all_refs, currency, amount, adjustments,
        net, n_transactions, n_adjustments, first_date, last_date,
        publishers, n_activities, activity_ids, evidence_amount,
        evidence_adjustments, evidence_net.
    Example: top_funders("Somalia", year_from=2022, limit=5)
    """
    raw = {"country": country, "transaction_types": transaction_types, "year_from": year_from,
           "year_to": year_to, "limit": limit, "publisher": publisher, "exclude_self": exclude_self}
    code, err = _country(country)
    if err or code is None:
        return _error(err[0] if err else "country is required", raw, err[1] if err else None)
    slug, _, err = _publisher(publisher)
    if err:
        return _error(err[0], raw, err[1])
    types, err = _types(transaction_types)
    if err:
        return _error(err, raw)
    year_from, err = _year(year_from, "year_from")
    if err:
        return _error(err, raw)
    year_to, err = _year(year_to, "year_to")
    if err:
        return _error(err, raw)
    lim = _limit(limit)
    params = {"country": code, "types": types, "year_from": year_from, "year_to": year_to,
              "publisher": slug, "canon": CANON, "names": _canon_names(), "exclude_self": bool(exclude_self),
              "limit": lim, "max_rows": min(MAX_LIMIT, lim * 4), "max_ids": MAX_IDS_PER_ROW}
    note = _note([_coverage([slug] if slug else None, year_from, money=True, types=types),
                  f"The limit ({lim}) applies per currency."])
    empty = f"No {', '.join(types)} transactions with a provider found for {code}"
    if exclude_self and any(t in ("Disbursement", "Expenditure", "Outgoing Commitment") for t in types):
        empty += (" other than ones where the provider is the publisher itself (hidden by exclude_self=True; "
                  "pass exclude_self=False to see them, or use the default 'Incoming Funds' for external funders)")
    out = _money(_run(TOP_FUNDERS_CYPHER, params, note, empty + "."),
                 _searched("rel_transaction_edges.csv", publisher=slug, country=code))
    for r in out["rows"]:
        if r["funder_id"] in E.PLACEHOLDERS:
            r["note"] = E.PLACEHOLDERS[r["funder_id"]]
    return out


FUNDING_OVER_TIME_CYPHER = """
MATCH (a:Activity)-[:HAS_TRANSACTION]->(t:Transaction)
WHERE t.type_name IN $types AND t.date IS NOT NULL
  AND ($publisher IS NULL OR a.publisher = $publisher)
  AND ($year_from IS NULL OR t.date.year >= $year_from)
  AND ($year_to IS NULL OR t.date.year <= $year_to)
OPTIONAL MATCH (a)-[tr:TARGETS]->(:Country {code: $country})
WITH a, t, tr WHERE $country IS NULL OR tr IS NOT NULL
WITH CASE $by WHEN 'quarter' THEN toString(t.date.year) + '-Q' + toString(t.date.quarter)
              WHEN 'month' THEN left(toString(t.date), 7)
              ELSE toString(t.date.year) END AS period,
     a, t, coalesce(tr.source_ids, []) AS ev_links
WITH period, a.publisher AS publisher, t.currency AS currency,""" + MONEY_AGG + """
RETURN period, publisher, currency, amount, adjustments, net, n_transactions, n_adjustments,
       size(acts) AS n_activities, acts[0..$max_ids] AS activity_ids, ev_amount, ev_adjustments, ev_net
ORDER BY period, publisher, currency
LIMIT $limit
"""


def funding_over_time(publisher=None, country=None, transaction_type="Incoming Funds", by="year",
                      year_from=None, year_to=None, limit=200):
    """Money per period, by publisher and currency: positive `amount`, negative
    `adjustments` as a separate category, and `net` = amount + adjustments.

    Args:
        publisher: one publisher, or None for all three (one row per publisher per period).
        country: optional hotspot country filter on the activities.
        transaction_type: one IATI transaction type name (default "Incoming Funds";
            use "Expenditure" for money spent, "Disbursement" only exists for Oxfam GB).
        by: "year" | "quarter" | "month".
        year_from, year_to: ints on the transaction date.
        limit: max rows (<= 500).
    Returns: rows of period, publisher, currency, amount, adjustments, net,
        n_transactions, n_adjustments, n_activities, activity_ids,
        evidence_amount, evidence_adjustments, evidence_net.
    Example: funding_over_time(publisher="WFP", country="Sudan", transaction_type="Expenditure")
    """
    raw = {"publisher": publisher, "country": country, "transaction_type": transaction_type, "by": by,
           "year_from": year_from, "year_to": year_to, "limit": limit}
    slug, _, err = _publisher(publisher)
    if err:
        return _error(err[0], raw, err[1])
    code, err = _country(country)
    if err:
        return _error(err[0], raw, err[1])
    types, err = _types(transaction_type)
    if err:
        return _error(err, raw)
    if by not in ("year", "quarter", "month"):
        return _error("by must be 'year', 'quarter' or 'month'", raw)
    year_from, err = _year(year_from, "year_from")
    if err:
        return _error(err, raw)
    year_to, err = _year(year_to, "year_to")
    if err:
        return _error(err, raw)
    params = {"publisher": slug, "country": code, "types": types, "by": by, "year_from": year_from,
              "year_to": year_to, "limit": _limit(limit), "max_ids": MAX_IDS_PER_ROW}
    note = _coverage([slug] if slug else None, year_from, money=True, types=types)
    return _money(_run(FUNDING_OVER_TIME_CYPHER, params, note, f"No {types[0]} transactions match."),
                  _searched(publisher=slug, country=code))


TRANSACTION_TOTALS_CYPHER = """
MATCH (a:Activity)-[:HAS_TRANSACTION]->(t:Transaction)
WHERE t.type_name IN $types
  AND ($currency IS NULL OR t.currency = $currency)
  AND ($publisher IS NULL OR a.publisher = $publisher)
  AND ($year_from IS NULL OR t.date.year >= $year_from)
  AND ($year_to IS NULL OR t.date.year <= $year_to)
OPTIONAL MATCH (a)-[tr:TARGETS]->(:Country {code: $country})
WITH a, t, tr WHERE $country IS NULL OR tr IS NOT NULL
WITH CASE WHEN $by_publisher THEN a.publisher END AS publisher, t.currency AS currency,
     a, t, coalesce(tr.source_ids, []) AS ev_links
WITH publisher, currency,""" + MONEY_AGG + """
RETURN publisher, currency, amount, adjustments, net, n_transactions, n_adjustments,
       size(acts) AS n_activities, acts[0..$max_ids] AS activity_ids, ev_amount, ev_adjustments, ev_net
ORDER BY publisher, currency
LIMIT $limit
"""


def transaction_totals(transaction_type="Incoming Funds", publisher=None, currency=None, country=None,
                       year_from=None, year_to=None, by_publisher=False):
    """Total money of ONE transaction type, one row per currency (never converted):
    positive `amount`, negative `adjustments` as a separate category, and `net`
    = amount + adjustments.

    Use for "how much did X receive/spend/disburse", "net incoming funds in USD
    in 2020", "positive / negative total", "by currency". Transactions without a
    date are included unless a year filter is given.

    Args:
        transaction_type: one IATI transaction type name or code (default "Incoming Funds").
            WFP mirrors commitments as expenditures, so never add those two types.
        publisher: one publisher, or None for all three.
        currency: e.g. "USD" or "GBP"; None = one row per currency.
        country: optional hotspot country filter on the activities.
        year_from, year_to: ints on the transaction date (inclusive calendar years).
        by_publisher: True = one row per publisher per currency.
    Returns: rows of publisher (only when by_publisher), currency, amount, adjustments, net,
        n_transactions, n_adjustments, n_activities, activity_ids, evidence_amount,
        evidence_adjustments, evidence_net.
    Example: transaction_totals("Expenditure", publisher="Oxfam America", currency="USD")
    """
    raw = {"transaction_type": transaction_type, "publisher": publisher, "currency": currency,
           "country": country, "year_from": year_from, "year_to": year_to, "by_publisher": by_publisher}
    types, err = _types(transaction_type)
    if err:
        return _error(err, raw)
    if len(types) != 1:
        return _error("give exactly one transaction type; amounts of different types must not be added", raw)
    slug, _, err = _publisher(publisher)
    if err:
        return _error(err[0], raw, err[1])
    code, err = _country(country)
    if err:
        return _error(err[0], raw, err[1])
    year_from, err = _year(year_from, "year_from")
    if err:
        return _error(err, raw)
    year_to, err = _year(year_to, "year_to")
    if err:
        return _error(err, raw)
    if currency is not None and not isinstance(currency, str):
        return _error(f"currency must be a code such as 'USD', got {currency!r}", raw)
    params = {"types": types, "publisher": slug, "currency": currency.strip().upper() if currency else None,
              "country": code, "year_from": year_from, "year_to": year_to, "by_publisher": bool(by_publisher),
              "limit": MAX_LIMIT, "max_ids": MAX_IDS_PER_ROW}
    note = _coverage([slug] if slug else None, year_from, money=True, types=types)
    return _money(_run(TRANSACTION_TOTALS_CYPHER, params, note, f"No {types[0]} transactions match."),
                  _searched(publisher=slug, country=code))


TOOLS = {f.__name__: f for f in (activities, shared_partners, top_funders, funding_over_time, transaction_totals)}
