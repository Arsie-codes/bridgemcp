"""
Tests for tool invocation through BridgeMCP.app.call().

Covers the happy path, missing tools, argument errors, and exception
chaining when a tool's own function raises.
"""

import pytest

from bridgemcp import BridgeMCP
from bridgemcp.exceptions import ToolExecutionError, ToolNotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(*tools):
    """Create a BridgeMCP instance with the given functions registered."""
    app = BridgeMCP(name="test-app")
    for fn in tools:
        app.tool(fn)
    return app


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_call_returns_result():
    """call() should return the tool's return value unchanged."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def ping() -> str:
        return "pong"

    assert app.call("ping") == "pong"


def test_call_passes_kwargs_to_function():
    """call() should forward keyword arguments to the tool function."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def greet(name: str) -> str:
        return f"Hello, {name}"

    assert app.call("greet", name="World") == "Hello, World"


def test_call_with_multiple_arguments():
    """call() should handle multiple keyword arguments correctly."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def add(x: int, y: int) -> int:
        return x + y

    assert app.call("add", x=3, y=4) == 7


def test_call_returns_none_when_tool_returns_none():
    """call() should return None if the tool returns None."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def do_nothing() -> None:
        return None

    assert app.call("do_nothing") is None


def test_call_returns_complex_value():
    """call() should return dicts, lists, and other types unchanged."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def get_record() -> dict:
        return {"id": 1, "name": "Alice"}

    result = app.call("get_record")
    assert result == {"id": 1, "name": "Alice"}


def test_call_uses_registered_name_override():
    """call() should use the name the tool was registered under, not __name__."""
    app = BridgeMCP(name="test-app")

    @app.tool(name="list_orders")
    def get_orders() -> list:
        return [1, 2, 3]

    assert app.call("list_orders") == [1, 2, 3]


# ---------------------------------------------------------------------------
# ToolNotFoundError
# ---------------------------------------------------------------------------


def test_call_raises_tool_not_found_for_unknown_name():
    """call() should raise ToolNotFoundError when the tool does not exist."""
    app = BridgeMCP(name="test-app")

    with pytest.raises(ToolNotFoundError):
        app.call("nonexistent")


def test_call_not_found_message_contains_tool_name():
    """The ToolNotFoundError message should include the requested tool name."""
    app = BridgeMCP(name="test-app")

    with pytest.raises(ToolNotFoundError, match="nonexistent"):
        app.call("nonexistent")


def test_call_not_found_message_lists_registered_tools():
    """The error message should list available tools to help the developer."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def ping() -> str:
        return "pong"

    with pytest.raises(ToolNotFoundError, match="ping"):
        app.call("typo_ping")


def test_call_not_found_message_when_no_tools_registered():
    """The error message should note when no tools are registered at all."""
    app = BridgeMCP(name="test-app")

    with pytest.raises(ToolNotFoundError, match="No tools are registered"):
        app.call("anything")


# ---------------------------------------------------------------------------
# ToolExecutionError — tool function raises
# ---------------------------------------------------------------------------


def test_call_wraps_exception_in_tool_execution_error():
    """If the tool raises, call() should raise ToolExecutionError."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def broken() -> None:
        raise RuntimeError("database is down")

    with pytest.raises(ToolExecutionError):
        app.call("broken")


def test_call_execution_error_message_contains_tool_name():
    """ToolExecutionError message should identify which tool failed."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def broken() -> None:
        raise RuntimeError("something failed")

    with pytest.raises(ToolExecutionError, match="broken"):
        app.call("broken")


def test_call_execution_error_preserves_original_exception():
    """The original exception should be accessible via __cause__."""
    app = BridgeMCP(name="test-app")

    original = ValueError("invalid customer ID")

    @app.tool
    def failing_tool() -> None:
        raise original

    with pytest.raises(ToolExecutionError) as exc_info:
        app.call("failing_tool")

    assert exc_info.value.__cause__ is original


def test_call_execution_error_preserves_original_message():
    """The original exception's message should appear in ToolExecutionError."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def broken() -> None:
        raise RuntimeError("database connection refused")

    with pytest.raises(ToolExecutionError, match="database connection refused"):
        app.call("broken")


def test_call_wraps_type_error_from_wrong_arguments():
    """A TypeError from wrong arguments is also wrapped in ToolExecutionError."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def greet(name: str) -> str:
        return f"Hello, {name}"

    # Calling without the required argument triggers a TypeError inside call()
    with pytest.raises(ToolExecutionError):
        app.call("greet")


# ---------------------------------------------------------------------------
# ToolExecutionError — async handler rejected by sync call()
# ---------------------------------------------------------------------------


def test_call_raises_for_async_tool():
    """call() should raise ToolExecutionError for async handlers; acall() should be used."""
    app = BridgeMCP(name="test-app")

    @app.tool
    async def async_tool() -> str:
        return "result"

    with pytest.raises(ToolExecutionError, match="acall"):
        app.call("async_tool")


# ---------------------------------------------------------------------------
# acall — async execution
# ---------------------------------------------------------------------------


async def test_acall_returns_result_from_sync_handler():
    """acall() should work with synchronous handlers."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def ping() -> str:
        return "pong"

    assert await app.acall("ping") == "pong"


async def test_acall_returns_result_from_async_handler():
    """acall() should work with asynchronous handlers."""
    app = BridgeMCP(name="test-app")

    @app.tool
    async def async_ping() -> str:
        return "async pong"

    assert await app.acall("async_ping") == "async pong"


async def test_acall_passes_kwargs_to_async_handler():
    app = BridgeMCP(name="test-app")

    @app.tool
    async def greet(name: str) -> str:
        return f"Hello, {name}"

    assert await app.acall("greet", name="World") == "Hello, World"


async def test_acall_raises_tool_not_found():
    app = BridgeMCP(name="test-app")

    with pytest.raises(ToolNotFoundError):
        await app.acall("nonexistent")


async def test_acall_wraps_exception_from_async_handler():
    app = BridgeMCP(name="test-app")

    @app.tool
    async def broken() -> None:
        raise RuntimeError("async failure")

    with pytest.raises(ToolExecutionError, match="async failure"):
        await app.acall("broken")


async def test_acall_preserves_original_exception_cause():
    app = BridgeMCP(name="test-app")
    original = ValueError("root cause")

    @app.tool
    async def broken() -> None:
        raise original

    with pytest.raises(ToolExecutionError) as exc_info:
        await app.acall("broken")

    assert exc_info.value.__cause__ is original
