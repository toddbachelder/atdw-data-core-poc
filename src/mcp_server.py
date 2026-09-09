"""
MCP server for the ATDW data probe.

Connects to the Supabase listings database and exposes listings, categories,
and statistics through MCP resources and tools.

Run: python src/mcp_server.py
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from db import get_conn, rows_as_dicts

load_dotenv()


# ============================================================================
# Cache Management
# ============================================================================

class TTLCache:
    """Simple in-memory cache with TTL (time-to-live)."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None
        return value

    def set(self, key: str, value: Any):
        self._cache[key] = (value, time.time() + self.ttl)

    def clear(self):
        self._cache.clear()


# Global cache: 5 min for stats, queries are always fresh
stats_cache = TTLCache(ttl_seconds=300)


# ============================================================================
# Database queries
# ============================================================================

def query_listings(
    category: str | None = None,
    status: str | None = None,
    search_text: str | None = None,
    organization: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Query listings with filters. Always fresh (not cached)."""
    conn = get_conn()
    cur = conn.cursor()

    # Build query
    where_clauses = []
    params = []

    if category:
        where_clauses.append("category = %s")
        params.append(category)

    if status:
        where_clauses.append("status = %s")
        params.append(status)

    if search_text:
        where_clauses.append(
            "(name ILIKE %s OR description ILIKE %s)"
        )
        search_param = f"%{search_text}%"
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

    rows = rows_as_dicts(cur)

    # Convert UUIDs and dates to strings for JSON serialization
    for row in rows:
        if row.get("id"):
            row["id"] = str(row["id"])
        if row.get("expires_at"):
            row["expires_at"] = row["expires_at"].isoformat() if hasattr(row["expires_at"], "isoformat") else str(row["expires_at"])
        if row.get("source_updated_at"):
            row["source_updated_at"] = row["source_updated_at"].isoformat() if hasattr(row["source_updated_at"], "isoformat") else str(row["source_updated_at"])
        if row.get("ingested_at"):
            row["ingested_at"] = row["ingested_at"].isoformat() if hasattr(row["ingested_at"], "isoformat") else str(row["ingested_at"])

    conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "records": rows,
    }


def get_category_stats() -> dict:
    """Get aggregate stats by category (cached 5 min)."""
    cache_key = "category_stats"
    cached = stats_cache.get(cache_key)
    if cached:
        return cached

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

    # Geo coverage (distinct states from address)
    cur.execute("""
        SELECT DISTINCT
            address->>'state' as state
        FROM listings
        WHERE address IS NOT NULL
        ORDER BY state
    """)
    states = [row[0] for row in cur.fetchall() if row[0]]

    result = {
        "total_records": sum(categories.values()),
        "categories": categories,
        "organisations": orgs,
        "statuses": statuses,
        "states": states,
        "cached_at": datetime.now().isoformat(),
    }

    stats_cache.set(cache_key, result)
    conn.close()

    return result


def get_summary_stats() -> dict:
    """Get overall summary stats (cached 5 min)."""
    cache_key = "summary_stats"
    cached = stats_cache.get(cache_key)
    if cached:
        return cached

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
    result = {
        "total_records": row[0],
        "unique_organisations": row[1],
        "records_with_images": row[2],
        "records_with_geo": row[3],
        "earliest_ingest": row[4].isoformat() if row[4] else None,
        "latest_ingest": row[5].isoformat() if row[5] else None,
        "newest_source_update": row[6].isoformat() if row[6] else None,
    }

    stats_cache.set(cache_key, result)
    conn.close()

    return result


def search_text(query: str, limit: int = 50) -> dict:
    """Full-text search by name and description."""
    conn = get_conn()
    cur = conn.cursor()

    search_param = f"%{query}%"

    cur.execute("""
        SELECT
            id, source_id, category, name, description,
            organisation_name, latitude, longitude, ingested_at
        FROM listings
        WHERE name ILIKE %s OR description ILIKE %s
        ORDER BY
            CASE
                WHEN name ILIKE %s THEN 0
                ELSE 1
            END,
            ingested_at DESC
        LIMIT %s
    """, (search_param, search_param, search_param, limit))

    rows = rows_as_dicts(cur)

    # Convert UUIDs and dates to strings for JSON serialization
    for row in rows:
        if row.get("id"):
            row["id"] = str(row["id"])
        if row.get("ingested_at"):
            row["ingested_at"] = row["ingested_at"].isoformat() if hasattr(row["ingested_at"], "isoformat") else str(row["ingested_at"])

    conn.close()

    return {
        "query": query,
        "limit": limit,
        "results_count": len(rows),
        "results": rows,
    }


# ============================================================================
# MCP Protocol Implementation (stdio-based)
# ============================================================================

def handle_tool_call(tool_name: str, arguments: dict) -> str:
    """Handle incoming tool calls."""
    try:
        if tool_name == "query_listings":
            result = query_listings(
                category=arguments.get("category"),
                status=arguments.get("status"),
                search_text=arguments.get("search_text"),
                organization=arguments.get("organization"),
                limit=arguments.get("limit", 50),
                offset=arguments.get("offset", 0),
            )
            return json.dumps(result)

        elif tool_name == "get_category_stats":
            result = get_category_stats()
            return json.dumps(result)

        elif tool_name == "get_summary_stats":
            result = get_summary_stats()
            return json.dumps(result)

        elif tool_name == "search_text":
            result = search_text(
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 50),
            )
            return json.dumps(result)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_resource_request(uri: str) -> str:
    """Handle incoming resource requests."""
    try:
        if uri == "listings://summary":
            return json.dumps(get_summary_stats())
        elif uri == "listings://categories":
            stats = get_category_stats()
            return json.dumps(stats["categories"])
        elif uri.startswith("listings://search/"):
            query = uri.split("/", 2)[2]
            return json.dumps(search_text(query, limit=20))
        else:
            return json.dumps({"error": f"Unknown resource: {uri}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def run_server():
    """Run the MCP server listening on stdin/stdout."""
    print(
        json.dumps({
            "jsonrpc": "2.0",
            "id": 0,
            "result": {
                "name": "ATDW Data Probe MCP Server",
                "version": "0.1.0",
                "tools": [
                    {
                        "name": "query_listings",
                        "description": "Query listings with filters by category, status, text, or organization",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "category": {
                                    "type": "string",
                                    "description": "Filter by category (e.g. TOUR, ATTRACTION, ACCOMM, RESTAURANT, EVENT)",
                                },
                                "status": {
                                    "type": "string",
                                    "description": "Filter by status (e.g. CURRENT, EXPIRED, PENDING)",
                                },
                                "search_text": {
                                    "type": "string",
                                    "description": "Search in name and description",
                                },
                                "organization": {
                                    "type": "string",
                                    "description": "Filter by organization name",
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Max results to return (default 50)",
                                },
                                "offset": {
                                    "type": "integer",
                                    "description": "Pagination offset (default 0)",
                                },
                            },
                        },
                    },
                    {
                        "name": "search_text",
                        "description": "Full-text search by name and description",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query",
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Max results (default 50)",
                                },
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_category_stats",
                        "description": "Get aggregate statistics by category, organization, and status",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "get_summary_stats",
                        "description": "Get overall summary statistics (record count, coverage, etc.)",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ],
                "resources": [
                    {
                        "uri": "listings://summary",
                        "name": "Summary Statistics",
                        "description": "Overall statistics for the listings database",
                    },
                    {
                        "uri": "listings://categories",
                        "name": "Category Counts",
                        "description": "Record counts grouped by category",
                    },
                    {
                        "uri": "listings://search/{query}",
                        "name": "Search Listings",
                        "description": "Full-text search on listing name and description",
                    },
                ],
            },
        }),
        file=sys.stdout,
        flush=True,
    )

    # Main loop: read JSON-RPC messages from stdin
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            message = json.loads(line)
            method = message.get("method")
            params = message.get("params", {})
            msg_id = message.get("id")

            if method == "tools/call":
                result = handle_tool_call(
                    params.get("name"),
                    params.get("arguments", {}),
                )
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": json.loads(result),
                }
            elif method == "resources/read":
                result = handle_resource_request(params.get("uri"))
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": json.loads(result),
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

            print(json.dumps(response), file=sys.stdout, flush=True)

        except json.JSONDecodeError as e:
            print(
                json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": f"Parse error: {e}"},
                }),
                file=sys.stderr,
                flush=True,
            )
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(
                json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": f"Internal error: {e}"},
                }),
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":
    run_server()
