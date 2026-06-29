"""
Middleware infrastructure for BridgeMCP.

Provides the InvocationContext dataclass, MiddlewareFn and Next type aliases,
and build_chain() for composing middleware stacks.

A middleware is any async callable with this signature::

    async def my_middleware(
        ctx: InvocationContext,
        next: Next,
    ) -> Any:
        # before handler
        result = await next(ctx)
        # after handler
        return result

Middleware classes with an async ``__call__`` method are equally valid.

Responsibility boundary: this module defines middleware types and chain
composition only.  Registration, invocation, and transport logic live
in application.py and the adapter layer.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class InvocationContext:
    """Context passed through the middleware chain on every handler invocation.

    Attributes:
        primitive: The MCP primitive type being invoked (``"tool"``,
            ``"resource"``, or ``"prompt"``).
        name: The registered identifier — tool name, resource URI, or
            prompt name.
        kwargs: Arguments forwarded to the handler.  Middleware may mutate
            this dict to alter what the handler receives.
        metadata: Mutable pass-through bag for middleware-to-middleware
            communication.  Not read or written by the BridgeMCP framework.
    """

    primitive: Literal["tool", "resource", "prompt"]
    name: str
    kwargs: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


#: Type alias for the ``next`` callable passed to each middleware.
Next = Callable[["InvocationContext"], Awaitable[Any]]

#: Type alias for a middleware function.  Both ``async def`` functions and
#: objects with an async ``__call__`` method satisfy this type.
MiddlewareFn = Callable[["InvocationContext", Next], Awaitable[Any]]


def build_chain(middleware: list[MiddlewareFn], terminus: Next) -> Next:
    """Compose a middleware list and a terminal handler into a single callable.

    Middleware executes in registration order: the first element in
    *middleware* is outermost (runs first before the handler, last after).

    Args:
        middleware: Ordered list of middleware callables.
        terminus: Innermost callable — the actual handler invocation.

    Returns:
        A single :data:`Next` callable that, when awaited with a context,
        runs the full chain ending at *terminus*.
    """
    chain: Next = terminus
    for mw in reversed(middleware):
        inner = chain

        async def step(
            ctx: InvocationContext,
            *,
            _mw: MiddlewareFn = mw,
            _inner: Next = inner,
        ) -> Any:
            return await _mw(ctx, _inner)

        chain = step
    return chain
