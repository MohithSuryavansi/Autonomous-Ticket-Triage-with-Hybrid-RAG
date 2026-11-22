"""
rag_pipeline/api/main.py  — RETIRED

The standalone RAG-only FastAPI service has been merged into backend/main.py,
which is now the single unified server handling both RAG queries and MongoDB
history persistence.

Start the unified backend instead:
    uvicorn backend.main:app --host 0.0.0.0 --port 5000 --reload

This file is kept only as a reference stub. Do not import it.
"""
raise ImportError(
    "rag_pipeline.api.main is retired. Use 'backend.main' instead.\n"
    "Run: uvicorn backend.main:app --host 0.0.0.0 --port 5000 --reload"
)
