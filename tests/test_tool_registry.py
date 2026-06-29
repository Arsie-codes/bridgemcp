"""
Tests for the tool registration system.

Covers ToolRegistry in isolation and the @app.tool decorator on BridgeMCP.
"""

from __future__ import annotations

import inspect

import pytest

from bridgemcp import BridgeMCP
from bridgemcp.exceptions import ToolRegistrationError
from bridgemcp.tools.registry import Tool, ToolRegistry

# ---------------------------------------------------------------------------
# Helpers — plain functions used as test fixtures
# ---------------------------------------------------------------------------


def simple_tool(x: int, y: int) -> int:
    """Add two numbers together."""
    return x + y


def no_annotations(x, y):
    return x + y


def no_docstring(name: str) -> str:
    return f"hello {name}"


async def async_tool(item_id: str) -> dict:
    """Fetch an item asynchronously."""
    return {"id": item_id}


# ---------------------------------------------------------------------------
# Tool — data class
# ---------------------------------------------------------------------------


def test_tool_is_immutable():
    """Tool instances should not allow field mutation after creation."""
    registry = ToolRegistry()
    tool = registry.register(simple_tool)

    with pytest.raises((AttributeError, TypeError)):
        tool.name = "something_else"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolRegistry — registration
# ---------------------------------------------------------------------------


def test_register_returns_tool():
    """register() should return a Tool instance."""
    registry = ToolRegistry()
    result = registry.register(simple_tool)

    assert isinstance(result, Tool)


def test_register_captures_name_from_function():
    """Tool name should default to the function's __name__."""
    registry = ToolRegistry()
    tool = registry.register(simple_tool)

    assert tool.name == "simple_tool"


def test_register_accepts_explicit_name():
    """An explicit name should override the function name."""
    registry = ToolRegistry()
    tool = registry.register(simple_tool, name="add_numbers")

    assert tool.name == "add_numbers"


def test_register_captures_docstring_as_description():
    """The function docstring should be used as the description."""
    registry = ToolRegistry()
    tool = registry.register(simple_tool)

    assert tool.description == "Add two numbers together."


def test_register_accepts_explicit_description():
    """An explicit description should override the docstring."""
    registry = ToolRegistry()
    tool = registry.register(simple_tool, description="Custom description")

    assert tool.description == "Custom description"


def test_register_description_is_none_when_no_docstring():
    """Description should be None when the function has no docstring."""
    registry = ToolRegistry()
    tool = registry.register(no_docstring)

    assert tool.description is None


def test_register_stores_callable():
    """The original function should be stored on the Tool."""
    registry = ToolRegistry()
    tool = registry.register(simple_tool)

    assert tool.fn is simple_tool


def test_register_captures_signature():
    """The function's full signature should be stored."""
    registry = ToolRegistry()
    tool = registry.register(simple_tool)

    assert isinstance(tool.signature, inspect.Signature)
    assert "x" in tool.signature.parameters
    assert "y" in tool.signature.parameters


def test_register_captures_return_annotation():
    """The return type annotation should be stored."""
    registry = ToolRegistry()
    tool = registry.register(simple_tool)

    assert tool.return_annotation is int


def test_register_return_annotation_none_when_absent():
    """Return annotation should be None when the function has no return hint."""
    registry = ToolRegistry()
    tool = registry.register(no_annotations)

    assert tool.return_annotation is None


def test_register_sync_function_is_not_async():
    """A regular function should have is_async=False."""
    registry = ToolRegistry()
    tool = registry.register(simple_tool)

    assert tool.is_async is False


def test_register_async_function_is_async():
    """An async function should have is_async=True."""
    registry = ToolRegistry()
    tool = registry.register(async_tool)

    assert tool.is_async is True


def test_register_duplicate_name_raises():
    """Registering two tools with the same name should raise ToolRegistrationError."""
    registry = ToolRegistry()
    registry.register(simple_tool)

    with pytest.raises(ToolRegistrationError, match="already registered"):
        registry.register(simple_tool)


