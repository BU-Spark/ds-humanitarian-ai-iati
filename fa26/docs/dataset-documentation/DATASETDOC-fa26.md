# Dataset documentation — Fall 2026

Updated October 21, 2026. Counts below were checked against the committed benchmark CSVs and SHA-256 manifest. This document describes the available export and completed offline work, not planned live infrastructure.

## Project information

- **Project:** Humanitarian AI Today: IATI to Knowledge Graph Data Prototype.
- **Repository:** [BU-Spark/ds-humanitarian-ai-iati](https://github.com/BU-Spark/ds-humanitarian-ai-iati).
- **Course:** BU Spark / CDS / DS 701, Fall 2026, as stated in the project brief.
- **Client:** Humanitarian AI Today, a volunteer-driven humanitarian AI initiative.
- **Contact:** Brent is identified in the supplied team meeting summary. Contact details and the Spark-owned Drive folder are managed by the PM; no confirmed Drive URL or private contact details are recorded here.
- **Goal:** Convert a selected slice of IATI activity and financial records into a traceable graph, improve data quality, and evaluate natural-language questions grounded in that graph.
- **Project brief:** `fa26/docs/FA 26' DS 701 Humanitarian AI Today PD.pdf` (path relative to the repository root).

## Data locations and sources

| Dataset / artifact | Location | Role |
| --- | --- | --- |
| Working graph export | [fa26/data/graph](../../data/graph/) | CSVs used by the application and pipeline reports |
| Fixed evaluation snapshot | [fa26/benchmark/snapshot](../../benchmark/snapshot/) | 22 pinned CSVs used for repeatable evaluation |
| Snapshot manifest | [manifest.json](../../benchmark/manifest.json) | File hashes, row counts, source commit and snapshot identity |
| Data dictionary | [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | All tables, fields, keys and join conventions |
| Public evaluation questions | [questions.json](../../benchmark/questions.json) | 20 questions and calculation contracts |
| Evaluator references | [benchmark README](../../benchmark/README.md) | Reference calculations, SQL baseline and scoring; keep out of model context |
| Test fixtures | [fa26/tests](../../tests/) | Small synthetic XML/JSON cases, not real-world ground truth |

The project inherits the [summer prototype](https://huggingface.co/spaces/shinushibu1798/iati-graph-prototype). The downloader uses the [IATI Bulk Data Service](https://bulk-data.iatistandard.org); XML records originate with the publishers. [IATI Standard](https://iatistandard.org/en/iati-standard/) supplies the format and codelist definitions. An inherited upstream metadata record identifies commit `c6b70f342272d2a2d011c8a1d626a9e02d5eb96b`; this is provenance metadata, not proof of current remote state.

The evaluation manifest records source commit `76546d3a2189e419c0233bfbf2093916f67ec4f7`, source folder `fa26/data/graph`, and pin date **2026-10-15**. The exact raw-download time is not recorded. A pin date is not the date an activity occurred or a transaction was reported.

**Snapshot ID:** `430caabd5a8ae1d0816a9941a4a8f730484c4c0b35360ee17983a76c3297658f`

## Motivation and scope

The original publishers disclose development/humanitarian activities through IATI XML. The prototype export was created to explore whether selected records can support graph browsing, funding analysis and traceable question answering. It addresses the difficulty of joining inconsistent publisher records; it is not a needs assessment.

The export is a deterministic, non-random filtered subset of three publishers:

| Publisher slug | Organisation | Activities |
| --- | --- | ---: |
| `oxfamgb` | Oxfam GB | 412 |
| `oxfamus` | Oxfam America | 11 |
| `wfp` | World Food Programme | 82 |

The configured geography is the 13 FAO-WFP Hunger Hotspots for the June–November 2026 outlook, as represented in `fa26/src/config.py`: Afghanistan, Democratic Republic of the Congo, Haiti, Lebanon, Madagascar, Mali, Myanmar, Nigeria, Palestine, Somalia, South Sudan, Sudan and Yemen. Country-level coverage does not establish coverage of every subnational hotspot.

**Tags:** humanitarian aid, IATI, knowledge graphs, data cleaning, entity resolution, information retrieval, Graph RAG, natural-language question answering, food security, nutrition, agriculture, funding transparency.

## Composition and dataset snapshot

The CSVs represent activities, organisations, countries, locations, sectors, transactions, budgets, SDG tags and explicit relationships. They are processed text/tabular graph exports, not raw XML. Titles/descriptions contain narrative text; financial amounts, dates and codes are stored as strings. Empty strings indicate absent/exported-missing fields, not zero. See the dictionary for field-specific meanings.

| Measure | Value |
| --- | --- |
| Format | 22 UTF-8 CSV files with headers |
| CSV payload size | 4,815,250 bytes (about 4.59 MiB; excludes reports and Git storage) |
| Total CSV data records | 59,978 across all tables |
| Node records | 27,279 |
| Explicit relationship records | 32,699 |
| Constructed graph relationships | 59,121 after adding activity→transaction and activity→budget links |
| Activities / transactions / budgets | 505 / 23,423 / 2,999 |
| Organisations / countries / locations | 238 / 13 / 82 |
| Fields | Table-specific: 2–22 columns; full inventory below |
| Human-validated labels | None supplied |
| Derived hunger-match labels | 430 `keyword`, 75 `sector`; these are filter explanations, not human truth labels |
| Evaluation questions | 20: 16 data-answerable; 4 test abstention or clarification |

| Table | Rows | Fields |
| --- | ---: | ---: |
| `nodes_activities.csv` | 505 | 22 |
| `nodes_budgets.csv` | 2,999 | 8 |
| `nodes_countries.csv` | 13 | 3 |
| `nodes_emergencies.csv` | 0 | 5 |
| `nodes_locations.csv` | 82 | 8 |
| `nodes_organisations.csv` | 238 | 3 |
| `nodes_policy_markers.csv` | 0 | 2 |
| `nodes_regions.csv` | 0 | 4 |
| `nodes_sdgs.csv` | 2 | 4 |
| `nodes_sectors.csv` | 17 | 5 |
| `nodes_transactions.csv` | 23,423 | 12 |
| `rel_classified_as.csv` | 1,238 | 3 |
| `rel_contributes_to.csv` | 82 | 2 |
| `rel_located_at.csv` | 82 | 2 |
| `rel_marked_with.csv` | 0 | 3 |
| `rel_participates.csv` | 3,457 | 3 |
| `rel_related_activity.csv` | 0 | 3 |
| `rel_reports.csv` | 505 | 2 |
| `rel_responds_to.csv` | 0 | 2 |
| `rel_targets_country.csv` | 505 | 4 |
| `rel_targets_region.csv` | 0 | 3 |
| `rel_transaction_edges.csv` | 26,830 | 3 |

The graph relationship count includes 23,423 `HAS_TRANSACTION` and 2,999 `HAS_BUDGET` links constructed from foreign keys; it is not an additional set of CSV rows. Empty tables are retained to preserve the schema and demonstrate unavailable data rather than invent relationships.

## Collection and time coverage

The inherited downloader selects publisher datasets from the bulk index using publisher slugs and filename heuristics for hotspot, global and regional activity files. Organisation-only datasets are skipped; a configured exception includes `wfp-wa`. These heuristics can miss relevant data or include broader files. The parser applies activity/transaction country and hunger-theme checks afterward. This is not a representative sample of all IATI records, all humanitarian organisations or all spending.

The inherited coverage report records 2,840 activities seen, 22 duplicate IDs dropped, 1,863 rejected for geography, 450 rejected for theme (299 no signal and 151 nonmatching recognized sectors), and 505 retained. These describe the previous pipeline run; raw input files are not committed, so the full retrieval cannot be independently reproduced from the export alone.

Observed transaction dates run from **2007-04-30 to 2026-06-30**. Actual activity start dates run from **2006-06-30 to 2026-01-01**; planned end dates extend to **2030-12-31**. Future planned dates are not evidence of completed activity. Publisher year coverage differs. These dates describe record fields, not the time window of collection or a history of all revisions.

External endpoints may change and are not guaranteed to remain available. The pinned CSV snapshot supports offline evaluation even if endpoints change, but does not archive the full original XML corpus or every external codelist.

## Preprocessing and labels

1. Download selected publisher XML using `fa26/src/download.py`.
2. Parse activity identifiers, narratives, organisations, codes, countries, coordinates, dates, transactions and budgets in `fa26/src/parse_filter.py`.
3. Retain activities connected to configured hotspot countries at activity or transaction level.
4. Match recognized sector/cluster codes against hunger rules. If recognized thematic sector information is unavailable (including unspecified codes), use keyword matching over titles, descriptions and sector names. Recognized nonmatching codes can reject an activity without keyword fallback. The configured general-emergency toggle has known issues documented by the audit; do not treat the configuration flag alone as proof of behavior.
5. Drop repeated activity IDs, export node/relationship CSVs, and run organisation resolution (`fa26/src/resolve_orgs.py`). The inherited resolution report records 240→238 organisations, three merge actions and 77 names filled; this is not a full identity-validation process.
6. Preserve raw reported amounts and currencies; do not perform FX conversion. Missing transaction/budget currency can inherit the activity default during parsing. Positional transaction/budget IDs are generated within activities.
7. Pin unchanged graph CSVs for evaluation using the manifest. Reviewed graph construction retains each source relationship record instead of overwriting records sharing endpoints and relationship type.

Raw XML is expected in ignored `fa26/data/raw/`; it is **not supplied in the committed dataset**. A small XML fixture is available only for tests. Graph CSVs cannot recover every original XML field or previous version. The working graph and benchmark snapshot are separate: changing pipeline output must not silently change an existing evaluation snapshot.

## Quality, missingness and known limitations

- Publisher coverage and coding conventions differ; activity counts cannot be interpreted as relative organisational effectiveness or total aid volume.
- Most retained activities (430/505) rely on keyword matching. A matching term does not prove a hunger-focused intervention. No hand-labeled hunger validation set is included.
- 96 organisation references are name-derived (`name:`); 13 organisation names are blank in this snapshot. Identity resolution remains incomplete, and name grouping can split or conflate organisations.
- There are 5,337 negative transaction values. They may include corrections/reversals; do not silently discard them or infer their cause without source context.
- Transaction types present are incoming funds (1), outgoing commitments (2), disbursements (3) and expenditure (4). They are different measures; summing them together can double-count or mix promises and movements.
- Currency counts are 9,581 GBP transactions and 13,842 USD transactions. Keep currencies separate unless a separately specified FX method is approved.
- Budgets include 2,979 revised/indicative rows and 20 original/committed rows. Summing revisions is not the same as selecting a current budget. The benchmark specifies its own exact contract.
- Participation records can share an organisation/activity pair and carry different roles. The earlier graph overwrote 807 records; corrected construction retains them, including 402 pairs with multiple roles. Use distinct entity IDs when a question asks for unique entities.
- Empty emergency, policy-marker, region and related-activity tables do not prove that such relationships do not exist in reality.
- No external needs/outcome data or historical snapshot series is included. `last_updated` and activity dates do not reconstruct a record's revision history.
- The fixed benchmark checks answers about this export. SQL/Python agreement is not independent verification of publisher statements, raw XML extraction or humanitarian facts.

## Splits, uses and evaluation

There is no train/validation/test split and no model training in this dataset. The 20 questions form a small development benchmark. Keep the answer key, evaluator scripts, catalog, baselines and previous results outside model retrieval context; use `fa26/benchmark/prepare_model_inputs.py` to export public inputs. Create a held-out set before claiming general model quality.

Completed uses: offline data profiling, graph/schema validation, the local Gradio visualisations, synthetic Text2Cypher control-flow tests, and the SQL/structured-answer benchmark. Potential uses include controlled graph retrieval and data-quality research. George confirmed that the model API runs and Neo4j load have **not** been performed. GLM is the preferred first candidate; free-tier access and model ID still need confirmation. No budget or credits are confirmed.

Do not use this export alone for beneficiary targeting, emergency resource allocation, ranking humanitarian need or organisation quality, causal claims, total country aid estimates or historical change claims. Counts and monetary answers must state the snapshot, transaction type, currency, period and aggregation rules.

## Privacy and sensitive content

The intended content is publisher-disclosed organisational/activity information, not private project correspondence or an intentionally collected individual-level dataset. However, narratives, names and locations may contain identifying or sensitive contextual information; no exhaustive PII or re-identification audit has been completed. Public publication does not guarantee absence of sensitive data. Review narrative/location fields before any new external distribution. Humanitarian descriptions may discuss conflict, displacement, hunger or other distressing conditions; no formal content labeling is available. No private contact details, meeting links, model credentials or API outputs are added by this documentation.

## Distribution, ownership and licensing

Repository collaborators can access the committed export through the project repository. A separately approved client distribution classification and data-retention policy are **not recorded**; the PM should confirm them before expanding access. This is not a claim that every field has been approved for unrestricted redistribution.

The repository contains a GPL-3.0 license for the project code; the inherited Spaces metadata lists MIT. Those code declarations do not establish the licenses of the underlying publishers' data. Publisher-specific licenses, attribution requirements and current IATI service terms must be checked before redistribution. No paid dataset subscription is required for the offline files already committed. API/model hosting cost decisions are separate from dataset licensing and from humanitarian funding amounts.

## Maintenance and extension

Use pull requests to `dev` and include the PM/technical reviewers. Code lives under `fa26/src`, working exports under `fa26/data/graph`, review evidence under `fa26/analysis`, and evaluation artifacts under `fa26/benchmark`. The PM should assign long-term data/refresh ownership; no scheduled daily production ingestion is verified here.

For a new dataset version: preserve acquisition dates, publisher metadata/licenses, retrieval errors and raw-input hashes; run parser/quality checks; create a separately versioned snapshot and manifest; regenerate reference answers; then rerun every compared system on that same version. Do not overwrite the pinned snapshot or use `pin_snapshot.py` as a normal refresh command. Source row IDs are stable only for the exact hashed file and can change when records are reordered.

Current reproducibility checks from the repository root:

```bash
python fa26/benchmark/test_benchmark.py
python fa26/benchmark/test_model_inputs.py
python fa26/src/run_offline_notebooks.py
python fa26/tests/test_text2cypher_eval.py
```

Use the documented project virtual environment and dependencies in `fa26/requirements-george.txt`. The offline runner checks snapshot integrity and graph counts. These checks do not require API credentials or a live database.

## Items requiring confirmation

- Spark-owned Drive location and long-term data maintainer (PM).
- Publisher-specific data licensing/attribution and the approved distribution classification.
- Raw acquisition timestamp/archive and original publisher license metadata.
- Financial aggregation policy, label validation protocol, held-out evaluation design and any future live-model access.

Unknown items are deliberately labeled rather than filled with assumed approvals or personal information.
