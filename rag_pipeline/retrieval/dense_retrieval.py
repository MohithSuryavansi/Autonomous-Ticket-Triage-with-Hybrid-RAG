"""
retrieval/dense_retrieval.py

Semantic (dense) retrieval using ChromaDB + BAAI/bge-base-en-v1.5 embeddings.
Returns the top-K most similar incident IDs and their metadata.

BGE embedding note:
  - Documents are embedded WITHOUT any prefix at ingestion time.
  - Queries are embedded WITH the BGE_QUERY_PREFIX at retrieval time.
  - This asymmetric approach is what BGE models are trained for and
    significantly improves retrieval quality.

Independently testable:
    python -m rag_pipeline.retrieval.dense_retrieval
"""
import sys
from pathlib import Path
from typing import List, Dict

import chromadb
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import (
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL,
    BGE_QUERY_PREFIX,
    DENSE_TOP_K,
)

# Shared model instance — loaded once per process
_embedding_model: SentenceTransformer = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


class DenseRetriever:
    """Wraps ChromaDB queries with BGE-base query embeddings."""

    def __init__(self) -> None:
        client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        self.collection = client.get_collection(CHROMA_COLLECTION_NAME)

    def _embed_query(self, query: str) -> List[float]:
        """Embed a query string with the BGE instruction prefix."""
        model = _get_embedding_model()
        prefixed = BGE_QUERY_PREFIX + query
        vector = model.encode(
            prefixed,
            normalize_embeddings=True,
        )
        return vector.tolist()

    def search(self, query: str, top_k: int = DENSE_TOP_K) -> List[Dict]:
        """
        Returns a list of dicts with keys: id, score, metadata, document.
        Ordered by descending cosine similarity.
        """
        vector = self._embed_query(query)
        results = self.collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            include=["distances", "metadatas", "documents"],
        )
        hits = []
        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]
        documents = results["documents"][0]

        for doc_id, dist, meta, doc in zip(ids, distances, metadatas, documents):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            hits.append({
                "id": doc_id,
                "score": 1 - dist,   # convert distance to similarity
                "metadata": meta,
                "document": doc,
            })
        return hits

    def get_ranked_ids(self, query: str, top_k: int = DENSE_TOP_K) -> List[str]:
        """Convenience method returning only ordered IDs — used by hybrid retriever."""
        return [h["id"] for h in self.search(query, top_k)]


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    query = "database connection timeout causing transaction failures"
    retriever = DenseRetriever()
    results = retriever.search(query, top_k=5)
    print(f"Dense top-5 for: '{query}'\n")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['id']}] score={r['score']:.4f} | {r['metadata'].get('short_description', '')}")
