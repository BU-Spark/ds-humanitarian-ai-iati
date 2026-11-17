# Slide figures: sources and calculations

All raster figures are exported at 300 DPI (3840 px wide for the wide figures, so they fill a 13.3 in slide at full resolution). Each number below can be checked against the file named next to it. Paths are relative to `fa26/`.

Scores come from Deniz's benchmark scorers (v1 and `score_v2.py` for v2): overall = 70% correctness + 30% evidence F1 for answer questions; clarify/abstain questions are scored on status plus reason-code F1.

## iati_v2_development_before_after_2026-11-05.jpg

Benchmark v2, development split (40 questions), hybrid router (notebook 06), overall score per category.

| Bar | Source file | Field |
| --- | --- | --- |
| first run | `reports/benchmark_runs/2026-11-05_v2_development_06_firstrun_before_fixes.json` | `runs[].summary.overall_pct`, `runs[].by_category.<cat>.overall_pct` |
| after fix | `reports/benchmark_runs/2026-11-05_v2_development_06_hybrid.json` | same fields |

Values are rounded to whole points. Overall: Sonnet 37.0 to 94.25, GLM-5.3 66.07 to 96.75. The first-run file also holds an Opus run (46.17), which is not plotted because only Sonnet and GLM-5.3 are run going forward. The first run's evidence ids were sanitised offline before scoring (models had cited activity identifiers instead of row ids); the after-fix run needed no sanitising because the output validator enforces row ids. Same questions, same graph, same models in both runs; only the pipeline changed. The held-out split is not in this figure.

## iati_budget_table_2026-10-23.jpg

Benchmark v1 (20 questions), one full run per architecture and model.

| Column | How it is calculated | Source |
| --- | --- | --- |
| Overall score | scorer output, `Overall %` | `reports/benchmark_runs/2026-10-22_v1_free_text2cypher.md` (nb05 rows, runs ending `_0935` and `_1521`), `reports/benchmark_runs/2026-10-22_v1_hybrid.md` (nb06 rows, runs ending `_1613`) |
| Mean latency / question | scorer output, `Mean ms` / 1000, rounded to 0.1 s | same files |
| Wall time, 20 Qs | mean latency x 20 (not separately timed) | derived |
| LLM calls | one planning call per question; retries were not triggered in these runs | notebook design |
| Est. cost / run | estimate: approximate input + output tokens per planning call x the provider's list price at the time, x 20. Not metered; read it as an order of magnitude, not a bill | estimate |

"verified" marks runs whose answers matched the manual-template run (`templates_manual__neo4j_templates__2026-10-22_1613`, 100%) question by question.

## iati_pipeline_validator_2026-11-05.jpg

Architecture diagram, no measured values. It describes the router in `src/ask.py` / notebook 06: one LLM planning call, then deterministic code (21 templates in `src/tools/templates.py`, Alex's 5 tools through `src/tools/adapter.py`, guarded free Cypher, output validation in `src/tools/contract.py`, at most 2 retries). The caption's "within three points" refers to the development scores above (94.25 vs 96.75).

## iati_status_map_2026-10-23.png / .pdf / .svg

Team status as of 2026-10-23, drawn by hand from the state of the notebooks and branches on that date. Numbers inside boxes are copied from: graph load counts (loader output, 27,279 nodes / 59,121 relationship rows), nb05 and nb06 scores (the two v1 files above), nb07 cross-check (`reports/benchmark_runs/2026-11-05_07_crosscheck.csv`, 18/18). **This map is outdated**: since then the adapter, schema switch, benchmark v2 and the Ask tab are done. Do not use it for final slides without redrawing.
