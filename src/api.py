"""
Read API + stats endpoints for the ATDW data probe.
Run: uvicorn src.api:app --reload
"""
import os
import sys
import json
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from db import get_conn, rows_as_dicts

load_dotenv()

app = FastAPI(title="ATDW Data Core Probe", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ── Listings ──────────────────────────────────────────────────────────────────

_SORT_MAP = {
    "expires_asc": "expires_at ASC NULLS LAST",
    "name_asc":    "name ASC NULLS LAST",
}

@app.get("/v1/listings")
def list_listings(
    category:   Optional[str] = Query(None),
    state:      Optional[str] = Query(None),
    search:     Optional[str] = Query(None),
    sort:       Optional[str] = Query(None),
    multi_area: bool          = Query(False),
    limit:      int           = Query(20, le=100),
    offset:     int           = Query(0),
):
    conn = get_conn()
    try:
        where_clauses, params = [], []

        if category:
            where_clauses.append("category = %s")
            params.append(category.upper())
        if state:
            where_clauses.append("address->0->>'state' = %s")
            params.append(state.upper())
        if search:
            where_clauses.append("name ILIKE %s")
            params.append(f"%{search}%")
        if multi_area:
            where_clauses.append("jsonb_array_length(address->0->'areas') > 1")

        where    = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        order_by = _SORT_MAP.get(sort, "ingested_at DESC")

        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM listings {where}", params)
        total_count = cur.fetchone()[0]

        cur.execute(
            f"SELECT * FROM listings {where} ORDER BY {order_by} LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        rows = rows_as_dicts(cur)
        return {"total_count": total_count, "limit": limit, "offset": offset, "data": rows}
    finally:
        conn.close()


@app.get("/v1/listings/geo")
def listings_geo():
    """All records with coordinates — used for the map view."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT source_id, name, category, latitude, longitude,
                   address->0->>'city'  AS city,
                   address->0->>'state' AS state,
                   organisation_name
            FROM listings
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """)
        return {"data": rows_as_dicts(cur)}
    finally:
        conn.close()


@app.get("/v1/listings/{source_id}")
def get_listing(source_id: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM listings WHERE source_id = %s", (source_id,))
        rows = rows_as_dicts(cur)
        if not rows:
            raise HTTPException(status_code=404, detail="Listing not found")
        return rows[0]
    finally:
        conn.close()


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/v1/stats")
def get_stats():
    conn = get_conn()
    try:
        cur = conn.cursor()

        # Category counts + geo coverage
        cur.execute("""
            SELECT category,
                   COUNT(*)                                    AS total,
                   COUNT(latitude)                             AS has_geo,
                   ROUND(AVG(LENGTH(description)))::int        AS avg_desc_len,
                   COUNT(CASE WHEN image_url IS NULL THEN 1 END) AS missing_image
            FROM listings
            GROUP BY category ORDER BY total DESC
        """)
        categories = rows_as_dicts(cur)

        # State distribution (core listings)
        cur.execute("""
            SELECT address->0->>'state' AS state, category, COUNT(*) AS n
            FROM listings
            WHERE category IN ('RESTAURANT','ACCOMM','TOUR','ATTRACTION','EVENT')
              AND address IS NOT NULL
            GROUP BY state, category
            ORDER BY state, n DESC
        """)
        states = rows_as_dicts(cur)

        # Top organisations per category
        cur.execute("""
            SELECT category, organisation_name, COUNT(*) AS n
            FROM listings
            GROUP BY category, organisation_name
            ORDER BY category, n DESC
        """)
        all_orgs = rows_as_dicts(cur)
        # Keep top 5 per category
        top_orgs: dict = {}
        for row in all_orgs:
            cat = row["category"]
            if cat not in top_orgs:
                top_orgs[cat] = []
            if len(top_orgs[cat]) < 5:
                top_orgs[cat].append({"org": row["organisation_name"], "n": row["n"]})

        # Expiry spread
        cur.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', expires_at), 'YYYY-MM') AS month,
                   COUNT(*) AS n
            FROM listings WHERE expires_at IS NOT NULL
            GROUP BY month ORDER BY month
        """)
        expiry = rows_as_dicts(cur)

        # Totals
        cur.execute("SELECT COUNT(*) FROM listings")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT address->0->>'state') FROM listings WHERE address IS NOT NULL")
        state_count = cur.fetchone()[0]

        return {
            "total_records": total,
            "total_states": state_count,
            "categories": categories,
            "state_distribution": states,
            "top_organisations": top_orgs,
            "expiry_spread": expiry,
        }
    finally:
        conn.close()
