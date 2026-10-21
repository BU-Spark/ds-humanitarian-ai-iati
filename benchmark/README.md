# IATI question set and answer key

This folder implements Deniz's 20-question evaluation task from slide 7 of the October 9 client meeting. It checks whether a model or agent answers questions correctly **about one fixed exported dataset**. It does not validate the publishers' original records or measure real-world humanitarian need.

Start with [QUESTIONS.md](QUESTIONS.md) and [ANSWER_KEY.md](ANSWER_KEY.md). The questions cover organizations, geography, sectors, time, explicitly defined financial measures, and cases requiring clarification or an explanation that the data is insufficient. Sixteen questions have data-derived answers; four assess appropriate limits.

## What is included

| File | Purpose |
| --- | --- |
| `snapshot/` and `manifest.json` | Unchanged copies of all 22 source graph CSVs; SHA-256 hashes and source Git commit |
| `questions.json` | Public questions and calculation contracts, without reference answers |
| `submission_template.json` | Blank JSON response file for a model/agent run |
| `reference.py`, `reference_answers.json` | Evaluator-side Python/Decimal calculations and complete supporting row IDs |
| `sql_baseline.py` | Independently written SQLite calculations; never loads the answer key |
| `score.py` | Model-independent structured-answer scoring and comparison output |
| `inspect_source.py` | Resolves citations to exported records, including original activity/transaction IDs |
| `runs/` | SQL baseline and two explicitly synthetic controls; no live model results |
| `results/` | Comparison table and question-level scores |
| `MEETING_NOTES.md` | Short explanation and findings to present to the team |

The prototype's parser, filters, graph exports, and app were not edited. Everything runs offline with Python 3.10+ and the standard library. No API keys, pip dependencies, Neo4j instance, or model subscription are required.

## Run it

From the repository root, with a working Python installation:

```sh
python benchmark/reference.py
python benchmark/sql_baseline.py
python benchmark/make_examples.py
python benchmark/test_benchmark.py
python benchmark/score.py benchmark/runs/sqlite_baseline.json benchmark/runs/deliberately_wrong.json benchmark/runs/no_evidence.json
```

`pin_snapshot.py` was run once to initialize the committed snapshot. Do not run it during normal evaluation: it intentionally refuses to overwrite the manifest. To evaluate a changed dataset, create a separately versioned benchmark with a new snapshot, recalculate all answers, and rerun all compared systems on that same version. Do not compare scores across changed snapshots as though the inputs were identical.

On this Windows workstation, the working bundled executable is:

```powershell
& 'C:\Users\deniz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' benchmark\test_benchmark.py
```

The default Windows Store `python.exe` alias was unavailable during this work. Other machines can use their normal Python executable.

## Give teammates these inputs

Give the model/agent the pinned data (or a Neo4j import preserving these same rows and citation IDs), `questions.json`, and the response instructions below. Keep `ANSWER_KEY.md`, `reference_answers.json`, `reference.py`, `catalog.py`, the SQL baseline, generated runs, results, and tests **outside the model's retrieval context**. The private catalog contains expected behavior for unanswerable questions.

Use this instruction with every model:

> Answer the supplied questions using only this snapshot and their calculation contracts. Return structured JSON following the submission format. Each fact must contain its value and the complete set of source row IDs used to calculate it. Do not invent missing data. Use `abstain` when the required information is unavailable and `clarify` when the question needs a definition. For those statuses, return an empty facts object and applicable reason codes. Do not combine currencies or financial transaction types unless a contract explicitly says to. Return amounts as decimal strings.

For an initial manual experiment, the team can fill the JSON after inspecting a model's response. Record that manual adaptation in the run name and preserve the original response separately. Do not silently correct a model's answer during adaptation. A live adapter can later produce the same JSON directly.

## Submission format

Copy `submission_template.json`, set a unique `run_name`, and fill its answers. Keep its exact `snapshot_id`. Each question uses this shape:

```json
{
  "id": "Q01",
  "status": "answer",
  "facts": {
    "publisher_slug": {
      "value": "integer or decimal string",
      "evidence": ["nodes_activities.csv:row:123"]
    }
  },
  "reasons": [],
  "latency_ms": null
}
```

This is a format illustration, not a correct Q01 answer. Fact keys follow the question contracts: publisher slugs, organization refs, role codes, match-basis labels, SDG keys, or the explicit scalar keys `count` and `total`. Omit zero groups where the question says to. Empty `facts` with status `answer` is not an abstention.

