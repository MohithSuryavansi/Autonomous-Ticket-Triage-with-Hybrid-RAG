"""
retrieval/hybrid_retrieval.py

Hybrid retrieval: runs Dense + Sparse in parallel and fuses their ranked
lists using Reciprocal Rank Fusion (RRF).

Also fetches full incident metadata for the fused result set from ChromaDB,
so downstream modules receive complete incident dicts.

Independently testable:
    python -m rag_pipeline.retrieval.hybrid_retrieval
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Tuple

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import (
    DENSE_TOP_K,
    SPARSE_TOP_K,
    RRF_K,
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
)
from rag_pipeline.retrieval.dense_retrieval import DenseRetriever
from rag_pipeline.retrieval.sparse_retrieval import SparseRetriever


def reciprocal_rank_fusion(
    dense_ids: List[str],
    sparse_ids: List[str],
    k: int = RRF_K,
) -> List[Tuple[str, float]]:
    """
    Merge two ranked lists using RRF.

    RRF(doc) = Σ  1 / (k + rank_i(doc))

    Returns list of (doc_id, rrf_score) sorted descending.
    """
    scores: Dict[str, float] = {}
    for rank, doc_id in enumerate(dense_ids, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    for rank, doc_id in enumerate(sparse_ids, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class HybridRetriever:
    """
    Combines DenseRetriever and SparseRetriever via RRF.
    Returns a fused, ranked list of incident dicts.
    """

    def __init__(self) -> None:
        self.dense = DenseRetriever()
        self.sparse = SparseRetriever()

        # ChromaDB client for metadata lookup after fusion
        client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        self.collection = client.get_collection(CHROMA_COLLECTION_NAME)

    def _fetch_metadata(self, doc_ids: List[str]) -> Dict[str, Dict]:
        """Batch-fetch metadata from ChromaDB for a list of IDs."""
        results = self.collection.get(ids=doc_ids, include=["metadatas", "documents"])
        return {
            doc_id: {"metadata": meta, "document": doc}
            for doc_id, meta, doc in zip(
                results["ids"], results["metadatas"], results["documents"]
            )
        }

    def search(
        self,
        query: str,
        dense_top_k: int = DENSE_TOP_K,
        sparse_top_k: int = SPARSE_TOP_K,
        rrf_k: int = RRF_K,
    ) -> List[Dict]:
        """
        Execute dense and sparse retrieval in parallel, fuse with RRF.

        Returns:
            List of dicts: {id, rrf_score, metadata, document}
            Ordered by descending RRF score.
        """
        with ThreadPoolExecutor(max_workers=2) as ex:
            dense_future = ex.submit(self.dense.get_ranked_ids, query, dense_top_k)
            sparse_future = ex.submit(self.sparse.get_ranked_ids, query, sparse_top_k)
            dense_ids = dense_future.result()
            sparse_ids = sparse_future.result()

        fused = reciprocal_rank_fusion(dense_ids, sparse_ids, k=rrf_k)

        all_ids = [doc_id for doc_id, _ in fused]
        meta_map = self._fetch_metadata(all_ids)

        return [
            {
                "id": doc_id,
                "rrf_score": rrf_score,
                "metadata": meta_map.get(doc_id, {}).get("metadata", {}),
                "document": meta_map.get(doc_id, {}).get("document", ""),
            }
            for doc_id, rrf_score in fused
        ]


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    query = "database connection timeout causing transaction failures"
    retriever = HybridRetriever()
    results = retriever.search(query)
    print(f"Hybrid (RRF) top results for: '{query}'\n")
    for i, r in enumerate(results[:8], 1):
        print(
            f"  {i}. [{r['id']}] rrf={r['rrf_score']:.5f} | "
            f"{r['metadata'].get('short_description', '')}"
        )
