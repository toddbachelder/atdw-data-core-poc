# ATDW Data Probe REST API Reference

Read-only API for querying ATDW listings database. **Base URL:** `https://your-api-url/api/v1`

**Interactive docs:** Visit `https://your-api-url/docs` (Swagger UI with live testing)

---

## Endpoints

### Listings

#### `GET /listings`
Query listings with optional filters.

**Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `category` | string | — | Filter by category (TOUR, ATTRACTION, ACCOMM, RESTAURANT, EVENT, etc.) |
| `status` | string | — | Filter by status (CURRENT, EXPIRED, PENDING, etc.) |
| `search` | string | — | Search in name and description |
| `organization` | string | — | Filter by organization name (partial match) |
| `limit` | int | 50 | Max results (1-500) |
| `offset` | int | 0 | Pagination offset |

**Example:**
```bash
# Get 10 accommodation listings
GET /listings?category=ACCOMM&limit=10

# Search for "tour" in TOUR category, skip first 20
GET /listings?category=TOUR&search=tour&limit=10&offset=20

# All listings from "Hipcamp"
GET /listings?organization=Hipcamp&limit=50
```

**Response:**
```json
{
  "total": 16252,
  "count": 10,
  "limit": 10,
  "offset": 0,
  "records": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "source_id": "P123456",
      "source_number": "12345",
      "category": "ACCOMM",
      "status": "CURRENT",
      "name": "Sydney Harbour Hotel",
      "description": "Historic pub overlooking the harbour...",
      "image_url": "https://...",
      "latitude": -33.8568,
      "longitude": 151.2093,
      "address": {
        "type": "business",
        "line1": "10 Argyle Street",
        "city": "The Rocks",
        "state": "NSW",
        "postcode": "2000",
        "country": "AU",
        "areas": ["Sydney", "Rocks"],
        "region": "Sydney & Surrounds"
      },
      "organisation_id": "ORG123",
      "organisation_name": "Hipcamp",
      "expires_at": "2027-09-09",
      "source_updated_at": "2026-09-08T22:47:42.667+00:00",
      "next_occurrence": "2026-09-10T00:00:00",
      "ingested_at": "2026-09-09T04:48:49.229203+00:00"
    }
  ]
}
```

---

#### `GET /listings/{source_id}`
Get a single listing by ID.

**Parameters:**
| Param | Type | Description |
|---|---|---|
| `source_id` | string (path) | The listing's source ID (e.g. P123456) |

**Example:**
```bash
GET /listings/P123456
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source_id": "P123456",
  "name": "Sydney Harbour Hotel",
  ...
}
```

**Status codes:**
- `200` — Listing found
- `404` — Listing not found

---

### Search

#### `GET /search`
Full-text search on listing name and description.

**Parameters:**
| Param | Type | Required | Description |
|---|---|---|---|
| `q` | string | Yes | Search query (minimum 2 characters) |
| `limit` | int | No | Max results (1-500, default 50) |

**Example:**
```bash
# Search for "Sydney"
GET /search?q=Sydney

# Search for "Bondi Beach", limit 5
GET /search?q=Bondi Beach&limit=5
```

**Response:**
```json
{
  "query": "Sydney",
  "limit": 50,
  "results_count": 1245,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "source_id": "P123456",
      "category": "ATTRACTION",
      "name": "Sydney Opera House Tour",
      "description": "Guided tour of the iconic Sydney Opera House...",
      "organisation_name": "Sydney Tours Inc",
      "latitude": -33.8568,
      "longitude": 151.2093,
      "ingested_at": "2026-09-09T04:48:49.229203+00:00"
    }
  ]
}
```

---

### Statistics

#### `GET /stats/summary`
Overall summary statistics.

**Parameters:** None

**Example:**
```bash
GET /stats/summary
```

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

---

#### `GET /stats/categories`
Aggregate statistics by category, organization, and state.

**Parameters:** None

**Example:**
```bash
GET /stats/categories
```

**Response:**
```json
{
  "total_records": 58430,
  "categories": {
    "ACCOMM": 16252,
    "ATTRACTION": 14834,
    "EVENT": 8983,
    "RESTAURANT": 8285,
    "TOUR": 3468,
    "DESTINFO": 1955,
    "GENSERVICE": 1803,
    "HIRE": 1224,
    "JOURNEY": 734,
    "INFO": 498,
    "TRANSPORT": 393
  },
  "organisations": [
    {
      "name": "Hipcamp",
      "count": 2158
    },
    {
      "name": "ToursByLocals",
      "count": 1245
    }
  ],
  "statuses": {
    "CURRENT": 45000,
    "EXPIRED": 13430
  },
  "states": ["ACT", "NSW", "QLD", "SA", "TAS", "VIC", "WA"],
  "cached_at": "2026-09-09T12:34:56.789012"
}
```

