# Product Requirements Document
## Incident RAG (Retrieval-Augmented Generation) System

| | |
|---|---|
| **Status** | Draft v1.0 |
| **Owner** | TBD |
| **Last Updated** | 2026-08-19 |

---

## 1. Overview

This system ingests a corpus of **500 historical incident records** (`incidents.json`) and builds a hybrid (dense + sparse) retrieval pipeline over them. Given a natural-language user query, the system retrieves the most relevant past incidents, re-ranks them, feeds the top results as context to an LLM, and returns a synthesized answer through a web UI. Every query and its results are logged for future reference.

## 2. Goals

- Allow a user to ask a free-text question about past incidents and get an LLM-generated answer grounded in the most relevant historical records.
- Combine semantic (dense) and lexical (sparse) retrieval so both conceptual and keyword-exact matches surface.
- Persist query history so past questions/answers can be reviewed or reused.

## 3. Scope

**In scope:** one-time embedding of 500 incidents, hybrid retrieval pipeline, re-ranking, LLM answer generation, React UI, query logging in Postgres (via Supabase).

**Out of scope (v1):** re-embedding pipeline for live/streaming incident updates, user authentication, multi-tenant access control, feedback-driven re-ranker fine-tuning. See §12.

---

## 4. System Architecture

```
 incidents.json (500 records)
          │
          ▼
 Preprocessing
 embed_text = short_description + description + keywords
          │
          ▼
 BAAI/bge-large-en-v1.5 embedding model (1024-dim)
          │
   ┌──────┴───────────────────────────┐
   ▼                                   ▼
 ChromaDB                        BM25 index (rank_bm25)
 (dense vectors + all            (tokenized corpus built
  incident attributes                 from same fields)
  as metadata)
   │                                   │
   │            User Query             │
   │                 │                 │
   ▼                 ▼                 ▼
 Dense search    ──────────────►  Sparse search
 top-15 results                   top-15 results
        │                              │
        └──────────────┬───────────────┘
                        ▼
        Reciprocal Rank Fusion (RRF)
           fused / re-ranked candidate pool
                        ▼
              Cross-encoder Re-ranker
                  → top 8 incidents
                        ▼
           LLM context assembly + generation
                        ▼
              React frontend (display)
                        ▼
        Supabase / Postgres (log query + results)
```

---

## 5. Functional Requirements

### 5.1 Data Ingestion & Preprocessing

- Source file: `incidents.json`, containing 500 incident objects.
- For each incident, construct a single **embedding source string** by concatenating:
  1. `short_description`
  2. `description`
  3. `keywords` (joined into a string, e.g. comma-separated)

  ```python
  embed_text = f"{short_description}. {description}. Keywords: {', '.join(keywords)}"
  ```
- All other fields on the incident (status, category, priority, timestamps, etc.) are **not** embedded — they are stored as metadata alongside the vector so they can be filtered on and returned to the UI/LLM.
- This is a one-time batch job (500 records); no live re-indexing is in scope for v1.

**Assumed incident schema** (confirm against the real `incidents.json`):

```json
{
  "id": "INC0010001",
  "short_description": "Login page returns 500 error",
  "description": "Users report intermittent 500 errors when submitting the login form...",
  "keywords": ["login", "500 error", "authentication"],
  "category": "Application",
  "priority": "P2",
  "status": "Resolved",
  "created_at": "2026-03-14T10:22:00Z",
  "resolution_notes": "Restarted auth service and cleared stale sessions."
}
```

### 5.2 Embedding Generation

- Model: **BAAI/bge-large-en-v1.5**, output dimension **1024**.
- Run once over all 500 incidents at ingestion time; store the resulting vectors in ChromaDB.
- Same model is used at query time to embed the incoming user query (BGE models typically expect a query instruction prefix, e.g. `"Represent this query for retrieving relevant incidents: "` — confirm against the specific BGE version used).

### 5.3 Vector Store — ChromaDB

- One persistent Chroma collection, e.g. `incidents`.
- **Document ID:** the incident's own `id` field is used as the Chroma document ID (unique per record).
- **Metadata:** every other incident attribute (`short_description`, `description`, `keywords`, `category`, `priority`, `status`, `created_at`, etc.) is stored as Chroma metadata on that document, so it can be returned directly from a query without a second lookup.
- *Note on "ID and keywords as global ID":* interpreted here as — `id` is the primary/unique key in the vector store, and `keywords` is retained as a filterable/searchable metadata field rather than concatenated into the ID string itself. Flag if a composite ID (e.g. `"{id}__{keywords}"`) was actually intended.

### 5.4 Sparse Retrieval — BM25

- Library: `rank_bm25` (`BM25Okapi`).
- Built from the **same embedding source text** (short_description + description + keywords) tokenized per incident, so dense and sparse retrieval operate over the same content.
- Index held in memory / persisted to disk (e.g. pickle) since the corpus is static at 500 documents.

### 5.5 Hybrid Retrieval — Reciprocal Rank Fusion (RRF)

For each user query:

