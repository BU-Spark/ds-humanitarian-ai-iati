# IATI Knowledge Graph: Baseline and Schema Findings

**Date:** 2026-10-15
**Author:** Xincheng (George) Ding
**Source notebooks:** `notebooks/01_reproduce_summer_baseline_2026-10-15.ipynb`, `notebooks/02_schema_draft_2026-10-15.ipynb`
**Data:** summer prototype graph CSVs (`reference/iati-graph-prototype/data/graph/`), Oxfam GB, Oxfam America, WFP, hunger-hotspot scope

> **Status 2026-11-17: historical record, kept as written.** Schema v0.1 and the notebook 04 loader were superseded on 2026-11-05 by Alex's `fa26/retrieval/load_neo4j.py` (schema `retrieval/schema_prototype.py`: `(Organisation)-[:PROVIDES]->(Transaction)`, typed values, no `type_label`; 58,911 relationships after merging duplicate participation rows). Notebook 03 became a Text2Cypher diagnostic, and the evaluation set is Deniz's benchmark (v1: 20 questions; v2: 100). The next steps in section 4 are therefore out of date; see `notebooks/README.md` for the current state.

## 1. Baseline reproduced (notebook 01)

- 27,279 nodes and 58,314 relationships once transaction edges are modelled. About 14% of the Aura Free limit (200k nodes / 400k relationships), so the three-publisher graph fits with room to spare.
- No duplicate primary keys and no orphan relationship rows in the prototype CSVs.
- Activities per publisher: Oxfam GB 412, WFP 82, Oxfam America 11.
- Transactions: 23,423 rows, currencies USD and GBP only, 22.8% of values are negative.
- Hunger filter basis: 430 activities matched by keyword, 75 by sector code.

## 2. Schema draft v0.1 (notebook 02)

Changes versus the prototype CSV layout:

1. `rel_transaction_edges` modelled as `(:Transaction)-[:PROVIDED_BY]->(:Organisation)` and `(:Transaction)-[:RECEIVED_BY]->(:Organisation)`. This connects the 55 organisations that were isolated in the prototype; isolated nodes are now 0.
2. IATI codes decoded onto nodes as `type_label` (transaction type 1 = Incoming Funds, 3 = Disbursement; organisation type 10 = Government, 21 = International NGO, and so on) so Text2Cypher can match on plain English.
3. Schema tables (8 node labels, 10 relationship types), Cypher DDL (8 uniqueness constraints, 6 indexes) and 5 core queries with expected results are generated into `data/interim/02_schema_draft_2026-10-15.md`.
4. Hunger relevance kept as an Activity property (`hunger_basis`), to be extended to the three-tier label (confirmed / likely / unverified).
5. Currency kept as reported; no FX conversion until the client confirms the approach. Queries group by currency.

## 3. Findings to raise with the team

**Only Oxfam GB reports Disbursement (transaction type 3).** WFP reports Incoming Funds, Outgoing Commitment and Expenditure only. The open client question "which transaction type is the default" is therefore not cosmetic: a Disbursement default removes WFP from all funding totals.

**96 of 238 organisations have no IATI organisation identifier.** Their `ref` is a `name:` prefixed string and 28 of them have no organisation type. This is the entity-resolution backlog and the reason provider totals (query Q3) are split across spelling variants of the same funder.

**Sector vocabularies differ by publisher.** WFP uses OECD DAC codes (vocabulary 1); Oxfam GB uses its own vocabulary 99. Query Q4 quantifies the effect: all 423 Oxfam activities enter the graph by keyword only, while 75 of WFP's 82 carry a hunger sector code. This is the root cause behind the hunger-filter redesign.

## 4. Next steps

- Agree with the team on where the prototype lives in the repo (`fa26/` vs root) before pushing.
- Notebook 03: hunger filter three-tier labelling and the 50-activity gold set.
- Notebook 04: Neo4j Aura load using the DDL from notebook 02 (requires network).
- Extend the 5 queries into the 20-question Graph RAG evaluation set.
