# Questions and answer key

These are reference answers for the pinned exported data, not verified real-world humanitarian facts.

## Q01: How many retained activities does each publisher have?

Category: organizations.

Calculation contract: Count distinct iati_identifier, grouped by publisher.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| oxfamgb | 412 | 412 |
| oxfamus | 11 | 11 |
| wfp | 82 | 82 |

## Q02: How many distinct hotspot countries does each publisher target?

Category: geography.

Calculation contract: Use rel_targets_country where is_hotspot=true; count distinct country_code by activity publisher.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| oxfamgb | 12 | 824 |
| oxfamus | 6 | 22 |
| wfp | 13 | 164 |

## Q03: How many retained activities target Somalia for each publisher?

Category: geography.

Calculation contract: Count distinct activity IDs with country_code=SO; include only publishers with matches.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| oxfamgb | 29 | 58 |
| oxfamus | 2 | 4 |
| wfp | 6 | 12 |

## Q04: Which organization references participate in activities from at least two publishers, and how many distinct activities does each participate in?

Category: organizations.

Calculation contract: Group rel_participates by org_ref; require at least two distinct activity publishers. Deduplicate activities. Return organization refs, not names.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| US-EIN-23-7069110 | 49 | 98 |

## Q05: How many distinct organization references occur in each participation role?

Category: organizations.

Calculation contract: Group by raw role code, counting distinct org_ref. Repeated participation rows do not increase counts.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| 1 | 181 | 2417 |
| 2 | 1 | 82 |
| 3 | 1 | 412 |
| 4 | 4 | 546 |

## Q06: How many activities were included by each match basis?

Category: quality.

Calculation contract: Group nodes_activities by match_basis; count distinct activity IDs.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| keyword | 430 | 430 |
| sector | 75 | 75 |

## Q07: How many retained WFP activities have activity-level sector 1:72040?

Category: sectors.

Calculation contract: Return count under key count. Use rel_classified_as, not text or transaction sectors.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| count | 66 | 132 |

## Q08: How many activities per publisher started in 2020 through 2025 inclusive?

Category: time.

Calculation contract: Use start_actual when nonempty, otherwise start_planned. Require date >=2020-01-01 and <2026-01-01. Omit publishers with zero matches.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| oxfamgb | 96 | 96 |
| wfp | 39 | 39 |

## Q09: What is the latest publisher-reported update calendar date among retained activities for each publisher?

Category: time.

Calculation contract: Take max of first 10 characters of nonempty last_updated. This is not a download timestamp.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| oxfamgb | 2026-05-27 | 412 |
| oxfamus | 2020-07-23 | 11 |
| wfp | 2026-07-06 | 82 |

## Q10: What is the net sum of WFP incoming funds in USD dated in calendar year 2020?

Category: funding.

Calculation contract: Return total. Sum type=1, currency=USD, date >=2020-01-01 and <2021-01-01. Include negative adjustments; no conversion or other types.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| total | 0 | 2 |

## Q11: What is the net sum of Oxfam GB disbursements in GBP dated in calendar year 2020?

Category: funding.

Calculation contract: Return total. Sum type=3, currency=GBP, date >=2020-01-01 and <2021-01-01. Include negative adjustments.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| total | 12260328.3000000001 | 94 |

## Q12: What is the net sum of Oxfam America expenditure in USD across all transaction dates in this snapshot?

Category: funding.

Calculation contract: Return total. Sum type=4 and currency=USD for oxfamus; include negatives. This is not a current-year total.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| total | 3781832.44 | 31 |

## Q13: How many negative transaction values does each publisher report?

Category: quality.

Calculation contract: Count transaction rows with Decimal(value)<0 by activity publisher. A negative value is not automatically invalid.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| oxfamgb | 2102 | 2384 |
| wfp | 3235 | 3308 |

## Q14: What is the sum of original, committed budget rows denominated in USD across all periods in this snapshot?

Category: funding.

Calculation contract: Return total. Sum nodes_budgets where type=1,status=2,currency=USD. This explicitly sums rows; it does not select revisions or estimate unique funding.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| total | 3816360.25 | 20 |

## Q15: How many distinct activities are linked to each SDG key?

Category: sectors.

Calculation contract: Count distinct activity IDs in rel_contributes_to by sdg_key. Do not interpret a tag as evidence of achieved results.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| 2:17 | 5 | 5 |
| 2:2 | 77 | 77 |

## Q16: How many distinct activities have at least one location node, by publisher?

Category: geography.

Calculation contract: Join rel_located_at to activities; count distinct activity IDs by publisher. Omit zero groups. A location is not necessarily a beneficiary location.

| Answer key | Value | Contributing source rows |
| --- | ---: | ---: |
| wfp | 82 | 164 |

## Q17: Which hotspot country currently needs humanitarian aid the most?

Category: unsupported.

Calculation contract: abstain|NEEDS_DATA_MISSING|The snapshot has no validated needs measure and is not real-time. Activity counts cannot establish unmet need.

Expected response: **abstain**. The snapshot has no validated needs measure and is not real-time. Activity counts cannot establish unmet need.

## Q18: What did these records say on January 1, 2020, before subsequent publisher corrections?

Category: unsupported.

Calculation contract: abstain|HISTORY_UNAVAILABLE|Only one exported snapshot is available. Transaction dates and publisher update dates cannot reconstruct earlier versions.

Expected response: **abstain**. Only one exported snapshot is available. Transaction dates and publisher update dates cannot reconstruct earlier versions.

## Q19: How much total funding did these organizations provide?

Category: ambiguous.

Calculation contract: clarify|FUNDING_DEFINITION_REQUIRED,CURRENCY_BASIS_REQUIRED,PERIOD_REQUIRED|Ask which financial measure, currency/conversion basis, and period are intended. Do not sum commitments, receipts, disbursements, expenditure, or different currencies together.

Expected response: **clarify**. Ask which financial measure, currency/conversion basis, and period are intended. Do not sum commitments, receipts, disbursements, expenditure, or different currencies together.

## Q20: Which exact original WFP XML field contained a country code instead of an activity identifier in the summer anomaly?

Category: unsupported.

Calculation contract: abstain|RAW_XML_UNAVAILABLE|The original anomaly XML is absent, and activity-reference attributes were not preserved in these exports. Request the original example.

Expected response: **abstain**. The original anomaly XML is absent, and activity-reference attributes were not preserved in these exports. Request the original example.
