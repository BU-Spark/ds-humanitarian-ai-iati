# Slide figures: sources and calculations

The JPG figures are 300 DPI, 3840 px wide (12.8 in); the status map PNG is 300 DPI, 2068 x 2320 px. Paths are relative to `fa26/`. Three figures are drawn by scripts, so every number on them is read from a file rather than typed in:

- `scripts/make_v1_table_figure.py` draws `iati_budget_table_2026-10-23.jpg` and writes `iati_budget_table_2026-10-23_values.csv` (the values it used) in this folder.
- `scripts/make_v2_figures.py` draws `iati_v2_development_before_after_2026-11-05.jpg` and `iati_pipeline_validator_2026-11-05.jpg`.

Some inputs are per-question eval CSVs in `data/processed/`, which is gitignored: they exist only on the machine that ran the evaluations (George's), so a fresh clone cannot re-check those particular numbers. Each case is marked below.

Scoring (Deniz's benchmark, `benchmark/README.md` and `benchmark/v2/README.md`): an answerable question scores 70% value correctness + 30% evidence F1; a clarify / abstain question scores its expected status and reason codes. Benchmark v2 has 100 questions in three splits: `regression` (20, the v1 questions), `development` (40, for improving the workflow) and `heldout` (40, first evaluation before tuning; the first run is frozen before any template is added from its failures). Rounding: the v2 bar chart rounds half up to whole points; caption numbers and the pipeline figure show the stored values (two decimals); the v1 table shows one decimal.

## iati_v2_development_before_after_2026-11-05.jpg

Benchmark v2 development split (40 questions), hybrid router (notebook 06), overall score per category, Sonnet 4.6 and GLM-5.3.

| Bar | Source | Field |
| --- | --- | --- |
| first run | `reports/benchmark_runs/2026-11-05_v2_development_06_firstrun_before_fixes.json` (runs in order Opus, Sonnet, GLM-5.3) | `runs[].summary.overall_pct`, `runs[].by_category.<cat>.overall_pct` |
| after fixes | `reports/benchmark_runs/2026-11-05_v2_development_06_hybrid.json` (runs in order Sonnet, GLM-5.3) | same fields, plus `runs[].questions[]` for the caption |

- Overall: Sonnet 37.0 to 94.25, GLM-5.3 66.07 to 96.75. The first-run file also holds an Opus run (46.17), not plotted because only Sonnet and GLM-5.3 are run going forward.
- After the fixes, all 30 answerable questions have correctness 1.0 for both models. Remaining loss: evidence F1 0.5 on V2Q010 and V2Q026 (both models); clarify / abstain questions scored 0 on V2Q042 and V2Q043 (Sonnet) and V2Q042 (GLM-5.3).
- "After fixes" is the third development run. The intermediate run scored Sonnet 91.42, GLM-5.3 95.92 (`benchmark/v2/results/live/06_development_2026-11-05_190236_752716/comparison.json`, gitignored).
- Between the first and third run the router prompt, the templates and the output checks changed (see the git log for 2026-11-05); the questions, the pinned snapshot and the two models did not.
- The first run's submissions were rewritten offline before scoring (models had cited activity identifiers instead of row ids; files ending `_evsanitised` in `data/processed`). The rewriting script was not saved, so that step cannot be reproduced.
- The heldout split is not in this figure.

## iati_pipeline_validator_2026-11-05.jpg

Architecture of the LangGraph router in notebook 06 (also packaged as `src/ask.py`): one planner node that calls the LLM, then 21 templates (`src/tools/templates.py`), Alex's 5 retrieval tools through `src/tools/adapter.py`, or guarded free Cypher, then output checks (`src/tools/contract.py`). A failed check returns the error to the planner, at most 2 retries, so a question takes 1 to 3 LLM calls.

Numbers in the caption:

- Calls on the heldout run: Sonnet 65, GLM-5.3 44 for 40 questions (sum of `model_calls` in `data/processed/06_hybrid_eval_2026-11-05_204405_996398.csv`, gitignored).
- Development split overall: Sonnet 94.25, GLM-5.3 96.75 (`2026-11-05_v2_development_06_hybrid.json`), 2.50 points apart.
- Heldout split overall: Sonnet 72.59, GLM-5.3 88.94 (`2026-11-05_v2_heldout_06_hybrid_FROZEN.json`), 16.35 points apart. The output checks do not make the two models equal on unseen questions.

## iati_budget_table_2026-10-23.jpg

Benchmark v1 (20 questions), one run per architecture and model. An earlier version had an estimated cost column whose source was not recorded; it was removed.

| Column | How it is calculated | Source |
| --- | --- | --- |
| Overall score, Correctness, Evidence F1 | scorer output `Overall %`, `Correctness %`, `Evidence F1 %` | `reports/benchmark_runs/2026-10-22_v1_free_text2cypher.md` (nb05 rows: Opus and Sonnet run `_0935`, GLM-5.3 run `_1521`); `reports/benchmark_runs/2026-10-22_v1_hybrid.md` (nb06 rows, run `_1613`) |
| Mean latency / question | scorer output `Mean ms` / 1000, rounded to 0.1 s | same files |
| LLM calls | sum of `model_calls` over the 20 questions; 0 retries in every case shown | nb06: `data/processed/06_hybrid_eval_2026-10-22_1613.csv`; nb05 GLM-5.3: `data/processed/05_live_eval_2026-10-22_1521.csv` (both gitignored). The nb05 Opus and Sonnet runs have no per-question CSV, so the figure shows "not recorded" |

Opus and Sonnet each have two nb05 runs that day (`_0933` and `_0935`); the figure uses the later one. Bold rows are the two runs at 100% overall.

## iati_status_map_2026-10-23.png / .pdf / .svg

Team status as of 2026-10-23, drawn by hand from the notebooks and branches on that date. Numbers in the boxes:

- 27,279 nodes / 59,121 relationships / 0 isolated: the graph counts expected by notebook 04 v2 (cell 0) for the load of the pinned snapshot at the time. 59,121 counts graph relationships, not CSV rows (the snapshot's relationship CSVs hold 32,699 rows; transactions and budgets add their HAS_TRANSACTION / HAS_BUDGET edges). The current graph, loaded by Alex's loader, has 58,911 relationships because duplicate participation rows are merged.
- nb05 and nb06 scores: the two v1 files above.
- Cross-check 18/18: `data/interim/07_crosscheck_2026-10-22_2043.csv` (gitignored; the 2026-11-05 rerun in `reports/benchmark_runs/2026-11-05_07_crosscheck.csv` is also 18/18).

**This map is outdated**: since then the adapter, the schema switch, benchmark v2 and the Ask tab are done. Redraw it before using it in final slides.
