# Benchmark v2: 100 questions

Start with **review.ipynb** for the question inventory, ten review examples, recorded
validation and run instructions. This work belongs to Deniz on `denizbranch`.

## What changed

V2 keeps Q01–Q20 as regression questions on the unchanged 22-CSV snapshot. It adds
80 questions: 20 direct, 20 two-step, 15 organisation/ambiguity, 15 financial and
10 limitations questions. IDs V2Q001–V2Q080 are stable within this version.

| Split | Questions | Use |
| --- | ---: | --- |
| regression | 20 | Compare with v1 using its original public calculation contracts |
| development | 40 | Inspect failures and improve the workflows |
| heldout | 40 | First evaluation before tuning on these questions |

The snapshot is referenced from `../snapshot/`; no data was copied or changed.
The benchmark is about this exported historical slice, not current global aid facts.

## Run locally

Python 3.10+ standard library only. From the repository root:

```bash
python fa26/benchmark/v2/build.py
python fa26/benchmark/v2/test_v2.py
python fa26/benchmark/test_benchmark.py
python fa26/benchmark/test_model_inputs.py
python fa26/benchmark/v2/export_inputs.py /tmp/iati-v2-development --split development
python fa26/benchmark/v2/score_v2.py /path/to/submission.json --split development --output /tmp/iati-v2-results
```

Export destinations must be new directories outside the benchmark folder. Use
`--split regression`, `heldout` or `all` explicitly when appropriate. No command
here calls a model, connects to Neo4j or spends credits. Existing v1 commands work
unchanged. Live results are ignored by Git by default.

## Inputs and outputs

The existing answer shape remains: `id`, `status`, `facts` with `value` and
`evidence`, `reasons`, and optional `latency_ms`. V2 adds required `benchmark_id`
and `split` alongside `snapshot_id` and `run_name`; optional `cost_usd` is a measured
whole-run cost, not an estimate. Unknown or duplicate IDs, incorrect metadata,
invalid source IDs and negative/non-finite latency or cost are rejected. Missing
answers count as zero. A submission must contain only IDs from the chosen split.

New model-facing questions contain **only ID and question text**. Output-key rules,
source citation conventions and a global reason vocabulary are provided separately.
Evaluator contracts, expected statuses, value types and reference answers never
enter the exported bundle. Original v1 public contracts remain for comparability.

`reference_answers.json` contains every contributing source row ID. Evidence is
scored with set F1 and correct numerical facts carry 70% weight, evidence 30%, as in
v1. Clarification/abstention uses expected status and reason-code F1. These checks
do not grade free-text explanations. A global reason vocabulary is necessary for
this deterministic scorer; paraphrased prose is not automatically mapped to codes.

Monetary sums use Decimal, with v1's one-cent comparison tolerance. Currencies and
transaction types remain separate. Count questions use distinct identifiers unless
explicitly asking for rows. Zero results cite the searched table manifests; date
extrema cite the considered rows. This full-evidence requirement is stricter than
showing a few example citations to a user.

Reports include overall, category and split scores, correctness, evidence,
clarification/abstention performance, latency sample counts and reported cost.
Always report original 20 and new splits separately. Do not describe the synthetic
100% SQL reference baseline as a model result.

## Verification and limitations

`engine.py` independently selects rows in Python and SQLite and compares all values
and evidence sets. SQL uses EXISTS for relationship restrictions to avoid join
multiplication; Python uses per-activity relationship indexes. Monetary aggregation
uses Decimal in both engines to avoid float loss. Both consume the same evaluator
specifications, so agreement validates execution, not whether the wording and
contracts are the best interpretation. **Deniz reports review with George is complete and approved.**

`review_examples.json` identifies ten initial cases, two per new category. The
remaining cases use the same checked evaluator operations. The tests also cover
invalid submissions, source IDs, missing evidence, ambiguity, currency grouping,
zero matches, organisation roles and preservation of v1 scoring.

