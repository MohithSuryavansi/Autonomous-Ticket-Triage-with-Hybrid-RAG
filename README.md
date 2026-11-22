# Incident RAG System

A hybrid (dense + sparse) Retrieval-Augmented Generation system for querying 500 historical IT incident records using natural language. Powered by **BAAI/bge-base-en-v1.5** (dense embeddings), **BM25** (sparse retrieval), **BAAI/bge-reranker-base** (cross-encoder reranking), and **Qwen3:8b via Ollama** (LLM generation).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Dense Embeddings | `BAAI/bge-base-en-v1.5` (HuggingFace, auto-downloaded) |
| Sparse Retrieval | `BM25Okapi` via `rank-bm25` |
| Cross-Encoder Reranker | `BAAI/bge-reranker-base` (HuggingFace, auto-downloaded) |
| LLM Generation | `qwen3:8b` via Ollama |
| Vector Store | ChromaDB (persistent) |
| Backend | **FastAPI** (Python, unified) |
| Database | MongoDB (Motor async driver) |
| Frontend | React + Vite |

---

## Prerequisites

| Tool | Required | Notes |
|---|---|---|
| Python | 3.10+ | Runs the RAG pipeline + backend |
| Ollama | Latest | Must be running (`ollama serve`) |
| MongoDB | 7.x / Atlas | Local or remote |
| Node.js | 18+ | Frontend only |

Start Ollama before any other step:

```bash
ollama serve
```

---

## Project Structure

```
Autonomous-Ticket-Triage-and-Resolution/
├── docs/                    # Architecture, PRD, and RAGAS Evaluation documentation
├── data/                    # Dataset files
├── rag_pipeline/            # Python RAG modules
│   ├── ingestion/           # Preprocessing + ChromaDB/BM25 ingestion
│   ├── retrieval/           # Dense, Sparse, Hybrid retrievers
│   ├── processing/          # Query preprocessing, classification, reranking
│   ├── generation/          # LLM generation + HyDE fallback
│   ├── evaluation/          # Retrieval + RAGAS multi-pipeline evaluation
│   └── utils/               # Model checker (Ollama + HuggingFace)
├── backend/                 # Unified FastAPI backend (Python)
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # Motor MongoDB connection
│   └── models.py            # Pydantic schemas
├── frontend/                # React frontend
└── venv/                    # Python virtual environment
```


---

## Step-by-Step Setup

### 1 — Python Environment

```bash
# From project root
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.\venv\Scripts\activate.bat

# Install all dependencies
pip install -r rag_pipeline/requirements.txt

# Download the spaCy model (used for preprocessing)
python -m spacy download en_core_web_sm
```

---

### 2 — Verify & Preload Models

Checks Ollama for `qwen3:8b` and preloads the HuggingFace models.
Any missing model is downloaded automatically.

```bash
# Ollama must be running first
python -m rag_pipeline.utils.model_checker
```

Only the LLM needs a manual Ollama pull if missing:

```bash
ollama pull qwen3:8b

# HuggingFace models auto-download via sentence-transformers.
# Cached at: ~/.cache/huggingface/hub/
```

---

### 3 — Preprocess & Index Incidents (Run Once)

Embeds all 500 incidents via `BAAI/bge-base-en-v1.5`, stores vectors in
ChromaDB, and saves the BM25 index to disk.

```bash
python -m rag_pipeline.ingestion.ingest
```

> ⚠️ First run downloads ~430 MB for the BGE embedding model and encodes all incidents.
> Re-run only when the dataset changes.

---

### 4 — Configure the Backend

```bash
cd backend
copy .env.example .env
# Edit .env and set MONGO_URI to your MongoDB connection string
```

---

### 5 — Start the Unified FastAPI Backend

```bash
# From project root (venv active)
uvicorn backend.main:app --host 0.0.0.0 --port 5000 --reload
```

| URL | Description |
|---|---|
| `http://localhost:5000` | API root |
| `http://localhost:5000/docs` | Swagger interactive docs |
| `http://localhost:5000/health` | Health check |
| `http://localhost:5000/api/search` | RAG search (POST) |
| `http://localhost:5000/api/history` | Query history (GET) |

