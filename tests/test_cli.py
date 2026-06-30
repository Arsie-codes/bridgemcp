"""
Tests for BridgeMCP CLI behaviour: run_cli(), terminal detection, and
startup messages from run_stdio() / run_http().

run_cli() owns argument parsing; it delegates to run() or run_http()
without absorbing transport logic.  Tests confirm that delegation boundary
is respected, that --help/-h and --version/-V work correctly, and that
unknown flags produce a non-zero exit.

Terminal detection tests confirm that run_stdio() only writes to stderr
when stdin is a TTY, and that run_http() always writes to stderr.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bridgemcp import BridgeMCP

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _app(
    name: str = "test-server",
    version: str = "1.0.0",
    description: str | None = None,
) -> BridgeMCP:
    return BridgeMCP(name=name, version=version, description=description)


# ---------------------------------------------------------------------------
# run_cli — help / version flags
# ---------------------------------------------------------------------------


def test_run_cli_help_long_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    app = _app()
    with pytest.raises(SystemExit) as exc_info:
        app.run_cli(["--help"])
    assert exc_info.value.code == 0


def test_run_cli_help_short_exits_zero() -> None:
    app = _app()
    with pytest.raises(SystemExit) as exc_info:
        app.run_cli(["-h"])
    assert exc_info.value.code == 0


def test_run_cli_version_long_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    app = _app()
    with pytest.raises(SystemExit) as exc_info:
        app.run_cli(["--version"])
    assert exc_info.value.code == 0


def test_run_cli_version_short_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    app = _app()
    with pytest.raises(SystemExit) as exc_info:
        app.run_cli(["-V"])
    assert exc_info.value.code == 0


def test_run_cli_version_output_contains_name_and_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = _app(name="my-server", version="2.3.4")
    with pytest.raises(SystemExit):
        app.run_cli(["--version"])
    out = capsys.readouterr().out
    assert "my-server" in out
    assert "2.3.4" in out


def test_run_cli_version_short_output_same_as_long(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = _app(name="my-server", version="2.3.4")
    with pytest.raises(SystemExit):
        app.run_cli(["-V"])
    out = capsys.readouterr().out
    assert "my-server" in out
    assert "2.3.4" in out


def test_run_cli_help_includes_app_name(capsys: pytest.CaptureFixture[str]) -> None:
    app = _app(name="weather-server")
    with pytest.raises(SystemExit):
        app.run_cli(["--help"])
    out = capsys.readouterr().out
    assert "weather-server" in out


def test_run_cli_help_includes_description(capsys: pytest.CaptureFixture[str]) -> None:
    app = _app(description="Provides weather data.")
    with pytest.raises(SystemExit):
        app.run_cli(["--help"])
    out = capsys.readouterr().out
    assert "Provides weather data." in out


def test_run_cli_help_mentions_http_flag(capsys: pytest.CaptureFixture[str]) -> None:
    app = _app()
    with pytest.raises(SystemExit):
        app.run_cli(["--help"])
    out = capsys.readouterr().out
    assert "--http" in out


# ---------------------------------------------------------------------------
# run_cli — unknown flags
# ---------------------------------------------------------------------------


def test_run_cli_unknown_flag_exits_nonzero() -> None:
    app = _app()
    with pytest.raises(SystemExit) as exc_info:
        app.run_cli(["--unknown-flag"])
    assert exc_info.value.code != 0


def test_run_cli_unknown_flag_exits_with_code_2() -> None:
    app = _app()
    with pytest.raises(SystemExit) as exc_info:
        app.run_cli(["--typo"])
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# run_cli — transport delegation
# ---------------------------------------------------------------------------


def test_run_cli_no_args_calls_run(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    called: list[str] = []
    monkeypatch.setattr(app, "run", lambda: called.append("run"))
    app.run_cli([])
    assert called == ["run"]


def test_run_cli_http_flag_calls_run_http(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        app, "run_http", lambda *, host, port: calls.append((host, port))
    )
    app.run_cli(["--http"])
    assert calls == [("127.0.0.1", 8000)]


def test_run_cli_http_default_host(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    calls: list[str] = []
    monkeypatch.setattr(app, "run_http", lambda *, host, port: calls.append(host))
    app.run_cli(["--http"])
    assert calls == ["127.0.0.1"]


def test_run_cli_http_default_port(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    calls: list[int] = []
    monkeypatch.setattr(app, "run_http", lambda *, host, port: calls.append(port))
    app.run_cli(["--http"])
    assert calls == [8000]


def test_run_cli_http_custom_host(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    calls: list[str] = []
    monkeypatch.setattr(app, "run_http", lambda *, host, port: calls.append(host))
    app.run_cli(["--http", "--host", "0.0.0.0"])
    assert calls == ["0.0.0.0"]


def test_run_cli_http_custom_port(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    calls: list[int] = []
    monkeypatch.setattr(app, "run_http", lambda *, host, port: calls.append(port))
    app.run_cli(["--http", "--port", "9000"])
    assert calls == [9000]


def test_run_cli_http_custom_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        app, "run_http", lambda *, host, port: calls.append((host, port))
    )
    app.run_cli(["--http", "--host", "0.0.0.0", "--port", "9000"])
    assert calls == [("0.0.0.0", 9000)]


def test_run_cli_delegates_not_absorbs_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_cli() must call run() and run_http() — not bypass them."""
    app = _app()
    run_called: list[bool] = []
    run_http_called: list[bool] = []
    monkeypatch.setattr(app, "run", lambda: run_called.append(True))
    monkeypatch.setattr(
        app, "run_http", lambda *, host, port: run_http_called.append(True)
    )
    app.run_cli([])
    assert run_called == [True]
    assert run_http_called == []

    app.run_cli(["--http"])
    assert run_http_called == [True]