def test_register_duplicate_explicit_name_raises():
    """An explicit name collision should also raise ToolRegistrationError."""
    registry = ToolRegistry()
    registry.register(simple_tool, name="my_tool")

    with pytest.raises(ToolRegistrationError, match="already registered"):
        registry.register(no_docstring, name="my_tool")


# ---------------------------------------------------------------------------
# ToolRegistry — retrieval
# ---------------------------------------------------------------------------


def test_get_returns_registered_tool():
    """get() should return the Tool for a known name."""
    registry = ToolRegistry()
    registry.register(simple_tool)

    tool = registry.get("simple_tool")
    assert tool is not None
    assert tool.name == "simple_tool"


def test_get_returns_none_for_unknown_name():
    """get() should return None for a name that has not been registered."""
    registry = ToolRegistry()

    assert registry.get("nonexistent") is None


def test_list_returns_all_tools():
    """list() should return all registered tools."""
    registry = ToolRegistry()
    registry.register(simple_tool)
    registry.register(no_docstring)

    tools = registry.list()
    names = [t.name for t in tools]

    assert "simple_tool" in names
    assert "no_docstring" in names


def test_list_returns_empty_for_new_registry():
    """list() on a fresh registry should return an empty list."""
    registry = ToolRegistry()

    assert registry.list() == []


def test_len_reflects_registration_count():
    """len() should return the number of registered tools."""
    registry = ToolRegistry()
    assert len(registry) == 0

    registry.register(simple_tool)
    assert len(registry) == 1

    registry.register(no_docstring)
    assert len(registry) == 2


# ---------------------------------------------------------------------------
# @app.tool — bare decorator
# ---------------------------------------------------------------------------


def test_bare_decorator_registers_tool():
    """@app.tool with no arguments should register the function."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def greet(name: str) -> str:
        return f"Hello {name}"

    tool = app._tool_registry.get("greet")
    assert tool is not None


def test_bare_decorator_returns_original_function():
    """@app.tool should return the original function unchanged."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def greet(name: str) -> str:
        return f"Hello {name}"

    # The function must still be directly callable
    assert greet("world") == "Hello world"


def test_bare_decorator_uses_function_name():
    """@app.tool should use the function name as the tool name."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def get_orders() -> list:
        return []

    tool = app._tool_registry.get("get_orders")
    assert tool is not None
    assert tool.name == "get_orders"


# ---------------------------------------------------------------------------
# @app.tool — decorator with arguments
# ---------------------------------------------------------------------------


def test_decorator_with_explicit_name():
    """@app.tool(name=...) should override the function name."""
    app = BridgeMCP(name="test-app")

    @app.tool(name="list_orders")
    def get_orders() -> list:
        return []

    assert app._tool_registry.get("list_orders") is not None
    assert app._tool_registry.get("get_orders") is None


def test_decorator_with_explicit_description():
    """@app.tool(description=...) should override the docstring."""
    app = BridgeMCP(name="test-app")

    @app.tool(description="Fetch all active orders")
    def get_orders() -> list:
        """This docstring should be ignored."""
        return []

    tool = app._tool_registry.get("get_orders")
    assert tool is not None
    assert tool.description == "Fetch all active orders"


def test_decorator_with_arguments_returns_original_function():
    """@app.tool(...) should return the original function unchanged."""
    app = BridgeMCP(name="test-app")

    @app.tool(name="greet_user")
    def greet(name: str) -> str:
        return f"Hello {name}"

    assert greet("world") == "Hello world"


def test_tool_registries_are_independent_across_instances():
    """Two BridgeMCP instances should have separate tool registries."""
    app_one = BridgeMCP(name="app-one")
    app_two = BridgeMCP(name="app-two")

    @app_one.tool
    def ping() -> str:
        return "pong"

    assert app_one._tool_registry.get("ping") is not None
    assert app_two._tool_registry.get("ping") is None