---

### Health

#### `GET /health`
Health check for monitoring.

**Response (healthy):**
```json
{
  "status": "ok",
  "database": "connected"
}
```

**Response (unhealthy):**
```json
{
  "status": "error",
  "database": "connection refused"
}
```

**Status codes:**
- `200` — Healthy
- `503` — Database connection failed

---

## Query Examples

### Use Case: Find all current events in NSW

```bash
GET /listings?category=EVENT&status=CURRENT&search=NSW&limit=20
```

### Use Case: Count how many restaurants we have

```bash
GET /stats/categories
# → Read categories.RESTAURANT
```

### Use Case: Search for "Bondi" attractions

```bash
GET /search?q=Bondi&limit=10
# Filter results client-side for category=ATTRACTION if needed
```

### Use Case: Get a specific listing

```bash
GET /listings/P12345
```

### Use Case: Check data freshness

```bash
GET /stats/summary
# → Read newest_source_update and latest_ingest
```

---

## Response Format

All responses are JSON with consistent structure:

**Query endpoints** (listings, search):
```json
{
  "total": number,      // Total matching records
  "count": number,      // Returned records in this response
  "limit": number,      // Requested limit
  "offset": number,     // Requested offset
  "records": [...]      // Array of listing objects
}
```

**Stats endpoints:**
```json
{
  // Various statistics
}
```

**Errors:**
```json
{
  "detail": "Error message"
}
```

---

## Error Handling

| Code | Meaning | Typical Causes |
|---|---|---|
| `200` | Success | — |
| `400` | Bad Request | Invalid parameter (e.g. `limit=1000` > max) |
| `404` | Not Found | Listing ID doesn't exist |
| `422` | Validation Error | Invalid query format |
| `500` | Server Error | Database error or bug |
| `503` | Service Unavailable | Database connection failed |

**Example error:**
```json
{
  "detail": "Database error: connection refused"
}
```

---

## Rate Limits

No built-in rate limiting. Deployed services (Railway, Render) may have per-plan limits:
- Free tier: ~100 requests/minute recommended (monitor if exceeding)
- Paid: Higher limits, depends on plan

For high-volume use, contact ATDW.

---

## Pagination

Use `limit` and `offset` for pagination:

```bash
# Page 1: 10 records
GET /listings?limit=10&offset=0

# Page 2: next 10 records
GET /listings?limit=10&offset=10

# Page 3: next 10 records
GET /listings?limit=10&offset=20
```

**Note:** Always respect the `total` count in responses for stopping pagination.

---

## CORS & Access

**CORS enabled:** ✅ Any origin can call this API from browsers
**Authentication:** None required (read-only)
**HTTPS:** Required for production deployments (Railway/Render auto-provide)

---

## Code Examples

### Python
```python
import requests

api = "https://your-api.railway.app/api/v1"

# Get accommodation listings
resp = requests.get(f"{api}/listings", params={"category": "ACCOMM", "limit": 5})
listings = resp.json()
print(f"Found {listings['total']} accommodation listings")

# Search
resp = requests.get(f"{api}/search", params={"q": "Sydney", "limit": 3})
results = resp.json()
for item in results["results"]:
    print(f"  - {item['name']}")
```

### JavaScript
```javascript
const api = "https://your-api.railway.app/api/v1";

// Get restaurants
fetch(`${api}/listings?category=RESTAURANT&limit=5`)
  .then(r => r.json())
  .then(data => {
    console.log(`Found ${data.total} restaurants`);
    data.records.forEach(r => console.log(`  - ${r.name}`));
  });
```

### curl
```bash
# Get stats
curl https://your-api.railway.app/api/v1/stats/summary | jq .

# Search
curl "https://your-api.railway.app/api/v1/search?q=Sydney&limit=5" | jq .results
```

---

## Deployment & Support

- **Deployment:** See `DEPLOYMENT.md` for hosting instructions
- **Interactive Docs:** Visit `https://your-api.../docs` to test endpoints live
- **Questions:** Contact ATDW technical team

---

**Last updated:** 2026-09-09
**API Version:** 1.0.0
