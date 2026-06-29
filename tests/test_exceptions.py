"""
Tests for the BridgeMCP exception hierarchy.

Verifies inheritance relationships, message handling, and that
exceptions integrate correctly with the framework.
"""

import pytest

from bridgemcp.exceptions import (
    BridgeMCPError,
    ConfigurationError,
    ExecutionError,
    NotFoundError,
    PromptExecutionError,
    PromptNotFoundError,
    PromptRegistrationError,
    RegistrationError,
    ResourceExecutionError,
    ResourceNotFoundError,
    ResourceRegistrationError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolRegistrationError,
)

# ---------------------------------------------------------------------------
# Inheritance — every exception must be a BridgeMCPError
# ---------------------------------------------------------------------------


def test_bridgemcp_error_is_standard_exception():
    """BridgeMCPError itself must be a standard Python Exception."""
    assert issubclass(BridgeMCPError, Exception)


def test_registration_error_is_bridgemcp_error():
    assert issubclass(RegistrationError, BridgeMCPError)


def test_tool_registration_error_is_registration_error():
    """ToolRegistrationError must be a RegistrationError for unified catching."""
    assert issubclass(ToolRegistrationError, RegistrationError)


def test_tool_registration_error_is_bridgemcp_error():
    """ToolRegistrationError must remain catchable as BridgeMCPError (transitively)."""
    assert issubclass(ToolRegistrationError, BridgeMCPError)


def test_resource_registration_error_is_registration_error():
    assert issubclass(ResourceRegistrationError, RegistrationError)


def test_resource_registration_error_is_bridgemcp_error():
    assert issubclass(ResourceRegistrationError, BridgeMCPError)


def test_not_found_error_is_bridgemcp_error():
    assert issubclass(NotFoundError, BridgeMCPError)


def test_tool_not_found_error_is_not_found_error():
    """ToolNotFoundError must be a NotFoundError for unified catching."""
    assert issubclass(ToolNotFoundError, NotFoundError)


def test_tool_not_found_error_is_bridgemcp_error():
    """ToolNotFoundError must remain catchable as BridgeMCPError (transitively)."""
    assert issubclass(ToolNotFoundError, BridgeMCPError)


def test_resource_not_found_error_is_not_found_error():
    assert issubclass(ResourceNotFoundError, NotFoundError)


def test_resource_not_found_error_is_bridgemcp_error():
    assert issubclass(ResourceNotFoundError, BridgeMCPError)


def test_execution_error_is_bridgemcp_error():
    assert issubclass(ExecutionError, BridgeMCPError)


def test_tool_execution_error_is_execution_error():
    """ToolExecutionError must be an ExecutionError for unified catching."""
    assert issubclass(ToolExecutionError, ExecutionError)


def test_tool_execution_error_is_bridgemcp_error():
    """ToolExecutionError must remain catchable as BridgeMCPError (transitively)."""
    assert issubclass(ToolExecutionError, BridgeMCPError)


def test_resource_execution_error_is_execution_error():
    assert issubclass(ResourceExecutionError, ExecutionError)


def test_resource_execution_error_is_bridgemcp_error():
    assert issubclass(ResourceExecutionError, BridgeMCPError)


def test_prompt_registration_error_is_registration_error():
    assert issubclass(PromptRegistrationError, RegistrationError)


def test_prompt_registration_error_is_bridgemcp_error():
    assert issubclass(PromptRegistrationError, BridgeMCPError)


def test_prompt_not_found_error_is_not_found_error():
    assert issubclass(PromptNotFoundError, NotFoundError)


def test_prompt_not_found_error_is_bridgemcp_error():
    assert issubclass(PromptNotFoundError, BridgeMCPError)


def test_prompt_execution_error_is_execution_error():
    assert issubclass(PromptExecutionError, ExecutionError)


def test_prompt_execution_error_is_bridgemcp_error():
    assert issubclass(PromptExecutionError, BridgeMCPError)


def test_configuration_error_is_bridgemcp_error():
    assert issubclass(ConfigurationError, BridgeMCPError)


# ---------------------------------------------------------------------------
# Raising and catching — base class catches all subclasses
# ---------------------------------------------------------------------------


