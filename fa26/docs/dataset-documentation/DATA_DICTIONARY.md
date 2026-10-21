# Data dictionary — IATI graph snapshot (Fall 2026)

This dictionary covers every column in the 22 CSVs under [fa26/benchmark/snapshot](../../benchmark/snapshot/). Counts refer to the fixed snapshot described in [DATASETDOC-fa26.md](DATASETDOC-fa26.md).

## Read and join conventions

- Read CSV with a proper CSV reader and preserve string identifiers/codes. Narrative fields can contain commas, quotes or embedded newlines.
- Empty string means absent/exported-missing information, not numerical zero. Date strings and decimal values need validation before conversion.
- Currency values are not converted; preserve signed values and specify transaction/budget rules before summing.
- Node keys join relationship columns as described below. Relationships have no universal unique business key: preserve each logical source row and its attributes, especially organisation roles.
- `table.csv:row:N` identifies the Nth logical data record, excluding the header. It is not a physical file line. Its meaning is tied to the manifest hash.
- Neo4j `source_id`, Activity `hunger_basis`, transaction `value_num` and decoded labels such as `type_label` are loader/graph properties, not additional columns in the source CSVs. `hunger_basis` copies `match_basis`; `value_num` is a convenience numeric conversion, while the evaluator uses Decimal strings.
- IATI codelists define source codes. [iati_codelists.py](../../src/iati_codelists.py) contains selected decoded labels used by this project. Missing/unknown codes must not be silently assigned a known category.


## `nodes_activities.csv`

Rows: **505**. Columns: **22**. Node key: `iati_identifier`.

| Field | Meaning |
| --- | --- |
| `iati_identifier` | Publisher-reported activity identifier; primary key of the retained activity table. |
| `title` | Exported activity title narrative. |
| `description` | Exported activity description narrative. |
| `status` | Reported IATI activity-status code; not budget status. |
| `humanitarian` | Reported IATI humanitarian flag; blank is not a verified false value. |
| `start_planned` | Planned activity start date. |
| `start_actual` | Actual start date as reported; missing does not imply the activity never started. |
| `end_planned` | Planned end date, which may be in the future. |
| `end_actual` | Actual end date as reported. |
| `default_currency` | Activity default currency used when a transaction/budget omits its own currency. |
| `publisher` | Downloader publisher slug: oxfamgb, oxfamus or wfp; not an organisation ID. |
| `hierarchy` | Reported activity hierarchy level; parser defaults to 1 when omitted. |
| `last_updated` | Reported activity last-updated timestamp; not the acquisition date or full revision history. |
| `aid_type` | Reported IATI aid-type code (activity default or transaction-level field depending on table). |
| `finance_type` | Reported default finance-type code. |
| `flow_type` | Reported default flow-type code. |
| `tied_status` | Reported default tied-status code. |
| `collaboration_type` | Reported collaboration-type code. |
| `scope` | Reported activity-scope code. |
| `capital_spend` | Reported capital-spend percentage. |
| `hotspot_countries` | Sorted pipe-separated configured country codes found at activity or transaction level. |
| `match_basis` | Derived filter reason: sector or keyword. Not human-annotated truth. |

## `nodes_budgets.csv`

Rows: **2,999**. Columns: **8**. Node key: `budget_id`.

| Field | Meaning |
| --- | --- |
| `budget_id` | Budget ID generated as activity ID plus #b and a zero-based XML budget position. |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `type` | Budget type: 1 original, 2 revised; parser defaults to 1 if omitted. |
| `status` | Budget status: 1 indicative, 2 committed; parser defaults to 1 if omitted. |
| `period_start` | Budget period start date as reported (ISO date string when supplied). |
| `period_end` | Budget period end date as reported (ISO date string when supplied). |
| `value` | Reported signed monetary value stored as a string. Parse with Decimal for benchmark calculations; do not combine currencies or transaction types without a contract. |
| `currency` | Reported monetary currency, with activity default fallback during parsing; no FX conversion. Snapshot transaction currencies are GBP and USD. |

## `nodes_countries.csv`

Rows: **13**. Columns: **3**. Node key: `code`.

| Field | Meaning |
| --- | --- |
| `code` | Country primary key: ISO alpha-2 code in the configured hotspot set. |
| `name` | Exported narrative/display name; may be empty or normalized by organisation resolution. |
| `hotspot_tier` | Configured concern tier: 1 highest concern, 2 very high concern, 3 hotspot; not a computed need score. |

## `nodes_emergencies.csv`

