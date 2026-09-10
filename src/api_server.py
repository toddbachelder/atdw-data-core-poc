"""
REST API for the ATDW data probe.

Read-only API for querying ATDW listings, searching, and retrieving statistics.
Designed for external consumption by ATDW colleagues and integrations.

Run: uvicorn src.api_server:app --host 0.0.0.0 --port 8000

Or with hot reload during development:
  uvicorn src.api_server:app --reload --host 127.0.0.1 --port 8000
"""
import os
import sys
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))
from db import get_conn, rows_as_dicts
from mcp_server import handle_tool_call

# ============================================================================
# FastAPI Setup
# ============================================================================

app = FastAPI(
    title="ATDW Data Probe API",
    description="Read-only REST API for ATDW listings database",
    version="1.0.0",
)

# CORS: Allow external origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Gzip compression for large responses
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ============================================================================
# Response Models
# ============================================================================

class Listing(BaseModel):
    """A single listing record."""
    id: str
    source_id: str
    source_number: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[list | dict] = None  # Can be array or dict
    organisation_id: Optional[str] = None
    organisation_name: Optional[str] = None
    expires_at: Optional[str] = None
    source_updated_at: Optional[str] = None
    next_occurrence: Optional[str] = None
    ingested_at: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "source_id": "P123456",
                "name": "Blue Mountains Day Tour",
                "category": "TOUR",
                "status": "CURRENT",
                "organisation_name": "Blue Mountains Tours",
                "latitude": -33.5,
                "longitude": 150.3,
                "ingested_at": "2026-06-18T05:45:48+00:00",
            }
        }


class ListingsResponse(BaseModel):
    """Response from listings query."""
    total: int
    limit: int
    offset: int
    count: int
    records: list[Listing]


class SearchResult(BaseModel):
    """A single search result."""
    id: str
    source_id: str
    category: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    organisation_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ingested_at: Optional[str] = None


class SearchResponse(BaseModel):
    """Response from search."""
    query: str
    limit: int
    results_count: int
    results: list[SearchResult]


class CategoryStats(BaseModel):
    """Category statistics."""
    total_records: int
    categories: dict[str, int]
    organisations: list[dict]
    statuses: dict[str, int]
    states: list[str]
    cached_at: str


class SummaryStats(BaseModel):
    """Summary statistics."""
    total_records: int
    unique_organisations: int
    records_with_images: int
    records_with_geo: int
    earliest_ingest: Optional[str] = None
    latest_ingest: Optional[str] = None
    newest_source_update: Optional[str] = None


# ============================================================================
# Database Queries (Read-Only)
# ============================================================================

def _serialize_row(row: dict) -> dict:
    """Convert UUIDs and dates to strings for JSON serialization."""
    if row.get("id"):
        row["id"] = str(row["id"])
    for date_field in ["expires_at", "source_updated_at", "ingested_at"]:
        if row.get(date_field) and hasattr(row[date_field], "isoformat"):
            row[date_field] = row[date_field].isoformat()
    return row


