# Update 2026-11-19: Atlas web app and ablation experiment 1 (cache)

## Atlas web app (`fa26/web/`)

- FastAPI service around the deployed engine (`src/ask.py`): `/api/ask` returns the answer plus a dashboard built only from the cited evidence rows. Live at https://iati-atlas-george.fly.dev (Fly.io, region ewr, Neo4j on Aura).
- Data shown by the app is the pinned benchmark snapshot (505 activities). `IATI_GRAPH_DIR` must point at the same CSVs that are loaded in Neo4j; see `web/README.md`.
- Hero globe rebuilt with three.js (land points from Natural Earth via world-atlas; licences in `web/static/vendor/THIRD_PARTY_LICENSES.txt`).
- UI guardrail for AI-built layout: `web/UI_GUARDRAILS.md` and `web/globe/ui_layout_check.mjs` (11 screen sizes, no text overlap, no sideways scroll, every visible button clickable). All 11 pass.
- Engine changes are opt-in and off by default: stage timings, token counts, path taken (tool / free_cypher / clarify / abstain), and a plan/result cache.

## Ablation experiment 1: cache

Script: `fa26/scripts/ablation.py`. Splits: regression (20) and development (40); heldout not used. Each model and config ran twice; the cache is shared across the two runs, so run 1 is cold and run 2 is warm. Source files: `ablation/2026-11-19_2030/summary.md` (per run), `question_scores.csv` (per question), `log.jsonl` (per call).

| Model | Regression overall | Development overall | Mean latency reg / dev | Warm cache latency |
|---|---|---|---|---|
| Sonnet 4.6 | 92.5 (both runs) | 99.25 (both runs) | 2.5 s / 3.1 s | about 1 ms, 0 model calls |
| Opus 4.6 | 90.0 (both runs) | 99.25 (both runs) | 3.2 s / 4.7 s | about 1 ms, 0 model calls |
| GLM-5.3 | 100 / 95 | 99.25 / 99.25 | 10.7 to 12.3 s / 5.3 to 5.6 s | about 1 ms, 0 model calls |

Findings:

1. The cache does not change answers: warm scores equal cold scores for every model. A hit costs no model call and no tokens.
2. It only hits on the exact same question text, so in real use it helps repeated and example questions, not paraphrases. Before using it in the deployed app it needs a size limit and must be cleared whenever the graph data is reloaded.
3. Sonnet is the best default: same accuracy as Opus or better, fastest, stable across runs. GLM-5.3 had the single best regression run but is unstable and has long latency tails (one Q19 call took 148 s).
4. Remaining point losses are the same across models, so they are not model problems:
   - V2Q010 and V2Q026: correct values, evidence F1 0.5 for every model. Same template each time; check the template's evidence scope against the benchmark's evidence definition.
   - Q17 and Q19: right status (abstain / clarify) but the reason code does not match.
5. Only 2 retries in 720 asks, so the next planned experiment (deterministic Cypher repair) has little to fix on this benchmark. Few-shot examples aimed at the reason codes look more useful.

Next: experiment 3 (lexical few-shot) or 2 (repair), then decide what goes into the deployed app.
