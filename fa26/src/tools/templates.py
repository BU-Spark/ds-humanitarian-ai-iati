"""Parameterised Cypher templates for the team graph schema (fa26/retrieval/schema_prototype.py, loaded by
fa26/retrieval/load_neo4j.py): typed dates (Activity.start_date, Transaction.date), float values, boolean
is_hotspot, (Organisation)-[:PROVIDES]->(Transaction), node `source_id` and relationship `source_ids` lists.

Every template returns rows with exactly three columns:
  key       group label (publisher slug, org ref, role code, sdg key, ...) or 'count' / 'total'
  value     integer, number or 'YYYY-MM-DD' string
  evidence  list of source_id strings for every node and relationship row that contributed
Evidence follows the benchmark convention: relationship rows plus the activity rows they
join through; scalar totals with no matches return value 0 and an empty evidence list.

Templates never contain user text: all filters are Cypher parameters, so the guard in
text2cypher_eval.guard_query passes and no value can inject Cypher.
"""
from __future__ import annotations
import re

PUBLISHERS = {"oxfamgb": "GB-CHC-202918", "oxfamus": "US-EIN-23-7069110", "wfp": "XM-DAC-41140"}
TX_TYPES = {"1": "incoming funds", "2": "outgoing commitment", "3": "disbursement", "4": "expenditure"}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# relationship evidence: each edge carries a list of CSV row ids; flatten the collected lists
_FLAT = "reduce(acc = [], l IN collect(DISTINCT {rel}.source_ids) | acc + coalesce(l, []))"  # __FLAT_<rel>__ in templates
# money measure (client decision 2026-10-23): amount = positive rows, adjustments = negative rows, net = both
_IN_MEASURE = "($measure = 'net' OR ($measure = 'amount' AND t.value > 0) OR ($measure = 'adjustments' AND t.value < 0))"
_MEASURE_PARAM = {"type": "enum", "values": ["net", "amount", "adjustments"], "required": False, "default": "net"}

