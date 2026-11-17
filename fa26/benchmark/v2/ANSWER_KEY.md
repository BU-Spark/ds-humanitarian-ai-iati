# Benchmark v2 answer review

Evaluator-only. Answers describe the frozen export, not independently verified real-world facts. Human review is pending.

## Q01 (regression): How many retained activities does each publisher have?

Count distinct iati_identifier, grouped by publisher.

Expected status: answer.

- oxfamgb: 412 (412 source references; IDs in reference_answers.json)
- oxfamus: 11 (11 source references; IDs in reference_answers.json)
- wfp: 82 (82 source references; IDs in reference_answers.json)

## Q02 (regression): How many distinct hotspot countries does each publisher target?

Use rel_targets_country where is_hotspot=true; count distinct country_code by activity publisher.

Expected status: answer.

- oxfamgb: 12 (824 source references; IDs in reference_answers.json)
- oxfamus: 6 (22 source references; IDs in reference_answers.json)
- wfp: 13 (164 source references; IDs in reference_answers.json)

## Q03 (regression): How many retained activities target Somalia for each publisher?

Count distinct activity IDs with country_code=SO; include only publishers with matches.

Expected status: answer.

- oxfamgb: 29 (58 source references; IDs in reference_answers.json)
- oxfamus: 2 (4 source references; IDs in reference_answers.json)
- wfp: 6 (12 source references; IDs in reference_answers.json)

## Q04 (regression): Which organization references participate in activities from at least two publishers, and how many distinct activities does each participate in?

Group rel_participates by org_ref; require at least two distinct activity publishers. Deduplicate activities. Return organization refs, not names.

Expected status: answer.

- US-EIN-23-7069110: 49 (98 source references; IDs in reference_answers.json)

## Q05 (regression): How many distinct organization references occur in each participation role?

Group by raw role code, counting distinct org_ref. Repeated participation rows do not increase counts.

Expected status: answer.

- 1: 181 (2417 source references; IDs in reference_answers.json)
- 2: 1 (82 source references; IDs in reference_answers.json)
- 3: 1 (412 source references; IDs in reference_answers.json)
- 4: 4 (546 source references; IDs in reference_answers.json)

## Q06 (regression): How many activities were included by each match basis?

Group nodes_activities by match_basis; count distinct activity IDs.

Expected status: answer.

- keyword: 430 (430 source references; IDs in reference_answers.json)
- sector: 75 (75 source references; IDs in reference_answers.json)

## Q07 (regression): How many retained WFP activities have activity-level sector 1:72040?

Return count under key count. Use rel_classified_as, not text or transaction sectors.

Expected status: answer.

- count: 66 (132 source references; IDs in reference_answers.json)

## Q08 (regression): How many activities per publisher started in 2020 through 2025 inclusive?

Use start_actual when nonempty, otherwise start_planned. Require date >=2020-01-01 and <2026-01-01. Omit publishers with zero matches.

Expected status: answer.

- oxfamgb: 96 (96 source references; IDs in reference_answers.json)
- wfp: 39 (39 source references; IDs in reference_answers.json)

## Q09 (regression): What is the latest publisher-reported update calendar date among retained activities for each publisher?

Take max of first 10 characters of nonempty last_updated. This is not a download timestamp.

Expected status: answer.

- oxfamgb: 2026-05-27 (412 source references; IDs in reference_answers.json)
- oxfamus: 2020-07-23 (11 source references; IDs in reference_answers.json)
- wfp: 2026-07-06 (82 source references; IDs in reference_answers.json)

## Q10 (regression): What is the net sum of WFP incoming funds in USD dated in calendar year 2020?

Return total. Sum type=1, currency=USD, date >=2020-01-01 and <2021-01-01. Include negative adjustments; no conversion or other types.

Expected status: answer.

- total: 0 (2 source references; IDs in reference_answers.json)

## Q11 (regression): What is the net sum of Oxfam GB disbursements in GBP dated in calendar year 2020?

