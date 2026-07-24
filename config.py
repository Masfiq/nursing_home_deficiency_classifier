"""
Central configuration for the Nursing Home Deficiency Classifier pipeline.

Keeping every constant in one file means fetch_data.py, classify.py,
recurring.py, and report.py all agree on paths, the CMS dataset id, the
category taxonomy, and the severity grid without importing each other.
"""

import os

# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------
# PROJECT_ROOT is the folder this file lives in, so the pipeline works no
# matter what directory it is *run* from (e.g. `python src/main.py` from
# elsewhere would otherwise write data/output in the wrong place).
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

# Where the per-tag LLM classification results are cached, keyed by
# deficiency_tag_number, so a re-run never re-pays for a tag it already
# classified.
CLASSIFICATION_CACHE_PATH = os.path.join(CACHE_DIR, "tag_classifications.json")

# ---------------------------------------------------------------------------
# CMS Provider Data Catalog API
# ---------------------------------------------------------------------------
# "Health Deficiencies" dataset on data.cms.gov. Identifier confirmed live
# against the CMS metastore on 2026-07-16:
#   https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items
CMS_API_BASE = "https://data.cms.gov/provider-data/api/1"
CMS_DEFICIENCIES_DATASET_ID = "r5ix-sfxw"
CMS_PAGE_SIZE = 500  # rows per HTTP request when paginating the datastore query

# ---------------------------------------------------------------------------
# Category taxonomy
# ---------------------------------------------------------------------------
# CMS's own "deficiency_category" field is broad (12 buckets, e.g.
# "Quality of Life and Care Deficiencies") and mixes unrelated concerns
# together. This project reclassifies each unique F-tag regulatory
# description into a finer, operationally useful taxonomy that mirrors how
# a quality/compliance team actually triages citations.
CATEGORY_TAXONOMY = [
    "Medication Management",
    "Fall Risk & Accident Prevention",
    "Staffing & Supervision",
    "Infection Control",
    "Dignity & Resident Rights",
    "Nutrition & Hydration",
    "Care Planning & Assessment",
    "Abuse & Neglect Prevention",
    "Facility & Environment Safety",
    "Administrative & Reporting",
    "Other",
]

# ---------------------------------------------------------------------------
# CMS scope/severity grid
# ---------------------------------------------------------------------------
# Every health citation gets a single letter (A-L) from CMS's official
# 4x3 scope/severity grid. This mapping is public and fixed by CMS
# regulation (42 CFR 488), so it is applied deterministically rather than
# guessed by an LLM.
#   Rows    = severity of harm (increasing)
#   Columns = scope (Isolated / Pattern / Widespread)
SCOPE_SEVERITY_GRID = {
    "A": {"harm_level": "No actual harm, potential for minimal harm", "scope": "Isolated", "severity_rank": 1},
    "B": {"harm_level": "No actual harm, potential for minimal harm", "scope": "Pattern", "severity_rank": 1},
    "C": {"harm_level": "No actual harm, potential for minimal harm", "scope": "Widespread", "severity_rank": 1},
    "D": {"harm_level": "No actual harm, potential for more than minimal harm", "scope": "Isolated", "severity_rank": 2},
    "E": {"harm_level": "No actual harm, potential for more than minimal harm", "scope": "Pattern", "severity_rank": 2},
    "F": {"harm_level": "No actual harm, potential for more than minimal harm", "scope": "Widespread", "severity_rank": 2},
    "G": {"harm_level": "Actual harm, not immediate jeopardy", "scope": "Isolated", "severity_rank": 3},
    "H": {"harm_level": "Actual harm, not immediate jeopardy", "scope": "Pattern", "severity_rank": 3},
    "I": {"harm_level": "Actual harm, not immediate jeopardy", "scope": "Widespread", "severity_rank": 3},
    "J": {"harm_level": "Immediate jeopardy to resident health or safety", "scope": "Isolated", "severity_rank": 4},
    "K": {"harm_level": "Immediate jeopardy to resident health or safety", "scope": "Pattern", "severity_rank": 4},
    "L": {"harm_level": "Immediate jeopardy to resident health or safety", "scope": "Widespread", "severity_rank": 4},
}

SEVERITY_BAND_LABELS = {
    1: "Low",
    2: "Moderate",
    3: "High",
    4: "Immediate Jeopardy",
}

# ---------------------------------------------------------------------------
# Recurrence detection
# ---------------------------------------------------------------------------
# A citation is flagged "recurring" if the same facility (CCN) was cited for
# the same F-tag in a *previous* survey within this many days. 3 years
# roughly spans the standard survey cycle (annual, but can slip), so it
# catches a facility that keeps failing the same requirement.
RECURRING_LOOKBACK_DAYS = 3 * 365

# ---------------------------------------------------------------------------
# Anthropic (Claude) API
# ---------------------------------------------------------------------------
# Switched to Haiku 4.5 (from Opus 4.8) to minimize usage across a run of
# several classification projects -- Haiku is priced roughly 5x cheaper per
# token than Opus and responds faster per call, at some cost to nuanced
# judgment on genuinely ambiguous F-tags.
ANTHROPIC_MODEL = "claude-haiku-4-5"
ANTHROPIC_API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"
