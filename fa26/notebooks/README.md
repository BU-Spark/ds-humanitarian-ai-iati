# Notebooks

Naming: `NN_short_description_YYYY-MM-DD.ipynb` (NN = run order).

| # | Notebook | Purpose |
|---|---|---|
| 01 | 01_reproduce_summer_baseline_2026-10-15.ipynb | Offline: profile prototype CSVs, Aura budget, DQ checks, in-memory NetworkX graph and first queries |

Rules: notebooks read from `data/raw` or the reference clone and write only to `data/interim` or `data/processed`. Reusable functions move to `src/`. Secrets live in `fa26/.env` (gitignored).
