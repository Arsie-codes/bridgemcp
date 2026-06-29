"""
Hello World — BridgeMCP Example Server

A minimal but complete MCP server that demonstrates:
  - Bare @app.tool decorator (no arguments)
  - @app.tool with name and description overrides
  - Default parameter values
  - Returning simple values and dicts

Run via stdio (for Claude Desktop / Cursor):
    python server.py

Run via HTTP/SSE (for network-based clients):
    python server.py --http
"""

import sys

from bridgemcp import BridgeMCP

app = BridgeMCP(
    name="hello-world",
    version="1.0.0",
    description="A minimal BridgeMCP example server.",
)


@app.tool
def greet(name: str, greeting: str = "Hello") -> str:
    """Greet someone by name.

    Args:
        name: The name of the person to greet.
        greeting: The greeting word to use. Defaults to "Hello".
    """
    return f"{greeting}, {name}!"


@app.tool
def add(x: int, y: int) -> int:
    """Add two integers and return the result."""
    return x + y


@app.tool(name="server_info", description="Return metadata about this server.")
def get_server_info() -> dict:
    return {
        "name": app.name,
        "version": app.version,
        "tools": [t.name for t in app.list_tools()],
    }


if __name__ == "__main__":
    if "--http" in sys.argv:
        app.run_http(host="127.0.0.1", port=8000)
    else:
        app.run()