1. Dense search → top **15** incidents from ChromaDB (by cosine/L2 similarity).
2. Sparse search → top **15** incidents from BM25.
3. Fuse both ranked lists via RRF:

   ```
   RRF(doc) = Σ 1 / (k + rank_i(doc))   for each list i the doc appears in
   ```
   - `k` = 60 (standard default; configurable).
   - A document only present in one list is scored using that list's rank only.

   ```python
   def reciprocal_rank_fusion(dense_ids, sparse_ids, k=60):
       scores = {}
       for rank, doc_id in enumerate(dense_ids, start=1):
           scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
       for rank, doc_id in enumerate(sparse_ids, start=1):
           scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
       return sorted(scores.items(), key=lambda x: x[1], reverse=True)
   ```
4. Output: the fused, RRF-sorted candidate pool (up to 30 unique incidents — fewer if the dense and sparse top-15s overlap).

### 5.6 Re-ranking

- The fused candidate pool is passed through a **cross-encoder re-ranker** that scores each (query, incident) pair directly.
- Only the **top 8** incidents after re-ranking are kept.
- Model not specified by requirements — default recommendation: `BAAI/bge-reranker-large` (same family as the embedding model) or `bge-reranker-v2-m3`. Should be swappable/configurable.

### 5.7 LLM Context Assembly & Answer Generation

- The 8 re-ranked incidents (full text + relevant metadata) are formatted into a single context block and passed to an LLM along with the original user query.
- LLM provider not specified — treat as a pluggable interface (e.g. Anthropic Claude, OpenAI GPT-4o, or a self-hosted model), configured via `.env`.
- Output: a synthesized natural-language answer, plus the 8 source incidents for citation/reference in the UI.

### 5.8 Query Persistence — Supabase / Postgres

Every query is logged, e.g. in a `query_logs` table:

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `query_text` | text | raw user query |
| `dense_top15_ids` | jsonb | for debugging/audit |
| `sparse_top15_ids` | jsonb | for debugging/audit |
| `rrf_fused_ids` | jsonb | ordered candidate pool |
| `reranked_top8_ids` | jsonb | final context used |
| `llm_response` | text | generated answer |
| `latency_ms` | int | end-to-end response time |
| `created_at` | timestamptz | default `now()` |

### 5.9 Frontend — React

- Single search interface: query input box, "Ask" button.
- Results view:
  - LLM-generated answer at the top.
  - The 8 supporting incidents below as cards (id, short description, category, priority, similarity/rerank score) — clicking a card expands full details.
- A history panel/sidebar listing past queries pulled from the `query_logs` table via Supabase client, so users can revisit earlier questions and answers.

---

## 6. Tech Stack Summary

| Layer | Choice |
|---|---|
| Embedding model | BAAI/bge-large-en-v1.5 (1024-dim) |
| Vector store | ChromaDB |
| Sparse retriever | BM25 (`rank_bm25`) |
| Fusion | Reciprocal Rank Fusion (k=60) |
| Re-ranker | Cross-encoder (default: `bge-reranker-large`), configurable |
| LLM | Pluggable (provider TBD) |
| Frontend | React |
| Backend | Node/Express (implied by "MERN") |
| Database | Supabase (managed Postgres) |
| Config/secrets | `.env` file |

> Note: "MERN" conventionally implies MongoDB, but the requirements specify Supabase/Postgres for storage. As written, this is effectively an Express + React + Node stack on top of Postgres (via Supabase) rather than Mongo — worth confirming which was intended.

---

## 7. Environment Configuration (`.env`)

Suggested variables (adjust to actual provider choices):

```
# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# LLM
LLM_PROVIDER=
LLM_API_KEY=

# Embedding / models
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-large

# Vector store
CHROMA_PERSIST_DIR=./chroma_data
CHROMA_COLLECTION_NAME=incidents

# Server
PORT=5000
NODE_ENV=development
```

`SUPABASE_SERVICE_ROLE_KEY` must stay server-side only (backend/.env), never exposed to the React client bundle.

---

## 8. Non-Functional Requirements

- **Latency:** target end-to-end query response (retrieval + re-rank + LLM) under a few seconds; log `latency_ms` per query to monitor this.
- **Reproducibility:** embedding + BM25 index build is a deterministic offline step; re-run whenever `incidents.json` changes.
- **Security:** all credentials in `.env`, excluded from version control (`.gitignore`); Supabase Row Level Security (RLS) policies should be considered before any multi-user access is added.
- **Scalability:** current design (500 docs, in-memory/local BM25 + Chroma) comfortably handles this scale; revisit if corpus grows by orders of magnitude.

---

## 9. Assumptions & Open Questions

1. Exact field names in `incidents.json` are assumed (see §5.1) — confirm against the real file.
2. Re-ranker model and LLM provider are not specified in requirements — defaults proposed above, pending confirmation.
3. "ID and keywords as global ID" interpreted as: `id` = Chroma document ID, `keywords` = metadata field (see §5.3) — confirm this matches intent.
4. Query embedding instruction-prefix conventions for BGE need confirming against the exact model checkpoint used.
5. "MERN stack" + Supabase/Postgres naming conflict (see §6) — confirm intended DB.

## 10. Out of Scope / Future Enhancements

- User authentication & multi-user history.
- Incremental re-indexing when incidents are added/updated (currently a static 500-record batch load).
- Feedback loop to fine-tune the re-ranker based on user ratings of answers.
- Analytics dashboard over query logs.

## 11. Success Metrics

- Retrieval quality: manual/labeled evaluation of whether the top-8 re-ranked incidents are relevant to test queries.
- Latency: p50/p95 end-to-end response time.
- Usage: query volume and repeat usage via the logged history.