def test_run_cli_args_param_overrides_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit args= must be used instead of sys.argv."""
    app = _app()
    called: list[str] = []
    monkeypatch.setattr(app, "run", lambda: called.append("run"))
    # sys.argv contains pytest arguments which would fail argparse if parsed
    app.run_cli([])
    assert called == ["run"]


# ---------------------------------------------------------------------------
# run_stdio — terminal detection (startup message)
# ---------------------------------------------------------------------------


def test_run_stdio_prints_to_stderr_when_tty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bridgemcp.adapters import mcp as adapter

    app = _app(name="my-server", version="9.9.9")
    tty_stdin = MagicMock()
    tty_stdin.isatty.return_value = True
    monkeypatch.setattr("sys.stdin", tty_stdin)
    monkeypatch.setattr(adapter, "build_mcp_server", lambda a: MagicMock())
    monkeypatch.setattr(adapter, "_with_lifecycle", lambda a, fn: None)

    adapter.run_stdio(app)

    err = capsys.readouterr().err
    assert "my-server" in err
    assert "9.9.9" in err


def test_run_stdio_mentions_stdio_when_tty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bridgemcp.adapters import mcp as adapter

    app = _app()
    tty_stdin = MagicMock()
    tty_stdin.isatty.return_value = True
    monkeypatch.setattr("sys.stdin", tty_stdin)
    monkeypatch.setattr(adapter, "build_mcp_server", lambda a: MagicMock())
    monkeypatch.setattr(adapter, "_with_lifecycle", lambda a, fn: None)

    adapter.run_stdio(app)

    err = capsys.readouterr().err
    assert "stdio" in err.lower()


def test_run_stdio_no_stderr_when_not_tty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bridgemcp.adapters import mcp as adapter

    app = _app()
    pipe_stdin = MagicMock()
    pipe_stdin.isatty.return_value = False
    monkeypatch.setattr("sys.stdin", pipe_stdin)
    monkeypatch.setattr(adapter, "build_mcp_server", lambda a: MagicMock())
    monkeypatch.setattr(adapter, "_with_lifecycle", lambda a, fn: None)

    adapter.run_stdio(app)

    assert capsys.readouterr().err == ""


def test_run_stdio_stdout_untouched_when_tty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bridgemcp.adapters import mcp as adapter

    app = _app()
    tty_stdin = MagicMock()
    tty_stdin.isatty.return_value = True
    monkeypatch.setattr("sys.stdin", tty_stdin)
    monkeypatch.setattr(adapter, "build_mcp_server", lambda a: MagicMock())
    monkeypatch.setattr(adapter, "_with_lifecycle", lambda a, fn: None)

    adapter.run_stdio(app)

    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# run_http — startup message (always printed)
# ---------------------------------------------------------------------------


def test_run_http_always_prints_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bridgemcp.adapters import mcp as adapter

    app = _app(name="my-server", version="9.9.9")
    monkeypatch.setattr(adapter, "build_mcp_server", lambda a, **kw: MagicMock())
    monkeypatch.setattr(adapter, "_with_lifecycle", lambda a, fn: None)

    adapter.run_http(app, host="127.0.0.1", port=8000)

    err = capsys.readouterr().err
    assert "my-server" in err
    assert "9.9.9" in err


def test_run_http_stderr_includes_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bridgemcp.adapters import mcp as adapter

    app = _app()
    monkeypatch.setattr(adapter, "build_mcp_server", lambda a, **kw: MagicMock())
    monkeypatch.setattr(adapter, "_with_lifecycle", lambda a, fn: None)

    adapter.run_http(app, host="0.0.0.0", port=9000)

    err = capsys.readouterr().err
    assert "0.0.0.0" in err
    assert "9000" in err


def test_run_http_stdout_untouched(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bridgemcp.adapters import mcp as adapter

    app = _app()
    monkeypatch.setattr(adapter, "build_mcp_server", lambda a, **kw: MagicMock())
    monkeypatch.setattr(adapter, "_with_lifecycle", lambda a, fn: None)

    adapter.run_http(app, host="127.0.0.1", port=8000)

    assert capsys.readouterr().out == ""
