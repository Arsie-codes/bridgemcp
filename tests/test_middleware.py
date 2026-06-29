"""
Tests for BridgeMCP middleware — bridgemcp/middleware.py and the middleware
integration points in bridgemcp/application.py.

Coverage:
  - InvocationContext dataclass
  - build_chain() composition and execution order
  - Middleware integration on all six invocation methods
  - Registration API (add_middleware / @app.middleware decorator)
  - Middleware context fields (primitive, name, kwargs, metadata)
  - Middleware kwargs mutation propagated to handler
  - Class-based middleware with async __call__
  - Middleware short-circuit (not calling next)
  - Middleware exception propagation
  - Fast path: no middleware → no event loop created for sync methods
"""

from __future__ import annotations

from typing import Any

import pytest

from bridgemcp import BridgeMCP
from bridgemcp.exceptions import ToolExecutionError, ToolNotFoundError
from bridgemcp.middleware import InvocationContext, Next, build_chain

# ---------------------------------------------------------------------------
# InvocationContext
# ---------------------------------------------------------------------------


def test_invocation_context_stores_fields():
    ctx = InvocationContext(primitive="tool", name="add", kwargs={"x": 1})
    assert ctx.primitive == "tool"
    assert ctx.name == "add"
    assert ctx.kwargs == {"x": 1}


def test_invocation_context_default_metadata_is_empty_dict():
    ctx = InvocationContext(primitive="resource", name="data://x", kwargs={})
    assert ctx.metadata == {}


def test_invocation_context_metadata_is_independent_per_instance():
    ctx1 = InvocationContext(primitive="tool", name="a", kwargs={})
    ctx2 = InvocationContext(primitive="tool", name="b", kwargs={})
    ctx1.metadata["key"] = "value"
    assert "key" not in ctx2.metadata


def test_invocation_context_kwargs_is_mutable():
    ctx = InvocationContext(primitive="tool", name="fn", kwargs={"x": 1})
    ctx.kwargs["y"] = 2
    assert ctx.kwargs == {"x": 1, "y": 2}


# ---------------------------------------------------------------------------
# build_chain — unit tests
# ---------------------------------------------------------------------------


async def test_build_chain_no_middleware_calls_terminus():
    called = []

    async def terminus(ctx: InvocationContext) -> str:
        called.append("terminus")
        return "result"

    chain = build_chain([], terminus)
    ctx = InvocationContext(primitive="tool", name="fn", kwargs={})
    result = await chain(ctx)

    assert result == "result"
    assert called == ["terminus"]


async def test_build_chain_single_middleware_wraps_terminus():
    order: list[str] = []

    async def mw(ctx: InvocationContext, next: Next) -> Any:
        order.append("mw:before")
        result = await next(ctx)
        order.append("mw:after")
        return result

    async def terminus(ctx: InvocationContext) -> str:
        order.append("terminus")
        return "ok"

    ctx = InvocationContext(primitive="tool", name="fn", kwargs={})
    result = await build_chain([mw], terminus)(ctx)

    assert result == "ok"
    assert order == ["mw:before", "terminus", "mw:after"]


async def test_build_chain_execution_order_first_registered_is_outermost():
    """First middleware in the list is the outermost — runs first before, last after."""
    order: list[str] = []

    async def mw_a(ctx: InvocationContext, next: Next) -> Any:
        order.append("A:before")
        result = await next(ctx)
        order.append("A:after")
        return result

    async def mw_b(ctx: InvocationContext, next: Next) -> Any:
        order.append("B:before")
        result = await next(ctx)
        order.append("B:after")
        return result

    async def terminus(ctx: InvocationContext) -> str:
        order.append("terminus")
        return "ok"

    ctx = InvocationContext(primitive="tool", name="fn", kwargs={})
    await build_chain([mw_a, mw_b], terminus)(ctx)

    assert order == ["A:before", "B:before", "terminus", "B:after", "A:after"]


