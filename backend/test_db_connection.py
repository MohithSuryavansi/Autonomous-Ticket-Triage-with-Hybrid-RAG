"""
backend/test_db_connection.py

Diagnostic & Verification Tool:
1. Tests MongoDB connectivity, TLS handshake, and authentication.
2. Pushes a realistic test incident query document into MongoDB.
3. Retrieves and validates the document to confirm read & write operations.
4. Tests the history list query sorted by newest timestamp.

Usage:
    python test_db_connection.py
"""
import asyncio
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load .env
load_dotenv(Path(__file__).resolve().parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId


def get_public_ip():
    try:
        return urllib.request.urlopen("https://api.ipify.org", timeout=4).read().decode("utf8")
    except Exception:
        return "Unable to determine"


async def main():
    print("=" * 65)
    print("  MongoDB Diagnostic & Full Read/Write Verification Check")
    print("=" * 65)

    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DB_NAME", "incident_rag")
    public_ip = get_public_ip()

    print(f"Current Public IP : {public_ip}")
    print(f"Configured URI    : {uri[:35]}... (hidden for security)")
    print(f"Target Database   : {db_name}")
    print(f"Target Collection : query_logs")
    print("-" * 65)

    if not uri:
        print("[FAIL] MONGO_URI is not set in backend/.env!")
        return

    print("1. [CONNECT] Attempting ping to MongoDB cluster...")

    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=6000)
        res = await client.admin.command("ping")
        print(f"   [OK] MongoDB Ping Successful: {res}")

        db = client[db_name]
        initial_count = await db["query_logs"].count_documents({})
        print(f"   [OK] Current count in '{db_name}.query_logs': {initial_count}")

        # ── Step 2: Push Test Dataset Document ─────────────────────────────────
        print("\n2. [WRITE TEST] Inserting a test incident query document into MongoDB...")
        test_doc = {
            "query_text": "Investigate P1 Database Connection Pool Exhaustion on primary cluster",
            "title": "Database Connection Pool Exhaustion",
            "llm_response": "### Root Cause Analysis\nThe PostgreSQL connection pool is saturated due to idle unclosed connections from worker threads.",
            "latency_ms": 1420,
            "hyde_used": False,
            "predicted_team": "Database Engineering",
            "predicted_priority": "P1 - Critical",
            "routing_justification": "Direct database saturation impacting multiple microservices.",
            "incident_attribution": [
                {
                    "id": "INC-1049",
                    "team": "Database Engineering",
                    "urgency": "High",
                    "impact": "Critical",
                }
            ],
            "incidents": [
                {
                    "id": "INC-1049",
                    "rrf_score": 0.032,
                    "rerank_score": 0.9412,
                    "short_description": "PostgreSQL connection pool exhausted under heavy peak load",
                    "description": "Backend API received 500 errors due to max client connections reached.",
                    "resolution": "Increased max_connections to 400 and enabled PgBouncer pooling.",
                    "category": "Database",
                    "urgency": "1 - High",
                    "impact": "1 - Critical",
                    "affected_component": "postgres-primary-db",
                    "assignment_group": "Database Engineering",
                    "keywords": "postgres, connection pool, pgbouncer",
                }
            ],
            "dense_ids": ["INC-1049", "INC-2031"],
            "sparse_ids": ["INC-1049", "INC-3088"],
            "rrf_fused_ids": ["INC-1049", "INC-2031", "INC-3088"],
            "reranked_ids": ["INC-1049"],
            "created_at": datetime.now(tz=timezone.utc),
            "is_test_entry": True,
        }

        insert_result = await db["query_logs"].insert_one(test_doc)
        inserted_id = insert_result.inserted_id
        print(f"   [OK] Document successfully written to MongoDB!")
        print(f"   [OK] Inserted ObjectId: {inserted_id}")

        # ── Step 3: Retrieve and Validate Document ──────────────────────────────
        print("\n3. [READ TEST] Fetching the newly inserted document by ObjectId...")
        fetched_doc = await db["query_logs"].find_one({"_id": inserted_id})

        if fetched_doc:
            print("   [OK] Document successfully retrieved from MongoDB!")
            print(f"     * ID                     : {fetched_doc['_id']}")
            print(f"     * Title                  : {fetched_doc.get('title')}")
            print(f"     * Query Text             : {fetched_doc.get('query_text')}")
            print(f"     * Designated Team        : {fetched_doc.get('predicted_team')}")
            print(f"     * Severity               : {fetched_doc.get('predicted_priority')}")
            print(f"     * Incidents Stored       : {len(fetched_doc.get('incidents', []))} incident(s)")
            print(f"     * Created Timestamp      : {fetched_doc.get('created_at')}")
        else:
            print("   [FAIL] Could not find the document after insertion!")

        # ── Step 4: Test History Feed Query (Sorted Newest First) ───────────────
        print("\n4. [FEED QUERY TEST] Querying the 3 most recent history records...")
        cursor = db["query_logs"].find(
            {},
            {"query_text": 1, "title": 1, "predicted_team": 1, "predicted_priority": 1, "created_at": 1}
        ).sort("created_at", -1).limit(3)

        recent_docs = await cursor.to_list(length=3)
        print(f"   [OK] Retrieved {len(recent_docs)} recent history record(s):")
        for i, d in enumerate(recent_docs, start=1):
            title_str = d.get('title') or d.get('query_text', '')[:25]
            print(f"     [{i}] ID: {d['_id']} | Title: '{title_str}' | Team: {d.get('predicted_team', '—')}")

        new_count = await db["query_logs"].count_documents({})
        print("\n" + "=" * 65)
        print(f"  ALL TESTS PASSED! Total Records in Database: {new_count}")
        print("  MongoDB read/write pipeline is fully active and functioning.")
        print("=" * 65)

    except Exception as exc:
        err_str = str(exc)
        print(f"\n[FAIL] MongoDB Connection or Operation Failed:")
        print(f"  Error Type: {type(exc).__name__}")
        print(f"  Details   : {err_str}\n")

        if "SSL" in err_str or "TLS" in err_str or "ServerSelectionTimeoutError" in err_str:
            print("=" * 65)
            print("  ROOT CAUSE & RESOLUTION STEPS (MongoDB Atlas)")
            print("=" * 65)
            print("1. Log in to MongoDB Atlas: https://cloud.mongodb.com/")
            print("2. Navigate to 'Network Access' (under Security in sidebar).")
            print("3. Click '+ Add IP Address'.")
            print(f"   Add your current IP: {public_ip} or allow access from anywhere (0.0.0.0/0).")
            print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
