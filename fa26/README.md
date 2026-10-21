# Fall 2026 — Humanitarian AI Today / IATI knowledge graph

All semester implementation, review, evaluation, figures and project documents live in this folder.

**Start with [the review notebook](notebooks/00_review_and_next_steps.ipynb).** It explains the completed offline work, results, file locations and next steps. GLM is the preferred first model pilot; model API calls and the Neo4j load have not run. No paid access or credits are confirmed.

## Folder map

| Folder | Contents |
| --- | --- |
| [notebooks/](notebooks/README.md) | Overview and focused graph/schema/evaluation/load notebooks |
| [src/](src/) | Pipeline, shared code labels, offline runner and evaluation helpers |
| [tests/](tests/) | Parser fixtures and evaluation regression tests |
| [spaces/](spaces/README.md) | Gradio application |
| [data/graph/](data/graph/) | Working graph CSVs and pipeline reports |
| [benchmark/](benchmark/README.md) | Pinned CSV snapshot, 20 questions, evaluator, baseline, controls and public-input exporter |
| [analysis/](analysis/review.md) | Review summary, audits and recorded validation evidence |
| [reports/figures/](reports/figures/README.md) | Application screenshots with filters and interpretation notes |
| [docs/dataset-documentation/](docs/dataset-documentation/README.md) | Completed dataset documentation and data dictionary |
| [docs/](docs/) | Project brief and supporting documentation |

`data/raw/`, `data/interim/` and `data/processed/` are local/ignored workflow outputs. Credentials stay in local environment configuration, never Git. Root-level README, license, ignore rules and the dataset-documentation navigation folder are repository-wide files.

## Set up and check

Commands below run **from the repository root**, using Python 3.12:

```bash
python -m pip install -r fa26/spaces/requirements.txt -r fa26/requirements-george.txt
python fa26/src/run_offline_notebooks.py
python fa26/tests/test_text2cypher_eval.py
python fa26/benchmark/test_benchmark.py
python fa26/benchmark/test_model_inputs.py
```

Use a project virtual environment. The offline runner executes notebooks 01–03 and writes local logs; the tests do not require API credentials or Neo4j. Read [notebook instructions](notebooks/README.md) before any future live run. Notebook 04 is not included in offline execution.

## Dataset and evaluation

The dataset contains 505 retained activities from Oxfam GB, Oxfam America and WFP. It is a filtered prototype export, not a complete measure of humanitarian aid. See [dataset documentation](docs/dataset-documentation/DATASETDOC-fa26.md) for measured counts, date coverage, preprocessing, limitations and licensing questions.

The working graph and evaluation snapshot have different purposes. Do not regenerate a pinned snapshot in place or expose the answer key to evaluated models. See [benchmark instructions](benchmark/README.md) for submission/scoring rules and the public-input exporter.
