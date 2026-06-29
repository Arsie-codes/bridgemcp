"""
BridgeMCP exception hierarchy.

All framework-specific exceptions inherit from BridgeMCPError so developers
can catch either the specific subclass or every BridgeMCP error at once.

Usage::

    from bridgemcp.exceptions import BridgeMCPError, ToolRegistrationError

    try:
        app.some_operation()
    except ToolRegistrationError as exc:
        print(f"Tool setup failed: {exc}")
    except BridgeMCPError as exc:
        print(f"Unexpected framework error: {exc}")
"""


class BridgeMCPError(Exception):
    """
    Base class for all BridgeMCP exceptions.

    Catch this to handle any error raised by the framework in one place.
    Catch a subclass to handle a specific category of error.
    """


class RegistrationError(BridgeMCPError):
    """
    Raised when any item (tool, resource, or prompt) cannot be registered.

    This is the common base class for all registration errors. Catch this
    to handle any startup-time registration conflict without needing to
    enumerate each specific subclass.

    Catch a subclass (e.g. ``ToolRegistrationError``) to handle a specific
    category of registration error.
    """


class ToolRegistrationError(RegistrationError):
    """
    Raised when a tool cannot be registered.

    This exception is raised at startup time — when the ``@app.tool``
    decorator runs — so problems are caught before the server starts
    rather than during a live request.

    Common causes:
      - Two tools registered with the same name.
      - A tool name that is empty or otherwise invalid.
    """


class ResourceRegistrationError(RegistrationError):
    """
    Raised when a resource cannot be registered.

    This exception is raised at startup time — when the ``@app.resource``
    decorator runs — so problems are caught before the server starts
    rather than during a live request.

    Common causes:
      - Two resources registered with the same URI.
      - A resource URI that is empty or whitespace-only.
    """


class PromptRegistrationError(RegistrationError):
    """
    Raised when a prompt cannot be registered.

    This exception is raised at startup time — when the ``@app.prompt``
    decorator runs — so problems are caught before the server starts
    rather than during a live request.

    Common causes:
      - Two prompts registered with the same name.
      - A prompt name that is empty or whitespace-only.
    """


class NotFoundError(BridgeMCPError):
    """
    Raised when a requested item (tool, resource, or prompt) does not exist.

    This is the common base class for all not-found errors. Catch this
    to handle any lookup failure without needing to enumerate each
    specific subclass.
    """


class ToolNotFoundError(NotFoundError):
    """
    Raised when a requested tool does not exist in the registry.

    This exception is raised when the framework is asked to look up
    a tool by name and no matching registration is found.

    Common causes:
      - A typo in the tool name.
      - Requesting a tool that was never registered.
    """


class ResourceNotFoundError(NotFoundError):
    """
    Raised when a requested resource does not exist in the registry.

    This exception is raised when the framework is asked to read a
    resource by URI and no matching registration is found.

    Common causes:
      - A typo in the URI.
      - Requesting a resource that was never registered.
    """


class PromptNotFoundError(NotFoundError):
    """
    Raised when a requested prompt does not exist in the registry.

    This exception is raised when the framework is asked to render a
    prompt by name and no matching registration is found.

    Common causes:
      - A typo in the prompt name.
      - Requesting a prompt that was never registered.
    """


class ConfigurationError(BridgeMCPError):
    """
    Raised when the framework detects an invalid or inconsistent configuration.

    This exception covers configuration problems that BridgeMCP itself
    detects — for example, conflicting settings or a missing required value
    that cannot be validated by Pydantic alone.

    For field-level validation errors (wrong type, out-of-range value),
    Pydantic raises its own ``ValidationError`` directly.
    """


class ExecutionError(BridgeMCPError):
    """
    Raised when a registered handler (tool, resource, or prompt) fails at runtime.

    This is the common base class for all execution errors. Catch this
    to handle any runtime handler failure without needing to enumerate
    each specific subclass.

    The original exception is always available via the ``__cause__`` attribute
    so the full error context is never lost.
    """


class ToolExecutionError(ExecutionError):
    """
    Raised when a registered tool's handler function raises an exception.

    The original exception is always available via the ``__cause__`` attribute
    so the full error context is never lost.

    Example::

        try:
            result = app.call("get_orders", customer_id="123")
        except ToolExecutionError as exc:
            print(f"Tool failed: {exc}")
            print(f"Caused by: {exc.__cause__}")
    """


class ResourceExecutionError(ExecutionError):
    """
    Raised when a registered resource's handler function fails at runtime.

    This covers two cases: the handler function raised an exception, or
    its return value could not be serialized into resource content.

    The original exception is always available via the ``__cause__`` attribute.

    Example::

        try:
            content = app.read_resource("config://app/settings")
        except ResourceExecutionError as exc:
            print(f"Resource failed: {exc}")
            print(f"Caused by: {exc.__cause__}")
    """


class PromptExecutionError(ExecutionError):
    """
    Raised when a registered prompt's handler function fails at runtime.

    This covers two cases: the handler function raised an exception, or
    its return value could not be normalized into ``list[PromptMessage]``.

    The original exception is always available via the ``__cause__`` attribute.

    Example::

        try:
            messages = app.render_prompt("code_review", language="python", code="...")
        except PromptExecutionError as exc:
            print(f"Prompt failed: {exc}")
            print(f"Caused by: {exc.__cause__}")
    """
