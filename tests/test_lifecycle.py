"""
Tests for plugin lifecycle integration — the adapter layer's responsibility
for invoking on_startup and on_shutdown hooks stored by BridgeMCP.

Coverage:
  - _invoke_startup_hooks: registration order, abort on first exception
  - _invoke_shutdown_hooks: reverse order, continue after exception, logging
  - _with_lifecycle: startup → run_fn → shutdown sequencing
  - _with_lifecycle: startup exception prevents run_fn and shutdown
  - _with_lifecycle: run_fn exception still triggers shutdown
  - _with_lifecycle: no hooks → run_fn called directly
  - Integration: full plugin lifecycle via register_plugin
"""

from __future__ import annotations

import logging

import pytest

from bridgemcp import BridgeMCP
from bridgemcp.adapters.mcp import (
    _invoke_shutdown_hooks,
    _invoke_startup_hooks,
    _with_lifecycle,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app_with_hooks(
    *,
    startup_tags: list[str] | None = None,
    shutdown_tags: list[str] | None = None,
) -> tuple[BridgeMCP, list[str]]:
    """Return an app with named startup and/or shutdown hooks and a shared log."""
    app = BridgeMCP(name="test")
    log: list[str] = []

    for tag in startup_tags or []:

        async def _startup(a: BridgeMCP, *, _tag: str = tag) -> None:
            log.append(f"startup:{_tag}")

        app._startup_hooks.append(_startup)

    for tag in shutdown_tags or []:

        async def _shutdown(a: BridgeMCP, *, _tag: str = tag) -> None:
            log.append(f"shutdown:{_tag}")

        app._shutdown_hooks.append(_shutdown)

    return app, log


# ---------------------------------------------------------------------------
# _invoke_startup_hooks
# ---------------------------------------------------------------------------


async def test_startup_hooks_run_in_registration_order():
    app, log = _make_app_with_hooks(startup_tags=["A", "B", "C"])
    await _invoke_startup_hooks(app)
    assert log == ["startup:A", "startup:B", "startup:C"]


async def test_startup_hooks_empty_list_is_noop():
    app = BridgeMCP(name="test")
    await _invoke_startup_hooks(app)  # must not raise


async def test_startup_exception_aborts_subsequent_hooks():
    app = BridgeMCP(name="test")
    called = []

    async def hook_a(a: BridgeMCP) -> None:
        called.append("A")
        raise RuntimeError("startup failure")

    async def hook_b(a: BridgeMCP) -> None:
        called.append("B")

    app._startup_hooks.extend([hook_a, hook_b])

    with pytest.raises(RuntimeError, match="startup failure"):
        await _invoke_startup_hooks(app)

    assert called == ["A"]


async def test_startup_hook_receives_app():
    app = BridgeMCP(name="test")
    received = []

    async def capture(a: BridgeMCP) -> None:
        received.append(a)

    app._startup_hooks.append(capture)
    await _invoke_startup_hooks(app)
    assert received == [app]


# ---------------------------------------------------------------------------
# _invoke_shutdown_hooks
# ---------------------------------------------------------------------------


async def test_shutdown_hooks_run_in_reverse_registration_order():
    app, log = _make_app_with_hooks(shutdown_tags=["A", "B", "C"])
    await _invoke_shutdown_hooks(app)
    assert log == ["shutdown:C", "shutdown:B", "shutdown:A"]


async def test_shutdown_hooks_empty_list_is_noop():
    app = BridgeMCP(name="test")
    await _invoke_shutdown_hooks(app)  # must not raise


async def test_shutdown_exception_does_not_prevent_remaining_hooks():
    app = BridgeMCP(name="test")
    called = []

    async def hook_a(a: BridgeMCP) -> None:
        called.append("A")

    async def hook_b(a: BridgeMCP) -> None:
        called.append("B")
        raise RuntimeError("shutdown failure")

    async def hook_c(a: BridgeMCP) -> None:
        called.append("C")

    # Registration order A→B→C; reverse shutdown order C→B→A
    app._shutdown_hooks.extend([hook_a, hook_b, hook_c])

    await _invoke_shutdown_hooks(app)  # must not raise
    # C runs first (reverse), then B (fails, logged), then A
    assert called == ["C", "B", "A"]


async def test_shutdown_exception_is_logged(caplog: pytest.LogCaptureFixture):
    app = BridgeMCP(name="test")

    async def failing_hook(a: BridgeMCP) -> None:
        raise ValueError("hook error")

    app._shutdown_hooks.append(failing_hook)

    with caplog.at_level(logging.ERROR, logger="bridgemcp.adapters.mcp"):
        await _invoke_shutdown_hooks(app)

    assert "hook error" in caplog.text


async def test_shutdown_hook_receives_app():
    app = BridgeMCP(name="test")
    received = []

    async def capture(a: BridgeMCP) -> None:
        received.append(a)

    app._shutdown_hooks.append(capture)
    await _invoke_shutdown_hooks(app)
    assert received == [app]


# ---------------------------------------------------------------------------
# _with_lifecycle
# ---------------------------------------------------------------------------


def test_with_lifecycle_calls_startup_before_run_fn():
    """startup → run_fn order must be preserved."""
    app, log = _make_app_with_hooks(startup_tags=["A"])
    run_log: list[str] = []

    def run_fn() -> None:
        run_log.append("run")

    _with_lifecycle(app, run_fn)
    assert log == ["startup:A"]
    assert run_log == ["run"]


def test_with_lifecycle_calls_shutdown_after_run_fn():
    """run_fn → shutdown order must be preserved."""
    app, log = _make_app_with_hooks(shutdown_tags=["A"])
    run_log: list[str] = []

    def run_fn() -> None:
        run_log.append("run")

    _with_lifecycle(app, run_fn)
    assert run_log == ["run"]
    assert log == ["shutdown:A"]


def test_with_lifecycle_full_sequence():
    """startup A→B, run_fn, shutdown B→A."""
    app = BridgeMCP(name="test")
    events: list[str] = []

    async def startup_a(a: BridgeMCP) -> None:
        events.append("startup:A")

    async def startup_b(a: BridgeMCP) -> None:
        events.append("startup:B")

    async def shutdown_a(a: BridgeMCP) -> None:
        events.append("shutdown:A")

    async def shutdown_b(a: BridgeMCP) -> None:
        events.append("shutdown:B")

    app._startup_hooks.extend([startup_a, startup_b])
    app._shutdown_hooks.extend([shutdown_a, shutdown_b])

    _with_lifecycle(app, lambda: events.append("run"))

    assert events == ["startup:A", "startup:B", "run", "shutdown:B", "shutdown:A"]


def test_with_lifecycle_startup_exception_prevents_run_fn():
    app = BridgeMCP(name="test")
    run_called: list[bool] = []

    async def failing_startup(a: BridgeMCP) -> None:
        raise RuntimeError("startup failed")

    app._startup_hooks.append(failing_startup)

    with pytest.raises(RuntimeError, match="startup failed"):
        _with_lifecycle(app, lambda: run_called.append(True))

    assert run_called == []


def test_with_lifecycle_startup_exception_prevents_shutdown_hooks():
    """If startup aborts, no shutdown hooks run — nothing was initialised."""
    app = BridgeMCP(name="test")
    shutdown_called: list[bool] = []

    async def failing_startup(a: BridgeMCP) -> None:
        raise RuntimeError("startup failed")

    async def shutdown(a: BridgeMCP) -> None:
        shutdown_called.append(True)

    app._startup_hooks.append(failing_startup)
    app._shutdown_hooks.append(shutdown)

    with pytest.raises(RuntimeError):
        _with_lifecycle(app, lambda: None)

    assert shutdown_called == []


def test_with_lifecycle_run_fn_exception_triggers_shutdown():
    """A server crash must still trigger shutdown for clean resource release."""
    app, log = _make_app_with_hooks(shutdown_tags=["A"])

    def crashing_run() -> None:
        raise RuntimeError("server crashed")

    with pytest.raises(RuntimeError, match="server crashed"):
        _with_lifecycle(app, crashing_run)

    assert log == ["shutdown:A"]


def test_with_lifecycle_no_hooks_calls_run_fn():
    app = BridgeMCP(name="test")
    run_called: list[bool] = []

    _with_lifecycle(app, lambda: run_called.append(True))
    assert run_called == [True]


def test_with_lifecycle_startup_only_no_shutdown():
    app, log = _make_app_with_hooks(startup_tags=["A"])
    run_called: list[bool] = []

    _with_lifecycle(app, lambda: run_called.append(True))
    assert log == ["startup:A"]
    assert run_called == [True]


def test_with_lifecycle_shutdown_only_no_startup():
    app, log = _make_app_with_hooks(shutdown_tags=["A"])
    run_called: list[bool] = []

    _with_lifecycle(app, lambda: run_called.append(True))
    assert run_called == [True]
    assert log == ["shutdown:A"]


# ---------------------------------------------------------------------------
# Integration — full plugin lifecycle via register_plugin
# ---------------------------------------------------------------------------


def test_full_lifecycle_via_register_plugin():
    """End-to-end: plugins registered on app, hooks fired via _with_lifecycle."""
    app = BridgeMCP(name="test")
    events: list[str] = []

    class PluginA:
        def setup(self, a: BridgeMCP) -> None:
            events.append("setup:A")

        async def on_startup(self, a: BridgeMCP) -> None:
            events.append("startup:A")

        async def on_shutdown(self, a: BridgeMCP) -> None:
            events.append("shutdown:A")

    class PluginB:
        def setup(self, a: BridgeMCP) -> None:
            events.append("setup:B")

        async def on_startup(self, a: BridgeMCP) -> None:
            events.append("startup:B")

        async def on_shutdown(self, a: BridgeMCP) -> None:
            events.append("shutdown:B")

    app.register_plugin(PluginA())
    app.register_plugin(PluginB())

    _with_lifecycle(app, lambda: events.append("run"))

    assert events == [
        "setup:A",
        "setup:B",
        "startup:A",
        "startup:B",
        "run",
        "shutdown:B",
        "shutdown:A",
    ]


def test_lifecycle_plugin_without_hooks():
    """Plugin with no lifecycle hooks must not affect _with_lifecycle."""
    app = BridgeMCP(name="test")
    run_called: list[bool] = []

    class SimplePlugin:
        def setup(self, a: BridgeMCP) -> None:
            pass

    app.register_plugin(SimplePlugin())
    _with_lifecycle(app, lambda: run_called.append(True))
    assert run_called == [True]


def test_lifecycle_shutdown_exception_all_others_run():
    """Shutdown hook exception must not skip remaining hooks in the adapter."""
    app = BridgeMCP(name="test")
    events: list[str] = []

    class GoodPlugin:
        def setup(self, a: BridgeMCP) -> None:
            pass

        async def on_shutdown(self, a: BridgeMCP) -> None:
            events.append("good")

    class BadPlugin:
        def setup(self, a: BridgeMCP) -> None:
            pass

        async def on_shutdown(self, a: BridgeMCP) -> None:
            raise RuntimeError("bad plugin")

    # Registration order: GoodPlugin first, BadPlugin second.
    # Reverse shutdown order: BadPlugin shuts down first (raises), GoodPlugin still runs.
    app.register_plugin(GoodPlugin())
    app.register_plugin(BadPlugin())

    _with_lifecycle(app, lambda: None)  # must not raise

    assert events == ["good"]


async def test_startup_hooks_invoked_with_correct_app_reference():
    """Each hook must receive the app it was registered on, not a copy."""
    app = BridgeMCP(name="my-server")
    received: list[str] = []

    async def capture_name(a: BridgeMCP) -> None:
        received.append(a.name)

    app._startup_hooks.append(capture_name)
    await _invoke_startup_hooks(app)
    assert received == ["my-server"]
