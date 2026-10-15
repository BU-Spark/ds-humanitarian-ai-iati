# Notebooks

Naming: `NN_short_description_YYYY-MM-DD.ipynb` (NN = run order).

| # | Notebook | Purpose |
|---|---|---|
| 01 | 01_reproduce_summer_baseline_2026-10-15.ipynb | Offline: profile prototype CSVs, Aura budget, DQ checks, in-memory NetworkX graph and first queries |
| 02 | 02_schema_draft_2026-10-15.ipynb | Offline: Neo4j schema v0.1 (adds PROVIDED_BY / RECEIVED_BY, decoded IATI codes), Cypher DDL, 5 core queries validated on NetworkX; writes data/interim/02_schema_draft_2026-10-15.md |
| 03 | 03_text2cypher_langgraph_eval_2026-10-15.ipynb | LangGraph Text2Cypher pipeline (generate, guard, execute, compare) run across every model in `.env`; scorecard to data/processed. `DRY_RUN=True` works offline |
| 04 | 04_neo4j_aura_load_2026-10-15.ipynb | Load schema v0.1 into Neo4j Aura (network). Run once before 03 with `DRY_RUN=False` |

Rules: notebooks read from `data/raw` or the reference clone and write only to `data/interim` or `data/processed`. Reusable functions move to `src/`. Secrets live in `fa26/.env` (gitignored).
