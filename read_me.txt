NURSING HOME DEFICIENCY CLASSIFIER
===================================

WHAT THIS PROJECT IS
---------------------
CMS (the Centers for Medicare & Medicaid Services) publishes inspection and
deficiency data for every certified nursing home in the US, free and without
credentialing, via the CMS Provider Data Catalog (data.cms.gov). Every health
inspection cites deficiencies against a fixed set of federal regulations
("F-tags"), but CMS's own categorization of those F-tags is broad (12 buckets
like "Quality of Life and Care Deficiencies") and mixes unrelated concerns
together, which makes it hard to search or triage citations the way an actual
compliance/quality team would want to: by concrete operational category
(medication errors, fall risk, staffing, infection control, dignity/rights,
etc.), by severity, and by whether a facility keeps failing the same
requirement across inspections.

This project builds a pipeline that:
  1. Pulls real citation data for one US state from the CMS public API.
  2. Re-classifies each unique F-tag regulatory description into a finer,
     operationally useful category using Claude (this is the genuinely
     ambiguous, LLM-worthy part -- many F-tag descriptions plausibly touch
     more than one category).
  3. Derives a severity band for every citation deterministically from CMS's
     own official scope/severity grid (a fixed regulatory lookup table --
     not something to ask an LLM to guess).
  4. Flags citations as "recurring" when the same facility was cited for the
     same F-tag (or the same category) in an earlier inspection within a
     configurable lookback window.
  5. Produces a coverage/quality report: CSV summaries by category,
     severity, and facility, a bar chart, and a markdown report.

HONEST SCOPE NOTE
------------------
CMS's public bulk API exposes the *regulatory* description of each F-tag
(the requirement text, ~150-200 unique strings across the whole dataset) and
citation-level metadata (facility, date, scope/severity code, correction
status) -- but not the inspector's facility-specific narrative from the
Statement of Deficiencies (CMS Form 2567), which is only published as
per-facility PDFs, not as a bulk dataset. So this pipeline classifies each
unique regulatory description once (cached, since ~150-200 unique tags cover
thousands of citation rows) rather than classifying free text per citation.
The classification task is still genuinely ambiguous -- e.g. an F-tag about
"sufficient staff to provide care" could reasonably be tagged Staffing &
Supervision or Care Planning & Assessment -- which is why it goes to Claude
rather than a fixed lookup table.

DATA SOURCE
------------
Dataset: "Health Deficiencies" on the CMS Provider Data Catalog.
  Dataset id:  r5ix-sfxw
  API base:    https://data.cms.gov/provider-data/api/1/datastore/query
No API key or account is required to read this dataset; it's public.

CATEGORY TAXONOMY (assigned by Claude, per unique F-tag)
-----------------------------------------------------------
  Medication Management
  Fall Risk & Accident Prevention
  Staffing & Supervision
  Infection Control
  Dignity & Resident Rights
  Nutrition & Hydration
  Care Planning & Assessment
  Abuse & Neglect Prevention
  Facility & Environment Safety
  Administrative & Reporting
  Other

SEVERITY (derived deterministically, no LLM)
-----------------------------------------------
Every CMS citation carries a single letter A-L from the official federal
scope/severity grid (42 CFR 488): rows are harm level (no actual harm ->
immediate jeopardy), columns are scope (isolated / pattern / widespread).
This project maps that letter to a 1-4 severity rank and label (Low,
Moderate, High, Immediate Jeopardy) via a fixed lookup table in config.py --
this is public regulatory structure, so there's nothing to classify here.

RECURRING (derived deterministically, no LLM)
-------------------------------------------------
A citation is flagged "recurring" if the same facility (by CMS Certification
Number) was cited for the same F-tag in a prior survey within the lookback
window (default 3 years, config.RECURRING_LOOKBACK_DAYS). A coarser
category-level recurring flag is also computed, for facilities whose
citations shift F-tag but stay in the same operational category.

PROJECT LAYOUT
----------------
  config.py            Central constants: CMS dataset id, category taxonomy,
                        severity grid, recurring window, Claude model.
  src/fetch_data.py     CMS API client with pagination + local CSV caching.
  src/classify.py       Claude-based per-tag classification, with a JSON
                        schema-constrained response and disk cache so re-runs
                        don't re-pay for tags already classified. Falls back
                        to a keyword heuristic (clearly labeled) if no
                        ANTHROPIC_API_KEY is set, so the rest of the pipeline
                        is still runnable/testable without API cost.
  src/severity.py       Deterministic scope/severity code -> band mapping.
  src/recurring.py      Deterministic recurrence detection.
  src/report.py         Aggregation, chart, and markdown report generation.
  src/main.py           CLI entry point wiring the above into one run.
  data/raw/             Cached CSVs of fetched CMS citation data (gitignored).
  data/cache/           Cached Claude classification results, keyed by F-tag
                         (gitignored).
  output/               Generated CSV summaries, chart, and report.md
                         (gitignored).

SETUP
------
  1. cd nursing_home_deficiency_classifier
  2. pip install -r requirements.txt
  3. (optional, for LLM classification) export ANTHROPIC_API_KEY=sk-ant-...
     Without this, classify.py uses an offline keyword fallback instead of
     Claude, clearly labeled as such in its output, so the pipeline still
     runs end to end for testing.

RUNNING
--------
  python src/main.py --state RI
  python src/main.py --state RI --max-rows 500      # quick demo run
  python src/main.py --state RI --force-refresh      # bypass the CSV cache

--state accepts any two-letter US state code. Smaller states (RI, VT, DE,
NH, MT, WY) keep the demo fast; omit --max-rows for the full state history.

OUTPUT
-------
  output/category_summary.csv    Citations by category: count, share,
                                  recurring rate, average severity.
  output/severity_summary.csv    Citations by severity band.
  output/facility_summary.csv    Top facilities by citation volume, with
                                  recurring counts and average severity.
  output/category_chart.png      Bar chart of citations by category.
  output/report.md               Everything above, assembled into one
                                  readable markdown report.

WHY THIS PROJECT
-----------------
Originally scoped as a portfolio/take-home style project: real regulatory
content, genuine classification ambiguity, and a finished coverage/quality
report deliverable -- built here end to end against live public CMS data.