For an abstention or clarification, use `facts: {}` and one or more of these reason codes: `NEEDS_DATA_MISSING`, `HISTORY_UNAVAILABLE`, `FUNDING_DEFINITION_REQUIRED`, `CURRENCY_BASIS_REQUIRED`, `PERIOD_REQUIRED`, `RAW_XML_UNAVAILABLE`. Describe the reason in an optional `explanation` field. Extra prose is not automatically scored; review it manually for unsupported claims.

`latency_ms` is optional (null means not measured). For live systems, measure from sending the question until the complete answer arrives, including retrieval; document model, agent version, hardware, and warm/cold conditions in your run records. SQLite baseline timings cover query/evidence construction after data loading and are **not comparable to end-to-end LLM latency**. A summary includes how many questions supplied timing; it does not impute missing measurements.

```sh
python benchmark/score.py path/to/george_glm_run.json path/to/another_run.json --output benchmark/results/model_comparison
```

The scorer writes `comparison.csv`, `comparison.md`, and `details.json`. Missing questions score zero; duplicate/unknown question IDs, mismatched snapshots, malformed evidence lists, and invalid latency values reject a submission. Output files in the chosen directory are replaced on rerun, so choose a different directory to preserve older comparisons.

## Evidence and traceability

`nodes_transactions.csv:row:1` means the first **logical CSV data record**, excluding the header. It is not a physical text line: quoted descriptions may contain newlines. Together with the snapshot hash, this is an unambiguous locator. The record itself contains its original exported `tx_id`, `iati_identifier`, `org_ref`, or other applicable key.

```sh
python benchmark/inspect_source.py nodes_transactions.csv:row:1
python benchmark/inspect_source.py manifest:nodes_transactions.csv
```

For an aggregate, reference evidence includes every contributing row, plus activity rows needed for publisher joins. For an empty result, `manifest:filename.csv` identifies the complete hashed table searched. Q10 is an example: no matching WFP incoming USD transactions dated in 2020 are present. This means no matches in the snapshot, not proof that WFP received no funds that year.

The evidence score is deliberately strict: it measures complete computational lineage, not whether a natural-language answer has one plausible citation. Systems may attach a provenance artifact containing those IDs instead of displaying thousands of citations to a user; the adapter must expand it into the JSON evidence list. A human should separately assess presentation and citation usability.

## Scoring

- A fact is correct when its key and value match. Integer values and dates must match exactly; money uses absolute tolerance of 0.01 in the specified currency. `NaN`, infinity, booleans, and nonnumeric text cannot pass numeric checks. Decimal arithmetic preserves the precision of exported strings.
- Per-question factual correctness is `2 * correct facts / (submitted facts + expected facts)`. Missing and extra facts reduce the score; abstaining on an answerable question scores zero.
- For each fact with a correct value, evidence F1 is `2 * shared source IDs / (submitted source IDs + expected source IDs)`. Wrong values receive zero evidence credit. Scores are averaged over the union of fact keys. Repeated citation IDs are deduplicated; invented or irrelevant IDs reduce precision.
- For the four limitation questions, the expected `abstain`/`clarify` status must match and no factual claims may be supplied. Correct reason-code F1 determines the score. Saying only “I don't know” without a relevant reason does not pass.
- An answerable question scores 70% factual correctness and 30% evidence F1. A limitation question scores its behavior result. Overall is the mean across all 20 questions. The table also reports correctness, evidence, and behavior separately so a composite cannot hide a weak dimension.

The scoring weights and tolerances are initial team choices, not client-approved acceptance thresholds. This is a small development benchmark, not a statistical estimate of general model performance. Once the team tunes against it, build an unseen evaluation set for independent assessment.

## Limitations

The source is the summer prototype's filtered export: 505 activities and 23,423 transactions. Filtering errors, missing publishers/years, unresolved identities, and repeated participation rows are inherited. The benchmark uses distinct IDs where requested; it does not repair the dataset. It sums signed transaction values only within explicitly selected types, currencies, and periods. Country questions count activity-country relationships rather than estimating country funding. The budget question explicitly sums original committed rows and does not claim to select the currently applicable budget revision.

The baseline uses hand-written SQL and fixed policy rules for the four limitation questions. It is not an AI model and has no measured natural-language understanding. A 100% baseline shows agreement with the separately implemented Python calculations and scorer, not independent verification of humanitarian facts. No live model comparison has been performed.
