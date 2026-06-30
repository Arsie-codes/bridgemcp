# BridgeMCP

[![CI](https://github.com/Arsie-codes/bridgemcp/actions/workflows/tests.yml/badge.svg)](https://github.com/Arsie-codes/bridgemcp/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/bridgemcp-py)](https://pypi.org/project/bridgemcp-py/)
[![Python](https://img.shields.io/pypi/pyversions/bridgemcp-py)](https://pypi.org/project/bridgemcp-py/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A production-ready Python framework for building MCP servers.**

BridgeMCP makes it simple to expose your application's data and actions to AI clients like Claude Desktop, Cursor, and VS Code through the [Model Context Protocol](https://modelcontextprotocol.io).

Write your business logic. BridgeMCP handles the protocol.

---

## Why BridgeMCP

The MCP Python SDK is powerful but low-level. Building a real server means wiring up transport layers, hand-crafting JSON schemas, managing tool dispatch, and handling protocol errors — before you write a single line of business logic.

BridgeMCP wraps all of that behind a clean, decorator-based API:

| Without BridgeMCP | With BridgeMCP |
|---|---|
| Manually define JSON schemas | Inferred from type annotations |
| Write protocol handlers | `@app.tool` decorator |
| Manage error codes | Typed exception hierarchy |
| Choose and wire a transport | `app.run()` or `app.run_http()` |

---

## Installation

```bash
# With MCP transport support
pip install 'bridgemcp-py[mcp]'

# Core only (no transport — useful if you only need app.call() in tests)
pip install bridgemcp-py
```

Python 3.11+ required.

---

## Quick Start

**1. Write your server** (`server.py`):

```python
from bridgemcp import BridgeMCP

app = BridgeMCP(name="my-app", version="1.0.0", description="My first MCP server.")

@app.tool
def greet(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

@app.tool
def add(x: int, y: int) -> int:
    """Add two integers."""
    return x + y

if __name__ == "__main__":
    app.run()
```

**2. Connect to Claude Desktop**

Edit your Claude Desktop config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "my-app": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

Restart Claude Desktop. Your tools will appear in the tool picker.

---

## Core Concepts

### Creating an application

```python
from bridgemcp import BridgeMCP
from bridgemcp.config import BridgeConfig

app = BridgeMCP(
    name="my-app",          # shown to AI clients during the MCP handshake
    version="1.0.0",        # defaults to the installed package version
    description="...",      # optional — shown as server instructions
    config=BridgeConfig(),
)
```

### Registering tools

Use `@app.tool` as a bare decorator or with keyword arguments:

```python
# Bare — uses function name and docstring automatically
@app.tool
def get_order(order_id: str) -> dict:
    """Fetch an order by ID."""
    return orders.get(order_id)

# With overrides
@app.tool(name="list_orders", description="List all open orders.")
def fetch_open_orders(limit: int = 20) -> list:
    return orders.list(status="open", limit=limit)
```

Type annotations become the JSON schema that AI clients use to call your tools. Default values become optional parameters. Docstrings become tool descriptions.

### Calling tools directly

The decorated function is returned unchanged, so you can call it in tests without touching the framework:

```python
# Direct call — no framework involved
assert get_order("ORD-123") == {"id": "ORD-123", ...}

# Through the framework — registry lookup + error wrapping
result = app.call("get_order", order_id="ORD-123")
```

### Running the server

```python
# stdio — subprocess transport (Claude Desktop, Cursor, VS Code)
app.run()

# HTTP/SSE — network transport
app.run_http(host="0.0.0.0", port=8000)
```

---

## Exception Hierarchy

All BridgeMCP exceptions inherit from `BridgeMCPError`:

```python
from bridgemcp.exceptions import (
    BridgeMCPError,              # base — catch this to handle any framework error

    # Tools
    ToolNotFoundError,           # raised by app.call() when the tool name is unknown
    ToolRegistrationError,       # raised by @app.tool when a name is already taken
    ToolExecutionError,          # raised when the tool function itself raises

    # Resources
    ResourceNotFoundError,       # raised by app.read_resource() when URI is unknown
    ResourceRegistrationError,   # raised by @app.resource when URI is already taken
    ResourceExecutionError,      # raised when the resource handler raises

    # Prompts
    PromptNotFoundError,         # raised by app.render_prompt() when name is unknown
    PromptRegistrationError,     # raised by @app.prompt when name is already taken
    PromptExecutionError,        # raised when the prompt handler raises
)
# The original exception is always available via __cause__ on execution errors.
```

---

## Architecture

```
bridgemcp/
├── application.py      # BridgeMCP — the single public entry point
├── config/             # BridgeConfig (Pydantic, frozen)
├── exceptions.py       # Typed exception hierarchy
├── execution.py        # Handler execution pipeline (shared by all primitives)
├── middleware.py       # InvocationContext, MiddlewareFn, build_chain()
├── plugin.py           # Plugin base class and duck-typing contract
├── tools/              # Tool dataclass + ToolRegistry
├── resources/          # Resource dataclass + ResourceRegistry
├── prompts/            # Prompt, PromptMessage, PromptRegistry
└── adapters/           # Protocol adapters (MCP SDK is only imported here)
    └── mcp.py          # build_mcp_server() → FastMCP
```

The framework is layered deliberately:

1. **`BridgeMCP`** owns the entire public API — decorators, invocation methods, `run()`.
2. **Registry modules** store primitive metadata independently of any protocol.
3. **`execution.py`** handles invocation, exception chaining, and output normalization.
4. **`middleware.py`** defines the composition layer — no framework imports.
5. **`adapters/mcp.py`** is the only place the MCP SDK is imported.

Because the MCP SDK is an optional dependency, `BridgeMCP` and all invocation methods work without it. Your unit tests run without any MCP imports, keeping them fast and your business logic decoupled from the transport.

---

## Examples

| Example | Description |
|---|---|
| [`examples/hello_world/`](examples/hello_world/server.py) | Minimal server — greet, add, server_info tools |

---

## Development

```bash
# Clone and install in editable mode with all dev dependencies
git clone https://github.com/Arsie-codes/bridgemcp.git
cd bridgemcp
pip install -e '.[mcp,dev]'

# Run the test suite
pytest

# Run a specific test file
pytest tests/test_tool_registry.py -v

# Lint and format
ruff check bridgemcp tests
black bridgemcp tests
```

The test suite requires no network access and no MCP client — it runs entirely against the in-process framework.

---

## What's in the core

| Feature | API |
|---|---|
| Tools | `@app.tool`, `app.call()`, `await app.acall()`, `app.list_tools()` |
| Resources | `@app.resource(uri=...)`, `app.read_resource()`, `await app.aread_resource()`, `app.list_resources()` |
| Prompts | `@app.prompt`, `app.render_prompt()`, `await app.arender_prompt()`, `app.list_prompts()` |
| Middleware | `app.add_middleware()`, `@app.middleware` |
| Plugins | `app.register_plugin()`, `Plugin` base class (optional) |
| Transport | `app.run()` (stdio), `app.run_http()` (HTTP/SSE) |

---
---

# Official BridgeMCP Ecosystem

## Framework

- **BridgeMCP**
  https://github.com/Arsie-codes/bridgemcp

## Official Plugins

- **bridgemcp-logging**
  https://github.com/Arsie-codes/bridgemcp-logging

## Official Servers

- **bridgemcp-server-weather**
  https://github.com/Arsie-codes/bridgemcp-server-weather

More official plugins and servers are currently under development.

## License

MIT — Copyright (c) 2026 Muhammad Arslan
