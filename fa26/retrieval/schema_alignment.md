# Schema v0.1 alignment: retrieval layer vs George's loader and templates

Written 2026-11-01 for the 10/23 next step "connect the query tools to the
LangGraph orchestrator once schema v0.1 is agreed". Compares
`schema_prototype.py` + `load_neo4j.py` (branch `alex`) with notebook 04,
`src/tools/templates.py` and `src/tools/resolver.py` (branch `george`, same
on `denizbranch`). Nothing on George's branch was changed.

## Decisions needed

| # | Question | Retrieval layer today | George's v0.1 | Recommendation |
|---|---|---|---|---|
| 1 | Funding edge direction | `(Organisation)-[:PROVIDES]->(Transaction)` | `(Transaction)-[:PROVIDED_BY]->(Organisation)` | Take George's. It matches the CSV `edge` column and `RECEIVED_BY`, so both funding edges leave the transaction. The retrieval tools change three MATCH lines. |
| 2 | Value and date types | `value` float, `date` a Neo4j date, `is_hotspot` boolean | all strings; sums use an added `value_num` | Typed values. Text2Cypher writes `t.date.year` and `t.value > 0` naturally; string dates make it compare text. Keep `value_num` as an alias if the templates rely on it. |
| 3 | Source IDs | **Added today:** node `source_id`, relationship `source_ids` (list), same `<file>.csv:row:<n>` format | node and relationship `source_id`; relationships MERGEd on it | Agree on one property name. The list exists because the retrieval loader MERGEs `PARTICIPATES_IN` on (org, activity, role): 222 exact-duplicate CSV rows (cleaned data) become one edge that still cites every row. George's v0.1 keeps one edge per row, so duplicate edges inflate any `count(p)`. |
| 4 | Negative transactions | Own category: `amount` (positive), `adjustments` (negative), `net` | Signed sum (`top_funders`, `transaction_total`, `funding_over_time` in templates.py) | Follow the client decision of 2026-10-23: report adjustments separately. The three templates need the same split. |
| 5 | Duplicate organisations | Merged at query time via `entities.SAME_AS` (64 pairs, 41 groups) | Raw `o.ref`; templates.py:145 notes a funder can appear several times | Keep refs raw in the graph, canonicalise in queries. Either load SAME_AS as `(:Organisation)-[:SAME_AS]->(:Organisation)` edges so templates can use them, or have the router call the retrieval tools for funder and partner questions. |
| 6 | Government vs agency | Separate rows; `resolve_entity` returns `ids` + `relation` so the caller decides | `resolver.py` groups e.g. UK_GOV = FCDO + DFID as candidates | Same open question was put to the client on 10/23 ("include agencies by default?"). Keep the choice explicit in the answer either way. |
| 7 | Extra labels | Emergency, Region, PolicyMarker + their edges | Omitted on purpose | Harmless: all are empty in the cleaned data (0 rows). Keep them loadable in case the filter scope widens. |
| 8 | `Organisation.publisher` | Set after load from REPORTS | Not set | Needed by the retrieval tools; cheap to add to v0.1. |
| 9 | Hunger-filter provenance | `match_basis`, `confidence`, `review_status`, `match_terms` loaded as-is | `hunger_basis` derived column | Load Devansh's columns unchanged so answers can say *why* an activity is in the graph (client asked for flagging over silent dropping). |

## Plugging the four tools into the router

The router (notebook 06) prompts with `tool_catalog()` and runs
`run_tool(run_cypher, name, args)`, which expects every row as
`{key, value, evidence}`. The retrieval tools are Python callables that
resolve free text themselves and return named columns. Two ways to connect:

1. **Dispatch to callables (preferred).** `run_tool` checks
   `tools.TOOLS` (retrieval) before the template registry; a small adapter
   turns each row into `key` (funder / period / organisation), `value`
   (`amount`, with `adjustments` and `net` as extra facts) and `evidence`
   (the `source_ids` of the contributing rows). Requires the tools to return
   `source_ids`; today they return `activity_ids`.
2. **Port as templates.** Rewrite the Cypher as pure templates. Loses
   free-text resolution and SAME_AS merging unless 5 above is done in the graph.

Either way, after the switch to the cleaned data (439 activities instead of
505) the benchmark answers change, so it needs a new version on the cleaned
snapshot, as the benchmark README already says.
