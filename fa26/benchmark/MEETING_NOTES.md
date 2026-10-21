# Update for the team

**My task:** Create the 20-question evaluation set from our next-steps slide, with an answer key and a shared way to compare responses.

**Completed:** 20 questions, a pinned copy of the existing data, calculated reference answers with source records, an independent SQL check, and a scoring script. Sixteen questions have answers in the data; four require an explanation of missing data or clarification.

**Example questions and findings:**

- How many activities does each publisher have? Oxfam GB: 412; Oxfam America: 11; WFP: 82.
- How many target Somalia? Oxfam GB: 29; Oxfam America: 2; WFP: 6.
- How many WFP activities have activity-level sector `1:72040`? 66.
- How much Oxfam America expenditure in USD is in the snapshot? USD 3,781,832.44, across all included dates, for transaction type 4 only.
- Which country needs aid most? The dataset cannot answer that without a valid needs measure.
- What is total funding? The system should ask for the financial measure, currency basis, and period first.

**Verification results:** The separate Python and SQL implementations agree across all 20 cases, including expected behavior for the four limitation questions. The SQL baseline scores 100%; deliberately wrong answers score 0%. Correct values with no evidence score 76% overall (100% correctness, 0% evidence, 100% limitation handling). These are synthetic checks of the benchmark, not model performance results. See [comparison](results/comparison.md).

**What teammates can do next:** Run their models/agents against the same questions and snapshot, fill the submission template, and use the script to compare results. Preserve source IDs when importing into Neo4j so evidence can be checked. If the hunger filter changes the dataset, create a new benchmark version and rerun every compared model on the same new snapshot.

**What we have not established:** Whether the exported records are complete or factually correct in the real world; whether any LLM performs well; whether the client accepts our initial score weights. The answer key is verified against this export, not against original XML or external needs information.

**Short team message:** “The 20-question set and verified answer key are ready. Send model outputs in the shared format and we can compare correctness, evidence, and handling of missing information.”

## Current team status — October 21, 2026

- George confirmed that he has **not yet run the model APIs or the Neo4j load**. His work provides the implementation; completed validation is offline only.
- **GLM is the client's preferred candidate** for the first model pilot. The exact model/version, provider endpoint and access limits still need confirmation.
- Kimi and Qwen remain optional comparison candidates, not equal-priority commitments.
- Start with verified free-tier access. No API budget, credits or paid access are confirmed; do not assume Brent will cover charges.
- Memory and reranking remain proposed architecture work, not implemented or evaluated features.
- No live model results, model ranking or live database validation are claimed.

**Immediate next step:** confirm GLM access, then use the public-input bundle for a controlled pilot. See `fa26/notebooks/00_review_and_next_steps.ipynb` for the consolidated review.