Return total. Sum type=3, currency=GBP, date >=2020-01-01 and <2021-01-01. Include negative adjustments.

Expected status: answer.

- total: 12260328.3000000001 (94 source references; IDs in reference_answers.json)

## Q12 (regression): What is the net sum of Oxfam America expenditure in USD across all transaction dates in this snapshot?

Return total. Sum type=4 and currency=USD for oxfamus; include negatives. This is not a current-year total.

Expected status: answer.

- total: 3781832.44 (31 source references; IDs in reference_answers.json)

## Q13 (regression): How many negative transaction values does each publisher report?

Count transaction rows with Decimal(value)<0 by activity publisher. A negative value is not automatically invalid.

Expected status: answer.

- oxfamgb: 2102 (2384 source references; IDs in reference_answers.json)
- wfp: 3235 (3308 source references; IDs in reference_answers.json)

## Q14 (regression): What is the sum of original, committed budget rows denominated in USD across all periods in this snapshot?

Return total. Sum nodes_budgets where type=1,status=2,currency=USD. This explicitly sums rows; it does not select revisions or estimate unique funding.

Expected status: answer.

- total: 3816360.25 (20 source references; IDs in reference_answers.json)

## Q15 (regression): How many distinct activities are linked to each SDG key?

Count distinct activity IDs in rel_contributes_to by sdg_key. Do not interpret a tag as evidence of achieved results.

Expected status: answer.

- 2:17: 5 (5 source references; IDs in reference_answers.json)
- 2:2: 77 (77 source references; IDs in reference_answers.json)

## Q16 (regression): How many distinct activities have at least one location node, by publisher?

Join rel_located_at to activities; count distinct activity IDs by publisher. Omit zero groups. A location is not necessarily a beneficiary location.

Expected status: answer.

- wfp: 82 (164 source references; IDs in reference_answers.json)

## Q17 (regression): Which hotspot country currently needs humanitarian aid the most?

abstain|NEEDS_DATA_MISSING|The snapshot has no validated needs measure and is not real-time. Activity counts cannot establish unmet need.

Expected status: abstain.

Reasons: NEEDS_DATA_MISSING

## Q18 (regression): What did these records say on January 1, 2020, before subsequent publisher corrections?

abstain|HISTORY_UNAVAILABLE|Only one exported snapshot is available. Transaction dates and publisher update dates cannot reconstruct earlier versions.

Expected status: abstain.

Reasons: HISTORY_UNAVAILABLE

## Q19 (regression): How much total funding did these organizations provide?

clarify|FUNDING_DEFINITION_REQUIRED,CURRENCY_BASIS_REQUIRED,PERIOD_REQUIRED|Ask which financial measure, currency/conversion basis, and period are intended. Do not sum commitments, receipts, disbursements, expenditure, or different currencies together.

Expected status: clarify.

Reasons: FUNDING_DEFINITION_REQUIRED, CURRENCY_BASIS_REQUIRED, PERIOD_REQUIRED

## Q20 (regression): Which exact original WFP XML field contained a country code instead of an activity identifier in the summer anomaly?

abstain|RAW_XML_UNAVAILABLE|The original anomaly XML is absent, and activity-reference attributes were not preserved in these exports. Request the original example.

Expected status: abstain.

Reasons: RAW_XML_UNAVAILABLE

## V2Q001 (development): How many activities are recorded in this snapshot?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: answer.

- count: 505 (505 source references; IDs in reference_answers.json)

## V2Q002 (development): How many activities are marked humanitarian?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'humanitarian': '1'}, 'links': {}, 'group': None}

Expected status: answer.

- count: 81 (81 source references; IDs in reference_answers.json)

## V2Q003 (development): How many activities are recorded as completed?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'status': '3'}, 'links': {}, 'group': None}

Expected status: answer.

- count: 404 (404 source references; IDs in reference_answers.json)

## V2Q004 (development): How many activities have no actual start date?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'start_actual': ''}, 'links': {}, 'group': None}

Expected status: answer.

