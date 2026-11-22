"""
backend/models.py

Pydantic schemas for the FastAPI backend.
Covers: search request/response, query log persistence, history list/detail.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel, Field


# ── Search ─────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_n: int = 8


class IncidentResult(BaseModel):
    id: str
    rrf_score: float
    rerank_score: float
    short_description: str
    description: str
    resolution: str
    category: str
    urgency: str
    impact: str
    affected_component: str
    assignment_group: str
    keywords: str


class SearchResponse(BaseModel):
    query: str
    title: str = ""
    answer: str
    incidents: List[IncidentResult]
    dense_ids: List[str]
    sparse_ids: List[str]
    rrf_ids: List[str]
    reranked_ids: List[str]
    latency_ms: int
    hyde_used: bool
    # ── Structured LLM routing output ──────────────────────────────────────
    predicted_team: str = ""
    predicted_priority: str = ""
    routing_justification: str = ""
    incident_attribution: List[Dict[str, Any]] = []


# ── Query Log (MongoDB) ────────────────────────────────────────────────────────

class QueryLogCreate(BaseModel):
    """Fields written to MongoDB on each search."""
    query_text: str
    title: str = ""
    incidents: List[IncidentResult] = []
    dense_ids: List[str] = []
    sparse_ids: List[str] = []
    rrf_fused_ids: List[str] = []
    reranked_ids: List[str] = []
    llm_response: str = ""
    latency_ms: int = 0
    hyde_used: bool = False
    predicted_team: str = ""
    predicted_priority: str = ""
    routing_justification: str = ""
    incident_attribution: List[Dict[str, Any]] = []


# ── History ────────────────────────────────────────────────────────────────────

class QueryLogSummary(BaseModel):
    """Lightweight shape returned by GET /api/history (list view)."""
    id: str
    query_text: str
    title: str = ""
    llm_response: str
    latency_ms: int
    hyde_used: bool
    created_at: datetime
    predicted_team: str = ""
    predicted_priority: str = ""


class QueryLogDetail(QueryLogSummary):
    """Full shape returned by GET /api/history/{id}."""
    incidents: List[IncidentResult] = []
    dense_ids: List[str] = []
    sparse_ids: List[str] = []
    rrf_fused_ids: List[str] = []
    reranked_ids: List[str] = []
    routing_justification: str = ""
    incident_attribution: List[Dict[str, Any]] = []


# ── Helpers ────────────────────────────────────────────────────────────────────

def _doc_to_summary(doc: dict) -> QueryLogSummary:
    return QueryLogSummary(
        id=str(doc["_id"]),
        query_text=doc.get("query_text", ""),
        title=doc.get("title") or doc.get("query_text", ""),
        llm_response=doc.get("llm_response", ""),
        latency_ms=doc.get("latency_ms", 0),
        hyde_used=doc.get("hyde_used", False),
        created_at=doc.get("created_at", datetime.utcnow()),
        predicted_team=doc.get("predicted_team", ""),
        predicted_priority=doc.get("predicted_priority", ""),
    )


def _doc_to_detail(doc: dict) -> QueryLogDetail:
    raw_incidents = doc.get("incidents", [])
    incidents = []
    for inc in raw_incidents:
        if isinstance(inc, dict):
            try:
                incidents.append(IncidentResult(**inc))
            except Exception:
                pass
        elif isinstance(inc, IncidentResult):
            incidents.append(inc)

    return QueryLogDetail(
        id=str(doc["_id"]),
        query_text=doc.get("query_text", ""),
        title=doc.get("title") or doc.get("query_text", ""),
        llm_response=doc.get("llm_response", ""),
        latency_ms=doc.get("latency_ms", 0),
        hyde_used=doc.get("hyde_used", False),
        created_at=doc.get("created_at", datetime.utcnow()),
        predicted_team=doc.get("predicted_team", ""),
        predicted_priority=doc.get("predicted_priority", ""),
        incidents=incidents,
        dense_ids=doc.get("dense_ids", []),
        sparse_ids=doc.get("sparse_ids", []),
        rrf_fused_ids=doc.get("rrf_fused_ids", []),
        reranked_ids=doc.get("reranked_ids", []),
        routing_justification=doc.get("routing_justification", ""),
        incident_attribution=doc.get("incident_attribution", []),
    )


