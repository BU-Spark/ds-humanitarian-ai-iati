# Hunger relevance filter

How the pipeline decides whether an IATI activity is hunger-related, what
changed in Fall 2026 ("Option A"), and how to test and tune it.

Code: `hunger_match()` in [`src/parse_filter.py`](../src/parse_filter.py).
Settings: [`src/config.py`](../src/config.py).
Tests: [`tests/`](../tests/).

## Why it changed

On the summer prototype's output, 430 of 505 kept activities (85%) were kept
by the keyword fallback rather than by sector codes, almost all from Oxfam GB.
Reviewing that fallback showed three failure patterns, each now reproduced by
a test:

| Problem | Example | Scale |
|---|---|---|
| **Own sector names were searched.** Oxfam GB files activities under its own categories (vocabulary 99), and the category "A Sustainable *Livelihood*" contains a keyword. | A governance project filed under that category was kept. | ~122 activities kept only for this reason |
| **Broad keywords counted as much as specific ones.** "food", "agriculture" and "livelihood" weighed the same as "malnutrition". | "Food for thought: civic education" would be a hunger project. | "food" was the only match for 36 activities |
| **Organisation names triggered matches.** | "World *Food* Programme", "Welt*hunger*hilfe" | 8 kept activities mention WFP |

The descriptions were also cut to 2,000 characters *before* matching, so
keywords late in long descriptions were missed.

Note: matching is still substring-based on purpose. Requiring whole words
was considered and rejected, because it would lose plurals and related forms
("livelihoods", "crops", "malnutrition" via "nutrition").

## How it works now

Geography is checked first (the activity, or one of its transactions, must
target a hotspot country). The theme check then goes in this order, and the
first rule that applies decides the activity's `match_basis`:

