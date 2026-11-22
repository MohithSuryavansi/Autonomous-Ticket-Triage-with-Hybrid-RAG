"""
backend/database.py

Async Motor (MongoDB) client.
Connection is opened at startup and closed at shutdown via the FastAPI lifespan.

Collection: query_logs
  Fields:
    query_text    : str
    dense_ids     : list[str]
    sparse_ids    : list[str]
    rrf_fused_ids : list[str]
    reranked_ids  : list[str]
    llm_response  : str
    latency_ms    : int
    hyde_used     : bool
    created_at    : datetime  (set on insert)
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_mongo_uri() -> str:
    return os.getenv("MONGO_URI", "mongodb://localhost:27017/incident_rag")


def _parse_db_name(uri: str) -> str:
    """
    Extract the database name from a MongoDB URI path segment.
    e.g. 'mongodb://host/mydb'  → 'mydb'
    Atlas URIs like '...mongodb.net/?appName=...' have no path DB — fall back to DB_NAME env.
    """
    from urllib.parse import urlparse
    path = urlparse(uri).path.lstrip("/").split("?")[0].split("/")[0]
    if path:
        return path
    return os.getenv("DB_NAME", "incident_rag")


async def connect_db() -> None:
    global _client, _db
    uri = get_mongo_uri()
    db_name = _parse_db_name(uri)
    try:
        _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        _db = _client[db_name]
        # Test connection with a quick ping
        await _client.admin.command("ping")
        print(f"[db] Successfully connected to MongoDB — database: '{db_name}'")
    except Exception as exc:
        print(f"\n[db] ⚠️  MongoDB connection warning: {exc}")
        print("[db]    Tip: If using MongoDB Atlas, make sure your IP is whitelisted in Atlas Network Access (0.0.0.0/0).")
        print("[db]    The app will continue running; queries will work without logging history until resolved.\n")


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        print("[db] MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase | None:
    return _db

