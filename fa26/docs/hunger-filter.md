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
| 1 | Has sector codes in a standard vocabulary (DAC 5-digit, DAC 3-digit, humanitarian clusters). They decide on their own, and keywords are not checked. | `sector` / `sector_no_match` | yes / no |
| 2 | Tagged with SDG Goal 2 "Zero Hunger" (sector vocabulary 7, code `2`) or one of its targets (vocabulary 8, codes `2.x`). | `sdg` | yes |
| 3 | Title or description contains a **strong** keyword. | `keyword` | yes |
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
| `HUNGER_KEYWORDS_STRONG` | food security, food insecurity, food assistance, food aid, emergency food, hunger, famine, nutrition, malnutrition, school feeding, IPC, EFSVL, FS&L |
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
| Oxfam GB | 415 (all `keyword`) | 316 = 160 `keyword` + 156 `keyword_weak` |
| Oxfam America | 11 (all `keyword`) | 11 = 4 `keyword` + 7 `keyword_weak` |
| WFP | 86 = 75 `sector` + 11 `keyword` | 86 = 75 `sector` + 11 `sdg` |
| **Total** | **512** | **413** |

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

| Filter | Accuracy | Precision | Recall | False positives | Missed |
|---|---|---|---|---|---|
| Original (summer) | 76% | 63% | 95% | 11 | 1 |
| John's context-based version (branch `john`) | 86% | 76% | 95% | 6 | 1 |
| **Current, `keyword_weak` kept** | 82% | 70% | 95% | 8 | 1 |
| Current, `keyword_weak` excluded | 88% | 89% | 80% | 2 | 4 |

What this shows:
- **The strong/weak split works.** Of the 8 false positives, 6 are `keyword_weak`. Excluding weak matches gives the best precision, but misses 3 more real hunger activities, for example "Cash Voucher (for food) Distribution".
- **John's context rule** (weak terms count only next to a food or nutrition word) catches some cases our tiers miss. Combining the two approaches is worth trying.
- **The activity every filter misses** is a French WFP "food assistance for assets" project. It is coded DAC 73010 (reconstruction) plus SDG target 2.4. The DAC code decides first, so the SDG tag is never checked.
- **Two labels may be worth a second look:** "Integrated Food security and WaSH assistance in Lahj, Yemen" and "Drought response in Badakshan". Both are labelled *not* hunger-related.

Caveats:
- 50 rows is small.
- The sample was drawn as roughly half kept and half dropped by the original filter, so these percentages do not estimate accuracy across the whole dataset.
- No Oxfam America activities are included.
- One person did the labelling.
- Avoid tuning the keyword lists to these exact 50 rows. Label a fresh sample to confirm any gain.

[`tests/test_labelled_sample.py`](../tests/test_labelled_sample.py) fails if
precision drops below 70% or recall below 95% on this sample.

## Known limitations and open decisions

- **The filter is still a rule of thumb.** It is measured only on the
  50-row sample above. A larger, randomly drawn sample that includes Oxfam
  America would give a more reliable estimate.
- **163 `keyword_weak` activities need review**, nearly all Oxfam GB. The
  app and queries currently treat them the same as `keyword`. Filter on
  `match_basis` to exclude them.
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
| `test_broad_keywords.py` | Strong vs weak tiers, plurals, EFSVL, keywords past 2,000 characters |
| `test_org_names.py` | Organisation names are ignored, but real hunger work with WFP is still kept |
| `test_parse_fixture.py` | End-to-end: runs the parser on `fixture_iati_2.03.xml` (in a temporary folder, never `data/graph/`) and checks all 7 labelled activities |
| `test_labelled_sample.py` | Precision and recall on John's 50 hand-labelled activities stay above the floors |

The tests that show a problem in the code are the record of each issue. If
you change the filter, update the tests in the same change.