| Step | Rule | `match_basis` | Kept? |
|---|---|---|---|
| 1 | Has sector codes in a standard vocabulary (DAC 5-digit, DAC 3-digit, humanitarian clusters). A hunger code keeps it. Non-hunger codes drop it, **unless** the text has a strong signal (step 3's rule): a missed hunger activity is worse than an extra one. | `sector` / `keyword_over_sector` / `sector_no_match` | yes / yes, low confidence / no |
| 2 | Tagged with SDG Goal 2 "Zero Hunger" (sector vocabulary 7, code `2`) or one of its targets (vocabulary 8, codes `2.x`). | `sdg` | yes |
| 3 | Title or description contains a **strong** keyword, **or** a context term (agriculture, livelihood, cash, voucher, …) together with a food word (food, nutrition, hunger). | `keyword` | yes |
| 4 | Title or description contains **only weak** keywords. | `keyword_weak` | yes, flagged for review |
| 5 | None of the above. | `no_signal` | no |

Before steps 3 and 4:
- Organisation names in `ORG_NAME_PATTERNS` are removed from the text.
- Sector *names* are not searched at all.
- The full description is searched. It is cut to 2,000 characters only when written to `nodes_activities.csv`.

Sector code 998 ("unspecified") doesn't count as a standard code, so
activities coded only 998 (Oxfam America) still go through steps 2 to 5.

### Keyword lists (`src/config.py`)

| List | Terms |
|---|---|
| `HUNGER_KEYWORDS_STRONG` | food security, food insecurity, food assistance, food aid, emergency food, hunger, famine, nutrition, malnutrition, school feeding, IPC, EFSVL, FS&L; from John's filter: food distribution, food voucher, therapeutic feeding, undernutrition, food access, food production, food-insecure, food insecure; French (WFP publishes in French for Haiti, Mali, DRC): sécurité alimentaire, insécurité alimentaire, assistance alimentaire, aide alimentaire, alimentation scolaire, cantines scolaires, faim |
| `HUNGER_CONTEXT_TERMS` | agricultur…, smallholder, farmer, crop, livestock, harvest, livelihood, resilien…, cash transfer, voucher, drought. Strong when paired with a `FOOD_CONTEXT_TERMS` word (food, nutrition, hunger) |
| `HUNGER_KEYWORDS_WEAK` | food, agriculture, agricultural, livestock, crop, harvest, livelihood, cash transfer, drought, farmer, smallholder |
| `ORG_NAME_PATTERNS` | World Food Programme, FAO, Welthungerhilfe, Action Against Hunger / Action contre la Faim, IFAD, International Crop Research…, Food for the Hungry |

EFSVL and FS&L are Oxfam's acronyms for "(Emergency) Food Security and
(Vulnerable) Livelihoods".

All matching is case-insensitive. To change a list, edit `config.py`, add a
test for the case you care about, and rerun the comparison below.

## Results

Old and new filters run on the **same** download of IATI data
(22 files, fetched 22 October 2026), so the difference comes from the
filter alone:

| Publisher | Old filter | New filter |
|---|---|---|
| Oxfam GB | 415 (all `keyword`) | 316 = 198 `keyword` + 118 `keyword_weak` |
| Oxfam America | 11 (all `keyword`) | 11 = 4 `keyword` + 7 `keyword_weak` |
| WFP | 86 = 75 `sector` + 11 `keyword` | 86 = 75 `sector` + 11 `sdg` |
| **Total** | **512** | **413** (125 `keyword_weak`) |

- **104 dropped**, all Oxfam GB. They were kept only because of the
  "A Sustainable Livelihood" category or an organisation name. In a
  spot-check, most are water and sanitation, governance, decent work or
  energy projects.
- **5 added**: drought responses and an EFSVL project that the old
  keyword list missed.
- The old filter keeps 512 on this data, versus 505 in the committed summer
  output. The difference comes from publishers updating their data since
  the summer.

The committed `data/graph/` CSVs have **not** been regenerated yet. They
still reflect the old filter. To apply the new filter:

```bash
cd fa26
python src/pipeline.py all       # download -> parse -> resolve -> sync
python src/pipeline.py refresh   # if data/raw/ is already downloaded
```

## Accuracy on the hand-labelled sample

John labelled 50 hotspot activities by hand
([`data/hunger_filter_sample_50.csv`](../data/hunger_filter_sample_50.csv),
39 Oxfam GB and 11 WFP). Each row stores the parsed activity as
`record_json`, so any version of `hunger_match()` can be scored on it
without raw XML. 20 of the 50 are labelled hunger-related.

Two ways to read the results:
- **Pipeline view:** `keyword_weak` counts as kept, which is what the graph does today.
- **Strong-only view:** only confident matches count.

| Filter | View | Accuracy | Precision | Recall |
|---|---|---|---|---|
| Original (summer) | — | 76% | 63% | 95% |
| John's (branch `john`) | — | 86% | 76% | 95% |
| Option A, before merging John's rules | pipeline | 82% | 70% | 95% |
| | strong-only | 88% | 89% | 80% |
| Option A + John's rules | pipeline | 82% | 70% | 95% |
| | strong-only | 90% | 86% | 90% |
| **Current: + text over sector, French terms** | **pipeline** | 84% | 71% | **100%** |
| | strong-only | 92% | 86% | 95% |

### What was taken from John's filter

Each candidate rule was scored on this sample and on the full download:
- **Taken: John's extra strong terms** (food distribution, food voucher, therapeutic feeding, …). No change on the sample, and 7 activities move from weak to strong.
- **Taken: John's context rule.** A context term next to a food word counts as strong. On the full data, 38 activities move from weak to strong (including the 7 above), and `keyword_weak` shrinks from 163 to 125. In the strong-only view, accuracy rises from 88% to 90% and recall from 80% to 90%, for example "Cash Voucher (for food) Distribution".
- **Taken in a narrower form: letting text override non-hunger sector codes.** In John's filter, *any* keyword can override standard but non-hunger codes. That adds 3 false positives on the sample and about 70 activities to the graph (mostly WFP). We let only a **strong** text signal override them (`keyword_over_sector`, confidence `low`). Together with the French terms, this adds 26 WFP activities, rescues the one missed activity on the sample, and adds no false positives. It was taken once the team decided recall matters more than precision. Letting an SDG 2 tag override sector codes was still not taken, because WFP tags SDG 2 broadly.
- **Not taken: searching sector names.** John's filter still searches category names such as "A Sustainable Livelihood". That is the problem Option A fixes.

### Remaining errors on this sample
- **No misses in the pipeline view.** The French WFP project "assistance alimentaire … création d'actifs" (DAC 73010) used to be missed. It is now kept as `keyword_over_sector`.
- **Weak matches:** in the pipeline view, 5 of the 8 false positives are `keyword_weak`. In the strong-only view, the 1 miss is.
- **Two labels may be worth a second look:** "Integrated Food security and WaSH assistance in Lahj, Yemen" and "Drought response in Badakshan". Both are labelled *not* hunger-related.

### Caveats
- 50 rows is small.
- The sample was drawn as roughly half kept and half dropped by the original filter, so these percentages do not estimate accuracy across the whole dataset.
- No Oxfam America activities are included.
- One person did the labelling.
- **This sample was used to tune the filter**, so its scores are optimistic. Use the held-out sample below for an honest score.

### Held-out sample (Devansh)

[`data/hunger_filter_sample_devansh_50.csv`](../data/hunger_filter_sample_devansh_50.csv)
was drawn **before** John's rules were merged, and was not looked at while
tuning:
- 25 Oxfam GB, 15 WFP and 10 Oxfam America activities, picked at random within each publisher (seed 2026).
- John's 50 are excluded.
- Filter predictions are not shown, so they can't bias the labeller.
- Parsed records are in the matching `_records.json` file. Some are too long for a spreadsheet cell, so they aren't in the CSV.

**Labelled 29 October 2026.** Claude drafted a label and a reason for each row from the title and description only. Devansh then checked every row, with the 14 borderline ones marked `BORDERLINE:` in `notes`, and agreed with all of them. The drafts are kept in `draft_label` / `draft_note`, so later LLM labelling can be compared with them. The definition used: an activity counts as **yes** if a meaningful part of it directly addresses food access, food assistance, nutrition, or food production for food security. It counts as **no** if food is incidental, or only the context.

15 of the 50 are hunger-related. The filter was scored once, as it was after the recall-first retune:

| View | Accuracy | Precision | Recall |
|---|---|---|---|
| Pipeline (`keyword_weak` kept) | 84% | 68% | **87%** |
| Strong-only | 88% | 91% | 67% |

- **2 misses**, both WFP:
  - "02 Country Capacity Strengthening" (Myanmar), which supports national food systems programmes.
  - "07 Safety nets (SR1)" (Somalia), which provides unconditional cash transfers under WFP's food-access result.

  Both are tagged SDG 2 but have non-hunger sector codes, and both are borderline labels. Letting an SDG 2 tag overrule sector codes would catch them. That rule was rejected earlier because it adds about 70 activities, and adopting it now would mean tuning on this sample.
- **6 false positives**, mostly Oxfam "livelihoods" and general humanitarian-response weak matches. Under the recall-first decision, this is the accepted cost.
- Recall falls from 100% on John's (tuning) sample to 87% here. That gap is the expected optimism of scoring on the sample you tuned on.

To rescore:

```bash
python src/evaluate_filter.py score data/hunger_filter_sample_devansh_50.csv
python src/evaluate_filter.py score data/hunger_filter_sample_devansh_50.csv --weak-as-no
```

If the filter is changed because of what this sample shows, it stops being
a held-out test. Say so in any write-up, and draw a new sample
(`evaluate_filter.py sample … --exclude` both existing sheets) for the
next honest score.

[`src/evaluate_filter.py`](../src/evaluate_filter.py) builds on John's
`evaluate_hunger_filter.py`. `sample` draws a new blind sheet and `score`
scores any labelled CSV, in John's format or this one.
[`tests/test_labelled_sample.py`](../tests/test_labelled_sample.py) fails if
scores on John's sample fall below 70% precision / 95% recall (pipeline
view) or 85% / 90% (strong-only view).

