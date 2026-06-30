# Hello World — BridgeMCP Example

A minimal but complete MCP server demonstrating the BridgeMCP framework.

## What it does

Registers three tools:

| Tool | Description |
|---|---|
| `greet(name, greeting?)` | Says hello. `greeting` defaults to `"Hello"`. |
| `add(x, y)` | Adds two integers. |
| `server_info()` | Returns the server name, version, and registered tool list. |

## Run it

```bash
# Install dependencies (first time only)
pip install 'bridgemcp-py[mcp]'

# stdio transport — for Claude Desktop, Cursor, VS Code
python server.py

# HTTP/SSE transport — for network-based clients
python server.py --http
```

## Connect to Claude Desktop

Add this to your `claude_desktop_config.json`
(`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "hello-world": {
      "command": "python",
      "args": ["/absolute/path/to/examples/hello_world/server.py"]
    }
  }
}
```

Replace `/absolute/path/to/` with the actual path on your machine, then restart Claude Desktop.
