"""
schema_prototype.py -- ALL Cypher for loading the summer-prototype CSVs.

This is the only file that knows node labels, relationship types, property
names and which CSV feeds which statement. load_neo4j.py is generic: it reads
this module, casts columns, batches rows and runs the statements in order.
When George's schema v0.1 lands, replace (or add a sibling of) this module and
point the loader at it with --schema.

Graph model (follows the prototype README):
  (Organisation)-[:REPORTS]->(Activity)
  (Organisation)-[:PARTICIPATES_IN {role, role_name}]->(Activity)
  (Activity)-[:TARGETS {percentage, is_hotspot}]->(Country)
  (Activity)-[:LOCATED_AT]->(Location)
  (Activity)-[:CLASSIFIED_AS {percentage}]->(Sector)
  (Activity)-[:HAS_TRANSACTION]->(Transaction)
  (Organisation)-[:PROVIDES]->(Transaction)-[:RECEIVED_BY]->(Organisation)
  (Activity)-[:HAS_BUDGET]->(Budget)
  (Activity)-[:RESPONDS_TO]->(Emergency)
  (Activity)-[:CONTRIBUTES_TO]->(SDG)
  (Activity)-[:MARKED_WITH {significance}]->(PolicyMarker)
  (Activity)-[:TARGETS_REGION {percentage}]->(Region)
  (Activity)-[:RELATED_TO {type}]->(Activity)

CSV `rel_transaction_edges.csv` stores both funding directions as
org -> transaction rows with an `edge` column; the loader maps
edge=PROVIDED_BY to (Organisation)-[:PROVIDES]->(Transaction) and
edge=RECEIVED_BY to (Transaction)-[:RECEIVED_BY]->(Organisation).
HAS_TRANSACTION and HAS_BUDGET have no rel CSV; they come from the
`iati_identifier` column on the transaction and budget node CSVs.
"""

NAME = "prototype-v0"

# IATI codelists used to add human-readable names at load time. Phase 4
# tools filter on the *_name values, so an LLM can pass "Disbursement".
TRANSACTION_TYPES = {
    "1": "Incoming Funds", "2": "Outgoing Commitment", "3": "Disbursement",
    "4": "Expenditure", "5": "Interest Payment", "6": "Loan Repayment",
    "7": "Reimbursement", "8": "Purchase of Equity", "9": "Sale of Equity",
    "10": "Credit Guarantee", "11": "Incoming Commitment",
    "12": "Outgoing Pledge", "13": "Incoming Pledge",
}
ORG_ROLES = {"1": "Funding", "2": "Accountable", "3": "Extending", "4": "Implementing"}
ACTIVITY_STATUS = {"1": "Pipeline/identification", "2": "Implementation",
                   "3": "Finalisation", "4": "Closed", "5": "Cancelled", "6": "Suspended"}
BUDGET_TYPES = {"1": "Original", "2": "Revised"}
BUDGET_STATUS = {"1": "Indicative", "2": "Committed"}

# --------------------------------------------------------------- casting --
# column -> cast name, per CSV. Everything else stays a string. Empty strings
# become null (and are therefore not stored) for every column.
CASTS = {
    "nodes_activities.csv": {
        "start_planned": "date", "start_actual": "date",
        "end_planned": "date", "end_actual": "date",
        "last_updated": "datetime", "capital_spend": "float",
    },
    "nodes_transactions.csv": {"value": "float", "date": "date", "value_date": "date"},
    "nodes_budgets.csv": {"value": "float", "period_start": "date", "period_end": "date"},
    "nodes_locations.csv": {"lat": "float", "lon": "float"},
    "nodes_countries.csv": {"hotspot_tier": "int"},
    "nodes_sectors.csv": {"is_hunger": "bool"},
    "rel_targets_country.csv": {"percentage": "float", "is_hotspot": "bool"},
    "rel_targets_region.csv": {"percentage": "float"},
    "rel_classified_as.csv": {"percentage": "float"},
}


# Derived columns, computed per row after casting. Keep these tiny.
def _derive_activity(r):
    return {
        "start_date": r["start_actual"] or r["start_planned"],   # rule app.py uses
        "end_date": r["end_actual"] or r["end_planned"],
        "status_name": ACTIVITY_STATUS.get(r["status"] or ""),
        "hotspot_countries": (r["hotspot_countries"] or "").split("|") if r["hotspot_countries"] else [],
    }


