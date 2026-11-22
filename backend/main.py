"""
backend/main.py

Unified FastAPI server — replaces the Node.js/Express backend entirely.

This app:
  - Imports the RAG pipeline directly (no internal HTTP hop)
  - Persists every query to MongoDB (Motor async driver)
  - Exposes the same API surface as the former Express backend

Endpoints:
  GET  /health              → liveness
  POST /api/search          → run RAG pipeline, log to MongoDB, return results
  GET  /api/history         → list past queries (summary, newest first)
  GET  /api/history/{id}    → full detail of a single query log

  Interactive docs: http://localhost:5000/docs

Start:
    uvicorn backend.main:app --host 0.0.0.0 --port 5000 --reload
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ── Project root on sys.path ───────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(Path(__file__).resolve().parent / ".env")

# ── RAG pipeline imports ───────────────────────────────────────────────────────
from rag_pipeline.config import (
    EMBEDDING_MODEL, RERANKER_MODEL, LLM_MODEL, TITLE_MODEL,
    OLLAMA_BASE_URL, RERANK_TOP_N,
)
from rag_pipeline.utils.model_checker import ensure_ollama_models, ensure_hf_models
from rag_pipeline.processing.query_preprocessing import preprocess_query
from rag_pipeline.processing.classification import classify, ROUTE_GREETING
from rag_pipeline.processing.cross_encoder_reranking import rerank
from rag_pipeline.generation.rag_generation import generate_answer
from rag_pipeline.generation.hyde_fallback import generate_hypothetical_doc, should_use_hyde
from rag_pipeline.generation.title_generation import generate_title
from rag_pipeline.retrieval.hybrid_retrieval import HybridRetriever


# ── Backend imports ────────────────────────────────────────────────────────────
from backend.database import connect_db, close_db, get_db
from backend.models import (
    SearchRequest, SearchResponse, IncidentResult,
    QueryLogCreate,
    QueryLogSummary, QueryLogDetail,
    _doc_to_summary, _doc_to_detail,
)

# ── Globals (initialised at startup) ──────────────────────────────────────────
_retriever: Optional[HybridRetriever] = None


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _retriever

    # 1. Ollama LLM check — warn if not running, do NOT crash startup
    try:
        ensure_ollama_models([LLM_MODEL, TITLE_MODEL], OLLAMA_BASE_URL)
    except RuntimeError as e:
        print(f"\n[server] ⚠️  WARNING: {e}")
        print("[server]    Retrieval & history endpoints will still work.")
        print("[server]    /api/search will fail at query time until Ollama is running.\n")

    # 2. HuggingFace models (embedding + reranker) — preload from cache
    ensure_hf_models([EMBEDDING_MODEL, RERANKER_MODEL])

    # 3. Warm up retriever (ChromaDB + BM25)
    _retriever = HybridRetriever()

    # 4. Connect to MongoDB
    await connect_db()

    print("[server] All systems ready. Accepting requests.")
    yield

    await close_db()
    print("[server] Shutdown complete.")



# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Incident Intelligence API",
    description="Unified FastAPI backend for the Autonomous Incident RAG System.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to ["http://localhost:5173"] in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse, tags=["RAG"])
async def search(req: SearchRequest):
    """
    Run the full RAG pipeline for a user query.
    Logs the interaction to MongoDB and returns the answer + context incidents.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    start = time.time()
    clean_query = preprocess_query(req.query)

    # Route classification — fast-path for greetings
    if classify(clean_query) == ROUTE_GREETING:
        return SearchResponse(
            query=clean_query,
            title="Greeting",
            answer="Hello! I can help you find information about past incidents. Please ask your question.",
            incidents=[],
            dense_ids=[], sparse_ids=[], rrf_ids=[], reranked_ids=[],
            latency_ms=int((time.time() - start) * 1000),
            hyde_used=False,
        )

    # 1. Generate session title via llama3.2:1b
    title = generate_title(clean_query)

    # 2. Hybrid retrieval (Dense + Sparse + RRF)
    candidates  = _retriever.search(clean_query)
    dense_ids   = _retriever.dense.get_ranked_ids(clean_query)
    sparse_ids  = _retriever.sparse.get_ranked_ids(clean_query)
    rrf_ids     = [c["id"] for c in candidates]

    # 3. Cross-encoder rerank
    reranked = rerank(clean_query, candidates, top_n=req.top_n)

    # 4. HyDE fallback if top result confidence is low
    hyde_used = False
    if should_use_hyde(reranked):
        hyde_used = True
        hypo_doc  = generate_hypothetical_doc(clean_query)
        reranked  = rerank(clean_query, _retriever.search(hypo_doc), top_n=req.top_n)

    reranked_ids = [r["id"] for r in reranked]
    answer, structured = generate_answer(clean_query, reranked)
    latency_ms   = int((time.time() - start) * 1000)

    incidents = [
        IncidentResult(
            id=r["id"],
            rrf_score=round(r.get("rrf_score", 0.0), 6),
            rerank_score=round(r.get("rerank_score", 0.0), 4),
            short_description=r["metadata"].get("short_description", ""),
            description=r["metadata"].get("description", ""),
            resolution=r["metadata"].get("resolution", ""),
            category=r["metadata"].get("category", ""),
            urgency=r["metadata"].get("urgency", ""),
            impact=r["metadata"].get("impact", ""),
            affected_component=r["metadata"].get("affected_component", ""),
            assignment_group=r["metadata"].get("assignment_group", ""),
            keywords=r["metadata"].get("keywords", ""),
        )
        for r in reranked
    ]

    # Persist to MongoDB (non-blocking — don't fail the response if this errors)
    try:
        db = get_db()
        if db is not None:
            log = QueryLogCreate(
                query_text=clean_query,
                title=title,
                incidents=incidents,
                dense_ids=dense_ids,
                sparse_ids=sparse_ids,
                rrf_fused_ids=rrf_ids,
                reranked_ids=reranked_ids,
                llm_response=answer,
                latency_ms=latency_ms,
                hyde_used=hyde_used,
                predicted_team=structured.get("predicted_team", ""),
                predicted_priority=structured.get("predicted_priority", ""),
                routing_justification=structured.get("routing_justification", ""),
                incident_attribution=structured.get("incident_attribution", []),
            )

            await db["query_logs"].insert_one({
                **log.model_dump(),
                "created_at": datetime.now(tz=timezone.utc),
            })
        else:
            print("[warn] MongoDB unavailable — query not persisted.")
    except Exception as exc:
        print(f"[warn] MongoDB log failed: {exc}")

    return SearchResponse(
        query=clean_query,
        title=title,
        answer=answer,
        incidents=incidents,
        dense_ids=dense_ids,
        sparse_ids=sparse_ids,
        rrf_ids=rrf_ids,
        reranked_ids=reranked_ids,
        latency_ms=latency_ms,
        hyde_used=hyde_used,
        predicted_team=structured.get("predicted_team", ""),
        predicted_priority=structured.get("predicted_priority", ""),
        routing_justification=structured.get("routing_justification", ""),
        incident_attribution=structured.get("incident_attribution", []),
    )


