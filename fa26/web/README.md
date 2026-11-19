# IATI Atlas web

The product page for the IATI knowledge graph: a walkthrough of the engine, a library for every module, and an
answer dashboard for any question. It runs on top of `src/ask.py` (the notebook 06 router) and Neo4j.

## Run locally

```bash
conda activate iati
pip install -r fa26/web/requirements.txt
python fa26/web/build_site.py        # regenerate static/data.json from the repository
python fa26/web/server.py            # http://127.0.0.1:8080
```

Neo4j and model keys come from `fa26/.env`, as for `ask_app.py`. If they are missing or the database is paused, the
page still loads and shows the benchmark example; `POST /api/ask` answers 503.

## Files

| File | Role |
|---|---|
| `server.py` | FastAPI app: serves the page and the API |
| `views.py` | Turns one answer plus its cited rows into dashboard views (breakdowns, flow, subgraph, rows) |
| `build_site.py` | Builds `static/data.json` from the code and the snapshot (templates, tools, alias groups, checks, schema, benchmark coverage, examples) |
| `static/index.html`, `static/app.js` | The page |
| `static/vendor/cobe.js` | Globe library (cobe 2.0.1, MIT, see `cobe.LICENSE`) |
| `static/vendor/poster-libs.js` | Single-answer poster: number-flow 0.6.2 (MIT), Splitting 1.1.0 (MIT), @paper-design/shaders 0.0.82 (Apache-2.0), bundled with esbuild; notices in `THIRD_PARTY_LICENSES.txt` |

## API

`POST /api/ask` with `{"question": str, "model": "default", "route": "auto"}` returns

```json
{"answer": {"status": "answer|clarify|abstain", "facts": {"total": {"value": "3781832.44", "evidence_n": 31}},
            "tool": "...", "args": {}, "cypher": "...", "reasons": [], "model_calls": 1,
            "timings": {"plan_ms": 0, "query_ms": 0, "format_ms": 0, "total_ms": 0}},
 "views":  {"measure": "money|count", "currency": "USD", "kpis": {}, "breakdowns": {"country": [], "year": []},
            "flow": {"links": []}, "graph": {"activities": []}, "rows": [], "rows_total": 31, "reconcile": {}}}
```

`views.layout` is `dashboard` when the answer has more than one number or cites activity / transaction rows, and
`poster` otherwise (one number, a zero result, a clarification or an abstention).

Every dashboard number is an aggregation of the rows the answer cites (`views.py`); `reconcile.match` says whether
those rows add up to a single-value answer.

`GET /api/meta` returns the dataset label, the open models (`default`) and routes (`auto`), and `compare.locked`.
Other models and the `template_only` / `free_cypher_only` routes are reserved for the comparison view and answer
423 until it is opened.

## Data

`IATI_GRAPH_DIR` must point at the CSV folder that was loaded into Neo4j, because evidence ids are row numbers in
those files (default `fa26/benchmark/snapshot`, the 505-activity benchmark snapshot). For the pipeline output use
`IATI_GRAPH_DIR=fa26/data/graph IATI_GRAPH_LABEL="pipeline output"` after loading that folder with
`retrieval/load_neo4j.py --graph-dir fa26/data/graph`.

## Deploy to Fly.io

`fa26/Dockerfile`, `fa26/.dockerignore` and `fa26/fly.toml` build an image with only `src/`, `retrieval/`, `web/`
and the benchmark snapshot; `.env` is never copied. Credentials are Fly secrets.

```bash
cd fa26
python web/build_site.py                      # refresh static/data.json before each deploy
fly launch --no-deploy --copy-config --name <unique-app-name>
fly secrets set NEO4J_URI=... NEO4J_USERNAME=... NEO4J_PASSWORD=... ANTHROPIC_API_KEY=...
fly secrets set IATI_BASIC_AUTH='team:<password>'   # optional browser login
fly deploy
```

The machine stops when idle and starts on the next request. `/api/health` is the health check.

## UI guardrails

Layout rules for AI-built UI and the viewport-matrix check (`globe/ui_layout_check.mjs`, `npm run check:layout`) are in [UI_GUARDRAILS.md](UI_GUARDRAILS.md). Run the check before deploying any visual change.
