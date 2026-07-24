"""
Builds the coverage/quality report: aggregated CSV tables, a summary
markdown document, and a bar chart, all written to output/.

This is the "so what" layer of the pipeline -- fetch_data.py, classify.py,
recurring.py and severity.py all produce row-level detail; this module rolls
that detail up into the facility- and category-level view a compliance team
would actually read.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")  # write PNGs directly, no display/GUI backend needed
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Single accent color used for the category bar chart. This is a one-series
# magnitude comparison (citation count per category), so every bar gets the
# same hue rather than a distinct categorical color per bar -- a fixed
# per-category color palette would incorrectly imply the categories are
# being compared as identities rather than ranked by count.
_CHART_ACCENT_COLOR = "#3B6FA0"


def build_category_summary(df):
    """
    One row per category: citation count, share of all citations, recurring
    rate (by tag), and average severity rank -- the primary "where are the
    problems concentrated" table.
    """
    grouped = df.groupby("category").agg(
        citation_count=("category", "size"),
        recurring_count=("is_recurring", "sum"),
        avg_severity_rank=("severity_rank", "mean"),
    )
    grouped["recurring_rate"] = (grouped["recurring_count"] / grouped["citation_count"]).round(3)
    grouped["pct_of_total_citations"] = (grouped["citation_count"] / len(df) * 100).round(1)
    grouped["avg_severity_rank"] = grouped["avg_severity_rank"].round(2)

    return grouped.sort_values("citation_count", ascending=False).reset_index()


def build_severity_summary(df):
    """One row per severity band: count and share of all citations."""
    grouped = df.groupby("severity_label").agg(citation_count=("severity_label", "size"))
    grouped["pct_of_total_citations"] = (grouped["citation_count"] / len(df) * 100).round(1)
    # Order by clinical severity (Low -> Immediate Jeopardy), not alphabetically.
    order = [config.SEVERITY_BAND_LABELS[k] for k in sorted(config.SEVERITY_BAND_LABELS)] + ["Unknown"]
    grouped = grouped.reindex([label for label in order if label in grouped.index])
    return grouped.reset_index()


def build_facility_summary(df, top_n=20):
    """
    Top facilities by citation volume, with recurring-citation counts and
    average severity -- surfaces which facilities warrant closer follow-up.
    """
    grouped = df.groupby(["cms_certification_number_ccn", "provider_name", "state"]).agg(
        citation_count=("cms_certification_number_ccn", "size"),
        recurring_count=("is_recurring", "sum"),
        avg_severity_rank=("severity_rank", "mean"),
        immediate_jeopardy_count=("severity_rank", lambda s: (s == 4).sum()),
    )
    grouped["avg_severity_rank"] = grouped["avg_severity_rank"].round(2)
    grouped = grouped.sort_values(["citation_count", "avg_severity_rank"], ascending=False)
    return grouped.head(top_n).reset_index()


def write_category_chart(category_summary, output_path):
    """Horizontal bar chart of citation counts by category, most-cited first."""
    ordered = category_summary.sort_values("citation_count", ascending=True)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(ordered["category"], ordered["citation_count"], color=_CHART_ACCENT_COLOR)

    ax.set_xlabel("Citation count")
    ax.set_title("Nursing Home Deficiency Citations by Category")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", color="#DDDDDD", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def write_markdown_report(category_summary, severity_summary, facility_summary, state, output_path, chart_filename):
    lines = []
    lines.append(f"# Nursing Home Deficiency Coverage & Quality Report -- {state}\n")
    lines.append(f"Total citations analyzed: **{int(category_summary['citation_count'].sum())}**\n")

    lines.append("## Citations by Category\n")
    lines.append(f"![Citations by category]({chart_filename})\n")
    lines.append(category_summary.to_markdown(index=False))
    lines.append("")

    lines.append("## Citations by Severity Band\n")
    lines.append(severity_summary.to_markdown(index=False))
    lines.append("")

    lines.append(f"## Top {len(facility_summary)} Facilities by Citation Volume\n")
    lines.append(facility_summary.to_markdown(index=False))
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def generate_report(df, state):
    """
    Entry point used by main.py. df must already have category, severity_*,
    and is_recurring columns populated (see classify.py / severity.py /
    recurring.py). Writes CSVs, a PNG chart, and a markdown report into
    config.OUTPUT_DIR, and returns the paths written.
    """
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    category_summary = build_category_summary(df)
    severity_summary = build_severity_summary(df)
    facility_summary = build_facility_summary(df)

    category_csv = os.path.join(config.OUTPUT_DIR, "category_summary.csv")
    severity_csv = os.path.join(config.OUTPUT_DIR, "severity_summary.csv")
    facility_csv = os.path.join(config.OUTPUT_DIR, "facility_summary.csv")
    chart_path = os.path.join(config.OUTPUT_DIR, "category_chart.png")
    report_path = os.path.join(config.OUTPUT_DIR, "report.md")

    category_summary.to_csv(category_csv, index=False)
    severity_summary.to_csv(severity_csv, index=False)
    facility_summary.to_csv(facility_csv, index=False)
    write_category_chart(category_summary, chart_path)
    write_markdown_report(
        category_summary, severity_summary, facility_summary, state,
        report_path, os.path.basename(chart_path),
    )

    return {
        "category_summary_csv": category_csv,
        "severity_summary_csv": severity_csv,
        "facility_summary_csv": facility_csv,
        "chart_png": chart_path,
        "report_md": report_path,
    }