- count: 1 (1 source references; IDs in reference_answers.json)

## V2Q005 (development): How many activities have no actual end date?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'end_actual': ''}, 'links': {}, 'group': None}

Expected status: answer.

- count: 101 (101 source references; IDs in reference_answers.json)

## V2Q006 (development): How many activities have a planned start date?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'start_planned__ne': ''}, 'links': {}, 'group': None}

Expected status: answer.

- count: 82 (82 source references; IDs in reference_answers.json)

## V2Q007 (development): How many activities have a planned end date?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'end_planned__ne': ''}, 'links': {}, 'group': None}

Expected status: answer.

- count: 122 (122 source references; IDs in reference_answers.json)

## V2Q008 (development): How many activities use GBP as their default currency?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'default_currency': 'GBP'}, 'links': {}, 'group': None}

Expected status: answer.

- count: 412 (412 source references; IDs in reference_answers.json)

## V2Q009 (development): How many distinct organisation references are recorded?

Evaluator-only selection: {'table': 'nodes_organisations', 'metric': 'count', 'field': 'ref', 'filters': {}, 'links': {}, 'group': None}

Expected status: answer.

- count: 238 (238 source references; IDs in reference_answers.json)

## V2Q010 (development): How many distinct named locations are recorded?

Evaluator-only selection: {'table': 'nodes_locations', 'metric': 'count', 'field': 'location_id', 'filters': {'name__ne': ''}, 'links': {}, 'group': None}

Expected status: answer.

- count: 82 (82 source references; IDs in reference_answers.json)

## V2Q011 (heldout): How many activities are in implementation?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'status': '2'}, 'links': {}, 'group': None}

Expected status: answer.

- count: 101 (101 source references; IDs in reference_answers.json)

## V2Q012 (heldout): What is the earliest recorded actual activity start date?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'min', 'field': 'start_actual', 'filters': {'start_actual__ne': ''}, 'links': {}, 'group': None}

Expected status: answer.

- date: 2006-06-30 (504 source references; IDs in reference_answers.json)

## V2Q013 (heldout): What is the latest recorded actual activity end date?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'max', 'field': 'end_actual', 'filters': {'end_actual__ne': ''}, 'links': {}, 'group': None}

Expected status: answer.

- date: 2025-12-31 (404 source references; IDs in reference_answers.json)

## V2Q014 (heldout): How many activities have no description?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'description': ''}, 'links': {}, 'group': None}

Expected status: answer.

- count: 0 (1 source references; IDs in reference_answers.json)

## V2Q015 (heldout): How many distinct transaction identifiers are recorded?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'count', 'field': 'tx_id', 'filters': {}, 'links': {}, 'group': None}

Expected status: answer.

- count: 23423 (23928 source references; IDs in reference_answers.json)

## V2Q016 (heldout): How many distinct budget identifiers are recorded?

Evaluator-only selection: {'table': 'nodes_budgets', 'metric': 'count', 'field': 'budget_id', 'filters': {}, 'links': {}, 'group': None}

Expected status: answer.

- count: 2999 (3504 source references; IDs in reference_answers.json)

## V2Q017 (heldout): How many distinct sector keys are recorded?

Evaluator-only selection: {'table': 'nodes_sectors', 'metric': 'count', 'field': 'sector_key', 'filters': {}, 'links': {}, 'group': None}

Expected status: answer.

- count: 17 (17 source references; IDs in reference_answers.json)

## V2Q018 (heldout): How many organisation references have no name?

Evaluator-only selection: {'table': 'nodes_organisations', 'metric': 'count', 'field': 'ref', 'filters': {'name': ''}, 'links': {}, 'group': None}

Expected status: answer.

- count: 13 (13 source references; IDs in reference_answers.json)

## V2Q019 (heldout): How many locations have no latitude?

Evaluator-only selection: {'table': 'nodes_locations', 'metric': 'count', 'field': 'location_id', 'filters': {'lat': ''}, 'links': {}, 'group': None}

Expected status: answer.

