"""
Tests for bridgemcp.execution — the shared handler execution pipeline.

These tests exercise invoke_sync and invoke_async in isolation, independent
of any registry or application logic.
"""

from __future__ import annotations

import pytest

from bridgemcp.exceptions import ToolExecutionError
from bridgemcp.execution import invoke_async, invoke_sync

# ---------------------------------------------------------------------------
# invoke_sync — happy path
# ---------------------------------------------------------------------------


def test_invoke_sync_calls_fn_with_kwargs():
    def fn(x: int, y: int) -> int:
        return x + y

    result = invoke_sync(
        fn, {"x": 1, "y": 2}, error_cls=ToolExecutionError, label="add"
    )
    assert result == 3


def test_invoke_sync_returns_raw_result_when_no_normalize():
    def fn() -> dict:
        return {"key": "value"}

    result = invoke_sync(fn, {}, error_cls=ToolExecutionError, label="fn")
    assert result == {"key": "value"}


def test_invoke_sync_returns_none_from_fn():
    def fn() -> None:
        return None

    result = invoke_sync(fn, {}, error_cls=ToolExecutionError, label="fn")
    assert result is None


# ---------------------------------------------------------------------------
# invoke_sync — exception wrapping
# ---------------------------------------------------------------------------


def test_invoke_sync_wraps_exception_in_error_cls():
    def fn() -> None:
        raise ValueError("boom")

    with pytest.raises(ToolExecutionError, match="boom"):
        invoke_sync(fn, {}, error_cls=ToolExecutionError, label="fn")


def test_invoke_sync_error_message_contains_label():
    def fn() -> None:
        raise ValueError("boom")

    with pytest.raises(ToolExecutionError, match="my_tool"):
        invoke_sync(fn, {}, error_cls=ToolExecutionError, label="my_tool")


def test_invoke_sync_preserves_cause():
    original = ValueError("root cause")

    def fn() -> None:
        raise original

    with pytest.raises(ToolExecutionError) as exc_info:
        invoke_sync(fn, {}, error_cls=ToolExecutionError, label="fn")

    assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# invoke_sync — normalization
# ---------------------------------------------------------------------------


def test_invoke_sync_applies_normalize_to_result():
    def fn() -> str:
        return "raw"

    result = invoke_sync(
        fn, {}, error_cls=ToolExecutionError, label="fn", normalize=str.upper
    )
    assert result == "RAW"


def test_invoke_sync_wraps_normalize_exception():
    def fn() -> None:
        return None

    def bad_normalize(x: object) -> None:
        raise ValueError("cannot normalize")

    with pytest.raises(ToolExecutionError, match="could not be normalized"):
        invoke_sync(
            fn, {}, error_cls=ToolExecutionError, label="fn", normalize=bad_normalize
        )


def test_invoke_sync_normalize_error_preserves_cause():
    original = ValueError("bad value")

    def fn() -> None:
        return None

    def bad_normalize(x: object) -> None:
        raise original

    with pytest.raises(ToolExecutionError) as exc_info:
        invoke_sync(
            fn, {}, error_cls=ToolExecutionError, label="fn", normalize=bad_normalize
        )

    assert exc_info.value.__cause__ is original


def test_invoke_sync_custom_normalize_error_message():
    def fn() -> None:
        return None

    def bad_normalize(x: object) -> None:
        raise ValueError("oops")

    with pytest.raises(ToolExecutionError, match="could not be serialized"):
        invoke_sync(
            fn,
            {},
            error_cls=ToolExecutionError,
            label="fn",
            normalize=bad_normalize,
            normalize_error="returned a value that could not be serialized",
        )


# ---------------------------------------------------------------------------
# invoke_async — happy path, sync handler
# ---------------------------------------------------------------------------


async def test_invoke_async_calls_sync_fn():
    def fn(x: int) -> int:
        return x * 2

    result = await invoke_async(
        fn, {"x": 5}, is_async=False, error_cls=ToolExecutionError, label="fn"
    )
    assert result == 10


