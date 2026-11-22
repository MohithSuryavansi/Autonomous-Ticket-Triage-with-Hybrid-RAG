"""
retrieval/sparse_retrieval.py

Lexical (sparse) retrieval using a pre-built BM25Okapi index.
The index must be created first by running ingestion/ingest.py.

Independently testable:
    python -m rag_pipeline.retrieval.sparse_retrieval
"""
import sys
import pickle
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import BM25_INDEX_PATH, SPARSE_TOP_K


class SparseRetriever:
    """BM25-based lexical retriever loaded from a pickled index on disk."""

    def __init__(self) -> None:
        if not BM25_INDEX_PATH.exists():
            raise FileNotFoundError(
                f"BM25 index not found at {BM25_INDEX_PATH}. "
                "Run `python -m rag_pipeline.ingestion.ingest` first."
            )
        with open(BM25_INDEX_PATH, "rb") as f:
            payload = pickle.load(f)

        self.bm25 = payload["bm25"]
        self.doc_ids: List[str] = payload["doc_ids"]

    def search(self, query: str, top_k: int = SPARSE_TOP_K) -> List[Dict]:
        """
        Returns a list of dicts with keys: id, score.
        Ordered by descending BM25 score.
        """
        tokens = query.lower().split()
        scores = self.bm25.get_scores(tokens)

        # Pair each doc_id with its BM25 score, sort descending
        ranked = sorted(
            zip(self.doc_ids, scores), key=lambda x: x[1], reverse=True
        )
        return [{"id": doc_id, "score": float(score)} for doc_id, score in ranked[:top_k]]

    def get_ranked_ids(self, query: str, top_k: int = SPARSE_TOP_K) -> List[str]:
        """Convenience method returning only ordered IDs — used by hybrid retriever."""
        return [h["id"] for h in self.search(query, top_k)]


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    query = "database connection timeout causing transaction failures"
    retriever = SparseRetriever()
    results = retriever.search(query, top_k=5)
    print(f"Sparse (BM25) top-5 for: '{query}'\n")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['id']}] score={r['score']:.4f}")