Rows: **0**. Columns: **5**. Node key: `emergency_key`.

| Field | Meaning |
| --- | --- |
| `emergency_key` | Composite humanitarian-scope identifier; joins to nodes_emergencies.emergency_key. |
| `code` | Code in the table-specific vocabulary; keep as a string, including leading zeros. |
| `vocabulary` | Identifier of the codelist/vocabulary used to interpret code. |
| `type` | Humanitarian-scope type: 1 emergency, 2 appeal. |
| `name` | Exported narrative/display name; may be empty or normalized by organisation resolution. |

## `nodes_locations.csv`

Rows: **82**. Columns: **8**. Node key: `location_id`.

| Field | Meaning |
| --- | --- |
| `location_id` | Generated activity-scoped location identifier; joins to nodes_locations.location_id. |
| `name` | Exported narrative/display name; may be empty or normalized by organisation resolution. |
| `ref` | Publisher-supplied location reference; may be blank and is not the generated graph location key. |
| `lat` | Latitude token parsed from location point coordinates; blank if absent. Validate before geographic analysis. |
| `lon` | Longitude token parsed from location point coordinates; blank if absent. Validate before geographic analysis. |
| `adm_code` | Reported administrative-area code. |
| `adm_vocab` | Vocabulary used for the administrative-area code. |
| `feature` | Reported location feature-designation code. |

## `nodes_organisations.csv`

Rows: **238**. Columns: **3**. Node key: `ref`.

| Field | Meaning |
| --- | --- |
| `ref` | Organisation key: reported or resolved IATI reference, or name:/unknown: fallback. It is not guaranteed to identify a unique real-world organisation. |
| `name` | Exported narrative/display name; may be empty or normalized by organisation resolution. |
| `type` | IATI organisation-type code; see shared codelists for decoded labels. Blank means unavailable. |

## `nodes_policy_markers.csv`

Rows: **0**. Columns: **2**. Node key: `code`.

| Field | Meaning |
| --- | --- |
| `code` | Code in the table-specific vocabulary; keep as a string, including leading zeros. |
| `name` | Exported narrative/display name; may be empty or normalized by organisation resolution. |

## `nodes_regions.csv`

Rows: **0**. Columns: **4**. Node key: `region_key`.

| Field | Meaning |
| --- | --- |
| `region_key` | Composite region vocabulary/code identifier; joins to nodes_regions.region_key. |
| `code` | Code in the table-specific vocabulary; keep as a string, including leading zeros. |
| `vocabulary` | Identifier of the codelist/vocabulary used to interpret code. |
| `name` | Exported narrative/display name; may be empty or normalized by organisation resolution. |

## `nodes_sdgs.csv`

Rows: **2**. Columns: **4**. Node key: `sdg_key`.

| Field | Meaning |
| --- | --- |
| `sdg_key` | SDG-tag identifier; joins to nodes_sdgs.sdg_key. |
| `code` | Code in the table-specific vocabulary; keep as a string, including leading zeros. |
| `level` | SDG tag level inferred from vocabulary by the parser. |
| `name` | Exported narrative/display name; may be empty or normalized by organisation resolution. |

## `nodes_sectors.csv`

Rows: **17**. Columns: **5**. Node key: `sector_key`.

| Field | Meaning |
| --- | --- |
| `sector_key` | Composite vocabulary/code identifier; joins to nodes_sectors.sector_key. |
| `code` | Code in the table-specific vocabulary; keep as a string, including leading zeros. |
| `vocabulary` | Identifier of the codelist/vocabulary used to interpret code. |
| `name` | Exported narrative/display name; may be empty or normalized by organisation resolution. |
| `is_hunger` | Lowercase string true/false from the sector-code hunger rule; not a human validation label. |

## `nodes_transactions.csv`

Rows: **23,423**. Columns: **12**. Node key: `tx_id`.

| Field | Meaning |
| --- | --- |
| `tx_id` | Transaction ID generated as activity ID plus #tx and a zero-based XML transaction position; snapshot-specific, not a globally issued transaction identifier. |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `type` | IATI transaction-type code. Observed: 1 incoming funds, 2 outgoing commitment, 3 disbursement, 4 expenditure. |
| `date` | Reported transaction date; distinct from valuation date and ingestion time. |
| `value` | Reported signed monetary value stored as a string. Parse with Decimal for benchmark calculations; do not combine currencies or transaction types without a contract. |
| `currency` | Reported monetary currency, with activity default fallback during parsing; no FX conversion. Snapshot transaction currencies are GBP and USD. |
| `value_date` | Date attached to the transaction value for valuation context; not an FX conversion applied by this project. |
| `recipient_country` | Transaction-specific recipient-country code; may be blank and differs from activity-level country allocation. |
| `sector_code` | Transaction-specific sector code. |
| `sector_vocab` | Vocabulary for the transaction-specific sector code. |
| `aid_type` | Reported IATI aid-type code (activity default or transaction-level field depending on table). |
| `humanitarian` | Reported IATI humanitarian flag; blank is not a verified false value. |

