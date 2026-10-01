<<<<<<< HEAD

<h1 align="center">
  <br>
  <a href="https://www.bu.edu/spark/" target="_blank"><img src="https://www.bu.edu/spark/files/2023/08/logo.png" alt="BUSpark" width="200"></a>
  <br>
  Project README Template <change to project name>
  <br>
</h1>

<h4 align="center">A template for the project readme file. </h4> <change to repo short description>

<p align="center">
  <a href="#key-features">Key Features</a> •
  <a href="#how-to-use">How To Use</a> •
  <a href="#project-description">Project Description</a> •
  <a href="#data-locations">Data Locations</a>
</p>

## Key Features
In this section you will be including a list of key features of your code/project.

You should also include a short description of what each part of your code does. (Detailed description in the readme of each directory, if applicable)
* /path/to/directory - function and description
  - Key notes
* /path/to/script - function and description
  - Key notes
* Lorem Ipsum - Dolor Sit Amet
  - Consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
* Duis Aute Irure Dolor
  - Excepteur sint occaecat
* Excepteur Sint Occaecat
  - Curabitur efficitur, nunc non ultricies gravida, felis purus posuere eros, sed faucibus sapien est nec quam. Nulla at nisl nisl.
 
## How To Use

To clone and run this application, you'll need <a href="https://git-scm.com" target="_blank">Git</a>
From your command line:

```bash
# Clone this repository
$ git clone [repo link]

# Further Instructions
...
```

Create a new branch from dev, add changes on the new branch you just created.

You will want to look into <a href="https://git-scm.com/docs/git-branch" target="_blank">git branch</a> and <a href="https://git-scm.com/docs/git-checkout" target="_blank">git checkout</a>

```bash
# Create and Checkout a new branch if it doesn't exist
$ git checkout -b your-branch main
...
```

Open a Pull Request to dev. Add your PM and TPM as reviewers. 

At the end of the semester during project wrap up open a final Pull Request to main from dev branch.
 
## Project Description

In this section, you should include the project description, either from the client or spark.

Please make sure it reflects what you see on the documents (project description) you recieved.

* Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla facilisi. Donec vel nunc at libero ultrices tincidunt. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Mauris ut ligula nec risus posuere ultricies at et ligula. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas.
* Veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.

## Data locations

In this section, you should include the location of all of your datasets for the project (if applicable)

<a href="dataset-documentation">Dataset Documentation</a>
* Location 1: [location]
  - [description]
* Location 2: [location]
  - [description]
=======
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
>>>>>>> main
