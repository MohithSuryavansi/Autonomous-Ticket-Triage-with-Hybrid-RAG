"""
processing/classification.py

Lightweight intent classifier that routes the query before hitting the full
retrieval pipeline.

Routes:
  - GREETING  → short canned response, no retrieval needed
  - INCIDENT  → standard RAG pipeline (default)

Implemented as simple pattern matching — no model call needed for this.
ponytail: LLM-based classification would add ~2s latency for zero gain on
          well-structured IT support queries. Upgrade path: replace with
          a small local classifier if query diversity grows significantly.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROUTE_GREETING = "GREETING"
ROUTE_INCIDENT = "INCIDENT"

_GREETING_PATTERNS = re.compile(
    r"^\s*(hi|hello|hey|howdy|greetings|good\s?(morning|afternoon|evening)|what'?s?\s?up|yo)\W*$",
    re.IGNORECASE,
)


def classify(query: str) -> str:
    """
    Return one of: GREETING, INCIDENT.

    Args:
        query: Pre-processed user query string.

    Returns:
        Route constant string.
    """
    if _GREETING_PATTERNS.match(query):
        return ROUTE_GREETING
    return ROUTE_INCIDENT


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        "Hello!",
        "hi there",
        "database connection timeout",
        "RBAC permission denied on sales UI",
        "Good morning",
    ]
    for t in tests:
        print(f"  {classify(t):10s} | {t!r}")
