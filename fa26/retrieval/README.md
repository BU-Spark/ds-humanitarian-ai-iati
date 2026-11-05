# Retrieval layer

Query tools the Graph RAG orchestrator calls. Plain Python, no LangChain.
Everything here reads the Neo4j graph loaded by `load_neo4j.py` from the
prototype's `data/graph/*.csv`. Nothing under `src/` is touched.

```
retrieval/
  db.py               one database path: .env, read-only transactions, timeout, mandatory LIMIT
  load_neo4j.py       CSV -> Neo4j loader (generic; all Cypher lives in the schema module)
  schema_prototype.py node labels, relationship types, constraints, indexes, casts
  entities.py         curated tables: SAME_AS duplicates, AGENCY_OF hierarchies, aliases, placeholders
  resolve_entity.py   text -> graph IDs, plus the duplicate-organisation report
  tools.py            the five query tools
  validate_graph.py   post-load checks: constraints, orphans, required properties, source ids
  schema_alignment.md differences from George's schema v0.1 and what to decide
  org_duplicates.csv  report for the pipeline team (64 pairs, 41 groups)
  findings.md         Phase 1 baseline review of the prototype
  tests/              pytest, expected values recomputed from the CSVs with pandas
```

## Setup

```bash
pip install -r fa26/retrieval/requirements.txt   # neo4j, python-dotenv, rapidfuzz, pytest, pandas
```

**Data location.** The loader and tests read graph CSVs from
`fa26/data/graph/` (not committed). Either the summer prototype's
`data/graph/` (505 activities) or the cleaned output of Devansh's pipeline
(`python fa26/src/pipeline.py download parse resolve` on his branch; 439
activities on 2026-11-01). Pass `--graph-dir PATH` to the loader and
validator, and set `RETRIEVAL_GRAPH_DIR=PATH` for the tests, to use another
folder, and `RETRIEVAL_ENV=PATH` to point the tests at another `.env`.
Tests compare against whichever CSVs the graph was loaded from.

Connection details come from a `.env` file (see `fa26/.env.example`),
searched in `fa26/` first, then its parent. Keys: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`,
optional `NEO4J_DATABASE`. Never commit it.

```bash
brew services start neo4j                                   # local Neo4j (Homebrew)
python fa26/retrieval/load_neo4j.py                    # load into an empty DB
python fa26/retrieval/load_neo4j.py --reset            # wipe + reload (refuses a DB it did not fill unless --force)
python fa26/retrieval/load_neo4j.py --env ../.env      # use another .env, e.g. Aura
python fa26/retrieval/validate_graph.py --baseline-dir OLD_CSVS   # checks + per-publisher before/after
python -m pytest fa26/retrieval/tests -q               # 59 tests, skipped if no DB is reachable
```

The loader prints a table of CSV rows vs database counts and runs one
semantic spot check (top USD incoming-funds providers into Somalia) against
the same CSVs. The only expected count deviation is `PARTICIPATES_IN`:
exact duplicate rows in the CSV (210 summer, 222 cleaned) collapse to one
edge each.

Every node carries `source_id` and every relationship `source_ids`, the CSV
rows it came from as `<file>.csv:row:<n>` (data rows counted from 1): the
citation format of the team benchmark. A collapsed edge lists all its rows.

`Transaction` and `Budget` nodes keep `value` as a float and also get
`value_cents`, an exact integer computed with `Decimal` from the raw CSV
string. The money tools sum `value_cents` and divide by 100 once, so totals
match a Decimal sum to the cent however many rows there are. Sub-cent digits
in the exports are float artefacts (`770317.9300000001`), so rounding each row
to the cent loses nothing real. `validate_graph.py` checks that the cents in
the database add up to the CSV total exactly.

## Using the tools

```python
import sys; sys.path.insert(0, "fa26/retrieval")
from tools import activities, shared_partners, top_funders, funding_over_time, transaction_totals
from resolve_entity import resolve_entity

