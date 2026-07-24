# Nursing Home Deficiency Classifier

Every nursing home in the US that accepts Medicare or Medicaid — which is nearly all of them — gets inspected regularly by CMS (the Centers for Medicare & Medicaid Services), and every time an inspector finds a facility falling short of a federal requirement, it gets written up as a citation against a specific regulation, called an F-tag. All of that is public data. The problem is that CMS's own way of grouping these citations is broad and a little clumsy — a single bucket like "Quality of Life and Care Deficiencies" can quietly contain everything from incontinence care to fall hazards to dialysis, all lumped together — so if you actually wanted to answer something specific, like "how many of this facility's citations are about falls," the raw data won't tell you that on its own.

This project fixes that. It pulls real inspection data for a US state straight from CMS, has Claude sort each unique regulation into a clearer, more useful category, and builds a report that actually says something: which problems show up most, how severe they were, and which facilities keep getting cited for the same thing over and over.

## What it actually does

1. **Pulls real citation data** for one US state from CMS's public API — no account, no API key needed for this part, it's open data.
2. **Re-classifies every unique F-tag** into a cleaner category — medication errors, fall risk, staffing, infection control, dignity and resident rights, and so on — using Claude. This is the one genuinely ambiguous step in the pipeline: a lot of these regulations plausibly touch more than one category, and a simple keyword search just isn't equipped to make that call well (more on that below).
3. **Figures out how severe each citation was** — but not with Claude. Every citation already carries an official letter grade (A through L) from CMS's own severity grid, so this is a fixed, deterministic lookup, not a judgment call.
4. **Flags citations as recurring** when the same facility gets cited for the same problem again within a few years — a plain date comparison, no model involved.
5. **Builds a report** — category breakdowns, severity bands, which facilities have the most citations, a chart, and a written summary pulling it all together.

## Why some of this needs Claude, and some of it really doesn't

The honest answer to "why not just write rules for this" is: for two of the four things this project figures out, you're right, rules are exactly the correct tool, and that's what's actually used.

**Severity is a lookup table, not a model call.** CMS already grades every citation on an official A–L scale defined by federal regulation — it's not ambiguous, it's not something that needs interpreting, it's already decided. Asking an LLM to re-derive it would just be introducing a chance to get something wrong that was already correct.

**Recurring is date math.** Same facility, same F-tag, within a few years of the last time — that's a `groupby` and a date subtraction, not a classification problem.

**Category is genuinely a judgment call**, and this is where a plain keyword search actually falls apart. Take F0553, one of the real regulations in this dataset: *"Allow resident to participate in the development and implementation of his or her person-centered plan of care."* There's no obvious keyword in there — no mention of "rights," no mention of "care plan" as a phrase — but a person reading it immediately recognizes it as a resident-autonomy issue. When this project was first tested with a plain keyword-matching fallback (for when no Claude access is configured), 48% of citations couldn't be confidently placed anywhere and landed in a generic "Other" bucket. With real Claude classification against the same data, that dropped to 1.2%. That gap is the entire reason this step goes through an LLM instead of a hand-written rule list.

## An honest note on what "accuracy" means here

CMS's own category field is broad, but there's no official, fine-grained answer key for "the correct operational category" for each F-tag — this taxonomy was designed for this project, not published by CMS. So there's no ground truth to compute real precision against, and nothing here claims one. What the 48% → 1.2% comparison actually measures is *coverage* — how often each method could confidently commit to a specific category instead of giving up — not correctness against a labeled answer key. If two categories both seem defensible for the same regulation, that's not a bug, it's just a genuinely fuzzy taxonomy boundary; a different reasonable person might file it differently too.

## Project layout

```
config.py              Central constants: CMS dataset id, the category taxonomy, the severity
                        grid, the recurring lookback window, and the Claude model in use.
src/fetch_data.py       CMS API client, paginated, with local CSV caching so a repeat run
                        doesn't re-download the same state's data.
src/classify.py         Claude-based classification, once per unique F-tag (not per citation --
                        the same ~150-200 regulations repeat across thousands of citations), with
                        a JSON-schema-constrained response and a disk cache. Falls back to a
                        keyword heuristic, clearly labeled as such, if no ANTHROPIC_API_KEY is set.
src/severity.py         Deterministic scope/severity letter -> band mapping. No LLM, no ambiguity.
src/recurring.py        Deterministic recurrence detection based on facility + F-tag + date.
src/report.py           Aggregation, the chart, and the final markdown report.
src/main.py             The CLI entry point that runs all of the above in order.
data/raw/               Cached CSVs of fetched CMS citation data.
data/cache/             Cached Claude classification results, keyed by F-tag.
output/                 The generated CSV summaries, chart, and report.md.
```

## Setup

```bash
cd nursing_home_deficiency_classifier
pip install -r requirements.txt

# Optional, for real Claude classification. Without this, classify.py falls
# back to a keyword heuristic instead -- clearly labeled as such in its
# output, so the pipeline still runs end to end for testing without it.
export ANTHROPIC_API_KEY=sk-ant-...
```

## Running it

```bash
python src/main.py --state RI
python src/main.py --state RI --max-rows 500      # a quick, cheaper demo run
python src/main.py --state RI --force-refresh      # bypass the cached CSV and re-pull from CMS
```

`--state` takes any two-letter US state code. Smaller states (RI, VT, DE, NH, MT, WY) make for a fast demo; drop `--max-rows` for a state's full inspection history.

## Output

| File | What's in it |
|---|---|
| `output/category_summary.csv` | Citations by category — count, share of total, recurring rate, average severity |
| `output/severity_summary.csv` | Citations by severity band |
| `output/facility_summary.csv` | The facilities with the most citations, and how severe/recurring they are |
| `output/category_chart.png` | A bar chart of citations by category |
| `output/report.md` | Everything above, written up as one readable report |

## Where this came from

The first in a small series of classification projects, each one turning messy public data into something structured enough to actually act on. This one set the pattern the others followed: figure out which parts of the problem are genuinely ambiguous and deserve an LLM's judgment, and which parts are already decided by an authority (CMS, in this case) and should be a plain, deterministic lookup instead.
