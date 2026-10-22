# Graph and evaluation review

The main team/PM review is [00_review_and_next_steps.ipynb](../notebooks/00_review_and_next_steps.ipynb). It contains the full findings, file map, recorded evidence, 20-question list, reproduction commands and next steps. Keep detailed updates there.

## Current team status — October 22, 2026

Based on George's team update; the live artifacts and comparison table have not yet been independently reviewed here.

- George confirmed the `source_id` relationship merge fix and adopted the loader as notebook 04 v2. He adopted the 20-question benchmark and `score.py` as his evaluation standard.
- **George reports that the model APIs and Neo4j load have run.** Aura contains **27,279 nodes, 59,121 relationships and 0 isolated nodes**, using the reviewed loader.
- His notebook 03 has live diagnostic scorecards for **Opus, Sonnet, GLM-5.3 and GLM-4.7-Flash**. Exact Claude model IDs and run artifacts are pending review; these diagnostics are separate from the 20-question benchmark.
- The **20-question benchmark is in progress** through a LangGraph agent that writes the shared submission format. George will provide the comparison table; no final benchmark ranking is available yet.
- George reports verified **Z.ai access with model `glm-5.3`**, at **under USD 0.10 per 20-question pass**. This is a reported run cost, not a guaranteed price, free-tier entitlement or authorization for further spending.
- A PR to `denizbranch` is expected for value-based comparison in `text2cypher_eval.py`: exact-row comparison can reject correct results when a returned column is renamed. It is pending, not merged.
- Memory/reranking validation and a broader API budget are not established by this update.

## Completed offline work

- Preserved 807 previously overwritten participation records, including 402 organisation/activity pairs with different roles.
- Corrected graph: 27,279 nodes and 59,121 relationship records.
- Fixed failed-query scoring, retry handling, timing, provider endpoint checks and secret-bearing diagnostics.
- Three offline notebooks complete; 26 automated tests pass. Synthetic controls are not real model evaluations.
- Prepared a public-input exporter that excludes evaluator answers and previous results.

## Evidence and implementation

- Original findings: `fa26/analysis/george_review_results.json`; reproduce with `fa26/analysis/review_george.py`.
- Reviewed validation: `fa26/analysis/george_offline_validation.json`.
- Setup and commands: [notebooks README](../notebooks/README.md).
- Full benchmark: [benchmark README](../benchmark/README.md).
- Screenshots: [figures](../reports/figures/README.md); these show existing application views, not model results.

## Next steps

1. Review George's comparison table, structured submissions and live scorecards when shared. Keep five-question diagnostics separate from the 20-question benchmark.
2. Review the incoming value-based comparison PR, including renamed-column cases, duplicate rows and failure handling, before merging.
3. Record exact model IDs, snapshot identity, prompts, retry settings, latency, token usage and observed costs with the comparison.
4. Confirm the loaded graph's snapshot and server-enforced read-only evaluation permissions from the live configuration.
5. Agree on humanitarian funding-data definitions: transaction types, currencies, promised/actual amounts, dates and negative corrections.
6. Update the client slides with the reported live progress; add model rankings only after reviewing the completed results.