async def test_build_chain_middleware_can_modify_kwargs():
    seen_kwargs: dict = {}

    async def inject(ctx: InvocationContext, next: Next) -> Any:
        ctx.kwargs["injected"] = True
        return await next(ctx)

    async def terminus(ctx: InvocationContext) -> Any:
        seen_kwargs.update(ctx.kwargs)
        return "ok"

    ctx = InvocationContext(primitive="tool", name="fn", kwargs={"x": 1})
    await build_chain([inject], terminus)(ctx)

    assert seen_kwargs == {"x": 1, "injected": True}


async def test_build_chain_middleware_can_modify_result():
    async def double(ctx: InvocationContext, next: Next) -> Any:
        result = await next(ctx)
        return result * 2

    async def terminus(ctx: InvocationContext) -> int:
        return 21

    ctx = InvocationContext(primitive="tool", name="fn", kwargs={})
    result = await build_chain([double], terminus)(ctx)

    assert result == 42


async def test_build_chain_middleware_can_catch_terminus_exception():
    async def catcher(ctx: InvocationContext, next: Next) -> Any:
        try:
            return await next(ctx)
        except ToolExecutionError:
            return "caught"

    async def terminus(ctx: InvocationContext) -> Any:
        raise ToolExecutionError("boom")

    ctx = InvocationContext(primitive="tool", name="fn", kwargs={})
    result = await build_chain([catcher], terminus)(ctx)

    assert result == "caught"


async def test_build_chain_middleware_exception_propagates():
    async def exploding(ctx: InvocationContext, next: Next) -> Any:
        raise ValueError("mw failure")

    async def terminus(ctx: InvocationContext) -> Any:
        return "ok"

    ctx = InvocationContext(primitive="tool", name="fn", kwargs={})
    with pytest.raises(ValueError, match="mw failure"):
        await build_chain([exploding], terminus)(ctx)


async def test_build_chain_short_circuit_skips_terminus():
    terminus_called = []

    async def gate(ctx: InvocationContext, next: Next) -> Any:
        return "short-circuited"  # never calls next

    async def terminus(ctx: InvocationContext) -> Any:
        terminus_called.append(True)
        return "should not reach"

    ctx = InvocationContext(primitive="tool", name="fn", kwargs={})
    result = await build_chain([gate], terminus)(ctx)

    assert result == "short-circuited"
    assert terminus_called == []


async def test_build_chain_metadata_passes_between_middleware():
    async def writer(ctx: InvocationContext, next: Next) -> Any:
        ctx.metadata["span_id"] = "abc123"
        return await next(ctx)

    seen_metadata: dict = {}

    async def reader(ctx: InvocationContext, next: Next) -> Any:
        seen_metadata.update(ctx.metadata)
        return await next(ctx)

    async def terminus(ctx: InvocationContext) -> str:
        return "ok"

    ctx = InvocationContext(primitive="tool", name="fn", kwargs={})
    await build_chain([writer, reader], terminus)(ctx)

    assert seen_metadata["span_id"] == "abc123"


# ---------------------------------------------------------------------------
# Registration API
# ---------------------------------------------------------------------------


def test_add_middleware_appends_to_chain():
    app = BridgeMCP(name="test")
    assert app._middleware == []

    async def mw(ctx, next):
        return await next(ctx)

    app.add_middleware(mw)
    assert len(app._middleware) == 1
    assert app._middleware[0] is mw


def test_middleware_decorator_registers_and_returns_original():
    app = BridgeMCP(name="test")

    async def log(ctx, next):
        return await next(ctx)

    returned = app.middleware(log)

    assert returned is log
    assert len(app._middleware) == 1


def test_middleware_decorator_used_as_at_syntax():
    app = BridgeMCP(name="test")

    @app.middleware
    async def log(ctx, next):
        return await next(ctx)

    assert len(app._middleware) == 1
    assert app._middleware[0] is log