def _derive_transaction(r):
    return {"type_name": TRANSACTION_TYPES.get(r["type"] or "")}


def _derive_budget(r):
    return {"type_name": BUDGET_TYPES.get(r["type"] or ""),
            "status_name": BUDGET_STATUS.get(r["status"] or "")}


def _derive_participates(r):
    return {"role_name": ORG_ROLES.get(r["role"] or "")}


DERIVE = {
    "nodes_activities.csv": _derive_activity,
    "nodes_transactions.csv": _derive_transaction,
    "nodes_budgets.csv": _derive_budget,
    "rel_participates.csv": _derive_participates,
}

# ---------------------------------------------------------------- schema --
CONSTRAINTS = [
    "CREATE CONSTRAINT activity_id IF NOT EXISTS FOR (n:Activity) REQUIRE n.iati_identifier IS UNIQUE",
    "CREATE CONSTRAINT organisation_ref IF NOT EXISTS FOR (n:Organisation) REQUIRE n.ref IS UNIQUE",
    "CREATE CONSTRAINT country_code IF NOT EXISTS FOR (n:Country) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT sector_key IF NOT EXISTS FOR (n:Sector) REQUIRE n.sector_key IS UNIQUE",
    "CREATE CONSTRAINT transaction_id IF NOT EXISTS FOR (n:Transaction) REQUIRE n.tx_id IS UNIQUE",
    "CREATE CONSTRAINT budget_id IF NOT EXISTS FOR (n:Budget) REQUIRE n.budget_id IS UNIQUE",
    "CREATE CONSTRAINT location_id IF NOT EXISTS FOR (n:Location) REQUIRE n.location_id IS UNIQUE",
    "CREATE CONSTRAINT sdg_key IF NOT EXISTS FOR (n:SDG) REQUIRE n.sdg_key IS UNIQUE",
    "CREATE CONSTRAINT emergency_key IF NOT EXISTS FOR (n:Emergency) REQUIRE n.emergency_key IS UNIQUE",
    "CREATE CONSTRAINT region_key IF NOT EXISTS FOR (n:Region) REQUIRE n.region_key IS UNIQUE",
    "CREATE CONSTRAINT policy_marker_code IF NOT EXISTS FOR (n:PolicyMarker) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT load_meta_name IF NOT EXISTS FOR (n:LoadMeta) REQUIRE n.name IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX organisation_name IF NOT EXISTS FOR (n:Organisation) ON (n.name)",
    "CREATE INDEX activity_publisher IF NOT EXISTS FOR (n:Activity) ON (n.publisher)",
    "CREATE INDEX activity_start_date IF NOT EXISTS FOR (n:Activity) ON (n.start_date)",
    "CREATE INDEX activity_end_date IF NOT EXISTS FOR (n:Activity) ON (n.end_date)",
    "CREATE INDEX activity_match_basis IF NOT EXISTS FOR (n:Activity) ON (n.match_basis)",
    "CREATE INDEX transaction_type IF NOT EXISTS FOR (n:Transaction) ON (n.type)",
    "CREATE INDEX transaction_type_name IF NOT EXISTS FOR (n:Transaction) ON (n.type_name)",
    "CREATE INDEX transaction_date IF NOT EXISTS FOR (n:Transaction) ON (n.date)",
    "CREATE INDEX transaction_currency IF NOT EXISTS FOR (n:Transaction) ON (n.currency)",
    "CREATE INDEX budget_period_start IF NOT EXISTS FOR (n:Budget) ON (n.period_start)",
    "CREATE INDEX budget_status IF NOT EXISTS FOR (n:Budget) ON (n.status)",
    "CREATE INDEX country_name IF NOT EXISTS FOR (n:Country) ON (n.name)",
]

