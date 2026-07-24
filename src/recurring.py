"""
Flags citations as "recurring" using plain date/group logic on the CMS
data -- no LLM involved. A citation is recurring when the same facility was
cited for the same F-tag in an earlier survey within the lookback window
(config.RECURRING_LOOKBACK_DAYS), which is the operationally useful
definition of "this facility keeps failing the same requirement."
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def annotate_recurring(
    df,
    facility_column="cms_certification_number_ccn",
    tag_column="deficiency_tag_number",
    date_column="survey_date",
):
    """
    Add an is_recurring boolean column: True if the same facility was cited
    for the same tag_number in a strictly earlier survey within
    config.RECURRING_LOOKBACK_DAYS days.
    """
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")

    df = df.sort_values([facility_column, tag_column, date_column])

    # Within each facility+tag group, the prior survey date is just the
    # previous row's date once sorted chronologically.
    prior_date = df.groupby([facility_column, tag_column])[date_column].shift(1)
    gap_days = (df[date_column] - prior_date).dt.days

    df["is_recurring"] = gap_days.notna() & (gap_days <= config.RECURRING_LOOKBACK_DAYS)
    df["days_since_prior_same_tag_citation"] = gap_days

    return df


def annotate_recurring_by_category(
    df,
    facility_column="cms_certification_number_ccn",
    category_column="category",
    date_column="survey_date",
):
    """
    Coarser companion signal: True if the same facility was cited for the
    same operational *category* (not necessarily the same F-tag) in an
    earlier survey within the lookback window. Useful for spotting a
    facility with a persistent category of problems even if the specific
    regulation cited varies between inspections.
    """
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")

    df = df.sort_values([facility_column, category_column, date_column])
    prior_date = df.groupby([facility_column, category_column])[date_column].shift(1)
    gap_days = (df[date_column] - prior_date).dt.days

    df["is_recurring_category"] = gap_days.notna() & (gap_days <= config.RECURRING_LOOKBACK_DAYS)

    return df
