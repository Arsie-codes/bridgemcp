"""
Tests for the resource registration system.

Covers ResourceRegistry in isolation and the @app.resource decorator on BridgeMCP.
"""

from __future__ import annotations

import pytest

from bridgemcp import BridgeMCP
from bridgemcp.exceptions import ResourceRegistrationError
from bridgemcp.resources.registry import Resource, ResourceRegistry

# ---------------------------------------------------------------------------
# Helpers — plain functions used as test fixtures
# ---------------------------------------------------------------------------


def simple_resource() -> str:
    """Return some data."""
    return "data"


def no_docstring() -> str:
    return "data"


async def async_resource() -> str:
    """Fetch data asynchronously."""
    return "async data"


# ---------------------------------------------------------------------------
# Resource — data class
# ---------------------------------------------------------------------------


def test_resource_is_immutable():
    """Resource instances should not allow field mutation after creation."""
    registry = ResourceRegistry()
    resource = registry.register(simple_resource, uri="data://simple")

    with pytest.raises((AttributeError, TypeError)):
        resource.uri = "data://other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ResourceRegistry — URI validation
# ---------------------------------------------------------------------------


def test_register_rejects_empty_uri():
    """An empty URI string should raise ResourceRegistrationError."""
    registry = ResourceRegistry()

    with pytest.raises(ResourceRegistrationError, match="non-empty string"):
        registry.register(simple_resource, uri="")


def test_register_rejects_whitespace_only_uri():
    """A URI containing only whitespace should raise ResourceRegistrationError."""
    registry = ResourceRegistry()

    with pytest.raises(ResourceRegistrationError, match="non-empty string"):
        registry.register(simple_resource, uri="   ")


def test_register_strips_uri_whitespace():
    """Leading and trailing whitespace in the URI should be stripped silently."""
    registry = ResourceRegistry()
    resource = registry.register(simple_resource, uri="  data://simple  ")

    assert resource.uri == "data://simple"


def test_stripped_uri_is_used_as_registry_key():
    """The stripped URI should be the key used for deduplication and lookup."""
    registry = ResourceRegistry()
    registry.register(simple_resource, uri="  data://simple  ")

    result = registry.get("data://simple")
    assert result is not None
    assert result.uri == "data://simple"


# ---------------------------------------------------------------------------
# ResourceRegistry — registration
# ---------------------------------------------------------------------------


def test_register_returns_resource():
    """register() should return a Resource instance."""
    registry = ResourceRegistry()
    result = registry.register(simple_resource, uri="data://test")

    assert isinstance(result, Resource)


def test_register_stores_uri():
    """The URI passed to register() should be stored on the Resource."""
    registry = ResourceRegistry()
    resource = registry.register(simple_resource, uri="config://app/settings")

    assert resource.uri == "config://app/settings"


def test_register_defaults_name_to_function_name():
    """Resource name should default to the function's __name__."""
    registry = ResourceRegistry()
    resource = registry.register(simple_resource, uri="data://test")

    assert resource.name == "simple_resource"


def test_register_accepts_explicit_name():
    """An explicit name should override the function name."""
    registry = ResourceRegistry()
    resource = registry.register(simple_resource, uri="data://test", name="My Data")

    assert resource.name == "My Data"


def test_register_captures_docstring_as_description():
    """The function docstring should be used as the description."""
    registry = ResourceRegistry()
    resource = registry.register(simple_resource, uri="data://test")

    assert resource.description == "Return some data."


def test_register_accepts_explicit_description():
    """An explicit description should override the docstring."""
    registry = ResourceRegistry()
    resource = registry.register(
        simple_resource, uri="data://test", description="Custom description."
    )

    assert resource.description == "Custom description."


def test_register_description_is_none_when_no_docstring():
    """Description should be None when the function has no docstring."""
    registry = ResourceRegistry()
    resource = registry.register(no_docstring, uri="data://test")

    assert resource.description is None


