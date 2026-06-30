"""MCP adapter: bridges a BridgeMCP application to a FastMCP server.

Public entry points
-------------------
run_stdio(app)
    Build and run the server on stdio transport.  Called by BridgeMCP.run().

run_http(app, *, host, port)
    Build and run the server on HTTP/SSE transport.  Called by
    BridgeMCP.run_http().

build_mcp_server(app, *, host, port)
    Build and return the configured FastMCP instance without starting it.
    Useful for tests, introspection, and hosting the server inside a larger
    ASGI application.

All transport knowledge (which SDK to import, which transport string to pass,
which SDK-specific run method to call) lives exclusively in this module.
BridgeMCP core (application.py) delegates here and never touches the server
object itself.

Lifecycle
---------
Plugin startup and shutdown hooks are managed entirely within this module.
BridgeMCP.application stores ``_startup_hooks`` and ``_shutdown_hooks`` lists;
the adapter is responsible for invoking them at the correct points.

Startup hooks run in registration order before the server accepts requests.
A startup exception propagates immediately — the server does not start and
no shutdown hooks run.

Shutdown hooks run in reverse registration order after the server stops.
Each hook is individually guarded: an exception is logged but does not
prevent the remaining hooks from running.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from bridgemcp.application import BridgeMCP
    from bridgemcp.prompts.registry import Prompt
    from bridgemcp.resources.registry import Resource
    from bridgemcp.tools.registry import Tool

_logger = logging.getLogger(__name__)


async def _invoke_startup_hooks(app: BridgeMCP) -> None:
    """Invoke startup hooks in registration order.

    Raises the first exception encountered, aborting subsequent hooks.
    The server will not start if this coroutine raises.
    """
    for hook in app._startup_hooks:  # type: ignore[reportPrivateUsage]
        await hook(app)


async def _invoke_shutdown_hooks(app: BridgeMCP) -> None:
    """Invoke shutdown hooks in reverse registration order.

    Each hook is individually guarded.  An exception is logged at ERROR
    level but does not prevent the remaining hooks from running.
    """
    for hook in reversed(app._shutdown_hooks):  # type: ignore[reportPrivateUsage]
        try:
            await hook(app)
        except Exception:
            _logger.exception("Shutdown hook %r raised an exception", hook)


def _with_lifecycle(app: BridgeMCP, run_fn: Callable[[], None]) -> None:
    """Wrap *run_fn* with plugin startup and shutdown lifecycle hooks.

    Startup hooks execute synchronously (via ``asyncio.run``) before
    *run_fn* is called.  If any startup hook raises, *run_fn* is not
    called and no shutdown hooks run — the caller receives the exception.

    Shutdown hooks execute synchronously (via ``asyncio.run``) after
    *run_fn* returns, whether it returned normally or raised.  Shutdown
    hook exceptions are logged; all hooks run regardless of individual
    failures.

    Args:
        app: BridgeMCP application whose hook lists to invoke.
        run_fn: Zero-argument callable that starts the server transport.
            Typically ``lambda: server.run(transport=...)``.
    """
    if app._startup_hooks:  # type: ignore[reportPrivateUsage]
        asyncio.run(_invoke_startup_hooks(app))
    try:
        run_fn()
    finally:
        if app._shutdown_hooks:  # type: ignore[reportPrivateUsage]
            asyncio.run(_invoke_shutdown_hooks(app))


def run_stdio(app: BridgeMCP) -> None:
    """Build the MCP server and run it on stdio transport.

    Plugin startup hooks execute before the server begins accepting requests.
    Plugin shutdown hooks execute in reverse registration order after the
    server stops.

    This is the standard transport for AI clients such as Claude Desktop
    and Cursor that launch the server as a subprocess.

    Requires: ``pip install 'bridgemcp[mcp]'``
    """
    server = build_mcp_server(app)
    _with_lifecycle(app, lambda: server.run(transport="stdio"))


def run_http(app: BridgeMCP, *, host: str, port: int) -> None:
    """Build the MCP server and run it on HTTP/SSE transport.

    Plugin startup hooks execute before the server begins accepting requests.
    Plugin shutdown hooks execute in reverse registration order after the
    server stops.

    Use this when AI clients should connect over the network rather than
    via a subprocess.

    Requires: ``pip install 'bridgemcp[mcp]'``
    """
    server = build_mcp_server(app, host=host, port=port)
    _with_lifecycle(app, lambda: server.run(transport="sse"))


def build_mcp_server(
    app: BridgeMCP,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> FastMCP:
    """Build a FastMCP server from a BridgeMCP application.

    All registered tools, resources, and prompts are wrapped so that execution
    goes through ``app.call()``, ``app.read_resource()``, and
    ``app.render_prompt()`` respectively, keeping BridgeMCP's error handling
    and exception hierarchy intact.

    Args:
        app: The BridgeMCP application to expose as an MCP server.
        host: Host to bind to for HTTP/SSE transports. Defaults to "127.0.0.1".
        port: Port to listen on for HTTP/SSE transports. Defaults to 8000.

    Returns:
        A configured FastMCP server instance ready to run.

    Raises:
        ImportError: If ``mcp`` is not installed.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "The MCP SDK is required to run a BridgeMCP server. "
            "Install it with: pip install 'bridgemcp[mcp]'"
        ) from None

    server = FastMCP(
        name=app.name,
        instructions=app.description,
        host=host,
        port=port,
    )

    # FastMCP does not expose a public `version` constructor parameter.
    # The low-level Server it wraps does, and falls back to the MCP SDK's own
    # package version when left unset.  Until FastMCP adds first-class version
    # support, set it via the internal attribute so clients see the user's
    # declared version string.  When FastMCP adds a public API for this (e.g.
    # a `version=` parameter on FastMCP()), pass app.version there and remove
    # this line.
    server._mcp_server.version = app.version  # type: ignore[reportPrivateUsage]

    _register_tools(server, app)
    _register_resources(server, app)
    _register_prompts(server, app)

    return server


