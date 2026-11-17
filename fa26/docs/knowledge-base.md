# Knowledge base: Milestone 1

A searchable knowledge base (KB) over the activities the pipeline keeps,
with citations and CSV export. It is the first step of the RAG system, and
it works without any LLM.

Code: [`kb/`](../kb/). Tests: [`tests/test_kb.py`](../tests/test_kb.py).

## Why it is built this way

From the client meeting:
- **Brent:** keep the KB to IATI for now. IATI and the ONE Data Observatory want to query *and export* data, and he liked the idea of querying IATI's related documents.
- **Sylvan:** start with a small proof of concept and grow it, measuring how more data affects performance.
- **Amy:** build the RAG before the graph is final, so it shows what the graph needs, and work in milestones.

So Milestone 1 uses **keyword search in SQLite (FTS5, BM25 ranking)**:
- It needs no model and no server, and gives the same results every run.
- The whole KB is one file that can be copied, queried with any SQLite tool, or exported.
- It is the baseline that later steps (embeddings, more data) are measured against.

| Milestone | Adds | Status |
|---|---|---|
| 1 | Keyword search over the 439 kept activities, citations, export, evaluation | **this** |
| 2 | IATI's linked documents: about 38 useful WFP pages (Country Strategic Plans, Annual Country Reports). Oxfam publishes none. | next |
| 3 | Grow the data and measure: all hotspot activities before the hunger filter, WFP results and indicators, embedding search | planned |
| 4 | Connect to the Neo4j graph once its schema settles | planned |

## Use

From `fa26/`, after the pipeline has produced `data/graph/`:

```bash
python -m kb.build                                   # -> data/kb/kb.sqlite (not in git)
python -m kb.search "cash vouchers for food" --country YE
python -m kb.search "school meals" --publisher wfp --limit 20 --export hits.csv
python -m kb.search "malnutrition" --min-confidence medium --json
python -m kb.evaluate --show-misses
```

- Every hit cites its **IATI identifier**, with publisher, country, status, dates, funders, implementers, the hunger filter's `confidence`, and a snippet with the matched words in `[brackets]`.
- `--country` takes a hotspot code or name. `--min-confidence medium` leaves out the filter's low-confidence activities.
- A question becomes an OR of its content words: question words such as "which" or "projects" are dropped, and words in `"double quotes"` stay together as a phrase. Punctuation can't break the query.

## What is searched

One entry per activity, with these fields searched (weight in brackets):

| Field | Source | Weight |
|---|---|---|
| Title | `nodes_activities.csv` | 5 |
| Countries and publisher | hotspot countries | 2 |
| Organisations | participating organisations, without the "Oxfam Partner(s)" / "Oxfam Donor(s)" placeholders | 1.5 |
| Sectors | standard sector names only (DAC, clusters, SDG). Oxfam's own categories are left out, for the same reason the hunger filter ignores them | 1.5 |
| Description | `nodes_activities.csv`, cut at 2,000 characters (12 of 439 are cut) | 1 |

Words are matched by stem ("vouchers" finds "voucher") and without accents ("securite" finds "sécurité").

## Evaluation

[`kb/eval_questions.json`](../kb/eval_questions.json) has 12 questions about what projects *do*, which Deniz's benchmark doesn't cover. Each one lists the activities that should be found.

- **How the answers were judged:** candidates came from broad patterns over the text and organisations, independent of the search engine, plus WFP's activity-type codes. Each candidate was then read and judged against the question's notes.
- **Who judged them:** drafts by Claude, to be checked by Devansh, as with the held-out hunger sample.
- **Patterns alone weren't enough:** they missed several relevant WFP nutrition records, which is why the codes were also used.

Baseline on 17 November 2026, with each question's country filter applied:

| Kind | Questions | P@10 | R@20 | MRR |
|---|---|---|---|---|
| Topic | 5 | 0.76 | 0.53 | 1.00 |
| Topic + country | 4 | 0.75 | 0.82 | 0.88 |
| Organisation (ECHO) | 1 | 1.00 | 0.61 | 1.00 |
| Cross-language | 2 | 0.25 | 0.50 | 0.17 |
| **All** | **12** | **0.69** | **0.63** | **0.82** |

P@10 is the share of the top 10 that is relevant. R@20 is the share of relevant activities found in the top 20. MRR is the average of 1 / rank of the first relevant hit. Without country filters, the overall P@10 drops to 0.62.

What the baseline shows:
- **English keywords miss French records.** "School meals in Haiti" finds none of its 4 activities, because they are WFP records in French ("repas scolaires").
  - The Lebanon question only reaches full recall because the country filter leaves 12 activities.
- **Jargon hides relevant activities.** "Communities building assets for food or cash" finds 33% of 39, because many records say "FFA", "ACL" or "cash for work".
- **Different words for the same group.** Pregnant and breastfeeding women appear as "PLW/G", "PLWG", "nursing mothers" and "femmes enceintes ou allaitantes".

These are the cases to measure embedding search on in Milestone 3.

To keep the evaluation honest:
- Change the search, then rerun `python -m kb.evaluate`, and report both numbers.
- If you tune on these 12 questions, write a fresh set before claiming an improvement.

## Known limitations

- Many WFP donors are named in French ("Etats-Unis", "Allemagne"), so "United States" does not find them.
- WFP's EU funding appears only on transactions, which are not in the KB yet. The ECHO question covers Oxfam GB only.
- The KB is rebuilt from scratch each time (it takes under a second). It is not updated in place.