async def test_invoke_async_returns_raw_result_sync():
    def fn() -> str:
        return "sync result"

    result = await invoke_async(
        fn, {}, is_async=False, error_cls=ToolExecutionError, label="fn"
    )
    assert result == "sync result"


# ---------------------------------------------------------------------------
# invoke_async — happy path, async handler
# ---------------------------------------------------------------------------


async def test_invoke_async_calls_async_fn():
    async def fn(x: int) -> int:
        return x * 3

    result = await invoke_async(
        fn, {"x": 4}, is_async=True, error_cls=ToolExecutionError, label="fn"
    )
    assert result == 12


async def test_invoke_async_returns_raw_result_async():
    async def fn() -> str:
        return "async result"

    result = await invoke_async(
        fn, {}, is_async=True, error_cls=ToolExecutionError, label="fn"
    )
    assert result == "async result"


# ---------------------------------------------------------------------------
# invoke_async — exception wrapping
# ---------------------------------------------------------------------------


async def test_invoke_async_wraps_sync_fn_exception():
    def fn() -> None:
        raise RuntimeError("sync fail")

    with pytest.raises(ToolExecutionError, match="sync fail"):
        await invoke_async(
            fn, {}, is_async=False, error_cls=ToolExecutionError, label="fn"
        )


async def test_invoke_async_wraps_async_fn_exception():
    async def fn() -> None:
        raise RuntimeError("async fail")

    with pytest.raises(ToolExecutionError, match="async fail"):
        await invoke_async(
            fn, {}, is_async=True, error_cls=ToolExecutionError, label="fn"
        )


async def test_invoke_async_preserves_cause_from_async_fn():
    original = ValueError("root cause")

    async def fn() -> None:
        raise original

    with pytest.raises(ToolExecutionError) as exc_info:
        await invoke_async(
            fn, {}, is_async=True, error_cls=ToolExecutionError, label="fn"
        )

    assert exc_info.value.__cause__ is original


async def test_invoke_async_preserves_cause_from_sync_fn():
    original = ValueError("root cause")

    def fn() -> None:
        raise original

    with pytest.raises(ToolExecutionError) as exc_info:
        await invoke_async(
            fn, {}, is_async=False, error_cls=ToolExecutionError, label="fn"
        )

    assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# invoke_async — normalization
# ---------------------------------------------------------------------------


async def test_invoke_async_applies_normalize_to_async_result():
    async def fn() -> str:
        return "raw"

    result = await invoke_async(
        fn,
        {},
        is_async=True,
        error_cls=ToolExecutionError,
        label="fn",
        normalize=str.upper,
    )
    assert result == "RAW"


async def test_invoke_async_applies_normalize_to_sync_result():
    def fn() -> str:
        return "raw"

    result = await invoke_async(
        fn,
        {},
        is_async=False,
        error_cls=ToolExecutionError,
        label="fn",
        normalize=str.upper,
    )
    assert result == "RAW"


async def test_invoke_async_wraps_normalize_exception():
    async def fn() -> None:
        return None

    def bad_normalize(x: object) -> None:
        raise ValueError("bad")

    with pytest.raises(ToolExecutionError, match="could not be normalized"):
        await invoke_async(
            fn,
            {},
            is_async=True,
            error_cls=ToolExecutionError,
            label="fn",
            normalize=bad_normalize,
        )


async def test_invoke_async_normalize_error_preserves_cause():
    original = ValueError("bad value")

    async def fn() -> None:
        return None

    def bad_normalize(x: object) -> None:
        raise original

    with pytest.raises(ToolExecutionError) as exc_info:
        await invoke_async(
            fn,
            {},
            is_async=True,
            error_cls=ToolExecutionError,
            label="fn",
            normalize=bad_normalize,
        )

    assert exc_info.value.__cause__ is original
