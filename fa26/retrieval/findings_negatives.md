# Negative transactions: what the data shows

Written 2026-11-12. Follows the question at client meeting #4 (2026-11-06):
are negative transactions returned money, promised-but-not-given money, or
something else?

**Short answer.** The data shows *what* the negatives do, not *why*. Almost
every negative reduces money that was recorded earlier for the same donor on
the same activity. Whether a given reduction was a refund, a move to another
activity or a bookkeeping correction is not stated anywhere in the files.

## Data used

- **In scope**: the 439 hunger-related activities in the cleaned data of
  2026-11-01 (the team graph). Read from the raw IATI XML, which matches the
  cleaned CSVs on row counts and totals.
- **Whole file**: every activity the publisher reports (WFP 1,344, Oxfam GB
  1,113). Used where the answer depends on activities outside the hunger set.

Unless a line says otherwise, figures are for Incoming Funds (type 1), the
type the team counts as funding (`funding_definition.md`).

## What is established

### 1. How many

| In scope | Rows | Negative rows | Positive money | Negative money |
| --- | ---: | ---: | ---: | ---: |
| WFP (USD) | 9,811 | 3,622 (36.9%) | 20,863,404,050 | 1,917,271,463 (9.2% of positive) |
| Oxfam GB (GBP) | 4,594 | 1,256 (27.3%) | 533,937,929 | 29,869,095 (5.6% of positive) |

Negatives are common by count and small by value. Across all types in scope,
5,540 of 24,616 rows are negative (22.5%). Oxfam America has none.

### 2. A row is a period total, not a single payment

- WFP publishes one row per activity, donor and month-end date (56,760 of
  56,766 combinations in the whole file have exactly one row).
- Oxfam GB publishes one row per activity, donor, type and reporting period,
  labelled for example "Income Spent January 2019 - March 2019" (7,239 of
  7,268 combinations in scope have exactly one row).

So a negative row is a month or quarter in which the movement for that donor
on that activity was downward. IATI guidance allows this grouping ("expenses
could be published as one transaction for every month or every quarter").

### 3. Negatives cancel against earlier money from the same donor and activity

Add up every row for one donor on one activity and almost nothing stays
negative. Chart: `slide_charts/negatives_cancel_out.png` in the project folder.

| In scope | Negative money, row by row | Left after adding up per year | Left after adding up over all years |
| --- | ---: | ---: | ---: |
| WFP | USD 1,917,271,463 | USD 508,991,576 (26.5%) | USD 4,769,397 (0.2%) |
| Oxfam GB | GBP 29,869,095 | GBP 13,634,061 (45.6%) | GBP 1,015,797 (3.4%) |

- WFP: of 1,230 donor-and-activity pairs, 19 end below zero. 95% never go
  below zero at any point in time.
- Oxfam GB: of 951 pairs, 83 end below zero. 87% never go below zero.
- The typical negative arrives well after the money it reduces: a median of
  18 months after the pair's first positive row for WFP, 15 for Oxfam GB.
- The whole files show the same thing (WFP 2.6% left, Oxfam GB 6.0% left).
- Other transaction types behave the same way. Oxfam GB Expenditure, whole
  file: 14.5% of rows negative, 2.6% of the negative money left per activity
  and receiver.

### 4. Many WFP negatives are moves between activities of one country plan

WFP activity ids start with a country plan code (`SD02` in
`XM-DAC-41140-SD02.01.011.URT1`). In the whole WFP file, 6,090 of 15,545
negative rows (39%) have a positive row of exactly the same size, from the
same donor, on the same date, in another activity of the same plan. These are
the small ones: 7.6% of negative money. In scope: 1,307 of 3,622 rows, 5.0% of
the money.

### 5. The few that never cancel sit at the start of the data

WFP's published transactions begin in January 2021. Of the 93 in-scope WFP
negatives with no earlier positive from that donor on that activity, 77 are
dated 2021, and 14 of the 19 pairs that end below zero start in 2021. The
likely reading is that they reduce money recorded before the published
window. That reading is ours, not WFP's.

### 6. What does not explain them

- **Simple reversals.** Only 502 of the 5,540 negatives (9%) have an equal and
  opposite positive in the same activity, type and currency.
- **Planned versus actual.** Brent raised this at the meeting. No publisher
  here reports planned disbursements, and the value date equals the
  transaction date on every row. IATI defines the value date as "the date to
  be used for determining the exchange rate for currency conversions", so it
  is not a planned date in any case. Planned money appears only as budgets,
  which the graph loads separately.
- **One donor's money re-labelled as another's.** In Oxfam GB's whole file,
  185 of 3,361 negatives have an equal positive from a different donor on the
  same activity and date.

### 7. Timing

Oxfam GB's negatives cluster in the quarter ending March: 36% of in-scope rows
dated 31 March are negative, against 18% for 30 June. Its own labels show an
April-to-March year ("Expenditure April 2011 - March 2012"), so this looks
like year-end correction. WFP's share is flat across months (26% to 30%).

## What IATI says

From the IATI guidance on financial transactions:

> Transaction values can be positive or negative. Where finance is being
> passed up the delivery chain, this should be published as a negative
> transaction.

Its examples are a negative disbursement for money returned by a partner and
a negative commitment when a promise is reduced. It gives no example for a
negative Incoming Funds row, which is what WFP and Oxfam GB publish most.

## What we can and cannot say

**Can say.** Negatives are later reductions of amounts recorded earlier for
the same donor and activity. Counting them row by row overstates them. Over
the full period the net figure for a donor on an activity is reliable. Many
WFP negatives are moves between activities of one country plan.

**Cannot say.** Whether a reduction was money handed back to the donor, money
re-assigned, an exchange-rate revision or an accounting correction. WFP gives
no description on any transaction. Oxfam GB's descriptions give only the
period.

## What this means for the tools

No change is needed. The tools already report positive `amount`, negative
`adjustments` and `net` separately (client decision 2026-10-23). Two reading
rules follow from the findings:

- For one donor on one activity or country over the whole period, quote `net`.
- A year's `adjustments` often correct an earlier year's `amount`, so a single
  year's net can understate or overstate that year.

## Three examples to send Sylvan and Brent

1. **A move inside a plan (WFP).** On 2025-07-31 The World Bank (`44000`) has
   -1,759,780.18 USD on `XM-DAC-41140-SD02.01.011.URT1` (Unconditional general
   food assistance) and +1,759,780.18 USD on `XM-DAC-41140-SD02-DSC` (Non
   Activity Specific). Is this a re-allocation between budget lines?
2. **A pair that only has negatives (WFP).** Germany (`XM-DAC-5`) on
   `XM-DAC-41140-SD02.02.021.SMP1` has -1,463,448 USD on 2021-01-31 and -85,799
   on 2021-04-30 and nothing else. Does this reduce money recorded before
   WFP's published data begins?
3. **Year-end negatives (Oxfam GB).** "EU - Food Security" on
   `GB-CHC-202918-MLIA74`: -323,650 GBP for January to March 2019, -65,369 for
   October to December 2019, -33,586 for January to March 2020, then +22,636
   for January to March 2021. What does a negative "Income Spent" quarter mean?

## Not done

- Asking the publishers. The examples above are the question to send.
- Storing a label on each negative in the graph (Amy's suggestion). The only
  label the data supports today is "has an exact matching move in a sibling
  activity", which covers 36% of in-scope WFP negatives and has no equivalent for Oxfam GB.