def test_add_middleware_preserves_registration_order():
    app = BridgeMCP(name="test")

    async def mw_a(ctx, next):
        return await next(ctx)

    async def mw_b(ctx, next):
        return await next(ctx)

    async def mw_c(ctx, next):
        return await next(ctx)

    app.add_middleware(mw_a)
    app.add_middleware(mw_b)
    app.add_middleware(mw_c)

    assert [m for m in app._middleware] == [mw_a, mw_b, mw_c]


# ---------------------------------------------------------------------------
# Async invocation — acall
# ---------------------------------------------------------------------------


async def test_middleware_runs_on_acall():
    app = BridgeMCP(name="test")

    @app.tool
    def add(x: int, y: int) -> int:
        return x + y

    called = []

    @app.middleware
    async def track(ctx: InvocationContext, next: Next) -> Any:
        called.append(ctx.name)
        return await next(ctx)

    result = await app.acall("add", x=1, y=2)
    assert result == 3
    assert called == ["add"]


async def test_middleware_ctx_primitive_is_tool_for_acall():
    app = BridgeMCP(name="test")

    @app.tool
    def ping() -> str:
        return "pong"

    primitives = []

    @app.middleware
    async def capture(ctx: InvocationContext, next: Next) -> Any:
        primitives.append(ctx.primitive)
        return await next(ctx)

    await app.acall("ping")
    assert primitives == ["tool"]


async def test_middleware_ctx_kwargs_match_acall_arguments():
    app = BridgeMCP(name="test")

    @app.tool
    def echo(value: str) -> str:
        return value

    captured: dict = {}

    @app.middleware
    async def capture(ctx: InvocationContext, next: Next) -> Any:
        captured.update(ctx.kwargs)
        return await next(ctx)

    await app.acall("echo", value="hello")
    assert captured == {"value": "hello"}


async def test_middleware_runs_on_aread_resource():
    app = BridgeMCP(name="test")

    @app.resource(uri="data://test")
    def get_data() -> str:
        return "content"

    called = []

    @app.middleware
    async def track(ctx: InvocationContext, next: Next) -> Any:
        called.append((ctx.primitive, ctx.name))
        return await next(ctx)

    await app.aread_resource("data://test")
    assert called == [("resource", "data://test")]


async def test_middleware_runs_on_arender_prompt():
    app = BridgeMCP(name="test")

    @app.prompt
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    called = []

    @app.middleware
    async def track(ctx: InvocationContext, next: Next) -> Any:
        called.append((ctx.primitive, ctx.name))
        return await next(ctx)

    await app.arender_prompt("greet", name="Alice")
    assert called == [("prompt", "greet")]


async def test_multiple_middleware_run_in_order_on_acall():
    app = BridgeMCP(name="test")

    @app.tool
    def noop() -> None:
        return None

    order: list[str] = []

    @app.middleware
    async def first(ctx: InvocationContext, next: Next) -> Any:
        order.append("first:before")
        result = await next(ctx)
        order.append("first:after")
        return result

    @app.middleware
    async def second(ctx: InvocationContext, next: Next) -> Any:
        order.append("second:before")
        result = await next(ctx)
        order.append("second:after")
        return result

    await app.acall("noop")
    assert order == ["first:before", "second:before", "second:after", "first:after"]


# ---------------------------------------------------------------------------
# Sync invocation — call, read_resource, render_prompt
# ---------------------------------------------------------------------------


def test_middleware_runs_on_call():
    app = BridgeMCP(name="test")

    @app.tool
    def add(x: int, y: int) -> int:
        return x + y

    called = []

    @app.middleware
    async def track(ctx: InvocationContext, next: Next) -> Any:
        called.append(ctx.name)
        return await next(ctx)

    result = app.call("add", x=3, y=4)
    assert result == 7
    assert called == ["add"]