---

### 6 — Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## API Reference

### `POST /api/search`

```json
{
  "query": "database connection timeout causing transaction failures",
  "top_n": 8
}
```

### `GET /api/history?limit=20`

Returns the most recent query logs (summary view).

### `GET /api/history/{id}`

Returns full detail for a single query log by MongoDB ObjectId.

---

## Running Evaluations

For comprehensive architecture details, metric definitions, and sequential VRAM management, see [docs/RAGAS_Evaluation_Framework.md](file:///e:/College_Documents/GITHUB/Autonomous-Ticket-Triage-and-Resolution/docs/RAGAS_Evaluation_Framework.md).

```bash
# ── Modular RAGAS Benchmarks (DeepSeek-R1 + Qwen3:8b) ─────────────
# Run Hybrid evaluation (Dense + Sparse + RRF + Cross-Encoder)
python -m rag_pipeline.evaluation.run_hybrid

# Run Dense-Only evaluation
python -m rag_pipeline.evaluation.run_dense

# Run Sparse-Only (BM25) evaluation
python -m rag_pipeline.evaluation.run_sparse

# Smoke test on 3 samples
python -m rag_pipeline.evaluation.run_hybrid --max-samples 3
```

Results are saved to `rag_pipeline/evaluation/results/{mode}_results.json` and aggregate metrics to `rag_pipeline/evaluation/results/{mode}_summary.json`.

---

## Documentation

Full project documentation is available in the [`docs/`](file:///e:/College_Documents/GITHUB/Autonomous-Ticket-Triage-and-Resolution/docs) directory:
- [RAGAS Evaluation Framework](file:///e:/College_Documents/GITHUB/Autonomous-Ticket-Triage-and-Resolution/docs/RAGAS_Evaluation_Framework.md)
- [Project Architecture](file:///e:/College_Documents/GITHUB/Autonomous-Ticket-Triage-and-Resolution/docs/project_architecture.md)
- [Incident RAG System PRD](file:///e:/College_Documents/GITHUB/Autonomous-Ticket-Triage-and-Resolution/docs/Incident_RAG_System_PRD.md)


---

## Test Individual Retrieval Modules

```bash
python -m rag_pipeline.retrieval.dense_retrieval
python -m rag_pipeline.retrieval.sparse_retrieval
python -m rag_pipeline.retrieval.hybrid_retrieval
```

---

## Quick API Test

```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"database connection timeout causing transaction failures\"}"
```

---

## AI Model Inventory

| Model | Task | Source | Size |
|---|---|---|---|
| `BAAI/bge-base-en-v1.5` | Dense embeddings (bi-encoder) | HuggingFace (auto-download) | ~430 MB |
| `BAAI/bge-reranker-base` | Cross-encoder reranking | HuggingFace (auto-download) | ~1.1 GB |
| `qwen3:8b` | LLM generation + HyDE | Ollama (`ollama pull qwen3:8b`) | ~5.2 GB |
| `en_core_web_sm` | spaCy NLP (preprocessing) | spaCy (`python -m spacy download en_core_web_sm`) | ~12 MB |
| `BM25Okapi` | Sparse retrieval (algorithm) | `rank-bm25` library | — |

---

## Common Issues

| Issue | Fix |
|---|---|
| `Ollama is not running` | Run `ollama serve` in a separate terminal |
| `BM25 index not found` | Run `python -m rag_pipeline.ingestion.ingest` |
| `Collection not found` | Run `python -m rag_pipeline.ingestion.ingest` |
| `qwen3:8b not found in Ollama` | Run `ollama pull qwen3:8b` |
| HuggingFace download fails | Check internet; models cache at `~/.cache/huggingface/hub/` |
| MongoDB connection refused | Start MongoDB or set `MONGO_URI` to Atlas URL in `backend/.env` |
| spaCy model missing | Run `python -m spacy download en_core_web_sm` |
