"""Public questions and explicit calculation contracts, without answers."""

QUESTIONS = [
    ('Q01', 'organizations', 'How many retained activities does each publisher have?', 'integer', 'Count distinct iati_identifier, grouped by publisher.'),
    ('Q02', 'geography', 'How many distinct hotspot countries does each publisher target?', 'integer', 'Use rel_targets_country where is_hotspot=true; count distinct country_code by activity publisher.'),
    ('Q03', 'geography', 'How many retained activities target Somalia for each publisher?', 'integer', 'Count distinct activity IDs with country_code=SO; include only publishers with matches.'),
    ('Q04', 'organizations', 'Which organization references participate in activities from at least two publishers, and how many distinct activities does each participate in?', 'integer', 'Group rel_participates by org_ref; require at least two distinct activity publishers. Deduplicate activities. Return organization refs, not names.'),
    ('Q05', 'organizations', 'How many distinct organization references occur in each participation role?', 'integer', 'Group by raw role code, counting distinct org_ref. Repeated participation rows do not increase counts.'),
    ('Q06', 'quality', 'How many activities were included by each match basis?', 'integer', 'Group nodes_activities by match_basis; count distinct activity IDs.'),
    ('Q07', 'sectors', 'How many retained WFP activities have activity-level sector 1:72040?', 'integer', 'Return count under key count. Use rel_classified_as, not text or transaction sectors.'),
    ('Q08', 'time', 'How many activities per publisher started in 2020 through 2025 inclusive?', 'integer', 'Use start_actual when nonempty, otherwise start_planned. Require date >=2020-01-01 and <2026-01-01. Omit publishers with zero matches.'),
    ('Q09', 'time', 'What is the latest publisher-reported update calendar date among retained activities for each publisher?', 'date', 'Take max of first 10 characters of nonempty last_updated. This is not a download timestamp.'),
    ('Q10', 'funding', 'What is the net sum of WFP incoming funds in USD dated in calendar year 2020?', 'decimal', 'Return total. Sum type=1, currency=USD, date >=2020-01-01 and <2021-01-01. Include negative adjustments; no conversion or other types.'),
    ('Q11', 'funding', 'What is the net sum of Oxfam GB disbursements in GBP dated in calendar year 2020?', 'decimal', 'Return total. Sum type=3, currency=GBP, date >=2020-01-01 and <2021-01-01. Include negative adjustments.'),
    ('Q12', 'funding', 'What is the net sum of Oxfam America expenditure in USD across all transaction dates in this snapshot?', 'decimal', 'Return total. Sum type=4 and currency=USD for oxfamus; include negatives. This is not a current-year total.'),
    ('Q13', 'quality', 'How many negative transaction values does each publisher report?', 'integer', 'Count transaction rows with Decimal(value)<0 by activity publisher. A negative value is not automatically invalid.'),
    ('Q14', 'funding', 'What is the sum of original, committed budget rows denominated in USD across all periods in this snapshot?', 'decimal', 'Return total. Sum nodes_budgets where type=1,status=2,currency=USD. This explicitly sums rows; it does not select revisions or estimate unique funding.'),
    ('Q15', 'sectors', 'How many distinct activities are linked to each SDG key?', 'integer', 'Count distinct activity IDs in rel_contributes_to by sdg_key. Do not interpret a tag as evidence of achieved results.'),
    ('Q16', 'geography', 'How many distinct activities have at least one location node, by publisher?', 'integer', 'Join rel_located_at to activities; count distinct activity IDs by publisher. Omit zero groups. A location is not necessarily a beneficiary location.'),
    ('Q17', 'unsupported', 'Which hotspot country currently needs humanitarian aid the most?', 'unsupported', 'abstain|NEEDS_DATA_MISSING|The snapshot has no validated needs measure and is not real-time. Activity counts cannot establish unmet need.'),
    ('Q18', 'unsupported', 'What did these records say on January 1, 2020, before subsequent publisher corrections?', 'unsupported', 'abstain|HISTORY_UNAVAILABLE|Only one exported snapshot is available. Transaction dates and publisher update dates cannot reconstruct earlier versions.'),
    ('Q19', 'ambiguous', 'How much total funding did these organizations provide?', 'unsupported', 'clarify|FUNDING_DEFINITION_REQUIRED,CURRENCY_BASIS_REQUIRED,PERIOD_REQUIRED|Ask which financial measure, currency/conversion basis, and period are intended. Do not sum commitments, receipts, disbursements, expenditure, or different currencies together.'),
    ('Q20', 'unsupported', 'Which exact original WFP XML field contained a country code instead of an activity identifier in the summer anomaly?', 'unsupported', 'abstain|RAW_XML_UNAVAILABLE|The original anomaly XML is absent, and activity-reference attributes were not preserved in these exports. Request the original example.'),
]


def public_questions():
    return [dict(id=q[0], category=q[1] if q[3]!='unsupported' else 'reasoning', question=q[2], value_type=q[3] if q[3]!='unsupported' else 'structured', contract=q[4] if q[3]!='unsupported' else 'Use only the supplied snapshot. Answer when supported; otherwise explain the missing information or request clarification. Use the shared response schema.') for q in QUESTIONS]