def test_middleware_ctx_primitive_is_tool_for_call():
    app = BridgeMCP(name="test")

    @app.tool
    def ping() -> str:
        return "pong"

    primitives = []

    @app.middleware
    async def capture(ctx: InvocationContext, next: Next) -> Any:
        primitives.append(ctx.primitive)
        return await next(ctx)

    app.call("ping")
    assert primitives == ["tool"]


def test_middleware_runs_on_read_resource():
    app = BridgeMCP(name="test")

    @app.resource(uri="data://test")
    def get_data() -> str:
        return "content"

    called = []

    @app.middleware
    async def track(ctx: InvocationContext, next: Next) -> Any:
        called.append((ctx.primitive, ctx.name))
        return await next(ctx)

    app.read_resource("data://test")
    assert called == [("resource", "data://test")]


def test_middleware_runs_on_render_prompt():
    app = BridgeMCP(name="test")

    @app.prompt
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    called = []

    @app.middleware
    async def track(ctx: InvocationContext, next: Next) -> Any:
        called.append((ctx.primitive, ctx.name))
        return await next(ctx)

    app.render_prompt("greet", name="Alice")
    assert called == [("prompt", "greet")]


def test_sync_middleware_receives_correct_result():
    app = BridgeMCP(name="test")

    @app.tool
    def multiply(x: int, y: int) -> int:
        return x * y

    results = []

    @app.middleware
    async def capture_result(ctx: InvocationContext, next: Next) -> Any:
        result = await next(ctx)
        results.append(result)
        return result

    app.call("multiply", x=6, y=7)
    assert results == [42]


def test_multiple_middleware_run_in_order_on_call():
    app = BridgeMCP(name="test")

    @app.tool
    def noop() -> None:
        return None

    order: list[str] = []

    @app.middleware
    async def first(ctx: InvocationContext, next: Next) -> Any:
        order.append("first:before")
        result = await next(ctx)
        order.append("first:after")
        return result

    @app.middleware
    async def second(ctx: InvocationContext, next: Next) -> Any:
        order.append("second:before")
        result = await next(ctx)
        order.append("second:after")
        return result

    app.call("noop")
    assert order == ["first:before", "second:before", "second:after", "first:after"]


# ---------------------------------------------------------------------------
# Middleware can mutate ctx.kwargs to alter handler input
# ---------------------------------------------------------------------------


async def test_middleware_kwargs_mutation_reaches_handler_async():
    app = BridgeMCP(name="test")
    received: dict = {}

    @app.tool
    def capture(**kwargs: Any) -> None:
        received.update(kwargs)

    @app.middleware
    async def inject(ctx: InvocationContext, next: Next) -> Any:
        ctx.kwargs["injected"] = "yes"
        return await next(ctx)

    await app.acall("capture")
    assert received.get("injected") == "yes"


def test_middleware_kwargs_mutation_reaches_handler_sync():
    app = BridgeMCP(name="test")
    received: dict = {}

    @app.tool
    def capture(**kwargs: Any) -> None:
        received.update(kwargs)

    @app.middleware
    async def inject(ctx: InvocationContext, next: Next) -> Any:
        ctx.kwargs["injected"] = "yes"
        return await next(ctx)

    app.call("capture")
    assert received.get("injected") == "yes"


# ---------------------------------------------------------------------------
# Class-based middleware
# ---------------------------------------------------------------------------


async def test_class_based_middleware_async():
    app = BridgeMCP(name="test")

    @app.tool
    def ping() -> str:
        return "pong"

    class CountingMiddleware:
        def __init__(self) -> None:
            self.count = 0

        async def __call__(self, ctx: InvocationContext, next: Next) -> Any:
            self.count += 1
            return await next(ctx)

    counter = CountingMiddleware()
    app.add_middleware(counter)

    await app.acall("ping")
    await app.acall("ping")
    assert counter.count == 2