top_funders("Somalia", year_from=2022, limit=5)
activities(country="Yemen", publisher="Oxfam GB", year_from=2018, year_to=2020)
shared_partners(["Oxfam GB", "WFP"], country="South Sudan")
funding_over_time(publisher="WFP", transaction_type="Expenditure", by="quarter")
transaction_totals("Incoming Funds", publisher="WFP", currency="USD", year_from=2020, year_to=2020)
resolve_entity("UK government", "organisation")
```

### Return format (all five tools)

```python
{
  "status": "ok" | "no_results" | "error",
  "rows": [...],              # see per-tool columns below
  "cypher": "...",            # the exact query that ran ("" when input resolution failed)
  "params": {...},            # the exact parameters (includes the duplicate-ref map, so it can be long)
  "coverage_note": "...",     # what the answer does NOT cover
  "candidates": [...]         # only on status "error" caused by an ambiguous name
}
```

Activity rows carry `iati_identifier` and `publisher`. Aggregate rows carry
`activity_ids` (first 20) with `n_activities`, and `publishers`, so every
number is traceable to IATI records. `publisher` values are the slugs
`oxfamgb`, `oxfamus`, `wfp`.

**Money and evidence.** The three money tools (`top_funders`,
`funding_over_time`, `transaction_totals`) report `amount` (positive
transactions), `adjustments` (negative ones, their own category per the
client) and `net` per currency, summed exactly in integer cents. Every row also has
`evidence_amount`, `evidence_adjustments` and `evidence_net`: the complete
source-row ids behind each figure (transaction rows, their activity rows, and
the `rel_targets_country` / `rel_transaction_edges` rows a filter used), in
the benchmark's `<file>.csv:row:<n>` format and never truncated. An empty
money result carries a top-level `evidence` list of searched tables
(`manifest:nodes_transactions.csv`, plus activities when filtered by
publisher and targeting rows when filtered by country), which is how the
benchmark cites "no matching rows". Evidence needs a graph loaded by the
current `load_neo4j.py`; an older load has no source ids and gives empty lists.
A figure with no contributing rows (say `adjustments` of 0) cites the same
manifest ids. Evidence can be large (about 1 MB for `transaction_totals()`
over all publishers), so pass `for_model(result)` to the LLM and keep the full
result in code to attach citations.

`country` and `publisher` arguments are free text and go through
`resolve_entity`: "Somalia", "SO", "SOM", "DRC", "Oxfam GB", "WFP" all work.
An ambiguous name ("Oxfam") returns `status: "error"` with `candidates`
rather than a guess. Years may be ints or digit strings; anything else is an
error, not an empty result.

Safety: every query runs in a read transaction (the server rejects writes),
with a 30 s timeout, parameters only (no string formatting), and a `LIMIT`
capped at 500. A true read-only database user is not available on Aura Free
or Community Edition; read-mode transactions are the enforced substitute.

### `activities(country=None, publisher=None, year_from=None, year_to=None, match_type=None, limit=50)`

Hunger-related activities. The year window means **active during**: start
year ≤ `year_to` and end year (or start year if no end) ≥ `year_from`.
`match_type` filters on why the hunger filter kept the activity:
`"sector"`, `"sdg"`, `"keyword"`, `"keyword_over_sector"` or `"keyword_weak"`.
Columns: `iati_identifier, publisher, title, status, start_date, end_date, countries, match_basis, confidence, humanitarian`.

### `shared_partners(publishers, country=None, limit=50)`

Organisations linked to **every** listed publisher through participation,
providing a transaction (funder) or receiving one (recipient). The
publishers themselves, their duplicate refs and placeholder refs are
excluded. Duplicate refs are merged with `entities.SAME_AS`; a government
and its agencies (United States vs USAID) stay separate rows.
Columns: `organisation_id, organisation, all_refs, publishers, via, roles, n_activities, activity_ids`.

### `top_funders(country, transaction_types=("Incoming Funds",), year_from=None, year_to=None, limit=10, publisher=None, exclude_self=True)`

Provider organisations summed by currency for transactions of the given
type(s) on activities targeting the country. `limit` applies **per
currency** and rows never interleave currencies. `exclude_self` hides rows
where the provider is the activity's own reporting organisation; another
publisher still counts (WFP funding Oxfam GB's South Sudan activities is the
top GBP funder there).
Rows are ranked by `amount` within each currency.
Columns: `funder_id, funder, all_refs, currency, amount, adjustments, net, n_transactions, n_adjustments, first_date, last_date, publishers, n_activities, activity_ids`, the evidence lists, plus `note` on placeholder rows such as "Multilateral".

**Why the default is Incoming Funds, not Disbursement.** In this graph
external funders appear only as providers of Incoming Funds (type 1).
Disbursement rows (type 3) exist only for Oxfam GB and name Oxfam GB itself
as provider; WFP publishes none. Calling with `("Disbursement",)` therefore
returns `no_results` with a note explaining this. Change the default in
`tools.py` if the team decides otherwise.

### `funding_over_time(publisher=None, country=None, transaction_type="Incoming Funds", by="year", year_from=None, year_to=None, limit=200)`

Money per period (`year`, `quarter` or `month`) by publisher and
currency. Columns: `period, publisher, currency, amount, adjustments, net, n_transactions, n_adjustments, n_activities, activity_ids`, plus the evidence lists.

### `transaction_totals(transaction_type="Incoming Funds", publisher=None, currency=None, country=None, year_from=None, year_to=None, by_publisher=False)`

Totals of **one** transaction type, one row per currency (and per publisher
with `by_publisher=True`). Mixing types is rejected because WFP mirrors every
commitment as an identical expenditure. Undated transactions count unless a
year filter is given. Answers "net WFP incoming funds in USD in 2020",
"positive / negative total", "net expenditure by currency".
Columns: `publisher, currency, amount, adjustments, net, n_transactions, n_adjustments, n_activities, activity_ids`, plus the evidence lists.

### `resolve_entity(text, kind)`

`kind` is `"organisation"` or `"country"`. Order: exact match on ref or
name, curated alias, acronym derived from names, fuzzy (rapidfuzz, inputs of
4+ characters only). A fuzzy match counts as `ok` only at confidence ≥ 0.9
and clearly ahead of the runner-up; otherwise `ambiguous` with candidates.
`match.ids` lists every ref a tool should filter on (`relation` says whether
they are the same organisation or its agencies); `match.parent` is set when
the match is itself an agency. `python retrieval/resolve_entity.py --demo`
prints the brief's examples; `--report-duplicates` regenerates
`org_duplicates.csv`.

## Known limitations

- **No currency conversion.** Totals are per currency (USD and GBP in this slice).
- **Negative transactions** (about 23% of rows) are their own category, as the client chose on 2026-10-23: `amount` sums positive transactions only, `adjustments` sums the negative ones (`n_adjustments` rows), and `net` = amount + adjustments. Whether a given negative is a refund, correction or reversal is not knowable from the data.
- **Zero-value transactions** (91 rows in the cleaned data) count in `n_transactions` but in neither `amount` nor `adjustments`.
- **Oxfam America** has 11 activities, no funders, no partners, no sector codes: funder and partner questions return `no_results` for it.
- **WFP money starts in 2021** although its activities start in 2018. WFP mirrors every commitment as an identical expenditure; never add those two types.
- **Sector questions** are WFP-only: Oxfam GB uses its own "5 Aims" vocabulary and Oxfam America only "unallocated". Most Oxfam activities are kept by keyword match; `match_basis` and `confidence` (high/medium/low) say why each activity is in the graph.
- **Entity resolution is curated.** Oxfam GB names most funders without an IATI ref; cross-publisher matches depend on `entities.SAME_AS`. Unlisted variants stay separate rows.
- **Placeholders** ("Multilateral", "Oxfam Donor(s)", "Developing countries, unspecified") are kept in funder results with a `note`, because the pooled amounts are real money.
- **Single-country activities only** in this slice; if multi-country activities appear, a tool credits the full amount to each country (no percentage weighting).
- The graph CSVs are the pipeline's output, two transformations away from raw IATI XML. Some identifier oddities (uppercased bare names, the "FCDO - Procurement" label) come from the prototype's resolver, not the publishers.
