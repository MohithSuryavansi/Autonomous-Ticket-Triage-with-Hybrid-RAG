"""
ingestion/ingest.py

One-time ingestion script:
  1. Loads and preprocesses incidents.
  2. Embeds each incident's embed_text via BAAI/bge-base-en-v1.5 (HuggingFace).
  3. Stores vectors + metadata in ChromaDB.
  4. Builds a BM25Okapi index and pickles it to disk.

Run once before starting the API:
    python -m rag_pipeline.ingestion.ingest

Re-run whenever data/enhanced_incidents.json changes.
"""
import sys
import pickle
from pathlib import Path
from typing import List, Dict

from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import chromadb
from rank_bm25 import BM25Okapi

# Resolve project root so this works both as a module and standalone script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import (
    INCIDENTS_FILE,
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
    BM25_INDEX_PATH,
    EMBEDDING_MODEL,
)
from rag_pipeline.ingestion.preprocess import preprocess


# ── Helpers ────────────────────────────────────────────────────────────────────

def _embed(texts: List[str], model_name: str = EMBEDDING_MODEL) -> List[List[float]]:
    """
    Batch-embed texts using BAAI/bge-base-en-v1.5 via sentence-transformers.
    Documents are embedded WITHOUT the query instruction prefix — BGE only
    applies the prefix at query time to improve retrieval alignment.
    """
    print(f"[ingest] Loading embedding model '{model_name}' from HuggingFace...")
    model = SentenceTransformer(model_name)
    print(f"[ingest] Embedding {len(texts)} documents (batch mode)...")
    # encode() handles batching internally; show_progress_bar gives tqdm output
    vectors = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,   # cosine similarity works best with L2-normalised vectors
    )
    return [v.tolist() for v in vectors]


def _build_metadata(incident: Dict) -> Dict:
    """Extract metadata fields stored alongside each ChromaDB document."""
    return {
        "number": incident.get("number", ""),
        "short_description": incident.get("short_description", ""),
        "description": incident.get("description", ""),
        "resolution": incident.get("resolution", ""),
        "category": incident.get("category", ""),
        "assignment_group": incident.get("assignment_group", ""),
        "affected_component": incident.get("affected_component", ""),
        "urgency": str(incident.get("urgency", "")),
        "impact": str(incident.get("impact", "")),
        "start_date": incident.get("start_date", ""),
        "end_date": incident.get("end_date", ""),
        "keywords": ", ".join(incident.get("keywords", [])),
    }


# ── Main ingestion pipeline ────────────────────────────────────────────────────

def run_ingestion() -> None:
    print("[ingest] Loading and preprocessing incidents...")
    incidents = preprocess(INCIDENTS_FILE)
    print(f"[ingest] {len(incidents)} incidents loaded.")

    embed_texts = [inc["embed_text"] for inc in incidents]
    doc_ids = [inc["id"] for inc in incidents]

    # ── ChromaDB ───────────────────────────────────────────────────────────────
    print("[ingest] Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))

    # Delete existing collection so we get a clean re-index
    try:
        client.delete_collection(CHROMA_COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print("[ingest] Generating embeddings via BAAI/bge-base-en-v1.5...")
    vectors = _embed(embed_texts)

    print("[ingest] Upserting into ChromaDB...")
    metadatas = [_build_metadata(inc) for inc in incidents]
    # ChromaDB add() in batches of 100 to avoid memory spikes
    BATCH = 100
    for i in range(0, len(doc_ids), BATCH):
        collection.add(
            ids=doc_ids[i : i + BATCH],
            embeddings=vectors[i : i + BATCH],
            documents=embed_texts[i : i + BATCH],
            metadatas=metadatas[i : i + BATCH],
        )
    print(f"[ingest] ChromaDB collection '{CHROMA_COLLECTION_NAME}' has {collection.count()} docs.")

    # ── BM25 index ─────────────────────────────────────────────────────────────
    print("[ingest] Building BM25 index...")
    tokenised = [text.lower().split() for text in embed_texts]
    bm25 = BM25Okapi(tokenised)

    index_payload = {
        "bm25": bm25,
        "doc_ids": doc_ids,
        "tokenised_corpus": tokenised,
    }
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(index_payload, f)
    print(f"[ingest] BM25 index saved to {BM25_INDEX_PATH}.")

    print("[ingest] Ingestion complete.")


if __name__ == "__main__":
    run_ingestion()
