"""
Central configuration for the Incident RAG pipeline.
All tuneable parameters live here — no magic numbers scattered across modules.
"""
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
INCIDENTS_FILE = DATA_DIR / "enhanced_incidents.json"

# Auto-resolve test dataset: prioritize 50-item dataset, fallback to qwen/other
def _resolve_test_dataset():
    for name in ["test_dataset_ragas_50.json", "test_dataset_ragas_qwen.json", "test_dataset_ragas_40.json", "test_dataset_ragas_20.json"]:
        p = DATA_DIR / name
        if p.exists():
            return p
    return DATA_DIR / "test_dataset_ragas_50.json"

TEST_DATASET_FILE = _resolve_test_dataset()

CHROMA_PERSIST_DIR = ROOT_DIR / "chroma_data"

BM25_INDEX_PATH = ROOT_DIR / "bm25_index.pkl"

# ── Ollama (LLM only) ─────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"

# Generation / chat model — served by Ollama
LLM_MODEL = "qwen3:8b"

# Title generation model — lightweight model for naming conversation sessions in sidebar
TITLE_MODEL = "llama3.2:1b"


# ── HuggingFace models (sentence-transformers, auto-downloaded on first use) ────

# Bi-encoder embedding model for dense retrieval.
# BAAI/bge-base-en-v1.5: 768-dim, strong MTEB performance, efficient on CPU.
# Downloaded from HuggingFace via sentence-transformers on first run (~430 MB).
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIM = 768

# BGE models require an instruction prefix on QUERY strings (not on documents).
# Omitting this degrades retrieval quality significantly for BGE models.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Cross-encoder reranker.
# BAAI/bge-reranker-base: ~1.1 GB, strong reranking accuracy, runs on CPU.
# Downloaded from HuggingFace via sentence-transformers on first run.
RERANKER_MODEL = "BAAI/bge-reranker-base"

# ── ChromaDB ───────────────────────────────────────────────────────────────────
CHROMA_COLLECTION_NAME = "incidents"

# ── Retrieval parameters ───────────────────────────────────────────────────────
DENSE_TOP_K = 15
SPARSE_TOP_K = 15
RRF_K = 60            # RRF constant — standard default
RERANK_TOP_N = 8      # Final incidents passed to the LLM

# ── Embed text template ────────────────────────────────────────────────────────
# Fields used to build the embedding source string (matches PRD §5.1)
EMBED_FIELDS = ["short_description", "description", "keywords"]

def build_embed_text(incident: dict) -> str:
    """Construct the embedding source string from an incident record."""
    short = incident.get("short_description", "")
    desc = incident.get("description", "")
    kws = incident.get("keywords", [])
    kw_str = ", ".join(kws) if isinstance(kws, list) else str(kws)
    return f"{short}. {desc}. Keywords: {kw_str}"

# ── LLM Generation ────────────────────────────────────────────────────────────
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 4096

# Confidence threshold below which HyDE fallback is triggered
HYDE_CONFIDENCE_THRESHOLD = 0.30

# ── Server ─────────────────────────────────────────────────────────────────────
RAG_API_HOST = "0.0.0.0"
RAG_API_PORT = 8000