## `rel_classified_as.csv`

Rows: **1,238**. Columns: **3**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `sector_key` | Composite vocabulary/code identifier; joins to nodes_sectors.sector_key. |
| `percentage` | Reported relationship allocation percentage; blank means not supplied, not equal allocation. |

## `rel_contributes_to.csv`

Rows: **82**. Columns: **2**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `sdg_key` | SDG-tag identifier; joins to nodes_sdgs.sdg_key. |

## `rel_located_at.csv`

Rows: **82**. Columns: **2**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `location_id` | Generated activity-scoped location identifier; joins to nodes_locations.location_id. |

## `rel_marked_with.csv`

Rows: **0**. Columns: **3**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `marker_code` | Policy-marker code; joins to nodes_policy_markers.code. |
| `significance` | Reported policy-marker significance code. |

## `rel_participates.csv`

Rows: **3,457**. Columns: **3**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `org_ref` | Organisation reference; joins to nodes_organisations.ref. May be a name-derived identifier. |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `role` | Participating-organisation role code: 1 funding, 2 accountable, 3 extending, 4 implementing. Preserve multiple roles for the same endpoint pair. |

## `rel_related_activity.csv`

Rows: **0**. Columns: **3**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `related_ref` | Identifier of a related activity; it may reference an activity outside the retained export. |
| `type` | Reported related-activity relationship code; no rows in this snapshot. |

## `rel_reports.csv`

Rows: **505**. Columns: **2**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `org_ref` | Organisation reference; joins to nodes_organisations.ref. May be a name-derived identifier. |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |

## `rel_responds_to.csv`

Rows: **0**. Columns: **2**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `emergency_key` | Composite humanitarian-scope identifier; joins to nodes_emergencies.emergency_key. |

## `rel_targets_country.csv`

Rows: **505**. Columns: **4**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `country_code` | ISO alpha-2 country code; joins to nodes_countries.code. |
| `percentage` | Reported relationship allocation percentage; blank means not supplied, not equal allocation. |
| `is_hotspot` | Lowercase string true/false indicating membership in the configured hotspot country set. |

## `rel_targets_region.csv`

Rows: **0**. Columns: **3**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `iati_identifier` | Activity identifier; joins to nodes_activities.iati_identifier. Preserve the exact string. |
| `region_key` | Composite region vocabulary/code identifier; joins to nodes_regions.region_key. |
| `percentage` | Reported relationship allocation percentage; blank means not supplied, not equal allocation. |

## `rel_transaction_edges.csv`

Rows: **26,830**. Columns: **3**. Relationship records: preserve logical row identity.

| Field | Meaning |
| --- | --- |
| `tx_id` | Transaction ID generated as activity ID plus #tx and a zero-based XML transaction position; snapshot-specific, not a globally issued transaction identifier. |
| `org_ref` | Organisation reference; joins to nodes_organisations.ref. May be a name-derived identifier. |
| `edge` | Transaction-party relation type: PROVIDED_BY or RECEIVED_BY. Joins a transaction to an organisation. |

## Important relationship directions

- `rel_reports`: Organisation → Activity (`REPORTS`).
- `rel_participates`: Organisation → Activity (`PARTICIPATES_IN`, with role).
- `rel_targets_country`: Activity → Country (`TARGETS`).
- `rel_classified_as`: Activity → Sector (`CLASSIFIED_AS`).
- `rel_located_at`: Activity → Location (`LOCATED_AT`).
- `rel_contributes_to`: Activity → SDG (`CONTRIBUTES_TO`).
- `rel_transaction_edges`: Transaction → Organisation (`PROVIDED_BY` or `RECEIVED_BY`).
- Activity → Transaction (`HAS_TRANSACTION`) and Activity → Budget (`HAS_BUDGET`) are constructed from `iati_identifier` in the corresponding node tables; they do not have their own CSVs.
- Region, emergency, marker and related-activity tables are schema placeholders with no rows in this snapshot. The reviewed eight-label graph loader does not create those currently empty entity types.