- count: 0 (1 source references; IDs in reference_answers.json)

## V2Q020 (heldout): How many activities have a publisher-reported update timestamp?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'last_updated__ne': ''}, 'links': {}, 'group': None}

Expected status: answer.

- count: 505 (505 source references; IDs in reference_answers.json)

## V2Q021 (development): How many Oxfam GB activities in Somalia are recorded as completed?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'publisher': 'oxfamgb', 'status': '3'}, 'links': {'rel_targets_country': {'country_code': 'SO'}}, 'group': None}

Expected status: answer.

- count: 27 (54 source references; IDs in reference_answers.json)

## V2Q022 (development): How many WFP activities in Yemen are in implementation?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'publisher': 'wfp', 'status': '2'}, 'links': {'rel_targets_country': {'country_code': 'YE'}}, 'group': None}

Expected status: answer.

- count: 4 (8 source references; IDs in reference_answers.json)

## V2Q023 (development): How many activities targeting Afghanistan have a recorded location?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'rel_targets_country': {'country_code': 'AF'}, 'rel_located_at': {}}, 'group': None}

Expected status: answer.

- count: 4 (12 source references; IDs in reference_answers.json)

## V2Q024 (development): How many activities targeting South Sudan have a funding organisation listed?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'rel_targets_country': {'country_code': 'SS'}, 'rel_participates': {'role': '1'}}, 'group': None}

Expected status: answer.

- count: 62 (501 source references; IDs in reference_answers.json)

## V2Q025 (development): How many WFP activities have both a sector classification and an implementing organisation?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'publisher': 'wfp'}, 'links': {'rel_classified_as': {}, 'rel_participates': {'role': '4'}}, 'group': None}

Expected status: answer.

- count: 82 (410 source references; IDs in reference_answers.json)

## V2Q026 (development): How many Oxfam GB activities have both a recorded location and an implementing organisation?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'publisher': 'oxfamgb'}, 'links': {'rel_located_at': {}, 'rel_participates': {'role': '4'}}, 'group': None}

Expected status: answer.

- count: 0 (3 source references; IDs in reference_answers.json)

## V2Q027 (development): How many activities targeting Yemen have an SDG link?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'rel_targets_country': {'country_code': 'YE'}, 'rel_contributes_to': {}}, 'group': None}

Expected status: answer.

- count: 8 (24 source references; IDs in reference_answers.json)

## V2Q028 (development): How many activities targeting Somalia have an actual start date before 2020?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'start_actual__ne': '', 'start_actual__lt': '2020-01-01'}, 'links': {'rel_targets_country': {'country_code': 'SO'}}, 'group': None}

Expected status: answer.

- count: 23 (46 source references; IDs in reference_answers.json)

## V2Q029 (development): How many activities with a funding organisation have an actual end date before 2022?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'end_actual__ne': '', 'end_actual__lt': '2022-01-01'}, 'links': {'rel_participates': {'role': '1'}}, 'group': None}

Expected status: answer.

- count: 229 (903 source references; IDs in reference_answers.json)

## V2Q030 (development): How many Oxfam America activities have a transaction and a budget?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'publisher': 'oxfamus'}, 'links': {'nodes_transactions': {}, 'nodes_budgets': {}}, 'group': None}

Expected status: answer.

- count: 11 (51 source references; IDs in reference_answers.json)

## V2Q031 (heldout): How many activities have both a negative transaction and an implementing organisation?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'nodes_transactions': {'value__negative': True}, 'rel_participates': {'role': '4'}}, 'group': None}

Expected status: answer.

- count: 353 (6144 source references; IDs in reference_answers.json)

## V2Q032 (heldout): How many activities have both a commitment and an expenditure transaction?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'nodes_transactions': {'type': '2'}, 'nodes_transactions#expenditure': {'type': '4'}}, 'group': None}

Expected status: answer.

- count: 115 (6015 source references; IDs in reference_answers.json)