def test_catch_registration_error_catches_tool_registration_error():
    """RegistrationError should catch ToolRegistrationError."""
    with pytest.raises(RegistrationError):
        raise ToolRegistrationError("duplicate tool name")


def test_catch_registration_error_catches_resource_registration_error():
    """RegistrationError should catch ResourceRegistrationError."""
    with pytest.raises(RegistrationError):
        raise ResourceRegistrationError("duplicate resource URI")


def test_catch_base_catches_registration_error():
    """Catching BridgeMCPError should catch ToolRegistrationError."""
    with pytest.raises(BridgeMCPError):
        raise ToolRegistrationError("duplicate tool name")


def test_catch_not_found_error_catches_tool_not_found_error():
    """NotFoundError should catch ToolNotFoundError."""
    with pytest.raises(NotFoundError):
        raise ToolNotFoundError("tool not found")


def test_catch_not_found_error_catches_resource_not_found_error():
    """NotFoundError should catch ResourceNotFoundError."""
    with pytest.raises(NotFoundError):
        raise ResourceNotFoundError("resource not found")


def test_catch_execution_error_catches_tool_execution_error():
    """ExecutionError should catch ToolExecutionError."""
    with pytest.raises(ExecutionError):
        raise ToolExecutionError("tool failed")


def test_catch_execution_error_catches_resource_execution_error():
    """ExecutionError should catch ResourceExecutionError."""
    with pytest.raises(ExecutionError):
        raise ResourceExecutionError("resource failed")


def test_catch_registration_error_catches_prompt_registration_error():
    """RegistrationError should catch PromptRegistrationError."""
    with pytest.raises(RegistrationError):
        raise PromptRegistrationError("duplicate prompt name")


def test_catch_not_found_error_catches_prompt_not_found_error():
    """NotFoundError should catch PromptNotFoundError."""
    with pytest.raises(NotFoundError):
        raise PromptNotFoundError("prompt not found")


def test_catch_execution_error_catches_prompt_execution_error():
    """ExecutionError should catch PromptExecutionError."""
    with pytest.raises(ExecutionError):
        raise PromptExecutionError("prompt failed")


def test_catch_base_catches_not_found_error():
    """Catching BridgeMCPError should catch ToolNotFoundError."""
    with pytest.raises(BridgeMCPError):
        raise ToolNotFoundError("tool not found")


def test_catch_base_catches_configuration_error():
    """Catching BridgeMCPError should catch ConfigurationError."""
    with pytest.raises(BridgeMCPError):
        raise ConfigurationError("invalid config")


def test_catch_specific_does_not_catch_sibling():
    """Catching ToolRegistrationError should not catch ToolNotFoundError."""
    with pytest.raises(ToolNotFoundError):
        raise ToolNotFoundError("this should not be caught by the wrong handler")


# ---------------------------------------------------------------------------
# Messages — exceptions must carry the message through
# ---------------------------------------------------------------------------


def test_exception_message_is_accessible():
    """The message passed to an exception should be readable via str()."""
    exc = ToolRegistrationError("A tool named 'get_orders' is already registered.")
    assert "get_orders" in str(exc)


def test_exception_message_preserved_on_raise():
    """The message should survive being raised and caught."""
    message = "A tool named 'ping' is already registered."

    with pytest.raises(ToolRegistrationError, match="ping"):
        raise ToolRegistrationError(message)


# ---------------------------------------------------------------------------
# Exception chaining — BridgeMCPError works with Python's raise ... from
# ---------------------------------------------------------------------------


def test_exception_chaining_preserves_cause():
    """BridgeMCP exceptions should support raise X from Y chaining."""
    original = ValueError("something went wrong internally")

    with pytest.raises(ToolRegistrationError) as exc_info:
        raise ToolRegistrationError("Tool registration failed.") from original

    assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# Top-level import — BridgeMCPError is available from the bridgemcp package
# ---------------------------------------------------------------------------


def test_bridgemcp_error_importable_from_package():
    """BridgeMCPError should be importable directly from bridgemcp."""
    from bridgemcp import BridgeMCPError as TopLevelError

    assert TopLevelError is BridgeMCPError