TOOLS: dict[str, dict] = {
    # ---------------------------------------------------------------- activities
    "activities_per_publisher": {
        "description": "Number of distinct activities per publisher, optionally restricted to activities whose start date "
                       "(start_actual, else start_planned; stored as Activity.start_date) falls in [start_from, start_to). Omits publishers with zero matches.",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": False},
                   "start_from": {"type": "date", "required": False}, "start_to": {"type": "date", "required": False}},
        "cypher": f"""
MATCH (a:Activity)
WHERE ($publisher IS NULL OR a.publisher = $publisher)
  AND ($start_from IS NULL OR a.start_date >= date($start_from))
  AND ($start_to IS NULL OR a.start_date < date($start_to))
RETURN a.publisher AS key, count(DISTINCT a.iati_identifier) AS value, collect(DISTINCT a.source_id) AS evidence
ORDER BY key""",
        "coverage": "Counts retained activities in the snapshot only; the hunger filter decides what is retained.",
    },
    "activities_per_publisher_by_country": {
        "description": "Number of distinct activities per publisher that target one recipient country (ISO-2 code). "
                       "Only publishers with at least one match are returned.",
        "params": {"country_code": {"type": "str", "required": True, "pattern": r"^[A-Z]{2}$"}},
        "cypher": """
MATCH (a:Activity)-[r:TARGETS]->(c:Country {code: $country_code})
RETURN a.publisher AS key, count(DISTINCT a.iati_identifier) AS value,
       __FLAT_r__ + collect(DISTINCT a.source_id) AS evidence
ORDER BY key""",
        "coverage": "An activity targeting several countries is counted once per country; percentages are ignored.",
    },
    "hotspot_countries_per_publisher": {
        "description": "Number of distinct hunger-hotspot countries each publisher targets (TARGETS with is_hotspot = true).",
        "params": {},
        "cypher": """
MATCH (a:Activity)-[r:TARGETS {is_hotspot: true}]->(c:Country)
RETURN a.publisher AS key, count(DISTINCT c.code) AS value,
       __FLAT_r__ + collect(DISTINCT a.source_id) AS evidence
ORDER BY key""",
        "coverage": "Hotspot list is the FAO-WFP June-November 2026 outlook as encoded in the snapshot.",
    },
    "activities_by_match_basis": {
        "description": "Number of distinct activities grouped by how the hunger filter admitted them (match_basis: 'sector' or 'keyword').",
        "params": {},
        "cypher": """
MATCH (a:Activity)
RETURN a.match_basis AS key, count(DISTINCT a.iati_identifier) AS value, collect(DISTINCT a.source_id) AS evidence
ORDER BY key""",
        "coverage": "Reflects the summer prototype's filter; a revised filter changes these counts.",
    },
    "count_activities_by_sector": {
        "description": "Scalar count of distinct activities of one publisher classified with one activity-level sector key "
                       "(e.g. '1:72040'); returns key 'count'. Uses CLASSIFIED_AS only, not transaction sectors or text.",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": True},
                   "sector_key": {"type": "str", "required": True, "pattern": r"^\d+:[A-Za-z0-9.\-]+$"}},
        "cypher": """
OPTIONAL MATCH (a:Activity {publisher: $publisher})-[r:CLASSIFIED_AS]->(s:Sector {sector_key: $sector_key})
RETURN 'count' AS key, count(DISTINCT a.iati_identifier) AS value,
       __FLAT_r__ + [x IN collect(DISTINCT a.source_id) WHERE x IS NOT NULL] AS evidence""",
        "coverage": "Sector vocabularies differ by publisher (WFP uses DAC vocabulary 1, Oxfam GB vocabulary 99).",
    },
    "latest_update_per_publisher": {
        "description": "Latest publisher-reported last_updated calendar date (YYYY-MM-DD) per publisher.",
        "params": {},
        "cypher": """
MATCH (a:Activity) WHERE a.last_updated IS NOT NULL
WITH a.publisher AS key, max(a.last_updated) AS latest, collect(DISTINCT a.source_id) AS evidence
RETURN key, toString(date(latest)) AS value, evidence
ORDER BY key""",
        "coverage": "This is the publisher's own update stamp, not the snapshot download date.",
    },
    "activities_with_location_per_publisher": {
        "description": "Number of distinct activities per publisher that have at least one Location node.",
        "params": {},
        "cypher": """
MATCH (a:Activity)-[r:LOCATED_AT]->(:Location)
RETURN a.publisher AS key, count(DISTINCT a.iati_identifier) AS value,
       __FLAT_r__ + collect(DISTINCT a.source_id) AS evidence
ORDER BY key""",
        "coverage": "A location is not necessarily a beneficiary location.",
    },
    "activities_per_sdg": {
        "description": "Number of distinct activities linked to each SDG key (e.g. '2:2').",
        "params": {},
        "cypher": """
MATCH (a:Activity)-[r:CONTRIBUTES_TO]->(s:SDG)
RETURN s.sdg_key AS key, count(DISTINCT a.iati_identifier) AS value, __FLAT_r__ AS evidence
ORDER BY key""",
        "coverage": "An SDG tag is a publisher claim, not evidence of achieved results.",
    },
    # ------------------------------------------------------------ organisations
    "participants_by_role": {
        "description": "Number of distinct organisation refs occurring in each participation role code ('1' funding, '2' accountable, "
                       "'3' extending, '4' implementing). Repeated rows do not increase counts.",
        "params": {},
        "cypher": """
MATCH (o:Organisation)-[p:PARTICIPATES_IN]->(:Activity)
RETURN p.role AS key, count(DISTINCT o.ref) AS value, __FLAT_p__ AS evidence
ORDER BY key""",
        "coverage": "Role codes follow the IATI OrganisationRole codelist.",
    },
    "multi_publisher_participants": {
        "description": "Organisation refs that participate in activities of at least min_publishers distinct publishers, "
                       "with the number of distinct activities each participates in.",
        "params": {"min_publishers": {"type": "int", "required": False, "default": 2, "min": 2}},
        "cypher": """
MATCH (o:Organisation)-[p:PARTICIPATES_IN]->(a:Activity)
WITH o, collect(DISTINCT a.publisher) AS pubs, collect(DISTINCT a.iati_identifier) AS acts,
     __FLAT_p__ + collect(DISTINCT a.source_id) AS ev
WHERE size(pubs) >= $min_publishers
RETURN o.ref AS key, size(acts) AS value, ev AS evidence
ORDER BY key""",
        "coverage": "Identity is by organisation ref; the same organisation under different refs is not merged (see resolver).",
    },
    "top_funders": {
        "description": "Organisations providing the largest sum of transactions of one type to one publisher's activities, "
                       "grouped by provider ref and currency. Default type '1' (incoming funds). measure: net (default), "
                       "amount (positive rows only) or adjustments (negative rows only).",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": True},
                   "type_code": {"type": "enum", "values": list(TX_TYPES), "required": False, "default": "1"},
                   "currency": {"type": "enum", "values": ["USD", "GBP"], "required": False},
                   "measure": _MEASURE_PARAM,
                   "limit": {"type": "int", "required": False, "default": 10, "min": 1, "max": 50}},
        "cypher": """
MATCH (a:Activity {publisher: $publisher})-[:HAS_TRANSACTION]->(t:Transaction {type: $type_code})<-[pb:PROVIDES]-(o:Organisation)
WHERE ($currency IS NULL OR t.currency = $currency) AND __IN_MEASURE__
WITH o, t.currency AS currency, sum(t.value) AS total,
     collect(DISTINCT t.source_id) + __FLAT_pb__ + collect(DISTINCT a.source_id) AS ev
RETURN o.ref + ' [' + currency + ']' AS key, total AS value, ev AS evidence
ORDER BY total DESC LIMIT $limit""",
        "coverage": "Sums signed values per currency with no conversion; a provider published under several refs appears several times.",
    },
    "shared_partners": {
        "description": "Organisation refs that participate in activities of both publisher_a and publisher_b, with the number "
                       "of distinct activities across the two.",
        "params": {"publisher_a": {"type": "enum", "values": list(PUBLISHERS), "required": True},
                   "publisher_b": {"type": "enum", "values": list(PUBLISHERS), "required": True}},
        "cypher": """
MATCH (o:Organisation)-[p:PARTICIPATES_IN]->(a:Activity)
WHERE a.publisher IN [$publisher_a, $publisher_b]
WITH o, collect(DISTINCT a.publisher) AS pubs, collect(DISTINCT a.iati_identifier) AS acts,
     __FLAT_p__ + collect(DISTINCT a.source_id) AS ev
WHERE $publisher_a IN pubs AND $publisher_b IN pubs
RETURN o.ref AS key, size(acts) AS value, ev AS evidence
ORDER BY value DESC, key""",
        "coverage": "Participation role is ignored; use participants_by_role for role breakdowns.",
    },
    # ------------------------------------------------------------------ money
    "transaction_total": {
        "description": "Sum of transaction values for one publisher, one transaction type code and one currency, optionally "
                       "restricted to dates in [date_from, date_to). Returns key 'total'. measure: net (default, signed sum), "
                       "amount (positive transactions only) or adjustments (negative transactions only, a negative number).",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": True},
                   "type_code": {"type": "enum", "values": list(TX_TYPES), "required": True},
                   "currency": {"type": "enum", "values": ["USD", "GBP"], "required": True},
                   "measure": _MEASURE_PARAM,
                   "date_from": {"type": "date", "required": False}, "date_to": {"type": "date", "required": False}},
        "cypher": """
OPTIONAL MATCH (a:Activity {publisher: $publisher})-[:HAS_TRANSACTION]->(t:Transaction {type: $type_code, currency: $currency})
WHERE ($date_from IS NULL OR t.date >= date($date_from)) AND ($date_to IS NULL OR t.date < date($date_to)) AND __IN_MEASURE__
RETURN 'total' AS key, coalesce(sum(t.value), 0) AS value,
       [x IN collect(DISTINCT t.source_id) WHERE x IS NOT NULL] + [x IN collect(DISTINCT a.source_id) WHERE x IS NOT NULL] AS evidence""",
        "coverage": "One type and one currency only; never mixes commitments, disbursements or currencies.",
    },
    "funding_over_time": {
        "description": "Sum of transaction values per calendar year for one publisher, type code and currency. "
                       "measure: net (default), amount (positive rows) or adjustments (negative rows).",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": True},
                   "type_code": {"type": "enum", "values": list(TX_TYPES), "required": True},
                   "currency": {"type": "enum", "values": ["USD", "GBP"], "required": True},
                   "measure": _MEASURE_PARAM},
        "cypher": """
MATCH (a:Activity {publisher: $publisher})-[:HAS_TRANSACTION]->(t:Transaction {type: $type_code, currency: $currency})
WHERE t.date IS NOT NULL AND __IN_MEASURE__
RETURN toString(t.date.year) AS key, sum(t.value) AS value,
       collect(DISTINCT t.source_id) + collect(DISTINCT a.source_id) AS evidence
ORDER BY key""",
        "coverage": "Years are taken from transaction-date, not value-date.",
    },
    "negative_transactions_per_publisher": {
        "description": "Number of transaction rows with a negative value per publisher (adjustments and reversals, not errors).",
        "params": {},
        "cypher": """
MATCH (a:Activity)-[:HAS_TRANSACTION]->(t:Transaction)
WHERE t.value < 0
RETURN a.publisher AS key, count(t) AS value, collect(DISTINCT t.source_id) + collect(DISTINCT a.source_id) AS evidence
ORDER BY key""",
        "coverage": "Only 3% of negatives are exact reversals; most are partial adjustments.",
    },

    # -------------------------------------------------------------- composable counts (benchmark v2)
    "count_activities": {
        "description": "Scalar count of DISTINCT activities matching every given filter (all optional; omit = no filter). "
                       "Filters: publisher; country_code (ISO-2 targeted); status code ('2' implementation, '3' finalisation = completed); "
                       "humanitarian ('1'/'0'); default_currency; has_actual_start / has_actual_end / has_planned_start / "
                       "has_planned_end; has_location; has_sdg; has_sector; has_budget; has_transaction; has_negative_transaction; "
                       "transaction_type (activity has a transaction of this type code); participant_role and participant_role_2 "
                       "(activity has an organisation in this role: '1' funding, '2' accountable, '3' extending, '4' implementing); "
                       "actual_start_before / actual_end_before (YYYY-MM-DD, exclusive); start_from / start_to on start_date. "
                       "Returns key 'count'. Use for 'how many activities ...' questions combining conditions.",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": False},
                   "country_code": {"type": "str", "required": False, "pattern": r"^[A-Z]{2}$"},
                   "status": {"type": "enum", "values": ["1", "2", "3", "4", "5", "6"], "required": False},
                   "humanitarian": {"type": "enum", "values": ["1", "0"], "required": False},
                   "default_currency": {"type": "str", "required": False, "pattern": r"^[A-Z]{3}$"},
                   "has_actual_start": {"type": "bool", "required": False}, "has_actual_end": {"type": "bool", "required": False},
                   "has_planned_start": {"type": "bool", "required": False}, "has_planned_end": {"type": "bool", "required": False},
                   "has_location": {"type": "bool", "required": False}, "has_sdg": {"type": "bool", "required": False},
                   "has_sector": {"type": "bool", "required": False}, "has_budget": {"type": "bool", "required": False},
                   "has_transaction": {"type": "bool", "required": False},
                   "has_negative_transaction": {"type": "bool", "required": False},
                   "transaction_type": {"type": "enum", "values": list(TX_TYPES), "required": False},
                   "participant_role": {"type": "enum", "values": ["1", "2", "3", "4"], "required": False},
                   "participant_role_2": {"type": "enum", "values": ["1", "2", "3", "4"], "required": False},
                   "actual_start_before": {"type": "date", "required": False}, "actual_end_before": {"type": "date", "required": False},
                   "start_from": {"type": "date", "required": False}, "start_to": {"type": "date", "required": False}},
        "cypher": """
MATCH (a:Activity)
WHERE ($publisher IS NULL OR a.publisher = $publisher)
  AND ($status IS NULL OR a.status = $status)
  AND ($humanitarian IS NULL OR a.humanitarian = $humanitarian)
  AND ($default_currency IS NULL OR a.default_currency = $default_currency)
  AND ($has_actual_start IS NULL OR (a.start_actual IS NOT NULL) = $has_actual_start)
  AND ($has_actual_end IS NULL OR (a.end_actual IS NOT NULL) = $has_actual_end)
  AND ($has_planned_start IS NULL OR (a.start_planned IS NOT NULL) = $has_planned_start)
  AND ($has_planned_end IS NULL OR (a.end_planned IS NOT NULL) = $has_planned_end)
  AND ($actual_start_before IS NULL OR a.start_actual < date($actual_start_before))
  AND ($actual_end_before IS NULL OR a.end_actual < date($actual_end_before))
  AND ($start_from IS NULL OR a.start_date >= date($start_from))
  AND ($start_to IS NULL OR a.start_date < date($start_to))
  AND ($country_code IS NULL OR EXISTS { (a)-[:TARGETS]->(:Country {code: $country_code}) })
  AND ($has_location IS NULL OR EXISTS { (a)-[:LOCATED_AT]->(:Location) } = $has_location)
  AND ($has_sdg IS NULL OR EXISTS { (a)-[:CONTRIBUTES_TO]->(:SDG) } = $has_sdg)
  AND ($has_sector IS NULL OR EXISTS { (a)-[:CLASSIFIED_AS]->(:Sector) } = $has_sector)
  AND ($has_budget IS NULL OR EXISTS { (a)-[:HAS_BUDGET]->(:Budget) } = $has_budget)
  AND ($has_transaction IS NULL OR EXISTS { (a)-[:HAS_TRANSACTION]->(:Transaction) } = $has_transaction)
  AND ($has_negative_transaction IS NULL OR EXISTS { (a)-[:HAS_TRANSACTION]->(t:Transaction) WHERE t.value < 0 } = $has_negative_transaction)
  AND ($transaction_type IS NULL OR EXISTS { (a)-[:HAS_TRANSACTION]->(:Transaction {type: $transaction_type}) })
  AND ($participant_role IS NULL OR EXISTS { (:Organisation)-[:PARTICIPATES_IN {role: $participant_role}]->(a) })
  AND ($participant_role_2 IS NULL OR EXISTS { (:Organisation)-[:PARTICIPATES_IN {role: $participant_role_2}]->(a) })
OPTIONAL MATCH (a)-[r1:TARGETS]->(c1:Country) WHERE $country_code IS NOT NULL AND c1.code = $country_code
OPTIONAL MATCH (a)-[r2:LOCATED_AT]->(:Location) WHERE $has_location = true
OPTIONAL MATCH (a)-[r3:CONTRIBUTES_TO]->(:SDG) WHERE $has_sdg = true
OPTIONAL MATCH (a)-[r4:CLASSIFIED_AS]->(:Sector) WHERE $has_sector = true
OPTIONAL MATCH (a)-[r5:HAS_BUDGET]->(:Budget) WHERE $has_budget = true
OPTIONAL MATCH (a)-[r6:HAS_TRANSACTION]->(t6:Transaction)
  WHERE $has_transaction = true OR ($has_negative_transaction = true AND t6.value < 0) OR ($transaction_type IS NOT NULL AND t6.type = $transaction_type)
OPTIONAL MATCH (:Organisation)-[r7:PARTICIPATES_IN]->(a) WHERE r7.role = $participant_role OR r7.role = $participant_role_2
WITH a, __FLAT_r1__ + __FLAT_r2__ + __FLAT_r3__ + __FLAT_r4__ + __FLAT_r5__ + __FLAT_r6__ + __FLAT_r7__
     + [x IN collect(DISTINCT t6.source_id) WHERE x IS NOT NULL] AS ev
WITH count(DISTINCT a) AS n, collect(DISTINCT a.source_id) AS act_ev, reduce(acc = [], l IN collect(ev) | acc + l) AS rel_ev
RETURN 'count' AS key, n AS value, act_ev + rel_ev AS evidence""",
        "coverage": "Counts distinct retained activities; every filter is AND-ed. Role filters use participation rows, not transaction providers.",
    },
    "count_transactions": {
        "description": "Scalar count of transaction rows (key 'count'), optionally filtered by publisher, type_code, currency, "
                       "sign ('positive' value > 0, 'negative' value < 0, 'zero' value = 0), country_code of the activity, "
                       "and dates in [date_from, date_to).",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": False},
                   "type_code": {"type": "enum", "values": list(TX_TYPES), "required": False},
                   "currency": {"type": "str", "required": False, "pattern": r"^[A-Z]{3}$"},
                   "sign": {"type": "enum", "values": ["positive", "negative", "zero"], "required": False},
                   "country_code": {"type": "str", "required": False, "pattern": r"^[A-Z]{2}$"},
                   "date_from": {"type": "date", "required": False}, "date_to": {"type": "date", "required": False}},
        "cypher": """
MATCH (a:Activity)-[:HAS_TRANSACTION]->(t:Transaction)
WHERE ($publisher IS NULL OR a.publisher = $publisher)
  AND ($type_code IS NULL OR t.type = $type_code)
  AND ($currency IS NULL OR t.currency = $currency)
  AND ($sign IS NULL OR ($sign = 'positive' AND t.value > 0) OR ($sign = 'negative' AND t.value < 0) OR ($sign = 'zero' AND t.value = 0))
  AND ($date_from IS NULL OR t.date >= date($date_from)) AND ($date_to IS NULL OR t.date < date($date_to))
  AND ($country_code IS NULL OR EXISTS { (a)-[:TARGETS]->(:Country {code: $country_code}) })
WITH count(t) AS n, collect(DISTINCT t.source_id) AS tev, collect(DISTINCT a.source_id) AS aev
RETURN 'count' AS key, n AS value, tev + aev AS evidence""",
        "coverage": "Counts rows, not distinct amounts; zero-value rows count only with sign = 'zero' or no sign filter.",
    },
    "count_organisations": {
        "description": "Scalar count of DISTINCT organisation refs (key 'count'), optionally only those participating in a role "
                       "('1' funding ... '4' implementing) and/or in one publisher's activities. No filters = every Organisation node.",
        "params": {"participant_role": {"type": "enum", "values": ["1", "2", "3", "4"], "required": False},
                   "publisher": {"type": "enum", "values": list(PUBLISHERS), "required": False}},
        "cypher": """
MATCH (o:Organisation)
WHERE ($participant_role IS NULL AND $publisher IS NULL)
   OR EXISTS { (o)-[p:PARTICIPATES_IN]->(a:Activity) WHERE ($participant_role IS NULL OR p.role = $participant_role) AND ($publisher IS NULL OR a.publisher = $publisher) }
OPTIONAL MATCH (o)-[p:PARTICIPATES_IN]->(a:Activity)
  WHERE ($participant_role IS NOT NULL OR $publisher IS NOT NULL) AND ($participant_role IS NULL OR p.role = $participant_role) AND ($publisher IS NULL OR a.publisher = $publisher)
WITH o, __FLAT_p__ + [x IN collect(DISTINCT a.source_id) WHERE x IS NOT NULL] AS ev
WITH count(DISTINCT o.ref) AS n, collect(DISTINCT o.source_id) AS oev, reduce(acc = [], l IN collect(ev) | acc + l) AS rev
RETURN 'count' AS key, n AS value, oev + rev AS evidence""",
        "coverage": "Identity is by ref; the same organisation under several refs counts several times (see resolver).",
    },
    "count_locations": {
        "description": "Scalar count of DISTINCT named Location nodes (key 'count'), optionally for one publisher or one targeted country.",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": False},
                   "country_code": {"type": "str", "required": False, "pattern": r"^[A-Z]{2}$"}},
        "cypher": """
MATCH (a:Activity)-[r:LOCATED_AT]->(l:Location)
WHERE ($publisher IS NULL OR a.publisher = $publisher)
  AND ($country_code IS NULL OR EXISTS { (a)-[:TARGETS]->(:Country {code: $country_code}) })
WITH count(DISTINCT l.location_id) AS n, collect(DISTINCT l.source_id) AS lev, __FLAT_r__ AS rev, collect(DISTINCT a.source_id) AS aev
RETURN 'count' AS key, n AS value, lev + rev + aev AS evidence""",
        "coverage": "A location row is a publisher-declared place, not necessarily a beneficiary location.",
    },
    "date_extreme": {
        "description": "Earliest or latest recorded activity date (key 'date', value YYYY-MM-DD). field: start_actual, end_actual, "
                       "start_planned, end_planned or last_updated; which: 'earliest' or 'latest'. Optional publisher filter. "
                       "Evidence cites every row considered.",
        "params": {"field": {"type": "enum", "values": ["start_actual", "end_actual", "start_planned", "end_planned", "last_updated"], "required": True},
                   "which": {"type": "enum", "values": ["earliest", "latest"], "required": True},
                   "publisher": {"type": "enum", "values": list(PUBLISHERS), "required": False}},
        "cypher": """
MATCH (a:Activity)
WHERE ($publisher IS NULL OR a.publisher = $publisher) AND a[$field] IS NOT NULL
WITH CASE WHEN $which = 'earliest' THEN min(a[$field]) ELSE max(a[$field]) END AS d, collect(DISTINCT a.source_id) AS ev
RETURN 'date' AS key, left(toString(d), 10) AS value, ev AS evidence""",
        "coverage": "Dates are the publisher's recorded values; planned and actual fields are distinct.",
    },
    "budget_total": {
        "description": "Sum of Budget rows with one type code, one status code and one currency; returns key 'total'. "
                       "Sums rows as published and does not select the latest revision.",
        "params": {"type_code": {"type": "enum", "values": ["1", "2"], "required": True},
                   "status_code": {"type": "enum", "values": ["1", "2"], "required": True},
                   "currency": {"type": "enum", "values": ["USD", "GBP"], "required": True}},
        "cypher": """
OPTIONAL MATCH (b:Budget {type: $type_code, status: $status_code, currency: $currency})
RETURN 'total' AS key, coalesce(sum(b.value), 0) AS value, [x IN collect(DISTINCT b.source_id) WHERE x IS NOT NULL] AS evidence""",
        "coverage": "Budget type '1' original / '2' revised; status '1' indicative / '2' committed.",
    },
}

