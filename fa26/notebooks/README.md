# Notebooks

Naming: `NN_short_description_YYYY-MM-DD.ipynb` (NN = run order).

| # | Notebook | Purpose |
|---|---|---|
| 01 | 01_reproduce_summer_baseline_2026-10-15.ipynb | Offline: profile prototype CSVs, Aura budget, DQ checks, in-memory NetworkX graph and first queries |
| 02 | 02_schema_draft_2026-10-15.ipynb | Offline: Neo4j schema v0.1 (adds PROVIDED_BY / RECEIVED_BY, decoded IATI codes), Cypher DDL, 5 core queries validated on NetworkX; writes data/interim/02_schema_draft_2026-10-15.md |
| 03 | 03_text2cypher_langgraph_eval_2026-10-15.ipynb | LangGraph Text2Cypher pipeline (generate, guard, execute, compare) run across every model in `.env`; scorecard to data/processed. `DRY_RUN=True` works offline |
| 04 | 04_neo4j_aura_load_2026-10-15.ipynb | Load schema v0.1 into Neo4j Aura (network). Run once before 03 with `DRY_RUN=False` |
| 05 | `05_live_eval_20q_langgraph_2026-10-22.ipynb` | Live 20-question benchmark run: LangGraph plan/guard/execute/validate agent on Neo4j, scored by `benchmark/score.py` (Deniz). Needs `IATI_LIVE_EVAL=1`. | network |
| 06 | `06_hybrid_router_templates_2026-10-22.ipynb` | Hybrid architecture: 16 parameterised Cypher tools (`src/tools/`) + entity resolver + LLM router with free-Cypher fallback; three configs scored on the 20-question benchmark. Needs `IATI_LIVE_EVAL=1`. | network |

## Environment

Use a dedicated conda env so project packages (langgraph, openai 3.x) do not collide with other work in `base`:

```bash
conda create -n iati python=3.12 -y && conda activate iati
pip install -r fa26/requirements.txt ipykernel
python -m ipykernel install --user --name iati --display-name "Python (iati)"
```

Select the `Python (iati)` kernel in Cursor / Jupyter.

Rules: notebooks read from `data/raw` or the reference clone and write only to `data/interim` or `data/processed`. Reusable functions move to `src/`. Secrets live in `fa26/.env` (gitignored).

Notebook 04 v2 (2026-10-22) loads the pinned `benchmark/snapshot` with `source_id` on every node and relationship (Deniz review fix); set `IATI_ALLOW_DB_LOAD=1` and, when a v1 load is present, `IATI_WIPE_DB=1`.
