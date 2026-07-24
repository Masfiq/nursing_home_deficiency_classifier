"""
Deterministic mapping from CMS's official A-L scope/severity letter code to
a human-readable harm level, scope, and 1-4 severity rank.

This is NOT something to ask an LLM to judge: CMS fixes this grid by
regulation (42 CFR 488), so every citation's letter code maps to exactly one
cell. Keeping it as a lookup table (see config.SCOPE_SEVERITY_GRID) means the
severity band on the report is always regulator-accurate, and the LLM budget
in classify.py is spent only on the genuinely ambiguous part: category
tagging.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def scope_severity_lookup(code):
    """
    Look up one scope/severity letter code (A-L). Returns a dict with
    harm_level, scope, severity_rank (1-4), and severity_label. Unknown or
    missing codes map to a clearly-marked "Unknown" bucket rather than
    raising, since CMS data occasionally has blank codes for administrative
    citations.
    """
    if not isinstance(code, str):
        code = ""
    code = code.strip().upper()

    entry = config.SCOPE_SEVERITY_GRID.get(code)
    if entry is None:
        return {
            "harm_level": "Unknown",
            "scope": "Unknown",
            "severity_rank": 0,
            "severity_label": "Unknown",
        }

    return {
        "harm_level": entry["harm_level"],
        "scope": entry["scope"],
        "severity_rank": entry["severity_rank"],
        "severity_label": config.SEVERITY_BAND_LABELS[entry["severity_rank"]],
    }


def annotate_severity(df, code_column="scope_severity_code"):
    """
    Add severity_rank / severity_label / harm_level / scope columns to a
    citations DataFrame, derived purely from the existing scope_severity_code
    column (no network or LLM call).
    """
    looked_up = df[code_column].apply(scope_severity_lookup)
    df = df.copy()
    df["severity_rank"] = looked_up.apply(lambda d: d["severity_rank"])
    df["severity_label"] = looked_up.apply(lambda d: d["severity_label"])
    df["harm_level"] = looked_up.apply(lambda d: d["harm_level"])
    df["scope"] = looked_up.apply(lambda d: d["scope"])
    return df