## V2Q033 (heldout): How many activities have both incoming funds and disbursements?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'nodes_transactions': {'type': '1'}, 'nodes_transactions#disbursement': {'type': '3'}}, 'group': None}

Expected status: answer.

- count: 134 (3444 source references; IDs in reference_answers.json)

## V2Q034 (heldout): How many activities have both USD and GBP transactions?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'nodes_transactions': {'currency': 'USD'}, 'nodes_transactions#gbp': {'currency': 'GBP'}}, 'group': None}

Expected status: answer.

- count: 0 (2 source references; IDs in reference_answers.json)

## V2Q035 (heldout): How many activities with a revised budget are marked completed?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'status': '3'}, 'links': {'nodes_budgets': {'type': '2'}}, 'group': None}

Expected status: answer.

- count: 404 (1711 source references; IDs in reference_answers.json)

## V2Q036 (heldout): How many activities with a committed budget have an actual start date in 2021?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'start_actual__gte': '2021-01-01', 'start_actual__lt': '2022-01-01'}, 'links': {'nodes_budgets': {'status': '2'}}, 'group': None}

Expected status: answer.

- count: 0 (2 source references; IDs in reference_answers.json)

## V2Q037 (heldout): How many activities have a location link but no actual start date?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'start_actual': ''}, 'links': {'rel_located_at': {}}, 'group': None}

Expected status: answer.

- count: 1 (2 source references; IDs in reference_answers.json)

## V2Q038 (heldout): How many activities with sector 1:72040 also have an SDG link?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'rel_classified_as': {'sector_key': '1:72040'}, 'rel_contributes_to': {}}, 'group': None}

Expected status: answer.

- count: 66 (198 source references; IDs in reference_answers.json)

## V2Q039 (heldout): How many activities with incoming funds have no actual end date?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'end_actual': ''}, 'links': {'nodes_transactions': {'type': '1'}}, 'group': None}

Expected status: answer.

- count: 90 (9311 source references; IDs in reference_answers.json)

## V2Q040 (heldout): How many activities with an implementing organisation have a publisher-reported update in 2025?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'last_updated__gte': '2025-01-01', 'last_updated__lt': '2026-01-01'}, 'links': {'rel_participates': {'role': '4'}}, 'group': None}

Expected status: answer.

- count: 29 (69 source references; IDs in reference_answers.json)

## V2Q041 (development): How much did the UK give?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: clarify. Clarify government/agencies, transaction measure, currency and period.

Reasons: funding_scope

## V2Q042 (development): Show the total funding from Oxfam.

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: clarify. Clarify Oxfam entity, measure, currency and period.

Reasons: organisation_scope

## V2Q043 (development): How much did America contribute?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: clarify. America could mean a government or Oxfam America; clarify entity and financial scope.

Reasons: organisation_scope

## V2Q044 (development): Which Congo projects did we support?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: clarify. Clarify which Congo and the organisation meant by we.

Reasons: country_scope

## V2Q045 (development): How much funding came from the UN?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: clarify. Clarify which UN bodies and financial scope.

Reasons: organisation_scope

## V2Q046 (heldout): How much did the government spend in Yemen?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: clarify. The government is unspecified; clarify the entity and financial scope.

Reasons: organisation_scope

## V2Q047 (heldout): How much did our partners spend last year?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: clarify. Clarify our organisation, partners, absolute year, currency and measure.

Reasons: organisation_scope

## V2Q048 (heldout): How much did the ministry contribute?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: clarify. No ministry or country is identified; clarify entity and financial scope.

Reasons: organisation_scope

## V2Q049 (development): How many activities does the World Food Programme report?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'publisher': 'wfp'}, 'links': {}, 'group': None}

Expected status: answer.

- count: 82 (82 source references; IDs in reference_answers.json)

## V2Q050 (development): How many activities does Oxfam America report?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'publisher': 'oxfamus'}, 'links': {}, 'group': None}

Expected status: answer.

- count: 11 (11 source references; IDs in reference_answers.json)

## V2Q051 (development): How many activities does Oxfam Great Britain report?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {'publisher': 'oxfamgb'}, 'links': {}, 'group': None}

