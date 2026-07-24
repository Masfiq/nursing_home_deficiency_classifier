"""
CLI entry point that runs the full pipeline end to end:

  1. fetch_data  -- pull CMS Health Deficiency citations for one state
  2. classify    -- tag each unique F-tag description with an operational
                     category (Claude, cached per tag)
  3. severity    -- derive severity band deterministically from CMS's own
                     scope/severity code (no LLM needed)
  4. recurring   -- flag facilities repeatedly cited for the same tag
  5. report      -- write CSV summaries, a chart, and a markdown report

Usage:
    python src/main.py --state RI
    python src/main.py --state RI --max-rows 500 --force-refresh
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src import fetch_data, classify, severity, recurring, report


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--state", default="RI",
        help="Two-letter US state code to pull CMS deficiency data for (default: RI).",
    )
    parser.add_argument(
        "--max-rows", type=int, default=None,
        help="Cap on citation rows pulled from CMS (omit for the full state history).",
    )
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Re-fetch from the CMS API even if a cached CSV for this state already exists.",
    )
    return parser.parse_args()


def run(state, max_rows=None, force_refresh=False):
    print(f"[1/5] Fetching CMS Health Deficiency citations for state={state} ...")
    df = fetch_data.load_or_fetch(state, max_rows=max_rows, force_refresh=force_refresh)
    print(f"      {len(df)} citation rows loaded.")

    print("[2/5] Classifying unique F-tag descriptions ...")
    classifications = classify.classify_unique_tags(df)
    df = classify.apply_classifications(df, classifications)
    print(f"      {len(classifications)} unique tags classified (cached at {config.CLASSIFICATION_CACHE_PATH}).")

    print("[3/5] Deriving severity bands from CMS scope/severity codes ...")
    df = severity.annotate_severity(df)

    print("[4/5] Flagging recurring citations ...")
    df = recurring.annotate_recurring(df)
    df = recurring.annotate_recurring_by_category(df)

    print("[5/5] Building coverage/quality report ...")
    paths = report.generate_report(df, state)

    print("\nDone. Wrote:")
    for label, path in paths.items():
        print(f"  {label}: {path}")

    return df, paths


if __name__ == "__main__":
    args = parse_args()
    run(state=args.state, max_rows=args.max_rows, force_refresh=args.force_refresh)
