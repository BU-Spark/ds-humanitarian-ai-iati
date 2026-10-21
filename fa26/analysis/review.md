# Offline graph and evaluation review

The main team/PM review is [00_review_and_next_steps.ipynb](../notebooks/00_review_and_next_steps.ipynb). It contains the full findings, file map, recorded evidence, 20-question list, reproduction commands and next steps. Keep detailed updates there.

## Current team status — October 21, 2026

- George confirmed that he has **not yet run the model APIs or the Neo4j load**. His work provides the implementation; completed validation is offline only.
- **GLM is the client's preferred candidate** for the first model pilot. The exact model/version, provider endpoint and access limits still need confirmation.
- Kimi and Qwen remain optional comparison candidates, not equal-priority commitments.
- Start with verified free-tier access. No API budget, credits or paid access are confirmed; do not assume Brent will cover charges.
- Memory and reranking remain proposed architecture work, not implemented or evaluated features.
- No live model results, model ranking or live database validation are claimed.

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

## Next decisions

1. Confirm GLM free-tier access, an exact model ID, endpoint and usage limits.
2. Agree on humanitarian funding-data definitions separately from API costs: transaction types, currencies, promised/actual amounts, dates, history and negative corrections.
3. Validate an isolated evaluation database and server-enforced read-only evaluation account.
4. Run a small GLM pilot, then the same 20 questions with full source evidence. Only expand comparisons after reviewing results and available access.
5. Keep memory/reranking as explicitly scoped follow-up work. Do not claim a completed live pipeline yet.
