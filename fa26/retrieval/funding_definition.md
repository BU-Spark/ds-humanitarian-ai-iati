# What counts as "funding"

Written 2026-11-12 after client meeting #4 (2026-11-06), where the team agreed
to pick one funding type and document it so it can be changed later.

## The rule

**Funding = IATI transaction type 1, Incoming Funds.** The funder is the
organisation named as provider on the transaction.

- One type only by default. `transaction_totals` refuses more than one type.
  `top_funders` and `funding_over_time` will add types together if a caller
  passes several, with only a warning in the coverage note, so do not pass
  several.
- Positive transactions are the headline `amount`. Negative transactions are
  their own `adjustments` category (client decision 2026-10-23). `net` is the
  two added.
- One row per currency. Nothing is converted, so GBP and USD are never summed.

This is what the retrieval tools have defaulted to since October. It is
recorded here so the team can confirm it or change it in one place.

## Why this type

All figures below are from the cleaned data of 2026-11-01 (439 hunger-related
activities: Oxfam GB 316, WFP 112, Oxfam America 11) and were checked against
the raw IATI XML where marked. The benchmark uses a different, older snapshot.

1. **It is the only type that names outside funders.** WFP's 9,811 Incoming
   Funds rows name 123 different providers. Oxfam GB's 4,594 name 92.
2. **Disbursement does not show who funded anything here.** It exists only for
   Oxfam GB (423 rows), and every row names Oxfam GB itself as the provider.
   WFP and Oxfam America publish none.
3. **Adding types double counts.** WFP reports every Outgoing Commitment a
   second time as an Expenditure: 3,744 rows each, identical on activity, date,
   value and currency (confirmed in the raw XML). Each sums to
   USD 19,683,566,169.58 net. Adding the two would report USD 39.4 billion.

## What the rule gives

| Publisher | Currency | Rows | Amount (positive) | Adjustments (negative) | Net |
| --- | --- | ---: | ---: | ---: | ---: |
| WFP | USD | 9,811 | 20,863,404,049.76 | -1,917,271,463.21 | 18,946,132,586.55 |
| Oxfam GB | GBP | 4,594 | 533,937,929.00 | -29,869,095.00 | 504,068,834.00 |
| Oxfam America | USD | 0 | 0 | 0 | 0 |

The Oxfam America row is shown for completeness. The tools return no row for
a publisher with no matching transactions (`no_results` when it is the only
publisher asked for).

These are totals for the hunger-related activities in the graph, not for each
publisher as a whole. WFP money starts in January 2021 and Oxfam GB money in
June 2013, so the two are not comparable periods.

## Caveats to state with any funding figure

1. **Oxfam America shows zero funding.** Its whole file (401 activities,
   checked in the raw XML) contains Expenditure and three Disbursement rows and
   no Incoming Funds. Zero means "not reported", not "not funded".
2. **The same money can appear under two publishers.** GBP 199,548,739 of
   Oxfam GB's Incoming Funds (225 rows, 37% of its amount) names WFP as the
   provider. Donor money reported as Incoming Funds by WFP can therefore be
   reported again as Incoming Funds by Oxfam GB. The tools keep publishers and
   currencies on separate rows, so this only goes wrong if someone adds the
   rows up.
3. **Oxfam GB's figure includes money from inside Oxfam.** 2,468 of its 4,594
   rows (GBP 119,431,535) name an Oxfam organisation as provider, 807 of them
   Oxfam GB itself (GBP 19,954,112). `top_funders` hides the self-provided
   rows by default (`exclude_self=True`). `funding_over_time` and
   `transaction_totals` include them.
4. **Oxfam GB may record income when it is spent, not when it arrives.** Every
   one of its Incoming Funds rows is labelled "Income Spent" plus a reporting
   period, and its Incoming Funds and Expenditure totals are close
   (GBP 504 million and GBP 525 million net). This is a reading of the labels,
   not something Oxfam GB has confirmed.
5. **About 23% of all transactions are negative** (37% of WFP's Incoming Funds
   rows, 27% of Oxfam GB's). The cause is not in the data; see the note on
   negative transactions when it is written.

## How to change the rule

- Retrieval tools: `FUNDING_TRANSACTION_TYPE` in `tools.py` is the default for
  `top_funders`, `funding_over_time` and `transaction_totals`. Any call can
  still pass another type.
- George's templates (`fa26/src/tools/templates.py` on
  `retrieval-schema-integration`) keep their own default: the top-providers
  template defaults to type 1, and the totals and by-year templates make the
  caller choose. Change both places together.

## Not checked yet

- Whether Oxfam GB's Disbursement rows are money already counted in its
  Incoming Funds.
- Whether a WFP transaction can be matched to the Oxfam GB row that receives
  it. WFP's rows do not name a receiver in the cleaned data.
