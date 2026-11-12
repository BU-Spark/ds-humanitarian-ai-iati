# Notebooks

Naming: `NN_short_description_YYYY-MM-DD.ipynb` (NN = run order).

| # | Notebook | Purpose |
|---|---|---|
| 01 | 01_reproduce_summer_baseline_2026-10-15.ipynb | Offline: profile prototype CSVs, Aura budget, DQ checks, in-memory NetworkX graph and first queries |
| 02 | 02_schema_draft_2026-10-15.ipynb | Offline: Neo4j schema v0.1 (adds PROVIDED_BY / RECEIVED_BY, decoded IATI codes), Cypher DDL, 5 core queries validated on NetworkX; writes data/interim/02_schema_draft_2026-10-15.md |
| 03 | 03_text2cypher_langgraph_eval_2026-10-15.ipynb | Development diagnostic only: LangGraph Text2Cypher pipeline on 5 hand-written questions, every model in `.env`. Not the team benchmark; formal scores are in 05 and 06. `DRY_RUN=True` works offline |
| 04 | 04_neo4j_aura_load_2026-10-15.ipynb | Retired 2026-11-05. The graph is now loaded by `fa26/retrieval/load_neo4j.py` (team schema, `fa26/retrieval/schema_prototype.py`): `python fa26/retrieval/load_neo4j.py --reset --force --env fa26/.env --graph-dir fa26/benchmark/snapshot`, then `validate_graph.py` |
| 05 | `05_live_eval_20q_langgraph_2026-10-22.ipynb` | Live 20-question benchmark run: LangGraph plan/guard/execute/validate agent on Neo4j, scored by `benchmark/score.py` (Deniz). Needs `IATI_LIVE_EVAL=1`. | network |
| 06 | `06_hybrid_router_templates_2026-10-22.ipynb` | Hybrid architecture: 21 parameterised Cypher templates (`src/tools/templates.py`) + Alex's 5 retrieval tools via `src/tools/adapter.py` + entity resolver + LLM router with free-Cypher fallback; scored on benchmark v1 (20 questions) or a v2 bundle (`IATI_BENCHMARK_BUNDLE=<exported dir>`). Needs `IATI_LIVE_EVAL=1`. | network |
| 07 | `07_tool_layers_crosscheck_2026-10-22.ipynb` | Tool layers side by side: Aura schema vs Alex's `fa26/retrieval` expectations, cross-implementation agreement (Cypher template vs pandas/Decimal on the snapshot vs Alex's findings), entity-resolution effect, coverage matrix. Pandas half runs offline. | optional network |

## Choosing which models run (05 and 06)

Do not edit `.env` to select models. Both live notebooks have a switch in their model-registry cell
(05: cell 8, 06: cell 14), first lines:

```python
RUN_MODELS = ["anthropic/claude-sonnet-4-6", "zai/glm-5.3"]   # None = every model registered in .env
```

A name must already be registered in `.env` (`ANTHROPIC_EVAL_MODELS`, `ZAI_MODEL`, ...); unknown names
raise. One-off override without editing the notebook:

```bash
IATI_RUN_MODELS="zai/glm-5.3" jupyter nbconvert --execute ...
```

## Benchmark v2 runs (Deniz)

```bash
python fa26/benchmark/v2/export_inputs.py ~/Desktop/IATI/_bundles/v2-development-<date> --split development
IATI_BENCHMARK_BUNDLE=<that dir> python fa26/scripts/smoke_v2_development.py      # templates only, no LLM
IATI_BENCHMARK_BUNDLE=<that dir> caffeinate -dims jupyter nbconvert --to notebook --execute --inplace fa26/notebooks/06_hybrid_router_templates_2026-10-22.ipynb
```

Tune only on the development split; the first held-out run is frozen (see `benchmark/v2/README.md`).

## Ask tab (the engine as a module)

`fa26/src/ask.py` is notebook 06's router as an importable engine (`Engine().ask(question)` returns the
benchmark answer shape plus tool, arguments, query, latency; `evidence_rows()` returns the cited snapshot rows).
`fa26/ask_app.py` is a minimal Gradio page on top of it:

```bash
conda activate iati && pip install gradio
python fa26/ask_app.py                         # http://127.0.0.1:7861, model anthropic/claude-sonnet-4-6
IATI_ASK_MODEL=zai/glm-5.3 python fa26/ask_app.py
```

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