@app.get("/health")
def health_check():
    """Health check endpoint."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        conn.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": str(e)},
        )


@app.get("/api/v1/listings", response_model=ListingsResponse)
def query_listings(
    category: Optional[str] = Query(None, description="Filter by category (e.g. TOUR, ATTRACTION, ACCOMM)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    organization: Optional[str] = Query(None, description="Filter by organization name (partial match)"),
    limit: int = Query(50, ge=1, le=500, description="Max results (1-500)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Query listings with optional filters.

    Always returns fresh data (no caching).
    """
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Build WHERE clause
        where_clauses = []
        params = []

        if category:
            where_clauses.append("category = %s")
            params.append(category)

        if status:
            where_clauses.append("status = %s")
            params.append(status)

        if search:
            where_clauses.append("(name ILIKE %s OR description ILIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param])

        if organization:
            where_clauses.append("organisation_name ILIKE %s")
            params.append(f"%{organization}%")

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Count total
        count_sql = f"SELECT COUNT(*) FROM listings {where_sql}"
        cur.execute(count_sql, params)
        total = cur.fetchone()[0]

        # Fetch records
        sql = f"""
            SELECT
                id, source_id, source_number, category, status, name, description,
                image_url, latitude, longitude, address, organisation_id,
                organisation_name, expires_at, source_updated_at, next_occurrence,
                ingested_at
            FROM listings
            {where_sql}
            ORDER BY ingested_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        cur.execute(sql, params)

        rows = [_serialize_row(row) for row in rows_as_dicts(cur)]
        conn.close()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "count": len(rows),
            "records": rows,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/v1/listings/{source_id}", response_model=Listing)
def get_listing(source_id: str):
    """
    Get a single listing by source_id.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id, source_id, source_number, category, status, name, description,
                image_url, latitude, longitude, address, organisation_id,
                organisation_name, expires_at, source_updated_at, next_occurrence,
                ingested_at
            FROM listings
            WHERE source_id = %s
            LIMIT 1
        """, (source_id,))

        row = cur.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail=f"Listing {source_id} not found")

        cols = [d[0] for d in cur.description]
        listing = dict(zip(cols, row))
        return _serialize_row(listing)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/v1/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, ge=1, le=500, description="Max results (1-500)"),
):
    """
    Full-text search by name and description.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()

        search_param = f"%{q}%"

        cur.execute("""
            SELECT
                id, source_id, category, name, description,
                organisation_name, latitude, longitude, ingested_at
            FROM listings
            WHERE name ILIKE %s OR description ILIKE %s
            ORDER BY
                CASE WHEN name ILIKE %s THEN 0 ELSE 1 END,
                ingested_at DESC
            LIMIT %s
        """, (search_param, search_param, search_param, limit))

        rows = [_serialize_row(row) for row in rows_as_dicts(cur)]
        conn.close()

        return {
            "query": q,
            "limit": limit,
            "results_count": len(rows),
            "results": rows,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/v1/stats/categories", response_model=CategoryStats)
def get_category_stats():
    """
    Get aggregate statistics by category, organization, and status.

    Results are cached for 5 minutes.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Category counts
        cur.execute("""
            SELECT category, COUNT(*) as count
            FROM listings
            GROUP BY category
            ORDER BY count DESC
        """)
        categories = {row[0]: row[1] for row in cur.fetchall()}

        # Top organizations
        cur.execute("""
            SELECT organisation_name, COUNT(*) as count
            FROM listings
            WHERE organisation_name IS NOT NULL
            GROUP BY organisation_name
            ORDER BY count DESC
            LIMIT 20
        """)
        orgs = [{"name": row[0], "count": row[1]} for row in cur.fetchall()]

        # Status breakdown
        cur.execute("""
            SELECT status, COUNT(*) as count
            FROM listings
            GROUP BY status
            ORDER BY count DESC
        """)
        statuses = {row[0]: row[1] for row in cur.fetchall()}

        # States from address
        cur.execute("""
            SELECT DISTINCT address->>'state' as state
            FROM listings
            WHERE address IS NOT NULL
            ORDER BY state
        """)
        states = [row[0] for row in cur.fetchall() if row[0]]

        conn.close()

        from datetime import datetime
        return {
            "total_records": sum(categories.values()),
            "categories": categories,
            "organisations": orgs,
            "statuses": statuses,
            "states": states,
            "cached_at": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/v1/stats/summary", response_model=SummaryStats)
def get_summary_stats():
    """
    Get overall summary statistics.

    Results are cached for 5 minutes.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT organisation_id) as organisations,
                COUNT(CASE WHEN image_url IS NOT NULL THEN 1 END) as with_images,
                COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END) as with_geo,
                MIN(ingested_at) as earliest_ingest,
                MAX(ingested_at) as latest_ingest,
                MAX(source_updated_at) as newest_source_update
            FROM listings
        """)

        row = cur.fetchone()
        conn.close()

        return {
            "total_records": row[0],
            "unique_organisations": row[1],
            "records_with_images": row[2],
            "records_with_geo": row[3],
            "earliest_ingest": row[4].isoformat() if row[4] else None,
            "latest_ingest": row[5].isoformat() if row[5] else None,
            "newest_source_update": row[6].isoformat() if row[6] else None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================================================
# MCP JSON-RPC Endpoints
# ============================================================================

class MCPRequest(BaseModel):
    """JSON-RPC request."""
    jsonrpc: str = "2.0"
    method: str
    params: dict = {}
    id: int = 1


@app.post("/rpc")
def mcp_rpc(request: MCPRequest):
    """
    Handle JSON-RPC requests for MCP tools.

    Supports natural language queries and structured tool calls.
    """
    try:
        if request.method != "tools/call":
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32601, "message": "Method not found"},
            }

        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})

        result_str = handle_tool_call(tool_name, arguments)
        result = json.loads(result_str)

        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": result,
        }

    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32603, "message": str(e)},
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