def test_class_based_middleware_sync():
    app = BridgeMCP(name="test")

    @app.tool
    def ping() -> str:
        return "pong"

    class CountingMiddleware:
        def __init__(self) -> None:
            self.count = 0

        async def __call__(self, ctx: InvocationContext, next: Next) -> Any:
            self.count += 1
            return await next(ctx)

    counter = CountingMiddleware()
    app.add_middleware(counter)

    app.call("ping")
    app.call("ping")
    assert counter.count == 2


# ---------------------------------------------------------------------------
# Fast path — no middleware
# ---------------------------------------------------------------------------


def test_no_middleware_sync_call_succeeds():
    """Fast path: no middleware registered — sync method works without event loop."""
    app = BridgeMCP(name="test")

    @app.tool
    def add(x: int, y: int) -> int:
        return x + y

    assert app.call("add", x=10, y=20) == 30


async def test_no_middleware_async_call_succeeds():
    """Fast path: no middleware registered — async method works."""
    app = BridgeMCP(name="test")

    @app.tool
    def add(x: int, y: int) -> int:
        return x + y

    assert await app.acall("add", x=10, y=20) == 30


# ---------------------------------------------------------------------------
# Middleware metadata channel
# ---------------------------------------------------------------------------


async def test_metadata_channel_between_middleware():
    app = BridgeMCP(name="test")

    @app.tool
    def noop() -> None:
        return None

    @app.middleware
    async def writer(ctx: InvocationContext, next: Next) -> Any:
        ctx.metadata["trace_id"] = "xyz"
        return await next(ctx)

    seen: dict = {}

    @app.middleware
    async def reader(ctx: InvocationContext, next: Next) -> Any:
        seen.update(ctx.metadata)
        return await next(ctx)

    await app.acall("noop")
    assert seen["trace_id"] == "xyz"


# ---------------------------------------------------------------------------
# Error handling — ToolNotFoundError is NOT intercepted by middleware
# ---------------------------------------------------------------------------


async def test_not_found_error_bypasses_middleware():
    """Registry lookup happens before chain; NotFoundError propagates directly."""
    app = BridgeMCP(name="test")
    mw_called = []

    @app.middleware
    async def track(ctx: InvocationContext, next: Next) -> Any:
        mw_called.append(True)
        return await next(ctx)

    with pytest.raises(ToolNotFoundError):
        await app.acall("nonexistent")

    assert mw_called == []


def test_not_found_error_bypasses_middleware_sync():
    app = BridgeMCP(name="test")
    mw_called = []

    @app.middleware
    async def track(ctx: InvocationContext, next: Next) -> Any:
        mw_called.append(True)
        return await next(ctx)

    with pytest.raises(ToolNotFoundError):
        app.call("nonexistent")

    assert mw_called == []


# ---------------------------------------------------------------------------
# Middleware receives ToolExecutionError from failing handler
# ---------------------------------------------------------------------------


async def test_middleware_catches_execution_error_async():
    app = BridgeMCP(name="test")

    @app.tool
    def explode() -> None:
        raise RuntimeError("boom")

    errors = []

    @app.middleware
    async def catch_errors(ctx: InvocationContext, next: Next) -> Any:
        try:
            return await next(ctx)
        except ToolExecutionError as exc:
            errors.append(str(exc))
            raise

    from bridgemcp.exceptions import ToolExecutionError

    with pytest.raises(ToolExecutionError):
        await app.acall("explode")

    assert len(errors) == 1
    assert "boom" in errors[0]


def test_middleware_catches_execution_error_sync():
    from bridgemcp.exceptions import ToolExecutionError

    app = BridgeMCP(name="test")

    @app.tool
    def explode() -> None:
        raise RuntimeError("boom")

    errors = []

    @app.middleware
    async def catch_errors(ctx: InvocationContext, next: Next) -> Any:
        try:
            return await next(ctx)
        except ToolExecutionError as exc:
            errors.append(str(exc))
            raise

    with pytest.raises(ToolExecutionError):
        app.call("explode")

    assert len(errors) == 1
    assert "boom" in errors[0]