for _t in TOOLS.values():  # expand relationship-evidence and measure placeholders
    _t["cypher"] = re.sub(r"__FLAT_(\w+)__", lambda m: _FLAT.format(rel=m.group(1)), _t["cypher"]).replace("__IN_MEASURE__", _IN_MEASURE)

MANIFEST_SCOPE = {  # tables to cite when a scalar template finds no rows (benchmark convention)
    "count_activities_by_sector": ["rel_classified_as.csv", "nodes_activities.csv"],
    "budget_total": ["nodes_budgets.csv"],
    "transaction_total": ["nodes_transactions.csv", "nodes_activities.csv"],
    "count_activities": ["nodes_activities.csv"],
    "count_transactions": ["nodes_transactions.csv", "nodes_activities.csv"],
    "count_organisations": ["nodes_organisations.csv"],
    "count_locations": ["nodes_locations.csv", "rel_located_at.csv"],
}


def tool_catalog() -> str:
    """Compact text catalogue for the LLM router."""
    lines = []
    for name, t in TOOLS.items():
        ps = ", ".join(f"{p}{'' if s.get('required') else '?'}: {s['type']}{'=' + '|'.join(s['values']) if s['type'] == 'enum' else ''}"
                       for p, s in t["params"].items()) or "no parameters"
        lines.append(f"- {name}({ps}): {t['description']}")
    return "\n".join(lines)