@app.get("/api/history", response_model=List[QueryLogSummary], tags=["History"])
async def get_history(limit: int = Query(default=50, ge=1, le=100)):
    """Return the most recent `limit` query logs (summary view)."""
    db = get_db()
    if db is None:
        return []
    try:
        cursor = db["query_logs"].find(
            {},
            {"query_text": 1, "title": 1, "llm_response": 1, "latency_ms": 1, "hyde_used": 1, "created_at": 1, "predicted_team": 1, "predicted_priority": 1},
        ).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [_doc_to_summary(d) for d in docs]
    except Exception as exc:
        print(f"[warn] Failed to fetch history from MongoDB: {exc}")
        return []



@app.get("/api/history/{log_id}", response_model=QueryLogDetail, tags=["History"])
async def get_history_by_id(log_id: str):
    """Return the full query log for a single entry by MongoDB ObjectId."""
    try:
        oid = ObjectId(log_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid log ID format")

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        doc = await db["query_logs"].find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Log not found")
        return _doc_to_detail(doc)
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[warn] Failed to fetch log {log_id}: {exc}")
        raise HTTPException(status_code=503, detail="Database error occurred")


@app.delete("/api/history/{log_id}", tags=["History"])
async def delete_history_by_id(log_id: str):
    """Delete a single query log entry by its MongoDB ObjectId."""
    try:
        oid = ObjectId(log_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid log ID format")

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        result = await db["query_logs"].delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Log not found")
        return {"status": "deleted", "id": log_id}
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[warn] Failed to delete log {log_id}: {exc}")
        raise HTTPException(status_code=503, detail="Database error occurred")


