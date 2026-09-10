# ATDW MCP Server Integration Guide

**Endpoint:** `https://atdw-alpha-mcp.onrender.com/rpc`  
**Protocol:** JSON-RPC 2.0 (POST)  
**Status:** Live and Production-Ready ✓

---

## ChatGPT / OpenAI

### Option 1: OpenAI API with Custom Function (Recommended)

1. **Create a function definition** in your API call:

```json
{
  "type": "function",
  "function": {
    "name": "query_atdw_listings",
    "description": "Query ATDW listings database for accommodations, events, tours, restaurants, and attractions in Australia",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Natural language query or search term"
        },
        "category": {
          "type": "string",
          "enum": ["ACCOMM", "EVENT", "TOUR", "RESTAURANT", "ATTRACTION", "DESTINFO"],
          "description": "Optional category filter"
        },
        "organization": {
          "type": "string",
          "description": "Optional organization name filter"
        }
      },
      "required": ["query"]
    }
  }
}
```

2. **Call the MCP endpoint** when ChatGPT selects this function:

```bash
curl -X POST "https://atdw-alpha-mcp.onrender.com/rpc" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "query_listings",
      "arguments": {
        "category": "ACCOMM",
        "organization": "Hilton"
      }
    },
    "id": 1
  }'
```

### Option 2: Custom GPT with Actions

1. Go to **ChatGPT Builder** → **Create new GPT**
2. Click **Actions** → **Create new action**
3. Use the OpenAPI schema below
4. Paste this schema in the **Authentication** section

```yaml
openapi: 3.0.0
info:
  title: ATDW MCP Server
  version: 1.0.0
servers:
  - url: https://atdw-alpha-mcp.onrender.com
paths:
  /rpc:
    post:
      operationId: queryListings
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                jsonrpc:
                  type: string
                  default: "2.0"
                method:
                  type: string
                  default: "tools/call"
                params:
                  type: object
                  properties:
                    name:
                      type: string
                      enum: ["query_listings", "query_natural_language", "search_text"]
                    arguments:
                      type: object
      responses:
        "200":
          description: Query result
          content:
            application/json:
              schema:
                type: object
```

---

## Claude (via Claude API)

### Direct API Integration

```python
import anthropic
import requests

client = anthropic.Anthropic(api_key="your-api-key")

def query_mcp_server(tool_name, arguments):
    """Call ATDW MCP server"""
    response = requests.post(
        "https://atdw-alpha-mcp.onrender.com/rpc",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 1
        }
    )
    return response.json()["result"]

# Example: Query Hilton hotels
result = query_mcp_server(
    "query_listings",
    {
        "category": "ACCOMM",
        "organization": "Hilton",
        "limit": 50
    }
)

print(f"Found {result['total']} Hilton hotels")
```

### Claude with Tool Use (Recommended)

```python
tools = [
    {
        "name": "query_atdw",
        "description": "Query ATDW listings database",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "enum": ["query_listings", "query_natural_language", "search_text", "get_category_stats"]
                },
                "category": {"type": "string"},
                "organization": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer"}
            }
        }
    }
]

message = client.messages.create(
    model="claude-opus-5",
    max_tokens=1024,
    tools=tools,
    messages=[
        {"role": "user", "content": "How many Marriott hotels are in Australia?"}
    ]
)
```

---

## Perplexity

### Via Perplexity API

1. **Get your API key** from https://www.perplexity.ai/

2. **Add as a knowledge connector:**

```python
import requests

def search_atdw(query):
    """Search ATDW via Perplexity"""
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer YOUR_PERPLEXITY_API_KEY",
            "Content-Type": "application/json"
        },
        json={
            "model": "pplx-70b-online",
            "messages": [{
                "role": "user",
                "content": f"Query the ATDW database: {query}"
            }],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "query_atdw",
                    "description": "Query ATDW Australian tourism listings",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        }
                    }
                }
            }]
        }
    )
    return response.json()
```

### Using Perplexity Web Interface

1. Open https://www.perplexity.ai/
2. Type your query: "How many Hilton hotels are in Australia?"
3. Perplexity can call the MCP endpoint via its function calling capabilities

---

## Universal JSON-RPC Examples

### Natural Language Query
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "query_natural_language",
    "arguments": {
      "query": "restaurants in Sydney",
      "limit": 20
    }
  },
  "id": 1
}
```

### Direct Search
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_text",
    "arguments": {
      "query": "Blue Mountains",
      "limit": 10
    }
  },
  "id": 1
}
```

### Get Statistics
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_category_stats",
    "arguments": {}
  },
  "id": 1
}
```

---

## Available Tools

| Tool | Description | Parameters |
|------|-------------|-----------|
| `query_listings` | Query with filters | `category`, `organization`, `search_text`, `status`, `limit`, `offset` |
| `query_natural_language` | Natural language queries | `query`, `limit` |
| `search_text` | Full-text search | `query`, `limit` |
| `get_category_stats` | Category statistics | (none) |
| `get_summary_stats` | Summary statistics | (none) |

---

## Categories Available

- `ACCOMM` - Accommodation
- `ATTRACTION` - Attractions
- `EVENT` - Events
- `RESTAURANT` - Restaurants & Food
- `TOUR` - Tours & Activities
- `DESTINFO` - Destination Information
- `GENSERVICE` - General Services
- `HIRE` - Hire Services
- `JOURNEY` - Journeys
- `INFO` - Info Points
- `TRANSPORT` - Transport

---

## Testing

### Quick Test (cURL)
```bash
curl -X POST "https://atdw-alpha-mcp.onrender.com/rpc" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "query_natural_language",
      "arguments": {
        "query": "hotels in Sydney"
      }
    },
    "id": 1
  }' | jq '.'
```

### Health Check
```bash
curl "https://atdw-alpha-mcp.onrender.com/health"
```

---

## Notes

- **Rate Limiting:** No official rate limits (fair use)
- **Response Time:** Typical ~200-500ms
- **Database:** 58,000+ ATDW listings across Australia
- **Updates:** Real-time queries, no caching except stats (5-min TTL)
- **Authentication:** None required (public API)

---

## Support

For issues or questions, refer to:
- Repository: https://github.com/toddbachelder/atdw-data-core-poc
- MCP Server: `/rpc` endpoint
- Health Check: `/health` endpoint