def validate_args(name: str, args: dict) -> dict:
    """Return a complete, typed argument dict or raise ValueError."""
    if name not in TOOLS:
        raise ValueError(f"unknown tool {name!r}")
    spec = TOOLS[name]["params"]
    args = dict(args or {})
    unknown = set(args) - set(spec)
    if unknown:
        raise ValueError(f"unknown parameters for {name}: {sorted(unknown)}")
    out = {}
    for p, s in spec.items():
        v = args.get(p, s.get("default"))
        if v in (None, ""):
            if s.get("required"):
                raise ValueError(f"{name}: parameter {p!r} is required")
            out[p] = None
            continue
        if s["type"] == "enum":
            v = str(v)
            if v not in s["values"]:
                raise ValueError(f"{name}: {p}={v!r} not in {s['values']}")
        elif s["type"] == "date":
            v = str(v)
            if not _DATE.match(v):
                raise ValueError(f"{name}: {p} must be YYYY-MM-DD, got {v!r}")
        elif s["type"] == "int":
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError(f"{name}: {p} must be an integer")
            if "min" in s and v < s["min"] or "max" in s and v > s["max"]:
                raise ValueError(f"{name}: {p}={v} out of range")
        elif s["type"] == "bool":
            if isinstance(v, str):
                if v.strip().lower() not in ("true", "false", "1", "0", "yes", "no"):
                    raise ValueError(f"{name}: {p} must be true or false, got {v!r}")
                v = v.strip().lower() in ("true", "1", "yes")
            v = bool(v)
        elif s["type"] == "str":
            v = str(v).strip()
            if "pattern" in s and not re.match(s["pattern"], v):
                raise ValueError(f"{name}: {p}={v!r} does not match {s['pattern']}")
        out[p] = v
    return out


def run_tool(run_cypher, name: str, args: dict) -> dict:
    """Execute one template. run_cypher(query, params) -> list[dict]. Returns rows, cypher, params, coverage."""
    params = validate_args(name, args)
    cypher = TOOLS[name]["cypher"].strip()
    rows = run_cypher(cypher, params)
    for r in rows:
        r["evidence"] = sorted({e for e in (r.get("evidence") or []) if e})
        if not r["evidence"] and name in MANIFEST_SCOPE and r.get("value") in (0, 0.0):
            r["evidence"] = sorted(f"manifest:{t}" for t in MANIFEST_SCOPE[name])
    return {"tool": name, "params": params, "cypher": cypher, "rows": rows, "coverage": TOOLS[name]["coverage"]}
