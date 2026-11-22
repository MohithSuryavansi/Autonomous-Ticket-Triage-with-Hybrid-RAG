# Incident RAG System - Project Architecture

This document defines the comprehensive project structure, module organization, responsibilities, and interactions between components for the Incident RAG (Retrieval-Augmented Generation) System.

The architecture is designed to be highly modular, scalable, and fully separated into logical components, enabling independent testing and easy swapping of retrieval strategies or underlying models.

> **Backend:** The system uses a unified **Python FastAPI** backend, which directly imports the RAG pipeline modules (no internal HTTP hop). MongoDB is accessed via the async **Motor** driver. The former Node.js/Express backend has been removed.

---

## 1. High-Level Project Structure

The repository is organized into three primary subsystems:
1. **`rag_pipeline/`**: The core AI/Python application containing all retrieval, processing, and generation logic.
2. **`backend/`**: The Node.js/Express backend that handles API requests, database interactions (MongoDB), and orchestrates communication with the RAG pipeline.
3. **`frontend/`**: The React-based web application providing the user interface.

```text
Autonomous-Ticket-Triage-and-Resolution/
├── rag_pipeline/          # Python-based RAG and AI modules
├── backend/               # Node.js/Express backend & MongoDB integration
├── frontend/              # React user interface
├── data/                  # Raw and processed datasets (e.g., enhanced_incidents.json)
├── README.md              # Project overview and setup instructions
└── project_architecture.md # This architecture document
```

---

## 2. RAG Pipeline Architecture (`rag_pipeline/`)

The RAG pipeline is built using Python. To ensure maximum modularity and independent testability, each major stage of the pipeline is isolated into its own dedicated module. The system is designed so that the retrieval mode (Dense, Sparse, or Hybrid) can be easily switched without impacting downstream processing.

### Directory Layout

```text
rag_pipeline/
├── retrieval/
│   ├── __init__.py
│   ├── dense_retrieval.py      # BAAI/bge embedding and ChromaDB interaction
│   ├── sparse_retrieval.py     # BM25 tokenization and search
│   └── hybrid_retrieval.py     # Reciprocal Rank Fusion (RRF) combining Dense and Sparse
├── processing/
│   ├── __init__.py
│   ├── query_preprocessing.py  # Query cleaning, expansion, and structuring
│   ├── cross_encoder_reranking.py # Re-ranking candidate pools (e.g., BAAI/bge-reranker)
│   └── classification.py       # Intent classification/routing based on user prompt
├── generation/
│   ├── __init__.py
│   ├── rag_generation.py       # LLM context assembly and final answer synthesis
│   └── hyde_fallback.py        # Hypothetical Document Embeddings for fallback retrieval
├── evaluation/
│   ├── __init__.py
│   └── evaluation.py           # Evaluating retrieval metrics and generation quality (RAGAS)
├── api/
│   ├── __init__.py
│   └── main.py                 # FastAPI/Flask service exposing the pipeline to the Node backend
├── tests/                      # Independent test suites for each module
│   ├── test_dense_retrieval.py
│   ├── test_sparse_retrieval.py
│   ├── test_hybrid_retrieval.py
│   └── ...
├── requirements.txt            # Python dependencies
└── config.py                   # Configuration for models, DB paths, and thresholds
```

### Module Responsibilities

#### 2.1 Retrieval Modules
- **`dense_retrieval.py`**: Responsible for semantic search. Loads `BAAI/bge-base-en-v1.5` via `sentence-transformers`, applies the BGE query instruction prefix at query time (not at index time), queries ChromaDB, and returns the top-K semantically similar incidents.
- **`sparse_retrieval.py`**: Responsible for lexical/keyword search. It loads the pre-computed `BM25Okapi` index and tokenizes the incoming query to return the top-K exact keyword matches.
- **`hybrid_retrieval.py`**: Orchestrates hybrid search. It imports both `dense_retrieval.py` and `sparse_retrieval.py`, executes them in parallel (or sequentially), and fuses their results using the **Reciprocal Rank Fusion (RRF)** algorithm to produce a single ranked list.

*Note: Because these three modules are decoupled, they can be tested independently to measure the isolated performance of BM25 vs. Dense vs. Hybrid approaches.*

#### 2.2 Processing Modules
- **`query_preprocessing.py`**: Cleans the raw user query (strips non-printable chars, collapses whitespace). Kept lightweight — the BGE query instruction prefix is applied inside `dense_retrieval.py`, not here.
- **`classification.py`**: Determines the nature of the query via regex pattern matching. Routes greetings to a fast-path bypass; all other queries go to the full RAG pipeline.
- **`cross_encoder_reranking.py`**: Takes the fused top-N candidate list from the retrieval modules and re-scores each (query, document) pair using `BAAI/bge-reranker-base` (CrossEncoder via sentence-transformers), producing the highly-accurate final top-8 incidents.

#### 2.3 Generation Modules
- **`hyde_fallback.py`**: If the top reranked candidate's score is below the confidence threshold, generates a "hypothetical ideal incident" using `qwen3:8b` via Ollama and re-queries the vector space with that document's embedding.
- **`rag_generation.py`**: Takes the final top-8 re-ranked incidents, assembles them into a structured context prompt, and calls `qwen3:8b` via Ollama to generate the synthesised response.

