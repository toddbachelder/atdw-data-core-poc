"""
HTTP wrapper for the MCP server.

This allows the stdio-based MCP server to be accessed over HTTP from remote clients.
Useful for Render deployments and remote integrations.

Run: python src/http_mcp_server.py
"""
import json
import subprocess
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

app = FastAPI(title="ATDW MCP Server (HTTP)")

# Start the MCP server subprocess
mcp_process = subprocess.Popen(
    [sys.executable, os.path.join(os.path.dirname(__file__), "mcp_server.py")],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict = {}
    id: int = None


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "ATDW MCP Server"}


@app.post("/rpc")
def handle_rpc(request: MCPRequest):
    """Handle JSON-RPC requests to the MCP server."""
    try:
        # Send request to MCP server
        rpc_message = json.dumps({
            "jsonrpc": request.jsonrpc,
            "method": request.method,
            "params": request.params,
            "id": request.id or 1,
        })

        mcp_process.stdin.write(rpc_message + "\n")
        mcp_process.stdin.flush()

        # Read response from MCP server
        response_line = mcp_process.stdout.readline()
        if not response_line:
            raise HTTPException(status_code=500, detail="No response from MCP server")

        response = json.loads(response_line)
        return response

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MCP Error: {str(e)}")


@app.get("/")
def root():
    """Root endpoint with API documentation."""
    return {
        "service": "ATDW MCP Server (HTTP Gateway)",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "rpc": "/rpc (POST)",
        },
        "usage": {
            "example": "POST /rpc with JSON-RPC payload",
            "payload": {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "query_natural_language",
                    "arguments": {"query": "restaurants in Sydney"},
                },
                "id": 1,
            },
        },
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