def test_register_mime_type_defaults_to_none():
    """mime_type should be None when not explicitly provided."""
    registry = ResourceRegistry()
    resource = registry.register(simple_resource, uri="data://test")

    assert resource.mime_type is None


def test_register_accepts_explicit_mime_type():
    """An explicit mime_type should be stored on the Resource."""
    registry = ResourceRegistry()
    resource = registry.register(
        simple_resource, uri="data://test", mime_type="application/json"
    )

    assert resource.mime_type == "application/json"


def test_register_stores_callable():
    """The original function should be stored on the Resource."""
    registry = ResourceRegistry()
    resource = registry.register(simple_resource, uri="data://test")

    assert resource.fn is simple_resource


def test_register_sync_function_is_not_async():
    """A regular function should have is_async=False."""
    registry = ResourceRegistry()
    resource = registry.register(simple_resource, uri="data://test")

    assert resource.is_async is False


def test_register_async_function_is_async():
    """An async function should have is_async=True."""
    registry = ResourceRegistry()
    resource = registry.register(async_resource, uri="data://async")

    assert resource.is_async is True


def test_register_duplicate_uri_raises():
    """Registering two resources with the same URI should raise ResourceRegistrationError."""
    registry = ResourceRegistry()
    registry.register(simple_resource, uri="data://test")

    with pytest.raises(ResourceRegistrationError, match="already registered"):
        registry.register(no_docstring, uri="data://test")


def test_register_duplicate_uri_after_strip_raises():
    """A duplicate URI that matches only after stripping should still be rejected."""
    registry = ResourceRegistry()
    registry.register(simple_resource, uri="data://test")

    with pytest.raises(ResourceRegistrationError, match="already registered"):
        registry.register(no_docstring, uri="  data://test  ")


# ---------------------------------------------------------------------------
# ResourceRegistry — retrieval
# ---------------------------------------------------------------------------


def test_get_returns_registered_resource():
    """get() should return the Resource for a known URI."""
    registry = ResourceRegistry()
    registry.register(simple_resource, uri="data://test")

    resource = registry.get("data://test")
    assert resource is not None
    assert resource.uri == "data://test"


def test_get_returns_none_for_unknown_uri():
    """get() should return None for a URI that has not been registered."""
    registry = ResourceRegistry()

    assert registry.get("data://nonexistent") is None


def test_list_returns_all_resources():
    """list() should return all registered resources."""
    registry = ResourceRegistry()
    registry.register(simple_resource, uri="data://one")
    registry.register(no_docstring, uri="data://two")

    uris = [r.uri for r in registry.list()]
    assert "data://one" in uris
    assert "data://two" in uris


def test_list_returns_empty_for_new_registry():
    """list() on a fresh registry should return an empty list."""
    registry = ResourceRegistry()

    assert registry.list() == []


def test_list_preserves_registration_order():
    """list() should return resources in the order they were registered."""
    registry = ResourceRegistry()
    registry.register(simple_resource, uri="data://first")
    registry.register(no_docstring, uri="data://second")

    uris = [r.uri for r in registry.list()]
    assert uris == ["data://first", "data://second"]


def test_len_reflects_registration_count():
    """len() should return the number of registered resources."""
    registry = ResourceRegistry()
    assert len(registry) == 0

    registry.register(simple_resource, uri="data://one")
    assert len(registry) == 1

    registry.register(no_docstring, uri="data://two")
    assert len(registry) == 2


# ---------------------------------------------------------------------------
# @app.resource — decorator
# ---------------------------------------------------------------------------


def test_decorator_registers_resource():
    """@app.resource(uri=...) should register the function."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="config://settings")
    def get_settings() -> str:
        return "{}"

    resource = app._resource_registry.get("config://settings")
    assert resource is not None


def test_decorator_returns_original_function():
    """@app.resource should return the original function unchanged."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="config://settings")
    def get_settings() -> str:
        return "{}"

    assert get_settings() == "{}"


