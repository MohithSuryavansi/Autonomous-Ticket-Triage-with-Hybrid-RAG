"""
processing/cross_encoder_reranking.py

Re-ranks a candidate list of incidents using a cross-encoder (bi-directional
attention over query + document) for more accurate relevance scoring.

Model: BAAI/bge-reranker-base (sentence-transformers CrossEncoder)
       Downloaded automatically from HuggingFace on first run (~1.1 GB cached).
       Runs on CPU; adequate for 30 candidate docs without noticeable latency.
"""
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import RERANKER_MODEL, RERANK_TOP_N

# Lazy-load the cross encoder — avoids the startup cost unless reranking is needed
_cross_encoder = None


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder(RERANKER_MODEL)
    return _cross_encoder


def rerank(query: str, candidates: List[Dict], top_n: int = RERANK_TOP_N) -> List[Dict]:
    """
    Re-score and reorder candidates using the cross-encoder.

    Args:
        query:      The original user query.
        candidates: List of incident dicts from hybrid retrieval.
                    Each must have keys: id, metadata, document.
        top_n:      How many top results to return.

    Returns:
        List of top_n incident dicts, each augmented with 'rerank_score'.
        Ordered by descending rerank_score.
    """
    if not candidates:
        return []

    ce = _get_cross_encoder()

    # Build (query, passage) pairs for scoring
    # Use short_description + resolution for a dense but concise passage
    pairs = []
    for c in candidates:
        meta = c.get("metadata", {})
        passage = (
            f"{meta.get('short_description', '')}. "
            f"{meta.get('description', meta.get('document', ''))}. "
            f"Resolution: {meta.get('resolution', '')}"
        )
        pairs.append((query, passage))

    scores = ce.predict(pairs)

    for cand, score in zip(candidates, scores):
        cand["rerank_score"] = float(score)

    reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    return reranked[:top_n]


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Synthetic candidates — run after ingestion in a real test
    mock_candidates = [
        {
            "id": "INC00153",
            "metadata": {
                "short_description": "Merchant data displaying incorrectly",
                "description": "API endpoint returns 500 error during data upload.",
                "resolution": "Database replication misconfiguration fixed.",
            },
            "document": "",
        },
        {
            "id": "INC00469",
            "metadata": {
                "short_description": "Access Rights Restriction",
                "description": "RBAC misconfiguration blocking e-signature.",
                "resolution": "Permission added to Sales Agent role.",
            },
            "document": "",
        },
    ]
    query = "database connection timeout"
    results = rerank(query, mock_candidates, top_n=2)
    for r in results:
        print(f"  [{r['id']}] rerank_score={r['rerank_score']:.4f} | "
              f"{r['metadata']['short_description']}")
