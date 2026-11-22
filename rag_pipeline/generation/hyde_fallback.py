"""
generation/hyde_fallback.py

HyDE (Hypothetical Document Embedding) fallback.

When the top reranked candidate's score is below HYDE_CONFIDENCE_THRESHOLD,
we ask the LLM to generate a *hypothetical* ideal incident description for
the query. That hypothetical document is then embedded and used as the
dense-retrieval query instead of the raw user query, which often surfaces
better matches for vague or abstract questions.
"""
import sys
from pathlib import Path
from typing import List, Dict

import ollama

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import LLM_MODEL, HYDE_CONFIDENCE_THRESHOLD


_HYDE_SYSTEM = """\
You are a technical writer creating a sample IT incident record.
Given a user question, write a SHORT (3-5 sentence) hypothetical incident
description that would be the ideal match for that question. Write ONLY the
incident description — no explanation, no preamble.
"""


def generate_hypothetical_doc(query: str) -> str:
    """Generate a hypothetical incident text for HyDE-based embedding."""
    resp = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _HYDE_SYSTEM},
            {"role": "user", "content": query},
        ],
        options={"temperature": 0.4, "num_predict": 256},
    )
    return resp["message"]["content"].strip()


def should_use_hyde(reranked: List[Dict]) -> bool:
    """
    Return True if the top candidate's rerank score is below threshold,
    indicating low retrieval confidence.
    """
    if not reranked:
        return True
    top_score = reranked[0].get("rerank_score", 1.0)
    return top_score < HYDE_CONFIDENCE_THRESHOLD
