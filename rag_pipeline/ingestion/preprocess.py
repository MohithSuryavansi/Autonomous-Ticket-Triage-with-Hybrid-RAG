"""
ingestion/preprocess.py

Loads enhanced_incidents.json, performs lightweight cleaning, and returns
a list of processed incident dicts ready for indexing.

Preprocessing is intentionally minimal — the dataset is already clean and
well-structured. We only:
  1. Strip leading/trailing whitespace from string fields.
  2. Normalise the keywords list (lowercase, deduplicate).
  3. Build the embed_text string used for both dense and sparse indexing.

spaCy is used purely for sentence tokenisation of the resolution field
(useful for future summarisation) — not for heavy NLP at this stage.
"""
import json
import re
from pathlib import Path
from typing import List, Dict

import spacy

# Lazy-load the small English model — only sentence boundaries needed
_NLP = None


def _get_nlp():
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "tagger"])
        except OSError:
            # Auto-download if not present
            from spacy.cli import download
            download("en_core_web_sm")
            _NLP = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "tagger"])
    return _NLP


def _clean_str(value: str) -> str:
    """Strip whitespace and collapse internal multiple spaces."""
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalise_keywords(kws) -> List[str]:
    """Lowercase, strip, deduplicate keywords while preserving order."""
    if not isinstance(kws, list):
        return []
    seen = set()
    result = []
    for k in kws:
        normed = _clean_str(k).lower()
        if normed and normed not in seen:
            seen.add(normed)
            result.append(normed)
    return result


def build_embed_text(incident: Dict) -> str:
    """
    Build the single string that is embedded and BM25-indexed per incident.
    Format: '<short_description>. <description>. Keywords: <kw1>, <kw2>, ...'
    """
    short = incident.get("short_description", "")
    desc = incident.get("description", "")
    kws = incident.get("keywords", [])
    kw_str = ", ".join(kws) if kws else ""
    return f"{short}. {desc}. Keywords: {kw_str}"


def preprocess(raw_path: Path) -> List[Dict]:
    """
    Load and lightly preprocess incidents from disk.

    Returns:
        List of incident dicts, each augmented with an 'embed_text' key.
    """
    with open(raw_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    processed = []
    for rec in records:
        # Clean string fields in-place
        for field in ("short_description", "description", "resolution", "affected_component",
                      "category", "assignment_group"):
            if field in rec and isinstance(rec[field], str):
                rec[field] = _clean_str(rec[field])

        # Normalise keywords
        rec["keywords"] = _normalise_keywords(rec.get("keywords", []))

        # Build embed text
        rec["embed_text"] = build_embed_text(rec)

        # Ensure the incident has a unique ID key — dataset uses 'number'
        if "id" not in rec and "number" in rec:
            rec["id"] = rec["number"]

        processed.append(rec)

    return processed


# ── Standalone run ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from rag_pipeline.config import INCIDENTS_FILE

    incidents = preprocess(INCIDENTS_FILE)
    print(f"Loaded and preprocessed {len(incidents)} incidents.")
    print("\nSample embed_text:")
    print(incidents[0]["embed_text"][:300])