#### 2.4 Evaluation
- **`evaluation.py`**: Runs `test_dataset_ragas_qwen.json` through the pipeline to compute Precision@K, MRR, and RAGAS metrics. Supports `--mode dense`, `--mode sparse`, or `--mode hybrid` to evaluate each retrieval strategy independently.

---

## 2.5 Tech Stack & AI Model Inventory

| Component | Model / Tool | Source | Notes |
|---|---|---|---|
| Dense Embeddings | `BAAI/bge-base-en-v1.5` | HuggingFace (sentence-transformers) | 768-dim; query prefix applied at query time only |
| Sparse Retrieval | `BM25Okapi` | `rank-bm25` Python library | Algorithm only — no trained weights |
| Cross-Encoder Reranker | `BAAI/bge-reranker-base` | HuggingFace (sentence-transformers) | Scores (query, document) pairs; top-8 kept |
| LLM Generation | `qwen3:8b` | Ollama | Used for answer synthesis and HyDE fallback |
| NLP Preprocessing | `en_core_web_sm` | spaCy | Tokenisation only; minimal usage |
| Text Cleaning | Regex (`re`) | Python stdlib | No model; zero latency |

---

## 3. Backend Architecture (`backend/`)

The backend is a **unified Python FastAPI server** that replaces the former Node.js/Express layer entirely.
It imports the RAG pipeline modules directly (no internal HTTP hop) and accesses MongoDB asynchronously via Motor.

### Directory Layout

```text
backend/
├── main.py         # FastAPI app: all routes, startup lifespan, RAG orchestration
├── database.py     # Motor (async) MongoDB connection: connect_db / close_db / get_db
├── models.py       # Pydantic schemas: SearchRequest, SearchResponse, QueryLog shapes
├── __init__.py     # Package marker
├── .env.example    # Environment template (MONGO_URI, PORT)
└── .env            # Local environment (gitignored)
```

### Module Responsibilities

- **`main.py`**: FastAPI application entry point. Handles the startup lifespan (model checks, retriever warmup, DB connect), exposes all API routes, and orchestrates the full RAG pipeline for each search request.
- **`database.py`**: Thin async MongoDB client wrapper using Motor. Provides `connect_db()`, `close_db()`, and `get_db()` so `main.py` stays free of connection boilerplate.
- **`models.py`**: All Pydantic schemas — `SearchRequest`, `SearchResponse`, `IncidentResult`, `QueryLogCreate`, `QueryLogSummary`, `QueryLogDetail` — plus helpers that map raw MongoDB documents to response models.

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/search` | Run RAG pipeline, log to MongoDB, return answer + incidents |
| `GET` | `/api/history` | List recent query logs (summary, newest first) |
| `GET` | `/api/history/{id}` | Full query log detail by MongoDB ObjectId |

### Start command

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 5000 --reload
```

Interactive docs available at `http://localhost:5000/docs`.

---

## 4. Frontend Architecture (`frontend/`)

A React-based user interface to interact with the RAG system, display generated answers, and show historical queries.

### Directory Layout (High-Level)

```text
frontend/
├── public/
├── src/
│   ├── assets/                 # Images, icons, global styles
│   ├── components/             # Reusable UI components
│   │   ├── SearchBar.jsx       # Input field for queries
│   │   ├── IncidentCard.jsx    # Expandable card showing retrieved incident context
│   │   ├── AnswerBox.jsx       # Displays the synthesized LLM response
│   │   └── SidebarHistory.jsx  # Lists past queries fetched from MongoDB
│   ├── pages/
│   │   ├── Dashboard.jsx       # Main search and results page
│   │   └── History.jsx         # Detailed view of past queries
│   ├── services/
│   │   └── api.js              # Axios/Fetch clients connecting to the Node backend
│   ├── App.jsx                 # Main React component & Router
│   └── index.js                # React DOM entry
├── package.json
└── .env
```

---

## 5. Component Interaction Flow

1. **User Interaction**: The user submits a natural language question via the React `SearchBar` in the `frontend`.
2. **FastAPI Backend** (`POST /api/search`): The unified Python backend receives the request directly.
3. **Processing & Retrieval** (direct Python function calls — no HTTP hop):
   - `classification.py` fast-routes greetings; all other queries proceed.
   - `query_preprocessing.py` cleans the query text.
   - `hybrid_retrieval.py` triggers `dense_retrieval.py` and `sparse_retrieval.py` and fuses results via RRF.
4. **Re-ranking**: The fused list is passed to `cross_encoder_reranking.py` (`BAAI/bge-reranker-base`) to get the top-8 incidents.
5. **HyDE Fallback** *(if triggered)*: Low-confidence results cause `hyde_fallback.py` to generate a hypothetical incident via `qwen3:8b`, then re-retrieve and re-rank.
6. **Generation**: `rag_generation.py` assembles the top-8 incidents into a prompt and calls `qwen3:8b` via Ollama.
7. **MongoDB Logging**: The backend persists the full interaction (query, retrieved IDs, LLM response, latency, HyDE flag) into MongoDB via Motor.
8. **Response**: The FastAPI backend returns the structured `SearchResponse` JSON to the frontend.
9. **UI Rendering**: The React frontend updates the answer view and incident cards with the returned data.
