"""
Handler execution pipeline for BridgeMCP.

Provides two functions used by application.py to invoke registered handlers:

    invoke_sync   — execute a synchronous callable, wrap exceptions, normalize output.
    invoke_async  — execute a sync or async callable from an async context.

Responsibility boundary: this module handles handler invocation, exception
chaining, async dispatch, and optional normalization only.  Registry lookups,
transport logic, adapter logic, configuration, and middleware implementations
belong outside this module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bridgemcp.exceptions import ExecutionError


def invoke_sync(
    fn: Callable[..., Any],
    kwargs: dict[str, Any],
    *,
    error_cls: type[ExecutionError],
    label: str,
    normalize: Callable[[Any], Any] | None = None,
    normalize_error: str = "returned a value that could not be normalized",
) -> Any:
    """Execute a synchronous callable, normalize its output, and wrap exceptions.

    Args:
        fn: Synchronous callable to invoke.  Async callables are not supported
            here — use invoke_async from an async context instead.
        kwargs: Keyword arguments forwarded to fn.
        error_cls: ExecutionError subclass raised on failure.
        label: Human-readable identifier used in error messages (e.g. tool name).
        normalize: Optional function applied to fn's return value.  Must be
            synchronous.  If None, the raw return value is returned as-is.
        normalize_error: Verb phrase embedded in the normalization failure message.
            Defaults to "returned a value that could not be normalized".

    Returns:
        fn(**kwargs), or normalize(fn(**kwargs)) when normalize is provided.

    Raises:
        error_cls: If fn raises, or if normalize raises on fn's return value.
    """
    try:
        raw = fn(**kwargs)
    except Exception as exc:
        raise error_cls(f"{label!r} raised an exception: {exc}") from exc

    if normalize is None:
        return raw

    try:
        return normalize(raw)
    except Exception as exc:
        raise error_cls(f"{label!r} {normalize_error}: {exc}") from exc


async def invoke_async(
    fn: Callable[..., Any],
    kwargs: dict[str, Any],
    *,
    is_async: bool,
    error_cls: type[ExecutionError],
    label: str,
    normalize: Callable[[Any], Any] | None = None,
    normalize_error: str = "returned a value that could not be normalized",
) -> Any:
    """Execute a sync or async callable from an async context.

    Unlike invoke_sync, this coroutine handles both synchronous and asynchronous
    callables.  Pass is_async=True when fn is an async def function.

    Args:
        fn: Callable to invoke; may be sync or async.
        kwargs: Keyword arguments forwarded to fn.
        is_async: True when fn is an async def function; False for regular def.
            When False, fn is called directly with no event-loop overhead.
        error_cls: ExecutionError subclass raised on failure.
        label: Human-readable identifier used in error messages.
        normalize: Optional synchronous normalization function applied to the
            return value.  Normalization is CPU-bound; it does not need to be async.
        normalize_error: Verb phrase embedded in the normalization failure message.

    Returns:
        fn(**kwargs) (awaited when is_async is True), or normalize(result).

    Raises:
        error_cls: If fn raises, or if normalize raises on fn's return value.
    """
    try:
        raw = await fn(**kwargs) if is_async else fn(**kwargs)
    except Exception as exc:
        raise error_cls(f"{label!r} raised an exception: {exc}") from exc

    if normalize is None:
        return raw

    try:
        return normalize(raw)
    except Exception as exc:
        raise error_cls(f"{label!r} {normalize_error}: {exc}") from exc