Expected status: answer.

- count: 412 (412 source references; IDs in reference_answers.json)

## V2Q052 (heldout): How many activities list GB-CHC-202918 as an implementing organisation?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'rel_participates': {'org_ref': 'GB-CHC-202918', 'role': '4'}}, 'group': None}

Expected status: answer.

- count: 313 (626 source references; IDs in reference_answers.json)

## V2Q053 (heldout): How many activities list GB-CHC-202918 as a funding organisation?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'rel_participates': {'org_ref': 'GB-CHC-202918', 'role': '1'}}, 'group': None}

Expected status: answer.

- count: 202 (424 source references; IDs in reference_answers.json)

## V2Q054 (heldout): How many activities list GB-CHC-202918 as an extending organisation?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'rel_participates': {'org_ref': 'GB-CHC-202918', 'role': '3'}}, 'group': None}

Expected status: answer.

- count: 412 (824 source references; IDs in reference_answers.json)

## V2Q055 (heldout): How many activities target the Democratic Republic of the Congo?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {'rel_targets_country': {'country_code': 'CD'}}, 'group': None}

Expected status: answer.

- count: 43 (86 source references; IDs in reference_answers.json)

## V2Q056 (development): What is the signed total of negative WFP incoming-fund transactions in USD?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'publisher': 'wfp', 'type': '1', 'currency': 'USD', 'value__negative': True}, 'links': {}, 'group': None}

Expected status: answer.

- total: -1744504877.00 (3127 source references; IDs in reference_answers.json)

## V2Q057 (development): What is the total of positive WFP incoming-fund transactions in USD?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'publisher': 'wfp', 'type': '1', 'currency': 'USD', 'value__positive': True}, 'links': {}, 'group': None}

Expected status: answer.

- total: 19149380438.36 (5283 source references; IDs in reference_answers.json)

## V2Q058 (development): How many zero-value transactions are recorded?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'count', 'field': 'tx_id', 'filters': {'value__zero': True}, 'links': {}, 'group': None}

Expected status: answer.

- count: 103 (163 source references; IDs in reference_answers.json)

## V2Q059 (development): What is the net GBP expenditure recorded for Oxfam GB across the snapshot?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'publisher': 'oxfamgb', 'type': '4', 'currency': 'GBP'}, 'links': {}, 'group': None}

Expected status: answer.

- total: 606355658 (3375 source references; IDs in reference_answers.json)

## V2Q060 (development): What is the net USD commitment amount recorded for WFP across the snapshot?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'publisher': 'wfp', 'type': '2', 'currency': 'USD'}, 'links': {}, 'group': None}

Expected status: answer.

- total: 18017392410.28 (2838 source references; IDs in reference_answers.json)

## V2Q061 (development): What is the net USD expenditure recorded for WFP across the snapshot?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'publisher': 'wfp', 'type': '4', 'currency': 'USD'}, 'links': {}, 'group': None}

Expected status: answer.

- total: 18017392410.28 (2838 source references; IDs in reference_answers.json)

## V2Q062 (development): How many Oxfam GB disbursement transactions have negative values?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'count', 'field': 'tx_id', 'filters': {'publisher': 'oxfamgb', 'type': '3', 'value__negative': True}, 'links': {}, 'group': None}

Expected status: answer.

- count: 65 (119 source references; IDs in reference_answers.json)

## V2Q063 (heldout): What is the net incoming-fund amount by currency across all publishers?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'type': '1'}, 'links': {}, 'group': 'currency'}

Expected status: answer.

- GBP: 582068293 (6235 source references; IDs in reference_answers.json)
- USD: 17404875561.36 (8360 source references; IDs in reference_answers.json)

## V2Q064 (heldout): What is the net expenditure by currency across all publishers?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'type': '4'}, 'links': {}, 'group': 'currency'}

Expected status: answer.

- GBP: 606355658 (3375 source references; IDs in reference_answers.json)
- USD: 18021174242.72 (2869 source references; IDs in reference_answers.json)

