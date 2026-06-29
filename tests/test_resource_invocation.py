"""
Tests for resource invocation through BridgeMCP.app.read_resource().

Covers the happy path, missing resources, async rejection,
exception chaining, content normalization, and MIME type propagation.
"""

from __future__ import annotations

import pytest

from bridgemcp import BridgeMCP
from bridgemcp.exceptions import ResourceExecutionError, ResourceNotFoundError
from bridgemcp.resources.registry import ResourceContent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(*registrations):
    """Create a BridgeMCP instance with the given (uri, fn) pairs registered."""
    app = BridgeMCP(name="test-app")
    for uri, fn in registrations:
        app.resource(uri=uri)(fn)
    return app


# ---------------------------------------------------------------------------
# Happy path — ResourceContent is returned
# ---------------------------------------------------------------------------


def test_read_resource_returns_resource_content():
    """read_resource() should return a ResourceContent instance."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://test")
    def get_data() -> str:
        return "hello"

    result = app.read_resource("data://test")
    assert isinstance(result, ResourceContent)


def test_read_resource_echoes_uri():
    """The URI in ResourceContent should match the requested URI."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="config://settings")
    def get_settings() -> str:
        return "{}"

    result = app.read_resource("config://settings")
    assert result.uri == "config://settings"


def test_read_resource_returns_string_content():
    """A str-returning resource should produce str content."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://text")
    def get_text() -> str:
        return "plain text result"

    result = app.read_resource("data://text")
    assert result.content == "plain text result"
    assert isinstance(result.content, str)


def test_read_resource_returns_bytes_content():
    """A bytes-returning resource should produce bytes content."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://binary")
    def get_binary() -> bytes:
        return b"\x00\x01\x02"

    result = app.read_resource("data://binary")
    assert result.content == b"\x00\x01\x02"
    assert isinstance(result.content, bytes)


# ---------------------------------------------------------------------------
# MIME type — explicit passthrough, no inference
# ---------------------------------------------------------------------------


def test_read_resource_mime_type_is_none_when_not_set():
    """mime_type should be None in ResourceContent when not set at registration."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://test")
    def get_data() -> str:
        return "data"

    result = app.read_resource("data://test")
    assert result.mime_type is None


def test_read_resource_mime_type_passes_through_from_registration():
    """The explicit mime_type set at registration should appear in ResourceContent."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://json", mime_type="application/json")
    def get_json() -> str:
        return '{"key": "value"}'

    result = app.read_resource("data://json")
    assert result.mime_type == "application/json"


def test_read_resource_mime_type_not_inferred_for_dict_return():
    """Returning a dict should NOT trigger MIME type inference."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://dict")
    def get_dict() -> dict:
        return {"key": "value"}

    result = app.read_resource("data://dict")
    assert result.mime_type is None


def test_read_resource_mime_type_not_inferred_for_bytes_return():
    """Returning bytes should NOT trigger MIME type inference."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://bytes")
    def get_bytes() -> bytes:
        return b"binary"

    result = app.read_resource("data://bytes")
    assert result.mime_type is None


# ---------------------------------------------------------------------------
# Content normalization
# ---------------------------------------------------------------------------


def test_normalize_dict_to_json_string():
    """A dict return value should be serialized to a JSON string."""
    import json

    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://dict")
    def get_dict() -> dict:
        return {"name": "Alice", "age": 30}

    result = app.read_resource("data://dict")
    assert isinstance(result.content, str)
    assert json.loads(result.content) == {"name": "Alice", "age": 30}


def test_normalize_list_to_json_string():
    """A list return value should be serialized to a JSON string."""
    import json

    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://list")
    def get_list() -> list:
        return [1, 2, 3]

    result = app.read_resource("data://list")
    assert isinstance(result.content, str)
    assert json.loads(result.content) == [1, 2, 3]


def test_normalize_none_to_empty_string():
    """A None return value should produce an empty string."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://empty")
    def get_empty():
        return None

    result = app.read_resource("data://empty")
    assert result.content == ""
    assert isinstance(result.content, str)


def test_normalize_arbitrary_object_to_str():
    """An arbitrary object should be coerced to a string via str()."""
    app = BridgeMCP(name="test-app")

    class MyObj:
        def __str__(self) -> str:
            return "custom-str"

    @app.resource(uri="data://obj")
    def get_obj():
        return MyObj()

    result = app.read_resource("data://obj")
    assert result.content == "custom-str"
    assert isinstance(result.content, str)


def test_normalize_pydantic_model_to_json_string():
    """A Pydantic BaseModel return value should be serialized with model_dump_json()."""
    import json

    from pydantic import BaseModel

    class User(BaseModel):
        name: str
        age: int

    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://user")
    def get_user() -> User:
        return User(name="Alice", age=30)

    result = app.read_resource("data://user")
    assert isinstance(result.content, str)
    assert json.loads(result.content) == {"name": "Alice", "age": 30}


def test_normalize_non_serializable_dict_raises_resource_execution_error():
    """A dict with a non-JSON-serializable value should raise ResourceExecutionError."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://bad")
    def get_bad() -> dict:
        return {"value": object()}  # object() is not JSON-serializable

    with pytest.raises(ResourceExecutionError, match="could not be serialized"):
        app.read_resource("data://bad")