def _register_tools(server: Any, app: Any) -> None:
    """Register all tools from the app with the FastMCP server."""
    for tool in app._tool_registry.list():
        _register_tool(server, app, tool)


def _register_resources(server: Any, app: Any) -> None:
    """Register all resources from the app with the FastMCP server."""
    for resource in app._resource_registry.list():
        _register_resource(server, app, resource)


def _register_prompts(server: Any, app: Any) -> None:
    """Register all prompts from the app with the FastMCP server."""
    for prompt in app._prompt_registry.list():
        _register_prompt(server, app, prompt)


def _register_tool(server: Any, app: Any, tool: Tool) -> None:
    """Wrap one BridgeMCP tool and register it with the FastMCP server.

    ``functools.wraps`` copies ``__wrapped__``, ``__annotations__``, and
    ``__doc__`` from the original function. FastMCP's ``func_metadata``
    calls ``inspect.signature(fn, eval_str=True)`` which follows
    ``__wrapped__``, so the wrapper inherits the original's full parameter
    list and type annotations for schema generation.

    Execution is always delegated to ``app.acall()`` so that BridgeMCP's
    ``ToolExecutionError`` wrapping and registry lookup are used.  The wrapper
    is async so FastMCP awaits it for both sync and async tool handlers.
    """
    tool_name = tool.name
    original_fn = tool.fn

    @functools.wraps(original_fn)
    async def wrapper(**kwargs: Any) -> Any:
        return await app.acall(tool_name, **kwargs)

    # functools.wraps copies __name__ from original_fn, but the registered
    # name may differ (e.g. @app.tool(name="list_orders")). Override to match.
    wrapper.__name__ = tool_name

    server.add_tool(
        wrapper,
        name=tool_name,
        description=tool.description,
    )


def _register_resource(server: Any, app: Any, resource: Resource) -> None:
    """Wrap one BridgeMCP resource and register it with the FastMCP server.

    The handler is a zero-argument closure — intentionally not wrapped with
    ``functools.wraps``. FastMCP classifies a resource as a URI template when
    ``inspect.signature(fn)`` reveals parameters; wrapping would cause
    ``__wrapped__`` to propagate the original function's signature, incorrectly
    marking a static resource as a template.

    Execution is always delegated to ``app.aread_resource()`` so that BridgeMCP's
    content normalization and error handling remain active.  The handler is async
    so FastMCP awaits it for both sync and async resource handlers.

    Note: when ``mime_type`` is ``None``, FastMCP's ``FunctionResource``
    defaults to ``"text/plain"`` in the ``resources/list`` response. This is
    FastMCP's own default and is not controlled by BridgeMCP.
    """
    uri = resource.uri

    async def handler() -> str | bytes:
        return (await app.aread_resource(uri)).content

    handler.__name__ = resource.name

    server.resource(
        uri=uri,
        name=resource.name,
        description=resource.description,
        mime_type=resource.mime_type,
    )(handler)


def _register_prompt(server: Any, app: Any, prompt: Prompt) -> None:
    """Wrap one BridgeMCP prompt and register it with the FastMCP server.

    ``functools.wraps`` copies ``__wrapped__``, ``__annotations__``, and
    ``__doc__`` from the original function. FastMCP's ``func_metadata``
    calls ``inspect.signature(fn, eval_str=True)`` which follows
    ``__wrapped__``, so the wrapper inherits the original's full parameter
    list and type annotations for argument schema generation.

    Each BridgeMCP ``PromptMessage(role, content: str)`` is converted to a
    dict that FastMCP's message validator accepts.  All MCP SDK type knowledge
    stays in this module; BridgeMCP core is unaware of the wire format.

    Execution is always delegated to ``app.arender_prompt()`` so that
    BridgeMCP's normalization and error handling remain active.  The wrapper
    is async so FastMCP awaits it for both sync and async prompt handlers.
    """
    prompt_name = prompt.name
    original_fn = prompt.fn

    @functools.wraps(original_fn)
    async def handler(**kwargs: Any) -> list[dict[str, Any]]:
        messages = await app.arender_prompt(prompt_name, **kwargs)
        return [
            {"role": msg.role, "content": {"type": "text", "text": msg.content}}
            for msg in messages
        ]

    handler.__name__ = prompt_name

    server.prompt(name=prompt_name, description=prompt.description)(handler)
