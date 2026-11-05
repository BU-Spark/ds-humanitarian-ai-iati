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
        "description": "Organisations providing the largest net sum of transactions of one type to one publisher's activities, "
                       "grouped by provider ref and currency. Default type '1' (incoming funds).",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": True},
                   "type_code": {"type": "enum", "values": list(TX_TYPES), "required": False, "default": "1"},
                   "currency": {"type": "enum", "values": ["USD", "GBP"], "required": False},
                   "limit": {"type": "int", "required": False, "default": 10, "min": 1, "max": 50}},
        "cypher": """
MATCH (a:Activity {publisher: $publisher})-[:HAS_TRANSACTION]->(t:Transaction {type: $type_code})<-[pb:PROVIDES]-(o:Organisation)
WHERE $currency IS NULL OR t.currency = $currency
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
        "description": "Net sum of transaction values for one publisher, one transaction type code and one currency, optionally "
                       "restricted to dates in [date_from, date_to). Returns key 'total'; negative adjustments are included.",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": True},
                   "type_code": {"type": "enum", "values": list(TX_TYPES), "required": True},
                   "currency": {"type": "enum", "values": ["USD", "GBP"], "required": True},
                   "date_from": {"type": "date", "required": False}, "date_to": {"type": "date", "required": False}},
        "cypher": """
OPTIONAL MATCH (a:Activity {publisher: $publisher})-[:HAS_TRANSACTION]->(t:Transaction {type: $type_code, currency: $currency})
WHERE ($date_from IS NULL OR t.date >= date($date_from)) AND ($date_to IS NULL OR t.date < date($date_to))
RETURN 'total' AS key, coalesce(sum(t.value), 0) AS value,
       [x IN collect(DISTINCT t.source_id) WHERE x IS NOT NULL] + [x IN collect(DISTINCT a.source_id) WHERE x IS NOT NULL] AS evidence""",
        "coverage": "One type and one currency only; never mixes commitments, disbursements or currencies.",
    },
    "funding_over_time": {
        "description": "Net sum of transaction values per calendar year for one publisher, type code and currency.",
        "params": {"publisher": {"type": "enum", "values": list(PUBLISHERS), "required": True},
                   "type_code": {"type": "enum", "values": list(TX_TYPES), "required": True},
                   "currency": {"type": "enum", "values": ["USD", "GBP"], "required": True}},
        "cypher": """
MATCH (a:Activity {publisher: $publisher})-[:HAS_TRANSACTION]->(t:Transaction {type: $type_code, currency: $currency})
WHERE t.date IS NOT NULL
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

for _t in TOOLS.values():  # expand relationship-evidence placeholders
    _t["cypher"] = re.sub(r"__FLAT_(\w+)__", lambda m: _FLAT.format(rel=m.group(1)), _t["cypher"])

MANIFEST_SCOPE = {  # tables to cite when a scalar template finds no rows (benchmark convention)
    "count_activities_by_sector": ["rel_classified_as.csv", "nodes_activities.csv"],
    "budget_total": ["nodes_budgets.csv"],
    "transaction_total": ["nodes_transactions.csv", "nodes_activities.csv"],
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
