# Phase 1 findings: prototype baseline

Scope: `src/config.py`, `src/parse_filter.py`, `src/resolve_orgs.py`, `spaces/app.py`, and the CSVs in `data/graph/` (505 activities, 238 organisations, 23,423 transactions, 2,999 budgets). All numbers below were computed with pandas over those CSVs on 2026-10-21.

## 1. Three things in the data that contradict the brief

| Assumption in the brief | What the data says | Why it matters |
|---|---|---|
| `top_funders` should default to `transaction_types=("Disbursement",)` | Type 3 (Disbursement) exists only for Oxfam GB (614 rows) and the provider on every one of them is Oxfam GB itself. WFP has zero disbursements. External funders appear only as the provider on **type 1 (Incoming Funds)**: 8,310 WFP rows, 5,900 Oxfam GB rows. The prototype's own Sankey already uses type 1/11 for funders. | Default should be Incoming Funds. Disbursement answers "who did the publisher pay", not "who funded the country". |
| Oxfam GB covers ~2006-2016, WFP 2018+ | Oxfam GB activity starts run 2006-2026 (36 start in 2017, 29 in 2023, 10 in 2025). WFP activities start 2018+, but WFP **transactions** begin in 2021. Oxfam America: activities 2017-2018, transactions 2017-2020. | Year filters on activity start vs transaction date give different pictures; the WFP gap is 2018-2020 on money, not on activities. |
| Multi-country activities may be over-credited | There are none. All 505 activities have exactly one `TARGETS` row, all hotspot. Transaction-level `recipient_country` is empty on every row. `percentage` is filled on only 11 of 505 rows. | Moot today. The code would credit 100% to each country if a multi-country activity appeared (no percentage weighting), so the tool should document that. |

## 2. Graph model as written by `parse_filter.py`

Node labels and how their IDs are built:

| Label | ID / key | Built from | Notes |
|---|---|---|---|
| Activity | `iati_identifier` | `<iati-identifier>` | Duplicates across files dropped (22). Carries `publisher` (download folder slug), `hotspot_countries` (pipe-joined), `match_basis` (`sector` or `keyword`), start/end dates, status, aid/finance/flow type. |
| Organisation | `ref` | `@ref` of reporting-org, participating-org, provider-org, receiver-org | If no `@ref`, the ID is `name:<narrative text>`. Reporting org with no ref gets `unknown:<publisher>`. `resolve_orgs` then uppercases real refs, merges a `name:` ref into a real ref when normalised names match (2 merges), applies the alias table (GB-GOV-1 to XM-DAC-12-1), and fills 77 blank names from DAC/CRS codelists. |
| Country | `code` (ISO2) | `config.HOTSPOTS` only | 13 rows, with `hotspot_tier`. Non-hotspot recipient countries are never written as nodes. |
| Sector | `sector_key` = `<vocab>:<code>` | `<sector>` | `is_hunger` computed per code. |
| Transaction | `tx_id` = `<iati_identifier>#tx<N>` | position in XML | `type` is the IATI code as string (1 Incoming Funds, 2 Commitment, 3 Disbursement, 4 Expenditure). `value` is a string. `currency` falls back to activity default. |
| Budget | `budget_id` = `<iati_identifier>#b<N>` | position | `type` 1 original / 2 revised; `status` 1 indicative / 2 committed. |
| Location | `location_id` = `<iati_identifier>#loc<N>` | position | lat/lon as strings, 82 rows. |
| Region, Emergency, SDG, PolicyMarker | `<vocab>:<code>` | | Emergency and PolicyMarker are empty in this slice; SDG has 2 rows, Region 0. |

Relationships (CSV name, from, to, properties):

| CSV | Relationship | Properties |
|---|---|---|
| rel_reports | (Organisation)-[:REPORTS]->(Activity) | |
| rel_participates | (Organisation)-[:PARTICIPATES_IN]->(Activity) | `role` (1 Funding, 2 Accountable, 3 Extending, 4 Implementing) |
| rel_targets_country | (Activity)-[:TARGETS]->(Country) | `percentage`, `is_hotspot` |
| rel_classified_as | (Activity)-[:CLASSIFIED_AS]->(Sector) | `percentage` |
| rel_transaction_edges | (Organisation)-[:PROVIDED_BY / RECEIVED_BY]->(Transaction) | `edge` column holds the direction; 17,570 provider edges, 9,260 receiver edges, 5,853 transactions have no provider at all |
| rel_located_at, rel_contributes_to, rel_targets_region, rel_responds_to, rel_marked_with, rel_related_activity | as named in README | mostly empty |

Note: `nodes_transactions.csv` has an `iati_identifier` column, so `HAS_TRANSACTION` and `HAS_BUDGET` are implied by that column rather than by a separate edge file.

