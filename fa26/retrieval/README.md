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
  tools.py            the four query tools
  org_duplicates.csv  report for the pipeline team (64 pairs, 41 groups)
  findings.md         Phase 1 baseline review of the prototype
  tests/              pytest, expected values recomputed from the CSVs with pandas
```

## Setup

```bash
pip install -r fa26/retrieval/requirements.txt   # neo4j, python-dotenv, rapidfuzz, pytest, pandas
```

**Data location.** The loader and tests read the prototype's graph CSVs from
`fa26/data/graph/` (not committed). Copy them from the summer prototype's
`data/graph/`, or from `fa26/benchmark/snapshot/` on George's branch, or
pass `--graph-dir PATH` to the loader.

Connection details come from a `.env` file (see `fa26/.env.example`),
searched in `fa26/` first, then its parent. Keys: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`,
optional `NEO4J_DATABASE`. Never commit it.

```bash
brew services start neo4j                                   # local Neo4j (Homebrew)
python fa26/retrieval/load_neo4j.py                    # load into an empty DB
python fa26/retrieval/load_neo4j.py --reset            # wipe + reload (refuses a DB it did not fill unless --force)
python fa26/retrieval/load_neo4j.py --env ../.env      # use another .env, e.g. Aura
python -m pytest fa26/retrieval/tests -q               # 46 tests, skipped if no DB is reachable
```

The loader prints a table of CSV rows vs database counts and runs one
semantic spot check (top USD incoming-funds providers into Somalia) against
the same CSVs. The only expected count deviation is `PARTICIPATES_IN`:
210 exact duplicate rows in the CSV collapse to one edge each.

## Using the tools

```python
import sys; sys.path.insert(0, "fa26/retrieval")
from tools import activities, shared_partners, top_funders, funding_over_time
from resolve_entity import resolve_entity

top_funders("Somalia", year_from=2022, limit=5)
activities(country="Yemen", publisher="Oxfam GB", year_from=2018, year_to=2020)
shared_partners(["Oxfam GB", "WFP"], country="South Sudan")
funding_over_time(publisher="WFP", transaction_type="Expenditure", by="quarter")
resolve_entity("UK government", "organisation")
```

### Return format (all four tools)

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
`match_type` is `"sector"` (standard DAC/cluster code, WFP only) or
`"keyword"` (title/description match, all Oxfam activities).
Columns: `iati_identifier, publisher, title, status, start_date, end_date, countries, match_basis, humanitarian`.

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
Columns: `funder_id, funder, all_refs, currency, net, positive_total, negative_total, n_transactions, n_negative, first_date, last_date, publishers, n_activities, activity_ids`, plus `note` on placeholder rows such as "Multilateral".

**Why the default is Incoming Funds, not Disbursement.** In this graph
external funders appear only as providers of Incoming Funds (type 1).
Disbursement rows (type 3) exist only for Oxfam GB and name Oxfam GB itself
as provider; WFP publishes none. Calling with `("Disbursement",)` therefore
returns `no_results` with a note explaining this. Change the default in
`tools.py` if the team decides otherwise.

### `funding_over_time(publisher=None, country=None, transaction_type="Incoming Funds", by="year", year_from=None, year_to=None, limit=200)`

Net amount per period (`year`, `quarter` or `month`) by publisher and
currency. Columns: `period, publisher, currency, net, positive_total, negative_total, n_transactions, n_negative, n_activities, activity_ids`.

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
- **Negative transactions** (23% of rows) are netted; `n_negative` and `negative_total` expose them. Whether they are refunds or corrections is an open client question.
- **Oxfam America** has 11 activities, no funders, no partners, no sector codes: funder and partner questions return `no_results` for it.
- **WFP money starts in 2021** although its activities start in 2018. WFP mirrors every commitment as an identical expenditure; never add those two types.
- **Sector questions** are WFP-only: Oxfam GB uses its own "5 Aims" vocabulary and Oxfam America only "unallocated". 85% of activities were kept by keyword match (`match_basis`), which the client flagged as noisy.
- **Entity resolution is curated.** Oxfam GB names most funders without an IATI ref; cross-publisher matches depend on `entities.SAME_AS`. Unlisted variants stay separate rows.
- **Placeholders** ("Multilateral", "Oxfam Donor(s)", "Developing countries, unspecified") are kept in funder results with a `note`, because the pooled amounts are real money.
- **Single-country activities only** in this slice; if multi-country activities appear, a tool credits the full amount to each country (no percentage weighting).
- The graph is the summer prototype's output, two transformations away from raw IATI XML. Some identifier oddities (uppercased bare names, the "FCDO - Procurement" label) come from the prototype's resolver, not the publishers.
