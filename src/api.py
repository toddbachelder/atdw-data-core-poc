"""
Minimal versioned read API over the listings table.
Run: uvicorn src.api:app --reload
"""
import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from db import get_conn, rows_as_dicts

load_dotenv()

app = FastAPI(title="ATDW Data Core Probe", version="0.1.0")


@app.get("/v1/listings")
def list_listings(
    category: Optional[str] = Query(None, description="TOUR | ATTRACTION | ACCOMM | FOOD | EVENT"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
):
    conn = get_conn()
    try:
        where_clauses = ["status = 'ACTIVE'"]
        params: list = []

        if category:
            where_clauses.append("category = %s")
            params.append(category.upper())

        where = "WHERE " + " AND ".join(where_clauses)
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM listings {where} ORDER BY ingested_at DESC LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        rows = rows_as_dicts(cur)
        return {"total": len(rows), "limit": limit, "offset": offset, "data": rows}
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