## Manual review layer

Agreed at the 23 Oct client meeting: borderline activities are flagged for
a person to check, instead of being silently kept or dropped. The filter's
decision stands until someone reviews it. Code:
[`src/review.py`](../src/review.py) and `review_reasons()` in
`parse_filter.py`.

### What gets flagged

A wrong drop is the costly error, because the activity disappears from the
graph. So **only dropped activities are queued**:

| Reason | Rule | On the 22 Oct download |
|---|---|---|
| `near_miss_term` | No hunger signal, but mentions a term deliberately left out of the filter (`REVIEW_NEAR_MISS_TERMS`: cash for work, P4P / purchase for progress, agribusiness, market access, irrigation, fisher…) | 6 (Oxfam GB) |

Doubtful activities that the filter *keeps* are not queued. They are marked
`confidence = low` instead: 124 `keyword_weak` and 26 `keyword_over_sector`.
Anyone can still exclude one by adding it to the decisions file.

An earlier version also queued kept activities and text-vs-sector
conflicts, which came to 156 rows. That was too many to review by hand. On
John's sample, 5 of the 6 queued kept activities were not hunger-related
anyway, so reviewing them mostly confirmed false positives the team had
already accepted. Text-vs-sector conflicts are now kept automatically (see
step 1 above).

Every kept activity also gets these columns in `nodes_activities.csv`:
- `confidence`: `high` (sector or SDG coding), `medium` (strong keyword) or `low` (weak keyword only, or text overruling the sector code). This is the weighting Sylvan suggested in place of a plain yes/no.
- `review_status`: `not_flagged`, or `include` once a reviewer has kept it.
- `match_terms`: the keywords that matched, e.g. `strong: nutrition; context: livelihood`, so each decision can be explained.

