"""
processing/query_preprocessing.py

Lightweight query cleaning and formatting before embedding or retrieval.

Steps:
  1. Strip/collapse whitespace.
  2. Remove non-printable characters.
  3. (Optional) spell-check — skipped for now; Qwen3 handles typos well.

Does NOT do heavy NLP (no lemmatisation, stopword removal) because
modern embedding models perform better on natural language than
pre-stemmed tokens.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def preprocess_query(query: str) -> str:
    """
    Clean a raw user query string.

    Returns:
        Cleaned string ready to be embedded / BM25-tokenised.
    """
    # Remove non-printable / control characters
    query = re.sub(r"[^\x20-\x7E]", " ", query)
    # Collapse whitespace
    query = re.sub(r"\s+", " ", query).strip()
    return query


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    raw = "  database   connection \t timeout ??  "
    print(repr(preprocess_query(raw)))