def test_decorator_uses_function_name_as_default_name():
    """@app.resource should default the resource name to the function name."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="config://settings")
    def get_settings() -> str:
        return "{}"

    resource = app._resource_registry.get("config://settings")
    assert resource is not None
    assert resource.name == "get_settings"


def test_decorator_with_explicit_name():
    """@app.resource(name=...) should override the function name."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="config://settings", name="App Settings")
    def get_settings() -> str:
        return "{}"

    resource = app._resource_registry.get("config://settings")
    assert resource is not None
    assert resource.name == "App Settings"


def test_decorator_with_explicit_description():
    """@app.resource(description=...) should override the docstring."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="config://settings", description="Custom description.")
    def get_settings() -> str:
        """This docstring should be ignored."""
        return "{}"

    resource = app._resource_registry.get("config://settings")
    assert resource is not None
    assert resource.description == "Custom description."


def test_decorator_with_explicit_mime_type():
    """@app.resource(mime_type=...) should be stored on the Resource."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="users://list", mime_type="application/json")
    def list_users() -> str:
        return "[]"

    resource = app._resource_registry.get("users://list")
    assert resource is not None
    assert resource.mime_type == "application/json"


def test_decorator_requires_uri():
    """Calling @app.resource without uri should raise TypeError."""
    app = BridgeMCP(name="test-app")

    with pytest.raises(TypeError):

        @app.resource()  # type: ignore[call-arg]
        def get_data() -> str:
            return ""


def test_resource_registries_are_independent_across_instances():
    """Two BridgeMCP instances should have separate resource registries."""
    app_one = BridgeMCP(name="app-one")
    app_two = BridgeMCP(name="app-two")

    @app_one.resource(uri="data://shared-uri")
    def get_data() -> str:
        return ""

    assert app_one._resource_registry.get("data://shared-uri") is not None
    assert app_two._resource_registry.get("data://shared-uri") is None


# ---------------------------------------------------------------------------
# list_resources() — public introspection
# ---------------------------------------------------------------------------


def test_list_resources_returns_resource_objects():
    """list_resources() should return Resource instances, not strings."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://test")
    def get_data() -> str:
        return ""

    resources = app.list_resources()
    assert len(resources) == 1
    assert isinstance(resources[0], Resource)


def test_list_resources_returns_all_registered():
    """list_resources() should return all registered resources."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://one")
    def one() -> str:
        return ""

    @app.resource(uri="data://two")
    def two() -> str:
        return ""

    uris = [r.uri for r in app.list_resources()]
    assert "data://one" in uris
    assert "data://two" in uris


def test_list_resources_empty_when_none_registered():
    """list_resources() should return an empty list when no resources are registered."""
    app = BridgeMCP(name="test-app")

    assert app.list_resources() == []


def test_list_resources_preserves_registration_order():
    """list_resources() should return resources in registration order."""
    app = BridgeMCP(name="test-app")

    @app.resource(uri="data://first")
    def first() -> str:
        return ""

    @app.resource(uri="data://second")
    def second() -> str:
        return ""

    uris = [r.uri for r in app.list_resources()]
    assert uris == ["data://first", "data://second"]


def test_list_resources_returns_full_metadata():
    """list_resources() Resource objects should carry complete metadata."""
    app = BridgeMCP(name="test-app")

    @app.resource(
        uri="users://list",
        name="User List",
        description="All users.",
        mime_type="application/json",
    )
    def list_users() -> str:
        return "[]"

    resource = app.list_resources()[0]
    assert resource.uri == "users://list"
    assert resource.name == "User List"
    assert resource.description == "All users."
    assert resource.mime_type == "application/json"
    assert resource.fn is list_users


def test_tools_and_resources_registries_are_independent():
    """Registering a resource should not affect the tool registry, and vice versa."""
    app = BridgeMCP(name="test-app")

    @app.tool
    def ping() -> str:
        return "pong"

    @app.resource(uri="data://test")
    def get_data() -> str:
        return ""

    assert [t.name for t in app.list_tools()] == ["ping"]
    assert len(app.list_resources()) == 1
    assert app.list_resources()[0].uri == "data://test"
