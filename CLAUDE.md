# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in credentials
cp .env.example .env

# Initialise DB schema (creates listings table in Supabase)
python src/db.py

# Fetch ~50 records per category from DAPI and upsert into DB
python src/ingest.py

# Serve the read API (http://localhost:8000)
uvicorn src.api:app --reload
```

API endpoints:
- `GET /v1/listings?category=TOUR&limit=20&offset=0`
- `GET /v1/listings/{source_id}`

## What this is

A one-day data probe. The purpose is to understand ATDW's own DAPI product data hands-on — by actually mapping it — not to build a platform. The deliverable is the **findings log** as much as the working code.

DAPI records (events, attractions, accommodation, food/drink) are ingested from real exports, translated into a clean canonical schema, stored simply, and served back out through a minimal versioned read API.

## Primary goals, in order

1. Get real DAPI records flowing (a few dozen to ~200, spread across product categories)
2. Define a canonical schema for core listing entities
3. Write the translation layer — this is where the interesting problems live
4. Expose a simple versioned read API (`/v1/listings`, `/v1/listings/{id}`)
5. Keep a running findings log (`docs/findings.md`) — every mapping decision, surprise, or dead end

## Architecture

```
DAPI export (JSON)
    → ingest script (parse, identify record type, discard fragments)
    → translation layer (map to canonical schema)
    → local store (SQLite or similar — keep it simple)
    → read API (versioned, minimal endpoints)
```

The canonical schema and translation layer are the core intellectual work. Everything else is scaffolding.

## Findings log

`docs/findings.md` is a first-class deliverable. Log every time:
- A field doesn't map cleanly or is absent/inconsistent
- You have to make a decision that feels like it should be a data-design choice
- Something that looked simple turned out not to be
- You discard or skip something and why

The log format doesn't matter. Bullet points are fine. Timestamp entries if it helps.

## Constraints

- **Done beats perfect.** An ugly probe that processed real records beats clean code that's still theoretical.
- **No front end.** Every hour on UI is an hour not spent on the mapping.
- **No over-engineering.** SQLite over Postgres, Flask/FastAPI over a framework, flat files over a queue. This is a probe.
- **The export has multiple record types.** Identify and focus on the core listing record; don't burn time on fragment types.
- **Real data only.** No synthetic or sample records — the messiness is the point.

## Key question to answer

> "If we had to own the canonical version of this data nationally, what's actually hard about it?"

Everything in the codebase should be in service of being able to answer that honestly.
