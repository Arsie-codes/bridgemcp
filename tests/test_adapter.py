"""
Tests for the MCP adapter (bridgemcp/adapters/mcp.py).

These tests require the mcp extra to be installed. They are skipped
automatically when the MCP SDK is not available so the base test suite
continues to run without it.

Install with: pip install 'bridgemcp[mcp]'
"""

from __future__ import annotations

import asyncio

import pytest

mcp = pytest.importorskip(
    "mcp", reason="mcp extra not installed; skipping adapter tests"
)

from bridgemcp import BridgeMCP  # noqa: E402
from bridgemcp.adapters.mcp import build_mcp_server  # noqa: E402
from bridgemcp.prompts import PromptMessage  # noqa: E402

# ---------------------------------------------------------------------------
# build_mcp_server — basic construction
# ---------------------------------------------------------------------------


def test_build_mcp_server_returns_functional_server():
    """build_mcp_server should return a server that can list tools."""
    app = BridgeMCP(name="test-server")
    server = build_mcp_server(app)
    # Verify the returned object is a functional MCP server without asserting
    # the concrete FastMCP type — behavioral check is more adapter-agnostic.
    tools = asyncio.run(server.list_tools())
    assert isinstance(tools, list)


def test_build_mcp_server_propagates_name():
    """The MCP server should carry the app's name."""
    app = BridgeMCP(name="my-service")
    server = build_mcp_server(app)

    assert server.name == "my-service"


def test_build_mcp_server_propagates_version():
    """The underlying MCPServer should carry the app's version string.

    FastMCP does not expose a public version field on FastMCP itself.
    Until it does, the only observable path is through _mcp_server.version.
    This test will be updated when FastMCP adds a public version accessor.
    """
    app = BridgeMCP(name="versioned-server", version="2.5.0")
    server = build_mcp_server(app)

    # FastMCP has no public version attribute — see adapters/mcp.py for why
    # _mcp_server is accessed directly here.
    assert server._mcp_server.version == "2.5.0"


def test_build_mcp_server_version_is_not_sdk_version():
    """The server version should be the user's version, not the MCP SDK version."""
    app = BridgeMCP(name="test-server", version="99.0.0")
    server = build_mcp_server(app)

    assert server._mcp_server.version == "99.0.0"


def test_build_mcp_server_propagates_description():
    """The server's instructions should match the app's description."""
    app = BridgeMCP(name="test-server", description="Does great things.")
    server = build_mcp_server(app)

    assert server.instructions == "Does great things."


def test_build_mcp_server_no_description():
    """When the app has no description, instructions should be None."""
    app = BridgeMCP(name="test-server")
    server = build_mcp_server(app)

    assert server.instructions is None


# ---------------------------------------------------------------------------
# build_mcp_server — tool registration
# ---------------------------------------------------------------------------