Minor: `config.PUBLISHERS["oxfamus"]["org_ref"]` is `US-EIN-237069110` but the data uses `US-EIN-23-7069110`. The pipeline never reads `org_ref` (publisher comes from the folder name), so nothing breaks, but the alias/entity tool should use the data value.

## 3. The six "Ask the graph" queries

| Query | Logic in `app.py` | Result today | Issue | Likely cause | Suggested fix |
|---|---|---|---|---|---|
| Activities per hotspot per publisher | Explode `hotspot_countries`, count by country x publisher | Oxfam GB 412, WFP 82, Oxfam America 11 | Works. Counts, not money. | | Keep; add `match_basis` breakdown so keyword-matched share is visible (430 of 505, 100% of both Oxfams). |
| Shared partners across publishers | Join `rel_participates` to activity publisher, keep `org_ref`s seen under more than one publisher | One row: Oxfam America [oxfamgb, oxfamus], 49 activities | Confirmed as reported. Publishers count as their own partners; nothing shared with WFP. | (a) Every publisher lists itself as a participating org (Oxfam GB role 3 on all 412, role 4 on 313, role 1 on 222; WFP roles 2 and 4 on all 82; Oxfam America role 4 on all 11). Oxfam GB also lists Oxfam America as a funder on 38 activities. (b) Excluding self-refs leaves zero shared orgs because the same funders have different IDs per publisher: ECHO is `name:EU - ECHO (EC Humanitarian Aid Dept)` for Oxfam GB and `XI-IATI-EC_ECHO` for WFP; OCHA is a `name:` ref vs `XM-OCHA-CBPF`; UNICEF is a `name:` ref vs `XM-DAC-41122`; USAID is a `name:` ref vs `XM-DAC-302`; FCDO is a provider for both (176 Oxfam GB, 256 WFP edges) but WFP's participates rows use `XM-DAC-12`. (c) Oxfam GB anonymises 60 funders as `Oxfam Donor(s)` and 140 implementers as `Oxfam Partner(s)`. | Exclude the three reporting-org refs and all Oxfam affiliates; run shared-partner matching on resolved canonical IDs (Phase 3), and treat `Oxfam Donor(s)` / `Oxfam Partner(s)` as placeholders, not orgs. Coverage note: Oxfam America has no participants except itself. |
| Top funders into a country | Activities with the country in `hotspot_countries`, then all `PROVIDED_BY` edges on their transactions, `to_numeric(value)`, sum by `org_ref` x `currency`, sort by raw total | Somalia: United States 1.20bn, Somalia 343m, Multilateral 135m, FCDO - Procurement 59m. Yemen: United States 533m, Multilateral 189m, **Oxfam GB 115m GBP**, FCDO 111m USD and 34m GBP. South Sudan: United States 915m, Oxfam GB 295m GBP, Multilateral 223m, **UN World Food Programme (WFP) 178m GBP** | See detailed checks below. | | See below. |
| Hunger sector mix per publisher | Join classified_as to sectors, keep `is_hunger == "true"`, count by publisher x sector | WFP only (75 rows) | Confirmed. | Oxfam GB codes every activity in vocabulary 99 (its own "5 Aims": A Sustainable Livelihood, Life and Security...). Oxfam America has one distinct sector on all 11 activities: vocabulary 2, code 998 (unallocated). `is_hunger` is only true for DAC/cluster vocabularies, and WFP's other rows are vocab 7/8 (SDG goal/target). No transaction-level sector codes exist for any publisher. | Keep the DAC mix for WFP and label it as such. For Oxfam, report the vocab-99 mix separately and the keyword that matched. Coverage note on every sector answer: "Oxfam GB and Oxfam America have no standard sector codes". |
| Committed budgets per year | Keep budgets with `status == "2"`, sum by publisher x year x currency | Oxfam America only (20 rows, USD) | Confirmed. | Oxfam GB (412 rows) and WFP (2,567 rows) publish every budget as status 1 (indicative). Also split on `type`: Oxfam GB and WFP use type 2 (revised), Oxfam America type 1 (original). | Drop the status filter, return `status` and `type` as columns, and let the caller decide. Note WFP's 2,567 rows are about 31 per activity (short periods), so summing by year is the right unit. |
| Activities per start year | Count by first 4 chars of `start_actual` or `start_planned` | Oxfam GB 2006-2026, Oxfam America 2017-2018, WFP 2018-2026 | Works, but see the time-coverage correction above. 372 of 412 Oxfam GB activities are status 3 (closed); WFP 32 of 82. | | Expose both activity-year and transaction-year views. |

### Top funders, the specific checks