# ----------------------------------------------------------------- loads --
# Each entry: csv file, Cypher taking $rows, optional row filter {col: value},
# optional `columns` to restrict what is sent. Order matters: nodes first.
NODE_LOADS = [
    ("nodes_activities.csv",
     "UNWIND $rows AS r MERGE (n:Activity {iati_identifier: r.iati_identifier}) SET n += r", None, None),
    ("nodes_organisations.csv",
     "UNWIND $rows AS r MERGE (n:Organisation {ref: r.ref}) SET n += r", None, None),
    ("nodes_countries.csv",
     "UNWIND $rows AS r MERGE (n:Country {code: r.code}) SET n += r", None, None),
    ("nodes_sectors.csv",
     "UNWIND $rows AS r MERGE (n:Sector {sector_key: r.sector_key}) SET n += r", None, None),
    ("nodes_transactions.csv",
     "UNWIND $rows AS r MERGE (n:Transaction {tx_id: r.tx_id}) SET n += r", None, None),
    ("nodes_budgets.csv",
     "UNWIND $rows AS r MERGE (n:Budget {budget_id: r.budget_id}) SET n += r", None, None),
    ("nodes_locations.csv",
     "UNWIND $rows AS r MERGE (n:Location {location_id: r.location_id}) SET n += r", None, None),
    ("nodes_sdgs.csv",
     "UNWIND $rows AS r MERGE (n:SDG {sdg_key: r.sdg_key}) SET n += r", None, None),
    ("nodes_emergencies.csv",
     "UNWIND $rows AS r MERGE (n:Emergency {emergency_key: r.emergency_key}) SET n += r", None, None),
    ("nodes_regions.csv",
     "UNWIND $rows AS r MERGE (n:Region {region_key: r.region_key}) SET n += r", None, None),
    ("nodes_policy_markers.csv",
     "UNWIND $rows AS r MERGE (n:PolicyMarker {code: r.code}) SET n += r", None, None),
]

# Every node carries `source_id` and every relationship `source_ids`: the CSV
# rows it came from, as "<file>.csv:row:<n>" (n counts data rows from 1), the
# citation IDs Deniz's benchmark scores evidence against. A list on edges
# because MERGE collapses duplicate rows (PARTICIPATES_IN) into one edge.
SOURCE_IDS = "x.source_ids = coalesce(x.source_ids, []) + r.source_id"