## V2Q065 (heldout): What is the net USD incoming-fund amount for activities targeting Somalia?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'type': '1', 'currency': 'USD'}, 'links': {'rel_targets_country': {'country_code': 'SO'}}, 'group': None}

Expected status: answer.

- total: 2059760813.20 (449 source references; IDs in reference_answers.json)

## V2Q066 (heldout): What is the net GBP disbursement amount for activities targeting Yemen?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'type': '3', 'currency': 'GBP'}, 'links': {'rel_targets_country': {'country_code': 'YE'}}, 'group': None}

Expected status: answer.

- total: 2444910.00 (117 source references; IDs in reference_answers.json)

## V2Q067 (heldout): What is the net USD expenditure dated in 2022 for activities targeting Afghanistan?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'type': '4', 'currency': 'USD', 'date__gte': '2022-01-01', 'date__lt': '2023-01-01'}, 'links': {'rel_targets_country': {'country_code': 'AF'}}, 'group': None}

Expected status: answer.

- total: 1417444812.24 (42 source references; IDs in reference_answers.json)

## V2Q068 (heldout): What is the total value of revised indicative GBP budget rows across all periods?

Evaluator-only selection: {'table': 'nodes_budgets', 'metric': 'sum', 'field': 'value', 'filters': {'type': '2', 'status': '1', 'currency': 'GBP'}, 'links': {}, 'group': None}

Expected status: answer.

- total: 735639164 (824 source references; IDs in reference_answers.json)

## V2Q069 (heldout): What is the net USD incoming-fund amount dated before 2000?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'type': '1', 'currency': 'USD', 'date__ne': '', 'date__lt': '2000-01-01'}, 'links': {}, 'group': None}

Expected status: answer.

- total: 0 (1 source references; IDs in reference_answers.json)

## V2Q070 (heldout): What is the net EUR expenditure across the snapshot?

Evaluator-only selection: {'table': 'nodes_transactions', 'metric': 'sum', 'field': 'value', 'filters': {'type': '4', 'currency': 'EUR'}, 'links': {}, 'group': None}

Expected status: answer.

- total: 0 (1 source references; IDs in reference_answers.json)

## V2Q071 (development): How many people were lifted out of hunger by these projects?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. No verified beneficiary outcome measure is present.

Reasons: outcomes_unavailable

## V2Q072 (development): Which project reduced child mortality the most?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. No comparable causal mortality outcome measurements are present.

Reasons: outcomes_unavailable

## V2Q073 (development): How much funding was lost to corruption?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. Transactions do not establish misuse or corruption.

Reasons: misuse_unavailable

## V2Q074 (development): What is the current bank balance of each implementing partner?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. The snapshot is not a bank-account ledger.

Reasons: balances_unavailable

## V2Q075 (development): What are the real names behind every Oxfam Partner(s) entry?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. Anonymised identities cannot be recovered from this export.

Reasons: identity_unavailable

## V2Q076 (heldout): Which country will have the worst hunger crisis next year?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. No validated forecast or future needs data is included.

Reasons: forecast_unavailable

## V2Q077 (heldout): Which publisher is the most effective per dollar spent?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. Comparable outcomes and a defensible effectiveness measure are absent.

Reasons: outcomes_unavailable

## V2Q078 (heldout): Give the funding total converted to euros at today’s exchange rates.

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. No current exchange-rate source is supplied.

Reasons: exchange_rates_unavailable

## V2Q079 (heldout): How much did every humanitarian organisation worldwide spend this year?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. This is a historical three-publisher slice, not complete global coverage.

Reasons: coverage_unavailable

## V2Q080 (heldout): What is the home address of the person managing each project?

Evaluator-only selection: {'table': 'nodes_activities', 'metric': 'count', 'field': 'iati_identifier', 'filters': {}, 'links': {}, 'group': None}

Expected status: abstain. Project-manager residential addresses are not present.

Reasons: personal_details_unavailable

