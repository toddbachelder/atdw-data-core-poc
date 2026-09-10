"""
Simple HTTP wrapper for MCP server - minimal dependencies version.
Runs on Render as: uvicorn src.mcp_http_server:app
"""
import json
import sys
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="ATDW MCP Server", version="1.0")

# Direct imports - no subprocess complexity
sys.path.insert(0, os.path.dirname(__file__))

try:
    from mcp_server import handle_tool_call
except ImportError as e:
    print(f"Import error: {e}")
    handle_tool_call = None


class RPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict = {}
    id: int = 1


@app.get("/health")
def health():
    """Health check."""
    try:
        from mcp_server import get_summary_stats
        get_summary_stats()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "error", "message": str(e)}, 503


@app.get("/")
def root():
    """API info."""
    return {
        "name": "ATDW MCP Server (HTTP)",
        "version": "1.0",
        "endpoints": {
            "health": "GET /health",
            "rpc": "POST /rpc",
        },
    }


@app.post("/rpc")
async def rpc(request: RPCRequest):
    """Handle JSON-RPC requests."""
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
