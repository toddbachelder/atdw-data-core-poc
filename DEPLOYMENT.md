# ATDW Data Probe API — Deployment Guide

Deploy the REST API as a hosted service for ATDW colleagues.

**What you're deploying:** A read-only REST API to query 58k+ ATDW listings, with search, filtering, and statistics.

**Key characteristics:**
- ✅ Read-only (no data modifications)
- ✅ Auto-generated API docs at `/docs`
- ✅ CORS enabled (callable from browsers, external apps)
- ✅ Gzip compression
- ✅ Health checks built-in
- ✅ Connects to Supabase via `DATABASE_URL`

## Quick Deploy (5 minutes)

### Option 1: Railway.app (Recommended)

**Easiest:** Railway auto-deploys from git and handles environment variables.

1. **Create Railway account** → https://railway.app (free tier available)

2. **Connect your repository** → New Project → GitHub → Select this repo

3. **Add environment variables:**
   - Click on your deployment
   - **Variables** tab
   - Add: `DATABASE_URL` = `postgresql://...` (from Supabase)

4. **Set the start command:**
   - Deployment settings
   - **Build** → `pip install -r requirements.txt`
   - **Start command** → `uvicorn src.api_server:app --host 0.0.0.0 --port 8000`

5. **Deploy** → Railway auto-deploys on git push

**URL:** `https://<your-project>.railway.app`

**Cost:** Free tier includes 500 hours/month. For 24/7 hosting, ~$5-10/month.

---

### Option 2: Render.com

1. **Create account** → https://render.com

2. **New** → **Web Service** → **Connect GitHub repo**

3. **Configure:**
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn src.api_server:app --host 0.0.0.0 --port 8000`
   - **Environment:** Add `DATABASE_URL`

4. **Deploy** → Auto-deploys from git

**Cost:** Free tier has limits; paid starts at $7/month for always-on.

---

### Option 3: Heroku (Legacy, but still works)

```bash
# Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli

heroku login
heroku create atdw-probe-api
heroku config:set DATABASE_URL="postgresql://..." --app atdw-probe-api
git push heroku main
heroku open --app atdw-probe-api
```

**Cost:** No free tier anymore; starts at $7/month.

---

### Option 4: Docker (Self-Hosted)

Deploy to your own server or cloud infrastructure.

**Build the image:**
```bash
docker build -t atdw-probe-api .
```

**Run locally:**
```bash
docker run \
  -e DATABASE_URL="postgresql://postgres.xxx:password@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres" \
  -p 8000:8000 \
  atdw-probe-api
```

Then access at `http://localhost:8000`

**Push to container registry (Docker Hub, ECR, etc.):**
```bash
docker tag atdw-probe-api your-username/atdw-probe-api:latest
docker push your-username/atdw-probe-api:latest
```

Then deploy to Kubernetes, Docker Swarm, or any orchestration platform.

---

## Environment Variables

**Required:**
- `DATABASE_URL` — Supabase connection string (from Dashboard → Settings → Database → Connection string → Session pooler)
  ```
  postgresql://postgres.xxxxx:password@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres
  ```

**Optional:**
- `PORT` (default 8000) — Server port
- `WORKERS` (default 4) — Number of Uvicorn workers (for production)

---

## API Endpoints

Once deployed, your URL structure is:

```
https://your-api-url/api/v1/...
```

### Endpoints

**Listings:**
- `GET /api/v1/listings` — Query with filters
- `GET /api/v1/listings/{source_id}` — Get single listing

**Search:**
- `GET /api/v1/search?q=Sydney` — Full-text search

**Statistics:**
- `GET /api/v1/stats/summary` — Overall stats
- `GET /api/v1/stats/categories` — Category breakdown

**Health:**
- `GET /health` — Health check (for monitoring)

### Example Queries

```bash
# Get 10 accommodation listings
curl "https://your-api.railway.app/api/v1/listings?category=ACCOMM&limit=10"

# Search for "Sydney"
curl "https://your-api.railway.app/api/v1/search?q=Sydney&limit=5"

# Get summary stats
curl "https://your-api.railway.app/api/v1/stats/summary"

# Get listing by ID
curl "https://your-api.railway.app/api/v1/listings/P123456"
```

**Interactive docs:** Visit `https://your-api.railway.app/docs` to test endpoints in browser.

---

## Sharing with Colleagues

Once deployed, share the URL with ATDW colleagues:

### For Claude Code Users

They can configure it as an MCP server. Create a file at `~/.claude/settings.json`:

```json
{
  "mcp_servers": [
    {
      "name": "atdw-probe-api",
      "command": "python",
      "args": ["-c", "import requests; from anthropic import MCP; ..."]
    }
  ]
}
```

Or simpler: they can just call the REST API directly from Claude using the `requests` library or by passing the URL.

### For Python Users

```python
import requests

api_url = "https://your-api.railway.app"

# Query listings
resp = requests.get(f"{api_url}/api/v1/listings", params={
    "category": "TOUR",
    "limit": 10
})
listings = resp.json()

# Search
resp = requests.get(f"{api_url}/api/v1/search", params={"q": "Sydney"})
results = resp.json()

# Get stats
resp = requests.get(f"{api_url}/api/v1/stats/summary")
stats = resp.json()
```

### For JavaScript/Web Users

```javascript
const apiUrl = "https://your-api.railway.app";

// Query listings
fetch(`${apiUrl}/api/v1/listings?category=TOUR&limit=10`)
  .then(r => r.json())
  .then(data => console.log(data.records));

// Search
fetch(`${apiUrl}/api/v1/search?q=Sydney`)
  .then(r => r.json())
  .then(data => console.log(data.results));
```

### For Power Users (Excel, Zapier, etc.)

The REST API works with any tool that can make HTTP requests:
- **Excel:** `=WEBSERVICE()` or Power Query
- **Zapier:** Use Webhooks → GET requests
- **Google Sheets:** `=IMPORTJSON()`
- **Postman:** Organize queries as collections

---

## Monitoring & Maintenance

### Health Checks

Both Railway and Render support automatic health checks. The API has:

```
GET /health
```

Returns `{"status": "ok", "database": "connected"}` if healthy.

### Logs

**Railway:** Deployment → **Logs** tab
**Render:** Deployment → **Logs** tab

Check logs if queries return 5xx errors.

### Database Connection Issues

If you see `"database": "error"` in `/health`:

1. Verify `DATABASE_URL` is set correctly
2. Check if Supabase project is still active
3. Confirm the password hasn't expired (Supabase passwords should not expire, but check the pooler status)

### Performance

- **Typical query latency:** 200-500ms
- **Cold start after idle:** 1-2s (rebuilds connection pool)
- **Concurrent connections:** Platform-dependent (Railway/Render handle auto-scaling)

---

## Costs

| Platform | Free Tier | Paid (24/7) |
|---|---|---|
| **Railway** | 500h/mo | ~$5-10/mo |
| **Render** | Limited | $7+/mo |
| **Heroku** | None (deprecated) | $7+/mo |
| **AWS EC2** | 750h free/yr | $5+/mo |
| **Self-hosted** | Your infra | Depends |

For ATDW team use, Railway free tier is usually sufficient (500 hours/month = ~16-20 concurrent users querying continuously).

---

## Troubleshooting

### 503 Service Unavailable / Database Connection Failed

```json
{"status": "error", "database": "connection refused"}
```

**Causes:**
1. `DATABASE_URL` not set or invalid
2. Supabase project offline
3. Wrong password/pooler host

**Fix:**
- Check env var: `echo $DATABASE_URL`
- Test locally: `python src/dbcheck.py`
- Confirm Supabase project status at supabase.com/dashboard

### 500 Internal Server Error on Queries

```json
{"detail": "Database error: ..."}
```

Check the logs for the full error. Usually a connection pool issue.

**Fix:**
- Restart the deployment (Railway/Render dashboard → Redeploy)
- Check database query timeout (increase if queries are slow)

### Slow Queries

Large result sets or `limit=500` can be slow. Recommendations:
- Use `limit ≤ 100` in normal use
- Add filtering (`category`, `organization`) to reduce result size
- Use search for text queries (faster than `ILIKE` with large datasets)

### CORS Errors in Browser

Should not happen (CORS is enabled). If you see:
```
Access-Control-Allow-Origin header missing
```

There's a deployment issue. Restart the service.

---

## Next Steps

1. **Choose a deployment platform** → Railway recommended for ease
2. **Gather credentials:**
   - `DATABASE_URL` from Supabase
3. **Deploy** → Follow the option above
4. **Test** → Visit `https://your-api.../docs` and try a query
5. **Share the URL** with ATDW colleagues
6. **Monitor** → Check logs if issues arise

---

## Support

For questions or issues:
- Check `/docs` endpoint for interactive API documentation
- Review logs in the deployment platform
- Test locally first: `uvicorn src.api_server:app --reload`
- Verify database: `python src/dbcheck.py`

See `MCP_SERVER.md` for the stdio-based MCP variant (local use only).
