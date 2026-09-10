"""
HTTP wrapper for the MCP server.

This allows the stdio-based MCP server to be accessed over HTTP from remote clients.
Useful for Render deployments and remote integrations.

Run: python src/http_mcp_server.py
"""
import json
import sys
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ATDW MCP Server (HTTP)", version="0.1.0")

# Import MCP functions directly instead of spawning subprocess
sys.path.insert(0, os.path.dirname(__file__))
from mcp_server import (
    query_listings,
    query_natural_language,
    search_text,
    get_category_stats,
    get_summary_stats,
    handle_tool_call,
)


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict = {}
    id: int = None


@app.get("/health")
def health_check():
    """Health check endpoint."""
    try:
        # Try to connect to database
        get_summary_stats()
        return {
            "status": "ok",
            "service": "ATDW MCP Server",
            "database": "connected",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "service": "ATDW MCP Server",
            "database": "disconnected",
            "error": str(e),
        }, 503


@app.get("/")
def root():
    """Root endpoint with API documentation."""
    return {
        "service": "ATDW MCP Server (HTTP Gateway)",
        "version": "0.1.0",
        "endpoints": {
            "health": "GET /health",
            "rpc": "POST /rpc",
            "docs": "GET /docs (Swagger UI)",
        },
        "usage": {
            "description": "Send JSON-RPC requests to /rpc",
            "example_payload": {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "query_natural_language",
                    "arguments": {"query": "restaurants in Sydney", "limit": 50},
                },
                "id": 1,
            },
            "available_tools": [
                "query_listings",
                "query_natural_language",
                "search_text",
                "get_category_stats",
                "get_summary_stats",
            ],
        },
    }


@app.post("/rpc")
async def handle_rpc(request: MCPRequest):
    """Handle JSON-RPC requests to the MCP server."""
    try:
        logger.info(f"RPC Request: {request.method} with args: {request.params}")

        if request.method != "tools/call":
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32601, "message": f"Method not found: {request.method}"},
            }

        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})

        logger.info(f"Calling tool: {tool_name} with arguments: {arguments}")

        # Call the tool handler
        result_str = handle_tool_call(tool_name, arguments)
        result = json.loads(result_str)

        response = {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": result,
        }

        logger.info(f"RPC Response: {response}")
        return response

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
        }
    except Exception as e:
        logger.error(f"RPC error: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
        }


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    """Swagger UI documentation."""
    from fastapi.openapi.utils import get_openapi

    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="ATDW MCP Server",
        version="0.1.0",
        description="HTTP Gateway for ATDW MCP Server with natural language query support",
        routes=app.routes,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting MCP HTTP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
