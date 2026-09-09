# ATDW Data Probe MCP Server

A Model Context Protocol (MCP) server that exposes the ATDW probe database to Claude and other MCP clients.

## Features

- **Query listings** with filters by category, status, organization, or full-text search
- **Aggregate statistics** by category, organization, and state
- **Summary statistics** including record counts and data coverage
- **Caching** for stats (5-minute TTL) with always-fresh listing queries
- **Hybrid interface**: both high-level resources and low-level tool calls
- **JSON-RPC over stdio** for easy integration with Claude Code

## Running the Server

```bash
python src/mcp_server.py
```

The server listens on **stdin/stdout** for JSON-RPC 2.0 messages. It connects to the database using the `DATABASE_URL` in `.env`.

## Tools

### `query_listings`
Query listing records with filters.

**Arguments:**
- `category` (string, optional): Filter by category (TOUR, ATTRACTION, ACCOMM, RESTAURANT, EVENT, etc.)
- `status` (string, optional): Filter by status (CURRENT, EXPIRED, PENDING, etc.)
- `search_text` (string, optional): Search in name and description fields
- `organization` (string, optional): Filter by organization name (partial match)
- `limit` (integer, default 50): Max records to return
- `offset` (integer, default 0): Pagination offset

**Example:**
```json
{
  "category": "TOUR",
  "limit": 10,
  "offset": 0
}
```

**Response:**
```json
{
  "total": 3468,
  "count": 10,
  "limit": 10,
  "offset": 0,
  "records": [
    {
      "id": "uuid-string",
      "source_id": "P123456",
      "name": "Blue Mountains Day Tour",
      "category": "TOUR",
      "description": "...",
      "image_url": "...",
      "latitude": -33.5,
      "longitude": 150.3,
      "organisation_name": "...",
      ...
    }
  ]
}
```

### `search_text`
Full-text search by name and description.

**Arguments:**
- `query` (string, required): Search query
- `limit` (integer, default 50): Max results

**Response:**
```json
{
  "query": "Sydney",
  "limit": 50,
  "results_count": 42,
  "results": [...]
}
```

### `get_category_stats`
Get aggregate statistics by category, organization, and status.

**Arguments:** None

**Response:**
```json
{
  "total_records": 58430,
  "categories": {
    "ACCOMM": 16252,
    "ATTRACTION": 14834,
    "EVENT": 8983,
    ...
  },
  "organisations": [
    {
      "name": "Hipcamp",
      "count": 2158
    },
    ...
  ],
  "statuses": {
    "CURRENT": 45000,
    "EXPIRED": 13430,
    ...
  },
  "states": ["ACT", "NSW", "QLD", "SA", "TAS", "VIC", "WA"],
  "cached_at": "2026-09-09T12:34:56.789012"
}
```

### `get_summary_stats`
Get overall summary statistics.

**Arguments:** None

**Response:**
```json
{
  "total_records": 58430,
  "unique_organisations": 18376,
  "records_with_images": 57916,
  "records_with_geo": 55924,
  "earliest_ingest": "2026-06-15T07:22:20.373940+00:00",
  "latest_ingest": "2026-09-09T04:48:49.229203+00:00",
  "newest_source_update": "2026-09-08T22:47:42.667000+00:00"
}
```

## Resources

The server exposes these resources (queryable as named data):

- `listings://summary` — Overall statistics
- `listings://categories` — Category counts
- `listings://search/{query}` — Full-text search (example: `listings://search/Sydney`)

## Integration with Claude Code

### Option 1: Global MCP Server in settings.json

Add to `~/.claude/settings.json` or the project's `.claude/settings.json`:

```json
{
  "mcp_servers": [
    {
      "name": "atdw-probe",
      "command": "python",
      "args": [
        "C:\\Users\\ToddBachelder\\Documents\\atdw-data-core-poc\\src\\mcp_server.py"
      ]
    }
  ]
}
```

Then Claude Code will automatically connect to the server and make tools available.

### Option 2: Ad-hoc via Claude Code CLI

```bash
claude code --mcp python src/mcp_server.py
```

This starts Claude Code with the MCP server enabled for a single session.

### Option 3: Run the server separately

```bash
python src/mcp_server.py &
```

Then configure a client (e.g., Claude browser extension) to connect to the stdio stream. This is less common but useful for debugging.

## Example Queries (from Claude)

Once integrated, Claude can ask:

> "How many accommodation listings do we have?"
> → Calls `get_category_stats`, reads ACCOMM count

> "Show me 5 restaurants in Sydney"
> → Calls `query_listings(category=RESTAURANT)` + `search_text(query=Sydney)`

> "Which organization has the most listings?"
> → Calls `get_category_stats`, reads `organisations[0]`

> "What's the data coverage? How many records have images and geo?"
> → Calls `get_summary_stats`

## Caching

- **Stats queries** (`get_category_stats`, `get_summary_stats`): 5-minute cache TTL
- **Listing queries** (`query_listings`, `search_text`): Always fresh (no cache)

This balances freshness for individual lookups with performance for aggregate stats.

## Performance Notes

- **Page size**: Defaults to 50 records per query; configurable via `limit` argument
- **Latency**: ~200ms for typical queries (DB call + serialization)
- **Concurrency**: Single-threaded; safe for concurrent MCP clients (JSON-RPC is stateless)
- **DB connections**: Creates a new connection per request; Supabase pooler handles reuse

## Troubleshooting

**"DATABASE_URL not set"**
→ Check that `.env` exists and contains `DATABASE_URL`. The server reads it on startup.

**"password authentication failed"**
→ The DB password in `.env` is stale. Run `python src/dbcheck.py` to diagnose.

**"JSON serialization error"**
→ UUIDs and dates are converted to strings automatically. If you see this, there's a new field type that needs handling.

**Server hangs or slow queries**
→ Check Supabase project status. If the pooler has issues, queries can timeout. Increase the timeout parameter if needed.

## Development

The server uses:
- `pg8000` for PostgreSQL connections (reuses existing `db.py`)
- `rows_as_dicts()` utility from the probe's `db.py`
- JSON-RPC 2.0 over stdin/stdout (compatible with MCP spec)

To add a new tool:
1. Add a Python function that returns a dict
2. Add a handler in `handle_tool_call()`
3. Add the tool spec to the initialization response
4. Ensure JSON serialization of all returned types (convert UUID/datetime to strings)

## See Also

- **CLAUDE.md** — Project overview and setup
- **src/dbcheck.py** — Diagnostics for the database connection
- **docs/findings.md** — Accumulated findings from the probe
