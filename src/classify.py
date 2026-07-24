"""
Assigns each unique CMS F-tag regulatory description to a finer-grained
operational category (see config.CATEGORY_TAXONOMY) using Claude.

Why per-tag instead of per-citation: the CMS dataset repeats the same ~150-200
boilerplate regulatory descriptions across thousands of citation rows (one
per facility per inspection). Classifying each unique description once, then
joining the result back onto every citation that uses it, turns an O(rows)
LLM job into an O(unique tags) one -- a couple hundred calls instead of tens
of thousands -- and every result is cached to disk so a re-run of the
pipeline costs nothing extra.

If no Anthropic API key is configured, classification falls back to a small
keyword-matching heuristic so the rest of the pipeline (recurrence, report)
can still be exercised end-to-end without spending API credits. The fallback
is explicitly labeled in its output and is not a substitute for the LLM particularly
on ambiguous tags.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# JSON schema Claude's output is constrained to, via Structured Outputs
# (output_config.format). Guarantees every response is valid JSON with a
# category from our fixed taxonomy -- no prompt-injection-driven or
# malformed category values can leak into the report.
_CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": config.CATEGORY_TAXONOMY,
        },
        "rationale": {
            "type": "string",
            "description": "One sentence explaining why this category was chosen.",
        },
    },
    "required": ["category", "rationale"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "You are helping a nursing home quality-and-compliance team triage CMS "
    "health inspection citations. Each input is the official regulatory "
    "description of one F-tag deficiency (the requirement a facility failed "
    "to meet, not a facility-specific narrative). Assign it to exactly one "
    "category from the fixed taxonomy provided, choosing the single best fit "
    "even when a description could plausibly touch more than one category. "
    "Use 'Other' only when nothing else reasonably applies."
)


def _build_prompt(tag_number, description):
    return (
        f"F-tag {tag_number} regulatory description:\n\"{description}\"\n\n"
        f"Categories: {', '.join(config.CATEGORY_TAXONOMY)}"
    )


def _load_cache():
    if not os.path.exists(config.CLASSIFICATION_CACHE_PATH):
        return {}
    with open(config.CLASSIFICATION_CACHE_PATH, "r") as f:
        return json.load(f)


def _save_cache(cache):
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(config.CLASSIFICATION_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


# Small keyword heuristic used only when no API key is available, so the
# pipeline remains runnable (fetch -> classify -> recurring -> report) for
# demoing or testing without spending API credits. Order matters: first
# matching rule wins, so more specific rules are listed before general ones.
_FALLBACK_KEYWORD_RULES = [
    ("Medication Management", ["medication", "drug", "pharmac"]),
    ("Infection Control", ["infection", "communicable disease", "sanitary"]),
    ("Fall Risk & Accident Prevention", ["accident", "fall", "hazard", "supervision to prevent"]),
    ("Abuse & Neglect Prevention", ["abuse", "neglect", "exploitation", "mistreatment"]),
    ("Dignity & Resident Rights", ["dignity", "rights", "privacy", "grievance"]),
    ("Nutrition & Hydration", ["nutrition", "hydration", "weight loss", "meal", "food"]),
    ("Staffing & Supervision", ["staffing", "nurse staffing", "sufficient staff"]),
    ("Care Planning & Assessment", ["care plan", "assessment", "comprehensive care"]),
    ("Administrative & Reporting", ["submit", "report", "record", "administration", "governing body"]),
    ("Facility & Environment Safety", ["fire", "egress", "equipment", "environment", "building"]),
]


def _fallback_classify(description):
    text = description.lower()
    for category, keywords in _FALLBACK_KEYWORD_RULES:
        if any(kw in text for kw in keywords):
            return {
                "category": category,
                "rationale": "Offline keyword-fallback match (no ANTHROPIC_API_KEY set) -- not LLM-verified.",
            }
    return {
        "category": "Other",
        "rationale": "Offline keyword-fallback found no match (no ANTHROPIC_API_KEY set) -- not LLM-verified.",
    }


def _classify_with_claude(client, tag_number, description):
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=300,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(tag_number, description)}],
        output_config={"format": {"type": "json_schema", "schema": _CLASSIFICATION_SCHEMA}},
    )
    text_block = next(b.text for b in response.content if b.type == "text")
    return json.loads(text_block)


def classify_unique_tags(df, tag_column="deficiency_tag_number", description_column="deficiency_description"):
    """
    Classify every unique (tag_number, description) pair found in df,
    reusing cached results from previous runs. Returns a dict keyed by
    tag_number -> {"category": ..., "rationale": ...}.
    """
    unique_tags = (
        df[[tag_column, description_column]]
        .drop_duplicates(subset=[tag_column])
        .dropna(subset=[tag_column])
    )

    cache = _load_cache()

    api_key_present = bool(os.environ.get(config.ANTHROPIC_API_KEY_ENV_VAR))
    client = None
    if api_key_present:
        import anthropic  # imported lazily so the fallback path has no hard dependency
        client = anthropic.Anthropic()

    newly_classified = 0
    for _, row in unique_tags.iterrows():
        tag_number = str(row[tag_column])
        description = str(row[description_column])

        if tag_number in cache:
            continue

        if client is not None:
            try:
                cache[tag_number] = _classify_with_claude(client, tag_number, description)
            except Exception as exc:  # noqa: BLE001 -- log and fall back rather than aborting the whole batch
                cache[tag_number] = _fallback_classify(description)
                cache[tag_number]["rationale"] += f" (Claude call failed: {exc})"
        else:
            cache[tag_number] = _fallback_classify(description)

        newly_classified += 1

    if newly_classified:
        _save_cache(cache)

    return cache


def apply_classifications(df, classifications, tag_column="deficiency_tag_number"):
    """Join the per-tag classification dict back onto every citation row."""
    df = df.copy()
    df["category"] = df[tag_column].astype(str).map(lambda t: classifications.get(t, {}).get("category", "Other"))
    df["category_rationale"] = df[tag_column].astype(str).map(lambda t: classifications.get(t, {}).get("rationale", ""))
    return df