REL_LOADS = [
    ("rel_reports.csv",
     "UNWIND $rows AS r MATCH (o:Organisation {ref: r.org_ref}) "
     "MATCH (a:Activity {iati_identifier: r.iati_identifier}) MERGE (o)-[x:REPORTS]->(a) SET " + SOURCE_IDS, None, None),
    # MERGE on (org, activity, role) collapses exact duplicate CSV rows
    ("rel_participates.csv",
     "UNWIND $rows AS r MATCH (o:Organisation {ref: r.org_ref}) "
     "MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     "MERGE (o)-[x:PARTICIPATES_IN {role: r.role}]->(a) "
     f"SET x.role_name = r.role_name, {SOURCE_IDS}", None, None),
    ("rel_targets_country.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     "MATCH (c:Country {code: r.country_code}) "
     "MERGE (a)-[x:TARGETS]->(c) "
     f"SET x.percentage = r.percentage, x.is_hotspot = r.is_hotspot, {SOURCE_IDS}", None, None),
    ("rel_targets_region.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     "MATCH (g:Region {region_key: r.region_key}) "
     f"MERGE (a)-[x:TARGETS_REGION]->(g) SET x.percentage = r.percentage, {SOURCE_IDS}", None, None),
    ("rel_classified_as.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     "MATCH (s:Sector {sector_key: r.sector_key}) "
     f"MERGE (a)-[x:CLASSIFIED_AS]->(s) SET x.percentage = r.percentage, {SOURCE_IDS}", None, None),
    ("rel_located_at.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     "MATCH (l:Location {location_id: r.location_id}) MERGE (a)-[x:LOCATED_AT]->(l) SET " + SOURCE_IDS, None, None),
    ("nodes_transactions.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     f"MATCH (t:Transaction {{tx_id: r.tx_id}}) MERGE (a)-[x:HAS_TRANSACTION]->(t) SET {SOURCE_IDS}",
     None, ["iati_identifier", "tx_id", "source_id"]),
    ("nodes_budgets.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     f"MATCH (b:Budget {{budget_id: r.budget_id}}) MERGE (a)-[x:HAS_BUDGET]->(b) SET {SOURCE_IDS}",
     None, ["iati_identifier", "budget_id", "source_id"]),
    ("rel_transaction_edges.csv",
     "UNWIND $rows AS r MATCH (o:Organisation {ref: r.org_ref}) "
     "MATCH (t:Transaction {tx_id: r.tx_id}) MERGE (o)-[x:PROVIDES]->(t) SET " + SOURCE_IDS,
     {"edge": "PROVIDED_BY"}, None),
    ("rel_transaction_edges.csv",
     "UNWIND $rows AS r MATCH (o:Organisation {ref: r.org_ref}) "
     "MATCH (t:Transaction {tx_id: r.tx_id}) MERGE (t)-[x:RECEIVED_BY]->(o) SET " + SOURCE_IDS,
     {"edge": "RECEIVED_BY"}, None),
    ("rel_responds_to.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     "MATCH (e:Emergency {emergency_key: r.emergency_key}) MERGE (a)-[x:RESPONDS_TO]->(e) SET " + SOURCE_IDS, None, None),
    ("rel_contributes_to.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     "MATCH (g:SDG {sdg_key: r.sdg_key}) MERGE (a)-[x:CONTRIBUTES_TO]->(g) SET " + SOURCE_IDS, None, None),
    ("rel_marked_with.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     "MATCH (m:PolicyMarker {code: r.marker_code}) "
     f"MERGE (a)-[x:MARKED_WITH]->(m) SET x.significance = r.significance, {SOURCE_IDS}", None, None),
    # related activities may point outside the slice; only link when both exist
    ("rel_related_activity.csv",
     "UNWIND $rows AS r MATCH (a:Activity {iati_identifier: r.iati_identifier}) "
     "MATCH (b:Activity {iati_identifier: r.related_ref}) "
     f"MERGE (a)-[x:RELATED_TO]->(b) SET x.type = r.type, {SOURCE_IDS}", None, None),
]

# Run once after all loads. Publisher slug on the three reporting orgs is
# derived from the data, not config (config has a wrong Oxfam America ref).
POST_LOAD = [
    "MATCH (o:Organisation)-[:REPORTS]->(a:Activity) "
    "WITH o, collect(DISTINCT a.publisher) AS pubs SET o.publisher = pubs[0]",
]

# Expected count per label / relationship type, expressed as which CSV
# (and filter) it should match. Used only for the post-load report.
NODE_COUNTS = {
    "Activity": "nodes_activities.csv", "Organisation": "nodes_organisations.csv",
    "Country": "nodes_countries.csv", "Sector": "nodes_sectors.csv",
    "Transaction": "nodes_transactions.csv", "Budget": "nodes_budgets.csv",
    "Location": "nodes_locations.csv", "SDG": "nodes_sdgs.csv",
    "Emergency": "nodes_emergencies.csv", "Region": "nodes_regions.csv",
    "PolicyMarker": "nodes_policy_markers.csv",
}
REL_COUNTS = {
    "REPORTS": ("rel_reports.csv", None),
    "PARTICIPATES_IN": ("rel_participates.csv", None),
    "TARGETS": ("rel_targets_country.csv", None),
    "TARGETS_REGION": ("rel_targets_region.csv", None),
    "CLASSIFIED_AS": ("rel_classified_as.csv", None),
    "LOCATED_AT": ("rel_located_at.csv", None),
    "HAS_TRANSACTION": ("nodes_transactions.csv", None),
    "HAS_BUDGET": ("nodes_budgets.csv", None),
    "PROVIDES": ("rel_transaction_edges.csv", {"edge": "PROVIDED_BY"}),
    "RECEIVED_BY": ("rel_transaction_edges.csv", {"edge": "RECEIVED_BY"}),
    "RESPONDS_TO": ("rel_responds_to.csv", None),
    "CONTRIBUTES_TO": ("rel_contributes_to.csv", None),
    "MARKED_WITH": ("rel_marked_with.csv", None),
    "RELATED_TO": ("rel_related_activity.csv", None),
}
# Count deviations that are expected and why
EXPECTED_DEVIATIONS = {
    "PARTICIPATES_IN": "CSV has exact duplicate (org, activity, role) rows; MERGE collapses them",
    "RELATED_TO": "only linked when both activities are inside the hotspot slice",
}

# Semantic spot check run after load: Cypher vs the same thing computed from
# the CSVs. Proves casts (float value, date) and the PROVIDES direction.
SPOT_CHECK_CYPHER = """
MATCH (a:Activity)-[:TARGETS]->(:Country {code: $country}),
      (a)-[:HAS_TRANSACTION]->(t:Transaction {type: '1'})<-[:PROVIDES]-(o:Organisation)
WHERE t.currency = 'USD'
RETURN o.ref AS org_ref, round(sum(t.value)) AS total, count(t) AS n
ORDER BY total DESC LIMIT 3
"""
