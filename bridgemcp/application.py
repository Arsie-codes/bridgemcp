"""
Core application class for BridgeMCP.

This module defines the BridgeMCP class, which is the single entry point
for building an MCP server. Developers create one instance of this class
and use it to register tools, resources, and prompts.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, overload

from bridgemcp.config import BridgeConfig
from bridgemcp.exceptions import (
    PromptExecutionError,
    PromptNotFoundError,
    ResourceExecutionError,
    ResourceNotFoundError,
    ToolExecutionError,
    ToolNotFoundError,
)
from bridgemcp.execution import invoke_async, invoke_sync
from bridgemcp.middleware import InvocationContext, MiddlewareFn, Next, build_chain
from bridgemcp.prompts.normalize import normalize_messages
from bridgemcp.prompts.registry import Prompt, PromptMessage, PromptRegistry
from bridgemcp.resources.normalize import normalize_content
from bridgemcp.resources.registry import Resource, ResourceContent, ResourceRegistry
from bridgemcp.tools.registry import Tool, ToolRegistry


class BridgeMCP:
    """
    The BridgeMCP application.

    Create one instance of this class to define your MCP server.
    Register tools using the ``@app.tool`` decorator.

    Example::

        from bridgemcp import BridgeMCP

        app = BridgeMCP(name="my-app")

        @app.tool
        def get_orders(customer_id: str) -> list:
            return order_service.get(customer_id)
    """

    def __init__(
        self,
        name: str,
        version: str = "0.1.0",
        description: str | None = None,
        config: BridgeConfig | None = None,
    ) -> None:
        """
        Create a new BridgeMCP application.

        Args:
            name: The name of your MCP server. Shown to AI clients
                  during the connection handshake.
            version: The version of your MCP server. Defaults to "0.1.0".
            description: An optional description of what your server does.
            config: An optional BridgeConfig instance. If not provided,
                    default configuration is used.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "BridgeMCP requires a non-empty string for 'name'. " f"Got: {name!r}"
            )

        if not isinstance(version, str) or not version.strip():
            raise ValueError(
                "BridgeMCP requires a non-empty string for 'version'. "
                f"Got: {version!r}"
            )

        self.name = name.strip()
        self.version = version.strip()
        self.description = description
        self.config = config if config is not None else BridgeConfig()

        self._tool_registry = ToolRegistry()
        self._resource_registry = ResourceRegistry()
        self._prompt_registry = PromptRegistry()
        self._middleware: list[MiddlewareFn] = []
        self._plugins: list[Any] = []
        self._startup_hooks: list[Any] = []
        self._shutdown_hooks: list[Any] = []

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    @overload
    def tool(self, fn: Callable[..., Any]) -> Callable[..., Any]: ...

    @overload
    def tool(
        self,
        fn: None = None,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

    def tool(
        self,
        fn: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Any:
        """
        Register a function as an MCP tool.

        Can be used as a bare decorator or with keyword arguments::

            @app.tool
            def get_orders(customer_id: str) -> list:
                ...

            @app.tool(name="list_orders", description="List all orders")
            def get_orders(customer_id: str) -> list:
                ...

        The decorated function is returned unchanged so it can still be
        called directly in tests without going through the framework.
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._tool_registry.register(func, name=name, description=description)
            return func

        # Bare decorator: @app.tool — Python passes the function directly.
        if fn is not None:
            return decorator(fn)

        # Decorator with arguments: @app.tool(...) — return the decorator.
        return decorator

    # ------------------------------------------------------------------
    # Tool invocation
    # ------------------------------------------------------------------

    def call(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Call a registered tool by name and return its result.

        Synchronous handlers only.  For async handlers, use ``await app.acall()``.

        When middleware is registered, the chain runs via ``asyncio.run()``,
        which requires no running event loop in the calling thread.

        Args:
            tool_name: The name of the tool to call.
            **kwargs: Arguments forwarded directly to the tool function.

        Returns:
            Whatever the tool function returns, unchanged.

        Raises:
            ToolNotFoundError: If no tool with the given name is registered.
            ToolExecutionError: If the tool is async (use ``acall()`` instead),
                or if the tool function itself raises an exception.
        """
        tool = self._tool_registry.get(tool_name)

        if tool is None:
            available = [t.name for t in self._tool_registry.list()]
            hint = (
                f" Available tools: {available}"
                if available
                else " No tools are registered."
            )
            raise ToolNotFoundError(f"No tool named {tool_name!r} is registered.{hint}")

        if tool.is_async:
            raise ToolExecutionError(
                f"Tool {tool_name!r} is an async function — "
                f"use `await app.acall({tool_name!r}, ...)` instead."
            )

        ctx = InvocationContext(primitive="tool", name=tool_name, kwargs=kwargs)

        def direct(ctx: InvocationContext) -> Any:
            return invoke_sync(
                tool.fn,
                ctx.kwargs,
                error_cls=ToolExecutionError,
                label=tool_name,
            )

        return self._run_sync_chain(ctx, direct)

    async def acall(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Call a registered tool by name and return its result.

        Accepts both synchronous and asynchronous handlers.

        Args:
            tool_name: The name of the tool to call.
            **kwargs: Arguments forwarded directly to the tool function.

        Returns:
            Whatever the tool function returns, unchanged.

        Raises:
            ToolNotFoundError: If no tool with the given name is registered.
            ToolExecutionError: If the tool function raises an exception.
        """
        tool = self._tool_registry.get(tool_name)

        if tool is None:
            available = [t.name for t in self._tool_registry.list()]
            hint = (
                f" Available tools: {available}"
                if available
                else " No tools are registered."
            )
            raise ToolNotFoundError(f"No tool named {tool_name!r} is registered.{hint}")

        ctx = InvocationContext(primitive="tool", name=tool_name, kwargs=kwargs)

        async def terminus(ctx: InvocationContext) -> Any:
            return await invoke_async(
                tool.fn,
                ctx.kwargs,
                is_async=tool.is_async,
                error_cls=ToolExecutionError,
                label=tool_name,
            )

        return await self._run_chain(ctx, terminus)

    def list_tools(self) -> list[Tool]:
        """Return all registered tools in registration order."""
        return self._tool_registry.list()

    # ------------------------------------------------------------------
    # Resource registration
    # ------------------------------------------------------------------

    def resource(
        self,
        *,
        uri: str,
        name: str | None = None,
        description: str | None = None,
        mime_type: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """
        Register a function as an MCP resource.

        Unlike ``@app.tool``, a URI is always required because there is no
        meaningful default URI derivable from a function name::

            @app.resource(uri="config://app/settings")
            def get_settings() -> str:
                \"\"\"Return the current application configuration.\"\"\"
                return json.dumps(config)

            @app.resource(
                uri="users://list",
                name="Active Users",
                description="Returns all currently active users.",
                mime_type="application/json",
            )
            def list_users() -> str:
                return json.dumps(users)

        The decorated function is returned unchanged so it can still be
        called directly in tests without going through the framework.
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._resource_registry.register(
                fn,
                uri=uri,
                name=name,
                description=description,
                mime_type=mime_type,
            )
            return fn

        return decorator

    def list_resources(self) -> list[Resource]:
        """Return all registered resources in registration order."""
        return self._resource_registry.list()

    def read_resource(self, uri: str) -> ResourceContent:
        """
        Read a registered resource by URI and return its content.

        Synchronous handlers only.  For async handlers, use
        ``await app.aread_resource()``.

        Args:
            uri: The URI of the resource to read.

        Returns:
            A ``ResourceContent`` object with the serialized content and
            the MIME type declared at registration time.

        Raises:
            ResourceNotFoundError: If no resource with the given URI is registered.
            ResourceExecutionError: If the resource is async (use
                ``aread_resource()`` instead), if the handler raises, or if its
                return value cannot be serialized.
        """
        resource = self._resource_registry.get(uri)

        if resource is None:
            available = [r.uri for r in self._resource_registry.list()]
            hint = (
                f" Available resources: {available}"
                if available
                else " No resources are registered."
            )
            raise ResourceNotFoundError(
                f"No resource with URI {uri!r} is registered.{hint}"
            )

        if resource.is_async:
            raise ResourceExecutionError(
                f"Resource {uri!r} is an async function — "
                f"use `await app.aread_resource({uri!r})` instead."
            )

        ctx = InvocationContext(primitive="resource", name=uri, kwargs={})

        def direct(ctx: InvocationContext) -> ResourceContent:
            return invoke_sync(
                resource.fn,
                ctx.kwargs,
                error_cls=ResourceExecutionError,
                label=uri,
                normalize=lambda raw: normalize_content(
                    raw, uri=uri, mime_type=resource.mime_type
                ),
                normalize_error="returned a value that could not be serialized",
            )

        return self._run_sync_chain(ctx, direct)

    async def aread_resource(self, uri: str) -> ResourceContent:
        """
        Read a registered resource by URI and return its content.

        Accepts both synchronous and asynchronous handlers.

        Args:
            uri: The URI of the resource to read.

        Returns:
            A ``ResourceContent`` object with the serialized content and
            the MIME type declared at registration time.

        Raises:
            ResourceNotFoundError: If no resource with the given URI is registered.
            ResourceExecutionError: If the handler raises, or if its return value
                cannot be serialized.
        """
        resource = self._resource_registry.get(uri)

        if resource is None:
            available = [r.uri for r in self._resource_registry.list()]
            hint = (
                f" Available resources: {available}"
                if available
                else " No resources are registered."
            )
            raise ResourceNotFoundError(
                f"No resource with URI {uri!r} is registered.{hint}"
            )

        ctx = InvocationContext(primitive="resource", name=uri, kwargs={})

        async def terminus(ctx: InvocationContext) -> ResourceContent:
            return await invoke_async(
                resource.fn,
                ctx.kwargs,
                is_async=resource.is_async,
                error_cls=ResourceExecutionError,
                label=uri,
                normalize=lambda raw: normalize_content(
                    raw, uri=uri, mime_type=resource.mime_type
                ),
                normalize_error="returned a value that could not be serialized",
            )

        return await self._run_chain(ctx, terminus)

    # ------------------------------------------------------------------
    # Prompt registration
    # ------------------------------------------------------------------

    @overload
    def prompt(self, fn: Callable[..., Any]) -> Callable[..., Any]: ...

    @overload
    def prompt(
        self,
        fn: None = None,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

    def prompt(
        self,
        fn: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Any:
        """
        Register a function as an MCP prompt.

        Can be used as a bare decorator or with keyword arguments::

            @app.prompt
            def code_review(language: str, code: str) -> str:
                return f"Review this {language} code:\\n\\n{code}"

            @app.prompt(name="review", description="Request a code review.")
            def code_review(language: str, code: str) -> str:
                return f"Review this {language} code:\\n\\n{code}"

        The handler may return:

        - ``str`` — wrapped into a single user ``PromptMessage`` automatically
        - ``PromptMessage`` — wrapped into a single-element list automatically
        - ``list[PromptMessage]`` — used as-is for multi-turn templates

        The decorated function is returned unchanged so it can still be
        called directly in tests without going through the framework.
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._prompt_registry.register(func, name=name, description=description)
            return func

        if fn is not None:
            return decorator(fn)

        return decorator

    def list_prompts(self) -> list[Prompt]:
        """Return all registered prompts in registration order."""
        return self._prompt_registry.list()

    # ------------------------------------------------------------------
    # Prompt invocation
    # ------------------------------------------------------------------

    def render_prompt(self, name: str, /, **kwargs: Any) -> list[PromptMessage]:
        """
        Render a registered prompt by name and return its messages.

        Synchronous handlers only.  For async handlers, use
        ``await app.arender_prompt()``.

        Args:
            name: The name of the prompt to render.
            **kwargs: Arguments forwarded directly to the prompt function.

        Returns:
            A list of ``PromptMessage`` objects. Each message has a ``role``
            (``"user"`` or ``"assistant"``) and a ``content`` string.

        Raises:
            PromptNotFoundError: If no prompt with the given name is registered.
            PromptExecutionError: If the prompt is async (use ``arender_prompt()``
                instead), if the handler raises, or if its return value cannot be
                normalized to ``list[PromptMessage]``.
        """
        prompt = self._prompt_registry.get(name)

        if prompt is None:
            available = [p.name for p in self._prompt_registry.list()]
            hint = (
                f" Available prompts: {available}"
                if available
                else " No prompts are registered."
            )
            raise PromptNotFoundError(f"No prompt named {name!r} is registered.{hint}")

        if prompt.is_async:
            raise PromptExecutionError(
                f"Prompt {name!r} is an async function — "
                f"use `await app.arender_prompt({name!r}, ...)` instead."
            )

        ctx = InvocationContext(primitive="prompt", name=name, kwargs=kwargs)

        def direct(ctx: InvocationContext) -> list[PromptMessage]:
            return invoke_sync(
                prompt.fn,
                ctx.kwargs,
                error_cls=PromptExecutionError,
                label=name,
                normalize=normalize_messages,
            )

        return self._run_sync_chain(ctx, direct)

    async def arender_prompt(self, name: str, /, **kwargs: Any) -> list[PromptMessage]:
        """
        Render a registered prompt by name and return its messages.

        Accepts both synchronous and asynchronous handlers.

        Args:
            name: The name of the prompt to render.
            **kwargs: Arguments forwarded directly to the prompt function.

        Returns:
            A list of ``PromptMessage`` objects. Each message has a ``role``
            (``"user"`` or ``"assistant"``) and a ``content`` string.

        Raises:
            PromptNotFoundError: If no prompt with the given name is registered.
            PromptExecutionError: If the handler raises, or if its return value
                cannot be normalized to ``list[PromptMessage]``.
        """
        prompt = self._prompt_registry.get(name)

        if prompt is None:
            available = [p.name for p in self._prompt_registry.list()]
            hint = (
                f" Available prompts: {available}"
                if available
                else " No prompts are registered."
            )
            raise PromptNotFoundError(f"No prompt named {name!r} is registered.{hint}")

        ctx = InvocationContext(primitive="prompt", name=name, kwargs=kwargs)

        async def terminus(ctx: InvocationContext) -> list[PromptMessage]:
            return await invoke_async(
                prompt.fn,
                ctx.kwargs,
                is_async=prompt.is_async,
                error_cls=PromptExecutionError,
                label=name,
                normalize=normalize_messages,
            )

        return await self._run_chain(ctx, terminus)

    # ------------------------------------------------------------------
    # Middleware registration
    # ------------------------------------------------------------------

    def add_middleware(self, fn: MiddlewareFn) -> None:
        """Add a middleware function to the execution chain.

        Middleware executes in registration order — first registered is
        outermost (runs first before the handler, last after).

        Middleware applies to all six invocation methods: ``acall()``,
        ``aread_resource()``, ``arender_prompt()``, and their synchronous
        counterparts ``call()``, ``read_resource()``, ``render_prompt()``.
        For synchronous methods the chain runs in a temporary event loop
        created by ``asyncio.run()``; this requires no running event loop
        in the calling thread.

        Args:
            fn: An async callable with the signature
                ``async def fn(ctx: InvocationContext, next: Next) -> Any``.
                Objects with an async ``__call__`` method also qualify.
        """
        self._middleware.append(fn)

    def middleware(self, fn: MiddlewareFn) -> MiddlewareFn:
        """Decorator to register a middleware function.

        Equivalent to ``app.add_middleware(fn)`` but usable as a decorator::

            @app.middleware
            async def log_calls(ctx, next):
                print(f"→ {ctx.primitive} {ctx.name!r}")
                result = await next(ctx)
                print(f"← {ctx.primitive} {ctx.name!r}")
                return result

        Returns the original function unchanged.
        """
        self.add_middleware(fn)
        return fn

    # ------------------------------------------------------------------
    # Plugin registration
    # ------------------------------------------------------------------

    def register_plugin(self, plugin: Any) -> None:
        """Register a plugin and call its ``setup(app)`` method immediately.

        BridgeMCP uses duck typing: any object that exposes a
        ``setup(app)`` method is a valid plugin.  Inheriting from
        :class:`~bridgemcp.plugin.Plugin` is optional convenience.

        ``on_startup`` and ``on_shutdown`` hooks are collected
        automatically when present on the plugin object.  They are
        invoked by the transport adapter before the server starts and
        after it stops.

        Args:
            plugin: Any object with a ``setup(self, app)`` method.
                Optionally also exposes ``on_startup(app)`` and/or
                ``on_shutdown(app)`` async methods for lifecycle hooks.

        Example::

            app.register_plugin(LoggingPlugin(level="DEBUG"))
        """
        plugin.setup(self)
        self._plugins.append(plugin)
        if (hook := getattr(plugin, "on_startup", None)) is not None:
            self._startup_hooks.append(hook)
        if (hook := getattr(plugin, "on_shutdown", None)) is not None:
            self._shutdown_hooks.append(hook)

    # ------------------------------------------------------------------
    # Execution chain helpers (private)
    # ------------------------------------------------------------------

    async def _run_chain(self, ctx: InvocationContext, terminus: Next) -> Any:
        """Execute the middleware chain for an async invocation.

        Fast path: if no middleware is registered, the terminus is awaited
        directly without building a chain.
        """
        if not self._middleware:
            return await terminus(ctx)
        return await build_chain(self._middleware, terminus)(ctx)

    def _run_sync_chain(
        self,
        ctx: InvocationContext,
        direct: Callable[[InvocationContext], Any],
    ) -> Any:
        """Execute the middleware chain for a synchronous invocation.

        Fast path (no middleware): calls ``direct(ctx)`` without creating
        an event loop, preserving zero overhead for the common case.

        Slow path (middleware registered): wraps ``direct`` in an async
        terminus and runs the full chain via ``asyncio.run()``, which creates
        a temporary event loop.  Requires no running event loop in the calling
        thread — calling a synchronous invocation method from inside a
        coroutine is already considered incorrect usage.

        Args:
            ctx: Invocation context passed through the middleware chain.
            direct: Synchronous callable that performs the actual handler
                invocation.  Receives ``ctx`` so middleware modifications to
                ``ctx.kwargs`` are reflected in the handler call.
        """
        if not self._middleware:
            return direct(ctx)

        async def terminus(ctx: InvocationContext) -> Any:
            return direct(ctx)

        return asyncio.run(build_chain(self._middleware, terminus)(ctx))

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the MCP server using stdio transport.

        This is the standard transport for AI clients such as Claude Desktop
        and Cursor that launch your server as a subprocess.

        Requires: ``pip install 'bridgemcp[mcp]'``
        """
        from bridgemcp.adapters.mcp import run_stdio

        run_stdio(self)

    def run_http(self, *, host: str = "127.0.0.1", port: int = 8000) -> None:
        """Start the MCP server using HTTP/SSE transport.

        Use this when AI clients should connect over the network rather
        than via a subprocess.

        Args:
            host: The host to bind to. Defaults to "127.0.0.1".
            port: The port to listen on. Defaults to 8000.

        Requires: ``pip install 'bridgemcp[mcp]'``
        """
        from bridgemcp.adapters.mcp import run_http

        run_http(self, host=host, port=port)

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        desc = f", description={self.description!r}" if self.description else ""
        return f"BridgeMCP(name={self.name!r}, version={self.version!r}{desc})"
