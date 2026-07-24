"""
Pulls nursing home Health Deficiency citations from the CMS Provider Data
Catalog (data.cms.gov) and caches the raw result to a local CSV.

Dataset: "Health Deficiencies" (id r5ix-sfxw), part of the CMS Nursing Home
Care Compare data. Each row is one F-tag citation from one inspection of one
facility. The dataset already carries CMS's own broad `deficiency_category`
(12 buckets) plus the regulatory tag description text (`deficiency_description`)
and a scope/severity letter code — but not a facility-specific narrative, so
downstream classification (classify.py) operates on the ~150-200 unique
regulatory descriptions rather than per-citation free text.
"""

import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _fetch_page(state, offset, limit):
    """
    Fetch one page of citation rows for a given state from the CMS datastore
    query API. Returns (rows, total_count) so the caller can decide whether
    to keep paginating.
    """
    url = f"{config.CMS_API_BASE}/datastore/query/{config.CMS_DEFICIENCIES_DATASET_ID}/0"
    params = {
        "limit": limit,
        "offset": offset,
        "conditions[0][property]": "state",
        "conditions[0][value]": state,
        "conditions[0][operator]": "=",
    }
    # CMS occasionally throttles or has transient 5xx errors; retry a few
    # times with backoff before giving up, since this is a batch job, not an
    # interactive request that needs to fail fast.
    last_error = None
    for attempt in range(4):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["results"], data["count"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"CMS API request failed after retries: {last_error}")


def fetch_deficiencies(state, max_rows=None):
    """
    Pull every Health Deficiency citation row for one two-letter state code,
    paginating through the CMS datastore API.

    max_rows caps how many rows are pulled (useful for a quick demo run);
    None pulls the full set available for that state.
    """
    all_rows = []
    offset = 0
    total_count = None

    while True:
        page_size = min(config.CMS_PAGE_SIZE, (max_rows - len(all_rows)) if max_rows else config.CMS_PAGE_SIZE)
        if page_size <= 0:
            break
        rows, total_count = _fetch_page(state, offset, page_size)
        if not rows:
            break
        all_rows.extend(rows)
        offset += len(rows)
        if max_rows and len(all_rows) >= max_rows:
            break
        if offset >= total_count:
            break

    df = pd.DataFrame(all_rows)
    return df


def save_raw(df, state):
    """Write the fetched rows to data/raw/ so re-runs can skip the network call."""
    os.makedirs(config.RAW_DATA_DIR, exist_ok=True)
    path = os.path.join(config.RAW_DATA_DIR, f"deficiencies_{state}.csv")
    df.to_csv(path, index=False)
    return path


def load_or_fetch(state, max_rows=None, force_refresh=False):
    """
    Entry point used by main.py: reuse a previously saved CSV for this state
    unless force_refresh is set, otherwise hit the CMS API and cache the
    result.
    """
    path = os.path.join(config.RAW_DATA_DIR, f"deficiencies_{state}.csv")
    if not force_refresh and os.path.exists(path):
        return pd.read_csv(path, dtype=str)

    df = fetch_deficiencies(state, max_rows=max_rows)
    save_raw(df, state)
    return df