def test_normalization_serialization_error_preserves_cause():
    """ResourceExecutionError from serialization should chain the original error."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://bad")
    def get_bad() -> dict:
        return {"value": object()}

    with pytest.raises(ResourceExecutionError) as exc_info:
        app.read_resource("data://bad")

    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# ResourceNotFoundError
# ---------------------------------------------------------------------------


def test_read_resource_raises_for_unknown_uri():
    """read_resource() should raise ResourceNotFoundError for an unregistered URI."""
    app = BridgeMCP(name="test-app")

    with pytest.raises(ResourceNotFoundError):
        app.read_resource("data://nonexistent")


def test_read_resource_not_found_message_contains_uri():
    """The ResourceNotFoundError message should include the requested URI."""
    app = BridgeMCP(name="test-app")

    with pytest.raises(ResourceNotFoundError, match="data://nonexistent"):
        app.read_resource("data://nonexistent")


def test_read_resource_not_found_message_lists_available_uris():
    """The error message should list registered URIs to help the developer."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://real")
    def get_real() -> str:
        return ""

    with pytest.raises(ResourceNotFoundError, match="data://real"):
        app.read_resource("data://typo")


def test_read_resource_not_found_message_when_no_resources_registered():
    """The error message should note when no resources are registered at all."""
    app = BridgeMCP(name="test-app")

    with pytest.raises(ResourceNotFoundError, match="No resources are registered"):
        app.read_resource("data://anything")


# ---------------------------------------------------------------------------
# ResourceExecutionError — handler raises
# ---------------------------------------------------------------------------


def test_read_resource_wraps_exception_in_resource_execution_error():
    """If the handler raises, read_resource() should raise ResourceExecutionError."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://broken")
    def broken() -> str:
        raise RuntimeError("something failed")

    with pytest.raises(ResourceExecutionError):
        app.read_resource("data://broken")


def test_read_resource_execution_error_message_contains_uri():
    """ResourceExecutionError message should identify which resource failed."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://broken")
    def broken() -> str:
        raise RuntimeError("failure")

    with pytest.raises(ResourceExecutionError, match="data://broken"):
        app.read_resource("data://broken")


def test_read_resource_execution_error_preserves_original_exception():
    """The original exception should be accessible via __cause__."""
    app = BridgeMCP(name="test-app")

    original = ValueError("bad state")

    @app.resource(uri="data://broken")
    def broken() -> str:
        raise original

    with pytest.raises(ResourceExecutionError) as exc_info:
        app.read_resource("data://broken")

    assert exc_info.value.__cause__ is original


def test_read_resource_execution_error_preserves_original_message():
    """The original exception's message should appear in ResourceExecutionError."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://broken")
    def broken() -> str:
        raise RuntimeError("upstream service unavailable")

    with pytest.raises(ResourceExecutionError, match="upstream service unavailable"):
        app.read_resource("data://broken")


# ---------------------------------------------------------------------------
# Async resource rejection
# ---------------------------------------------------------------------------


def test_read_resource_raises_for_async_resource():
    """read_resource() should raise ResourceExecutionError for async handlers; use aread_resource()."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://async")
    async def get_async() -> str:
        return "async result"

    with pytest.raises(ResourceExecutionError, match="aread_resource"):
        app.read_resource("data://async")


# ---------------------------------------------------------------------------
# aread_resource — async execution
# ---------------------------------------------------------------------------


async def test_aread_resource_returns_content_from_sync_handler():
    """aread_resource() should work with synchronous handlers."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://sync")
    def get_data() -> str:
        return "hello"

    result = await app.aread_resource("data://sync")
    assert result.content == "hello"


async def test_aread_resource_returns_content_from_async_handler():
    """aread_resource() should work with asynchronous handlers."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://async")
    async def get_data() -> str:
        return "async hello"

    result = await app.aread_resource("data://async")
    assert result.content == "async hello"


async def test_aread_resource_echoes_uri():
    app = BridgeMCP(name="test-app")

    @app.resource(uri="config://settings")
    async def get_settings() -> str:
        return "{}"

    result = await app.aread_resource("config://settings")
    assert result.uri == "config://settings"


async def test_aread_resource_mime_type_passes_through():
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://json", mime_type="application/json")
    async def get_json() -> str:
        return '{"key": "value"}'

    result = await app.aread_resource("data://json")
    assert result.mime_type == "application/json"


async def test_aread_resource_raises_not_found():
    app = BridgeMCP(name="test-app")

    with pytest.raises(ResourceNotFoundError):
        await app.aread_resource("data://nonexistent")


async def test_aread_resource_wraps_exception_from_async_handler():
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://broken")
    async def broken() -> str:
        raise RuntimeError("async failure")

    with pytest.raises(ResourceExecutionError, match="async failure"):
        await app.aread_resource("data://broken")


async def test_aread_resource_preserves_cause_from_async_handler():
    app = BridgeMCP(name="test-app")
    original = ValueError("root cause")

    @app.resource(uri="data://broken")
    async def broken() -> str:
        raise original

    with pytest.raises(ResourceExecutionError) as exc_info:
        await app.aread_resource("data://broken")

    assert exc_info.value.__cause__ is original
