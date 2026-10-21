# Reviewed notebook workflow

**Start here:** [00_review_and_next_steps.ipynb](00_review_and_next_steps.ipynb). It brings together the review, recorded results, 20-question list, file locations, access/cost decisions, next steps. Run All reads local files by default; it makes no API calls and does not load a database. Re-running checks is an explicit offline opt-in.

The overview is the main reading notebook. Notebooks 01–04 remain focused working notebooks; reusable functions and tests stay in `src/`, `tests/` and `benchmark/` so they can be tested without copying code between notebooks.



The overview is the current review; historical draft reports and personal presentation notes are not part of this handoff.

| Notebook | Purpose | Verified here |
| --- | --- | --- |
| 00 | Review, recorded evidence, questions and next steps | Offline overview; local-file reads by default |
| 01 | Dataset profile and graph before transaction party edges | Offline code cells; 27,279 nodes / 32,291 edges |
| 02 | Shared code labels, full graph, schema and five diagnostics | Offline code cells; 59,121 edges; source roles preserved |
| 03 | Text2Cypher generate/guard/execute/compare | Synthetic controls only; defaults to offline |
| 04 | Source-record-preserving Neo4j import | Loader contract tested with a mock; no live database load |

## Run offline

From the repository root:

```bash
python -m pip install -r fa26/requirements-george.txt
python fa26/src/run_offline_notebooks.py
python fa26/tests/test_text2cypher_eval.py
python benchmark/test_benchmark.py
python benchmark/test_model_inputs.py
```

The runner uses the pinned `benchmark/snapshot` after hash verification. It writes
ignored logs and results under `fa26/data/processed` and schema output under
`fa26/data/interim`. No `.env`, API key, reference clone or database is needed.
Notebooks can also be run manually from the repository root or a descendant.
Top-level dependencies are pinned to tested versions; transitive packages are not locked.

## Future live runs (not part of the offline review)

**Free-tier first; no confirmed budget or credits.** George confirmed that the APIs and Neo4j load have not run. GLM is the client-preferred first pilot; Kimi and Qwen are optional comparisons. The exact model/version and architecture remain open. Confirm exact model availability and free quotas before testing; request separate explicit approval before any paid run. Brent has not committed to paying API costs. Provider names in `.env.example` do not prove access or approved spending; model IDs and credentials are intentionally blank. Memory/reranking were discussed but are not implemented in the current evaluation notebook.

API/hosting costs are separate from humanitarian funding calculations. See the overview for both decision lists.

Supply credentials securely; `.env` is optional and ignored. Set `IATI_LIVE_EVAL=1`
only for notebook 03 with exact model IDs, endpoints and a dedicated
`NEO4J_READ_USERNAME` / `NEO4J_READ_PASSWORD` account whose server permissions are
read-only. Read routing and a regex guard do not create those permissions.

Notebook 04 needs separate loader credentials and `IATI_ALLOW_DB_LOAD=1`.
Use a new isolated database, verify every mapped node/relationship count and the
snapshot identity, then connect the read-only account. Do not run it against an
existing import; old endpoint-only relationships are not migrated or deleted.

Synthetic model names start with `fake/` and must never enter a live model ranking.
Notebook 03's five diagnostic question IDs differ from benchmark Q01–Q20.
The legacy positive-only funding diagnostic is not a net-funding comparison.
Use [benchmark instructions](../../benchmark/README.md) and its public-input
exporter for the separate 20-question evidence and abstention evaluation.