| Check | Finding |
|---|---|
| Which transaction types are summed | All four. There is no type filter, so Incoming Funds, Commitments, Disbursements and Expenditure are added together. For Oxfam GB this double-counts money in (type 1) with the same money going out (types 3 and 4), with Oxfam GB as the provider on all 3,360 outgoing rows and on 1,066 type-1 rows (self to self, likely unrestricted funds). That is why Oxfam GB is a top "funder" into Yemen and South Sudan. The app's own Sankey filters to type 1/11; the table does not. |
| Amounts cast to numbers | Yes, `pd.to_numeric(errors="coerce")`. All 23,423 values parse; 103 are zero. |
| Negative values | Netted in silently. 5,337 rows (23%) are negative. WFP type 1: 3,077 negatives worth 9.1% of positive value, only 91 are exact reversals of an earlier row. Oxfam GB type 1: 5.5% of value. No WFP activity nets negative; one WFP funder does. The client meeting on 2026-10-09 left "refunds vs corrections vs reversals" open, so the tool should net by default and expose a `sign` breakdown rather than drop them. |
| Currencies | Grouped by currency, never converted. USD 13,842 rows, GBP 9,581. The table is sorted by raw total with GBP and USD rows interleaved, so FCDO appears twice in Yemen (111m USD, 34m GBP). Budgets are also split (USD 2,587, GBP 412). |
| Multi-country credit | Not applicable in this slice (see section 1). Code path would credit 100% per country. |
| "Multilateral" as a funder | Confirmed. `MU` ("Multilateral") and `ODM` ("Other Directed Multilateral") are WFP provider-org refs on 1,014 type-1 rows. They are pooled-funding placeholders, not organisations. Related: WFP encodes host-government contributions with DAC *recipient* codes, so "Somalia" (`XM-DAC-273`) is the second-largest funder into Somalia, and "Developing countries, unspecified" (`XM-DAC-998`) appears as a partner. |
| UK split | Confirmed. `XM-DAC-12` "United Kingdom" (WFP only: 73 provider rows, 42 participates rows) vs `XM-DAC-12-1` labelled "FCDO - Procurement" (Oxfam GB 176 and WFP 256 provider rows). The "FCDO - Procurement" name was most likely pulled from the DAC agency codelist by `resolve_orgs` pass 4 (agency 1 of donor 12), though it could also have arrived via the GB-GOV-1 alias merge; without `data/raw` or the `.bak` files this is not verifiable from the CSVs. Either way the label is misleading. The alias table only merges `GB-GOV-1` into `XM-DAC-12-1`, so donor-level and agency-level stay separate. Same pattern for Germany (`XM-DAC-5`, `XM-DAC-5-7`, `DE-1`), Japan (`XM-DAC-701`, `XM-DAC-701-2`), Canada (`XM-DAC-301`, `CA-3`), France (`XM-DAC-4`, `FR-6`), Korea (`XM-DAC-742`, `KR-GOV-010`), the EU (`XM-DAC-918-1` "EC", `XI-IATI-EC_ECHO`, `XI-IATI-EC_DEVCO`, `XI-IATI-EC_NEAR`), and WFP itself (`XM-DAC-41140` vs `name:UN World Food Programme (WFP)`, which has 262 provider rows in Oxfam GB data). |

Suggested fix for the tool: default to type 1, filter by country via `TARGETS`, exclude the reporting org from the funder list, return one row per canonical funder per currency with `n_positive`, `n_negative`, and `net`, and attach a coverage note: "no currency conversion; WFP money starts 2021; Oxfam America reports no funders".

## 4. Other things the retrieval layer should know

- Oxfam America is nearly empty: 11 activities, 20 expenditure rows (all type 4), zero provider or receiver edges, and its only participant is itself. Any Oxfam America answer about funders or partners will be `no_results`, and the coverage note should say why.
- WFP's type 2 (Commitment) and type 4 (Expenditure) totals are identical to the dollar (18,037,403,740 positive, 20,011,330 negative, 2,756 rows each). WFP mirrors every commitment as an expenditure. `funding_over_time` must not sum types 2 and 4 together for WFP.
- Organisation IDs: 96 of 238 are `name:` pseudo-refs, 13 have empty names, and `canon_ref` uppercases bare names that WFP put in the ref field (`FAROE ISLANDS`, `HOLY SEE`, `RWANDA`, `GLOBAL PARTNERSHIP FOR EDUCATION`). The fuzzy matcher in Phase 3 should treat the ref string itself as a name candidate.
- 430 of 505 activities (85%) are keyword-matched, including 100% of both Oxfams. The client flagged false positives at the 2026-10-09 meeting; every tool should return `match_basis` so the orchestrator can filter.
- Transactions carry no `recipient_country`, so country attribution always goes through the activity.
- The `.env` in the project folder points at a Neo4j Aura instance, not a local Neo4j. Phase 2's loader should work against either.