For a strict view of the graph, filter on `confidence IN ['high',
'medium'] OR review_status = 'include'`.

### How to review

1. Run the parser (`python src/pipeline.py refresh`). It writes
   `data/review/hunger_review_queue.csv`.
2. For each row, fill `decision` with `include` or `exclude`, plus `reviewer` (your initials) and `notes`. `yes` / `no` also work. Use the same definition as for the labelled samples (see above).
3. Save the file and run the parser again. Your decisions are copied into
   `data/review/hunger_review_decisions.csv` *before* the queue is rewritten, and the reviewed rows leave the queue.

`python src/review.py status` shows how many are left, by reason.

- A decision overrides the filter in both directions: `include` keeps an activity the filter dropped, and `exclude` drops one it kept.
- Decisions are tied to the IATI identifier, so they survive daily refreshes and filter changes.
- `hunger_review_decisions.csv` is the record of human judgement. Commit it, and edit it by hand only to correct a decision.
- Decisions do **not** change the accuracy scores above. `evaluate_filter.py` scores the filter on its own.
- Running with `--publisher` rewrites the queue for that publisher only. The other publishers' pending rows come back on the next full run, and no decisions are lost.

## Known limitations and open decisions

- **The filter is still a rule of thumb.** On the held-out sample it
  reaches 87% recall and 68% precision (n=50, 15 positives), so expect
  roughly 1 in 8 hunger activities to be missed.
- **150 low-confidence activities are kept without review** (124 `keyword_weak`,
  nearly all Oxfam GB, and 26 WFP `keyword_over_sector`). The app still
  treats them the same as `keyword`. On John's sample, the
  strong-only view scores better (90% vs 82% accuracy). Once the held-out
  sample confirms it, decide whether the app should
  hide `confidence = low` by default.
- **Keywords are English only.** Many WFP records are in French ("sécurité
  alimentaire", "nutritionnelle"). Sector codes cover most of them, but the
  keyword fallback only has a short list of French terms. Other languages
  (Spanish, Arabic) are not covered.
- **Some food-adjacent activities are still dropped.** Terms considered and
  deliberately *not* added: agribusiness / P4P ("Purchase for Progress",
  +5 activities), cash for work (+5) and market access (+2). They are easy
  to add to the weak list if the team decides otherwise.
- **The organisation-name list is maintained by hand.** A new partner with a
  hunger word in its name will match until it is added to the list.
- **Waiting on the client.** Brent has not yet answered whether indirect
  support (agriculture, livelihoods, cash) should count at all, or only
  officially coded activities ("Option B"). If he chooses Option B, almost
  all Oxfam activities drop out.

## Tests

```bash
cd fa26
pip install pytest
python -m pytest -v
```

| File | Covers |
|---|---|
| `test_own_sector_names.py` | Oxfam GB category names are not searched; SDG 2 tags count, but other SDGs do not |
| `test_broad_keywords.py` | Strong vs weak tiers, context rule (e.g. "cash voucher (for food)"), plurals, EFSVL, keywords past 2,000 characters |
| `test_org_names.py` | Organisation names are ignored, but real hunger work with WFP is still kept |
| `test_parse_fixture.py` | End-to-end: runs the parser on `fixture_iati_2.03.xml` (in a temporary folder, never `data/graph/`) and checks all 7 labelled activities |
| `test_labelled_sample.py` | Precision and recall on John's 50 hand-labelled activities stay above the floors, in both the pipeline and strong-only views; the same on Devansh's held-out 50, with its own floors |
| `test_review.py` | Only dropped near-misses are queued; strong text overrules non-hunger sector codes, including French text; confidence tiers; `match_terms` ignores organisation names; decisions override the filter in both directions, survive the queue being rewritten, and bad values are ignored |

The tests that show a problem in the code are the record of each issue. If
you change the filter, update the tests in the same change.