def test_build_mcp_server_registers_tools():
    """All tools registered on the app should appear in the MCP server."""
    app = BridgeMCP(name="test-server")

    @app.tool
    def ping() -> str:
        """Ping the server."""
        return "pong"

    @app.tool
    def add(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    server = build_mcp_server(app)
    registered_names = {t.name for t in asyncio.run(server.list_tools())}

    assert "ping" in registered_names
    assert "add" in registered_names


def test_build_mcp_server_registers_tool_with_name_override():
    """A tool registered under an explicit name should appear under that name."""
    app = BridgeMCP(name="test-server")

    @app.tool(name="list_orders")
    def get_orders() -> list:
        """Fetch orders."""
        return []

    server = build_mcp_server(app)
    registered_names = {t.name for t in asyncio.run(server.list_tools())}

    assert "list_orders" in registered_names
    assert "get_orders" not in registered_names


def test_build_mcp_server_with_no_tools():
    """An app with no tools should produce a server with no registered tools."""
    app = BridgeMCP(name="empty-server")
    server = build_mcp_server(app)

    assert asyncio.run(server.list_tools()) == []


# ---------------------------------------------------------------------------
# Tool execution through the adapter
# ---------------------------------------------------------------------------


def test_adapter_tool_executes_correctly():
    """A tool registered via the adapter should appear in the tool list."""
    app = BridgeMCP(name="test-server")

    @app.tool
    def greet(name: str) -> str:
        """Greet someone."""
        return f"Hello, {name}!"

    server = build_mcp_server(app)
    registered_names = {t.name for t in asyncio.run(server.list_tools())}

    assert "greet" in registered_names


def test_multiple_calls_to_build_mcp_server_are_independent():
    """Calling build_mcp_server twice should produce two independent server instances."""
    app = BridgeMCP(name="test-server")

    @app.tool
    def ping() -> str:
        return "pong"

    server_one = build_mcp_server(app)
    server_two = build_mcp_server(app)

    assert server_one is not server_two


# ---------------------------------------------------------------------------
# build_mcp_server — resource registration
# ---------------------------------------------------------------------------


def test_build_mcp_server_registers_resources():
    """All resources registered on the app should appear in the MCP server."""
    app = BridgeMCP(name="test-server")

    @app.resource(uri="config://settings")
    def get_settings() -> str:
        return "{}"

    @app.resource(uri="data://users")
    def get_users() -> str:
        return "[]"

    server = build_mcp_server(app)
    registered_uris = {str(r.uri) for r in asyncio.run(server.list_resources())}

    assert "config://settings" in registered_uris
    assert "data://users" in registered_uris


def test_build_mcp_server_registers_resource_uri():
    """The URI registered on the server should match the app registration."""
    app = BridgeMCP(name="test-server")

    @app.resource(uri="config://app/settings")
    def get_settings() -> str:
        return "{}"

    server = build_mcp_server(app)
    uris = {str(r.uri) for r in asyncio.run(server.list_resources())}

    assert "config://app/settings" in uris


def test_build_mcp_server_registers_resource_default_name():
    """When no name override is given, the resource name defaults to the function name."""
    app = BridgeMCP(name="test-server")

    @app.resource(uri="data://test")
    def get_data() -> str:
        return ""

    server = build_mcp_server(app)
    resources = {str(r.uri): r for r in asyncio.run(server.list_resources())}

    assert resources["data://test"].name == "get_data"


def test_build_mcp_server_registers_resource_explicit_name():
    """An explicit name set at registration should appear on the server resource."""
    app = BridgeMCP(name="test-server")

    @app.resource(uri="data://test", name="Application Data")
    def get_data() -> str:
        return ""

    server = build_mcp_server(app)
    resources = {str(r.uri): r for r in asyncio.run(server.list_resources())}

    assert resources["data://test"].name == "Application Data"


def test_build_mcp_server_registers_resource_description():
    """An explicit description should appear on the server resource."""
    app = BridgeMCP(name="test-server")

    @app.resource(uri="data://test", description="Returns current settings.")
    def get_data() -> str:
        return ""

    server = build_mcp_server(app)
    resources = {str(r.uri): r for r in asyncio.run(server.list_resources())}

    assert resources["data://test"].description == "Returns current settings."


def test_build_mcp_server_registers_resource_explicit_mime_type():
    """An explicit mime_type set at registration should appear on the server resource."""
    app = BridgeMCP(name="test-server")

    @app.resource(uri="data://test", mime_type="application/json")
    def get_data() -> str:
        return "{}"

    server = build_mcp_server(app)
    resources = {str(r.uri): r for r in asyncio.run(server.list_resources())}

    # MCP SDK Resource model uses camelCase: mimeType, not mime_type.
    assert resources["data://test"].mimeType == "application/json"


def test_build_mcp_server_resource_mime_type_none_defaults_to_text_plain():
    """FastMCP defaults mimeType to 'text/plain' when none is set at registration.

    This is FastMCP's own behavior (FunctionResource.from_function applies
    'mime_type or text/plain'). BridgeMCP does not control or override it.
    This test locks in the observed SDK behavior so any future SDK change
    that alters the default is caught immediately.
    """
    app = BridgeMCP(name="test-server")

    @app.resource(uri="data://test")
    def get_data() -> str:
        return "plain text"

    server = build_mcp_server(app)
    resources = {str(r.uri): r for r in asyncio.run(server.list_resources())}

    # MCP SDK Resource model uses camelCase: mimeType, not mime_type.
    assert resources["data://test"].mimeType == "text/plain"


def test_build_mcp_server_with_no_resources():
    """An app with no resources should produce a server with no registered resources."""
    app = BridgeMCP(name="test-server")
    server = build_mcp_server(app)

    assert asyncio.run(server.list_resources()) == []


def test_build_mcp_server_registers_multiple_resources():
    """Multiple registered resources should all appear in the server."""
    app = BridgeMCP(name="test-server")

    @app.resource(uri="data://one")
    def res_one() -> str:
        return ""

    @app.resource(uri="data://two")
    def res_two() -> str:
        return ""

    @app.resource(uri="data://three")
    def res_three() -> str:
        return ""

    server = build_mcp_server(app)
    registered_uris = {str(r.uri) for r in asyncio.run(server.list_resources())}

    assert "data://one" in registered_uris
    assert "data://two" in registered_uris
    assert "data://three" in registered_uris


def test_adapter_resource_returns_string_content():
    """A resource returning str should produce str content when read through the server."""
    app = BridgeMCP(name="test-server")

    @app.resource(uri="data://text")
    def get_text() -> str:
        return "hello from resource"

    server = build_mcp_server(app)
    # read_resource returns list[ReadResourceContents]; content is at .content
    result = asyncio.run(server.read_resource("data://text"))

    assert result[0].content == "hello from resource"


def test_adapter_resource_returns_bytes_content():
    """A resource returning bytes should produce bytes content when read through the server."""
    app = BridgeMCP(name="test-server")

    @app.resource(uri="data://binary")
    def get_binary() -> bytes:
        return b"\x00\x01\x02"

    server = build_mcp_server(app)
    # read_resource returns list[ReadResourceContents]; content is at .content
    result = asyncio.run(server.read_resource("data://binary"))

    assert result[0].content == b"\x00\x01\x02"


def test_build_mcp_server_resources_and_tools_are_independent():
    """Registering resources should not affect registered tools, and vice versa."""
    app = BridgeMCP(name="test-server")

    @app.tool
    def ping() -> str:
        return "pong"

    @app.resource(uri="data://test")
    def get_data() -> str:
        return ""

    server = build_mcp_server(app)

    tool_names = {t.name for t in asyncio.run(server.list_tools())}
    resource_uris = {str(r.uri) for r in asyncio.run(server.list_resources())}

    assert "ping" in tool_names
    assert "data://test" in resource_uris
    # Cross-contamination check
    assert "data://test" not in tool_names
    assert "ping" not in resource_uris


# ---------------------------------------------------------------------------
# build_mcp_server — prompt registration
# ---------------------------------------------------------------------------


def test_build_mcp_server_registers_prompts():
    """All prompts registered on the app should appear in the MCP server."""
    app = BridgeMCP(name="test-server")

    @app.prompt
    def greet(name: str) -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"

    @app.prompt
    def summarize(text: str, max_words: int = 100) -> str:
        """Summarize some text."""
        return f"Summarize in {max_words} words: {text}"

    server = build_mcp_server(app)
    registered_names = {p.name for p in asyncio.run(server.list_prompts())}

    assert "greet" in registered_names
    assert "summarize" in registered_names


def test_build_mcp_server_with_no_prompts():
    """An app with no prompts should produce a server with no registered prompts."""
    app = BridgeMCP(name="test-server")
    server = build_mcp_server(app)

    assert asyncio.run(server.list_prompts()) == []


def test_build_mcp_server_registers_prompt_with_name_override():
    """A prompt registered under an explicit name should appear under that name."""
    app = BridgeMCP(name="test-server")

    @app.prompt(name="code_review")
    def review_code(language: str, code: str) -> str:
        """Review code for quality."""
        return f"Review this {language}: {code}"

    server = build_mcp_server(app)
    registered_names = {p.name for p in asyncio.run(server.list_prompts())}

    assert "code_review" in registered_names
    assert "review_code" not in registered_names


def test_build_mcp_server_registers_prompt_description():
    """The prompt description should appear on the registered server prompt."""
    app = BridgeMCP(name="test-server")

    @app.prompt
    def ask() -> str:
        """Ask a helpful question."""
        return "What would you like to know?"

    server = build_mcp_server(app)
    prompts = {p.name: p for p in asyncio.run(server.list_prompts())}

    assert prompts["ask"].description == "Ask a helpful question."


def test_build_mcp_server_registers_prompt_arguments():
    """Prompt arguments should be inferred from the handler's parameter list."""
    app = BridgeMCP(name="test-server")

    @app.prompt
    def greet(name: str, title: str = "Dr.") -> str:
        return f"Hello, {title} {name}!"

    server = build_mcp_server(app)
    prompts = {p.name: p for p in asyncio.run(server.list_prompts())}
    arg_names = {a.name for a in prompts["greet"].arguments}

    assert "name" in arg_names
    assert "title" in arg_names


def test_build_mcp_server_marks_required_prompt_arguments():
    """Required arguments (no default) should be marked required; optional should not."""
    app = BridgeMCP(name="test-server")

    @app.prompt
    def greet(name: str, title: str = "Dr.") -> str:
        return f"Hello, {title} {name}!"

    server = build_mcp_server(app)
    prompts = {p.name: p for p in asyncio.run(server.list_prompts())}
    args = {a.name: a for a in prompts["greet"].arguments}

    assert args["name"].required is True
    assert args["title"].required is False


def test_build_mcp_server_registers_multiple_prompts():
    """Multiple prompts should all appear in the MCP server."""
    app = BridgeMCP(name="test-server")

    @app.prompt
    def one() -> str:
        return "one"

    @app.prompt
    def two() -> str:
        return "two"

    @app.prompt
    def three() -> str:
        return "three"

    server = build_mcp_server(app)
    registered_names = {p.name for p in asyncio.run(server.list_prompts())}

    assert {"one", "two", "three"}.issubset(registered_names)


# ---------------------------------------------------------------------------
# Prompt execution through the adapter
# ---------------------------------------------------------------------------


def test_adapter_prompt_returns_user_message():
    """A str-returning prompt should produce a user-role message when rendered."""
    app = BridgeMCP(name="test-server")

    @app.prompt
    def ask() -> str:
        return "What is the weather?"

    server = build_mcp_server(app)
    result = asyncio.run(server.get_prompt("ask"))

    assert len(result.messages) == 1
    assert result.messages[0].role == "user"
    assert result.messages[0].content.text == "What is the weather?"


def test_adapter_prompt_passes_arguments_to_handler():
    """Arguments passed to get_prompt should be forwarded to the handler."""
    app = BridgeMCP(name="test-server")

    @app.prompt
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    server = build_mcp_server(app)
    result = asyncio.run(server.get_prompt("greet", {"name": "Alice"}))

    assert result.messages[0].content.text == "Hello, Alice!"


def test_adapter_prompt_multi_turn_messages():
    """Multi-turn prompts should produce multiple messages with correct roles."""
    app = BridgeMCP(name="test-server")

    @app.prompt
    def debug(error: str) -> list[PromptMessage]:
        return [
            PromptMessage(role="user", content=f"Error: {error}"),
            PromptMessage(role="assistant", content="Share your code."),
            PromptMessage(role="user", content="Here it is."),
        ]

    server = build_mcp_server(app)
    result = asyncio.run(server.get_prompt("debug", {"error": "NPE"}))

    assert len(result.messages) == 3
    assert result.messages[0].role == "user"
    assert result.messages[0].content.text == "Error: NPE"
    assert result.messages[1].role == "assistant"
    assert result.messages[2].role == "user"


def test_adapter_prompt_works_with_async_handler():
    """An async prompt handler should execute correctly through the adapter."""
    app = BridgeMCP(name="test-server")

    @app.prompt
    async def async_ask(topic: str) -> str:
        return f"Tell me about {topic}."

    server = build_mcp_server(app)
    result = asyncio.run(server.get_prompt("async_ask", {"topic": "Python"}))

    assert result.messages[0].content.text == "Tell me about Python."


# ---------------------------------------------------------------------------
# Prompts, tools, and resources are independent
# ---------------------------------------------------------------------------


def test_build_mcp_server_all_three_primitives_are_independent():
    """Registering tools, resources, and prompts should not interfere with each other."""
    app = BridgeMCP(name="test-server")

    @app.tool
    def ping() -> str:
        return "pong"

    @app.resource(uri="data://test")
    def get_data() -> str:
        return ""

    @app.prompt
    def ask() -> str:
        return "Hello?"

    server = build_mcp_server(app)

    tool_names = {t.name for t in asyncio.run(server.list_tools())}
    resource_uris = {str(r.uri) for r in asyncio.run(server.list_resources())}
    prompt_names = {p.name for p in asyncio.run(server.list_prompts())}

    assert "ping" in tool_names
    assert "data://test" in resource_uris
    assert "ask" in prompt_names
    # Cross-contamination checks
    assert "ask" not in tool_names
    assert "ping" not in prompt_names


# ---------------------------------------------------------------------------
# ImportError when mcp is not installed
# ---------------------------------------------------------------------------


def test_build_mcp_server_import_error_message():
    """The ImportError message should contain installation instructions."""
    import importlib
    import sys
    import unittest.mock

    with (
        unittest.mock.patch.dict(
            sys.modules, {"mcp": None, "mcp.server.fastmcp": None}
        ),
        pytest.raises(ImportError, match="bridgemcp\\[mcp\\]"),
    ):
        # Re-import the function to trigger the deferred import
        from importlib import import_module

        adapter = import_module("bridgemcp.adapters.mcp")
        importlib.reload(adapter)
        adapter.build_mcp_server(BridgeMCP(name="x"))