Held-out questions and answers are present in this repository for evaluator review.
They are not access-controlled secrets. George/Alex should receive only the
exported development bundle during tuning. John can review the held-out answers
without sharing them with workflow authors. Record prior exposure before claiming
held-out performance. Even without exposure, several questions reuse data and
reasoning concepts from v1; this is a harder development benchmark, not a fully
independent estimate of general-world performance. Role-count variants share one
split. Report family-level failures rather than treating variants as independent.

## Review and team handoff

- Deniz: review the wording, generate the data-backed keys, maintain scorer/tests.
- Ask John to review the ten examples first, then all new contracts and limitations.
  This is a proposed review request, not a claim that John has accepted or completed it.
- George/Alex: run each workflow on the exported split, using the identical snapshot,
  model/version, prompt policy and retry budget for comparisons. Notebooks 05 and 06 now accept exported v2 bundles; see the adapter instructions below.
- Record model IDs, workflow commit, prompt/config, token use, timing and actual cost.
  Keep the evaluator checkout and answer key out of the agent's tools and context.
- Freeze the first held-out run before adding templates based on its failures.
- Confirm API access and spending limits before live runs. No live runs are included.

## Files

- `catalog_v2.py`, `evaluator_catalog.json`: private evaluation definitions and splits.
- `questions.json`, `splits.json`, `submission_template.json`: full inventory/templates.
- `reference_answers.json`, `ANSWER_KEY.md`: generated values, evidence and rationale.
- `engine.py`, `build.py`: independent calculations and deterministic regeneration.
- `score_v2.py`, `export_inputs.py`: scoring and isolated model-input export.
- `test_v2.py`: regression and failure checks.
- `results/offline_baseline.json`: synthetic reference report, no live model results.
- `review.ipynb`, `review_examples.json`: review entry point and initial ten cases.

## Notebook 05/06 adapter

Deniz reports that he and George reviewed v2 and agreed to proceed. Live model
comparison is still pending. The adapter reads only an exported public bundle;
it does not import evaluator definitions into either model prompt.

From the repository root:

```bash
python fa26/benchmark/v2/export_inputs.py /tmp/iati-v2-development --split development
```

Before running notebook 05 or 06, set these in the notebook kernel (a new first
code cell or your shell environment before starting Jupyter):

```python
import os
os.environ['IATI_BENCHMARK_BUNDLE'] = '/tmp/iati-v2-development'
os.environ['IATI_LIVE_EVAL'] = '0'  # fake model, no API or Neo4j calls
```

Run All. Notebook 05 generates queries; notebook 06 runs the existing hybrid
router. Both preserve the bundle's benchmark ID, snapshot ID, split and question
IDs in their submissions and invoke `score_v2.py` after generation. V2 reports
are under `fa26/benchmark/v2/results/live/`; submissions and diagnostic CSVs are
under `fa26/data/processed/`. Run IDs include microseconds to avoid collisions.

With an authorized budget, exact accessible models and the matching verified graph,
set `IATI_LIVE_EVAL=1` to use the existing provider/database configuration. This
adapter checks the bundle's CSV hashes; it does not independently establish the
identity of the remote graph. Confirm that the remote graph is the same snapshot
and uses notebook 04 source IDs before interpreting live scores.

To return to v1, remove `IATI_BENCHMARK_BUNDLE` from the kernel environment and
rerun from the top. Externally supplied flags take precedence over `.env`.
Notebook 06's manual question-ID mapping is v1-only and is skipped for every v2
split, including regression. V2 uses the unchanged template catalog plus the LLM
router/free-query fallback, not mappings invented from held-out answer keys.
Automatic mixing with previous notebook 05 outputs has been removed; compare
specific matching submissions explicitly with the v2 scorer when both runs finish.

Offline adapter verification (requires notebook dependencies):

```bash
IATI_TEST_NOTEBOOKS=1 python fa26/tests/test_benchmark_bundle.py
```

This exercises both notebooks in v1 and all four v2 selections using fake models,
checks bundle metadata/tampering and confirms malformed responses stop after the
retry limit. Fake outputs test integration, not model quality. Scoring runs in a
separate evaluator subprocess after model generation; the notebooks give models
no filesystem tool or access to the evaluator answer key.
