---
title: IATI Hunger Hotspots Knowledge Graph
emoji: 🕸️
colorFrom: purple
colorTo: green
sdk: gradio
sdk_version: 6.20.0
app_file: spaces/app.py
pinned: false
license: mit
---

# IATI Hunger Hotspots Knowledge Graph — Feasibility Prototype

Builds a knowledge graph from IATI activity data (graph-database-ready CSV nodes/edges), scoped to:

- **Orgs:** Oxfam GB vs Oxfam America, with WFP as comparison
- **Theme:** hunger-related activities (DAC purpose codes, humanitarian
  Food Security/Nutrition clusters, keyword fallback)
- **Geography:** the 13 FAO–WFP Hunger Hotspots from the June–November 2026
  outlook (CE0155EN): Sudan, South Sudan, Yemen, Palestine, Nigeria, Somalia
  (highest concern); Afghanistan, DRC, Haiti (very high concern); Lebanon,
  Madagascar, Myanmar, Mali (hotspots)

## Setup

Python 3.10+, standard library only (no pip installs needed for the pipeline).

## Workflow

One command runs everything:

```bash
python src/pipeline.py all        # download -> parse -> resolve -> sync to app
python src/pipeline.py refresh    # re-parse + resolve + sync (no download)
```

Or stage by stage (each also runs standalone with its own flags):

```bash
python src/pipeline.py download -- --find-publisher oxfam   # slug lookup
python src/pipeline.py download -- --dry-run                # preview selection
python src/download.py --publisher wfp                      # one publisher
python src/parse_filter.py --no-theme                       # coverage scan
python src/resolve_orgs.py --dry-run                        # resolution preview
```

## Live updates (every 1-2 weeks)

`src/live_updates.py` (`LiveUpdater` class) re-downloads the selected IATI
files when an update is due, replaces only files whose SHA-256 changed,
and re-runs parse -> resolve only if something changed.

```bash
python src/live_updates.py                    # runs only if 7+ days since last update
python src/live_updates.py --interval-days 14 # biweekly
python src/live_updates.py --force --sync     # now, and copy CSVs to spaces/data
python src/live_updates.py --status           # last run / next due
python src/pipeline.py update                 # same, via the pipeline entrypoint
```

Schedule it **daily**; it does real work only when due. State and a per-run
JSON log live in `data/live_updates/`; previous versions of changed files go
to `data/raw_archive/<timestamp>/` (both gitignored). A weekly GitHub Actions
workflow is in `.github/workflows/iati-live-update.yml`.

Then run the demo locally:

```bash
pip install -r spaces/requirements.txt
cd spaces && python app.py        # http://localhost:7860
```

Standalone shareable HTML graphs: `python src/visualize_html.py --country YE`.

## Graph model

```
(Organisation)-[:REPORTS]->(Activity)
(Organisation)-[:PARTICIPATES_IN {role}]->(Activity)
(Activity)-[:TARGETS {percentage, is_hotspot}]->(Country {hotspot_tier})
(Activity)-[:LOCATED_AT]->(Location {lat, lon, adm_code})
(Activity)-[:CLASSIFIED_AS {percentage}]->(Sector {is_hunger})
(Activity)-[:HAS_TRANSACTION]->(Transaction {type, value, date})
(Organisation)-[:PROVIDES]->(Transaction)-[:RECEIVED_BY]->(Organisation)
(Activity)-[:HAS_BUDGET]->(Budget {period, value, status})
(Activity)-[:RESPONDS_TO]->(Emergency {GLIDE or HRP code})
(Activity)-[:CONTRIBUTES_TO]->(SDG {goal or target})
(Activity)-[:MARKED_WITH {significance}]->(PolicyMarker)
(Activity)-[:TARGETS_REGION {percentage}]->(Region)
(Activity)-[:PARENT_OF|CHILD_OF|SIBLING_OF]->(Activity)
```

Transactions are nodes (not edge properties) so funding flows are traversable:
funder → transaction → activity → country. That is the query pattern the
Oxfam GB vs Oxfam America vs WFP comparison needs.

## Filtering logic

An activity is kept iff:

1. **Geography:** any `recipient-country` or transaction-level
   `recipient-country` is a hotspot ISO2 code (`config.HOTSPOTS`).
   Location-only matching (no country code) is not attempted in v0.
2. **Theme:** any sector matches hunger DAC codes / DAC 311·313·520
   categories / cluster codes 6 (Food Security) or 9 (Nutrition). If the
   activity carries no sector coding at all, a keyword scan of
   title+description is used as fallback, and the match basis is recorded on
   the Activity node (`match_basis: sector|keyword`) so keyword-matched
   activities can be reviewed or excluded later.

Toggles in `src/config.py`: `INCLUDE_GENERAL_EMERGENCY` (DAC 72010 is broad —
off by default), keyword list, hotspot tiers.

## Known limitations (v0, by design)

- Publisher attribution comes from the download folder, so keep each
  publisher's XML in its own directory under `data/raw/`.
- No currency conversion; transaction values are summed per currency.
- IATI 2.0x only (all three target publishers are on 2.03).
- Sub-national hotspot areas from the report (e.g. Borno State, Jonglei) are
  not matched yet; `Location.adm_code` (GeoNames/G1) is captured so this can
  be layered on next.
- The registry heuristic that picks per-country files falls back to
  downloading monolithic files whole; use `--all-files` to disable it.

## Prior art

DFID's [dcm-graph](https://github.com/DFID/dcm-graph) (2019) built an
IATI-to-Neo4j delivery chain map -- good validation of the concept to cite,
but it ingests all of IATI (~2.5 GB) on a 32 GB Azure VM and models only
Organisations/Activities. This prototype instead filters at ingest to a
theme + geography slice and adds Country, Location, Sector and Transaction
nodes, so it runs on a laptop and loads into AuraDB Free.

## Suggested demo path

1. Run the `--no-theme` coverage scan; screenshot
   `coverage_report.json` tables (activities per publisher × hotspot ×
   start year) for the geography/time-period recommendation.
2. Pick 1–2 hotspot countries with good coverage from all three publishers
   (Somalia, South Sudan or DRC are likely candidates), re-run the full
   filter, load into AuraDB Free.
3. Demo queries 2 (Oxfam GB/US overlap), 3 (shared partners) and 6 (funding
