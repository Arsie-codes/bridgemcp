# Changelog

All notable changes to BridgeMCP are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.2.0] — 2026-06-29

First stable public release. The core architecture is frozen.

This release expands the framework far beyond the 0.1.0a1 alpha (which covered
Tools only) to include all three MCP primitives, async invocation, a middleware
pipeline, and a plugin system with lifecycle hooks. The public API is now
considered stable under the versioning policy described in `GOVERNANCE.md`.

### Added

**Resources**
- `@app.resource(uri=...)` decorator (bare and keyword-argument forms)
- `app.read_resource(uri)` and `await app.aread_resource(uri)` — sync and async invocation
- `app.list_resources()` — returns `list[Resource]` in registration order
- `ResourceRegistry`, `Resource`, and `ResourceContent` dataclasses
- Content normalization: `str`, `bytes`, `int`, `float`, `bool`, and arbitrary objects
  are all coerced to a serialized `ResourceContent`
- `ResourceNotFoundError`, `ResourceRegistrationError`, `ResourceExecutionError`

**Prompts**
- `@app.prompt` decorator (bare and keyword-argument forms)
- `app.render_prompt(name, **kwargs)` and `await app.arender_prompt(name, **kwargs)`
- `app.list_prompts()` — returns `list[Prompt]` in registration order
- `PromptRegistry`, `Prompt`, `PromptMessage`, `PromptArgument` dataclasses
- Return-value normalization: `str`, `PromptMessage`, and `list[PromptMessage]` are all accepted
- `PromptNotFoundError`, `PromptRegistrationError`, `PromptExecutionError`

**Async invocation**
- `await app.acall(tool_name, **kwargs)` — async tool invocation (handles both sync and async handlers)
- `await app.aread_resource(uri)` — async resource invocation
- `await app.arender_prompt(name, **kwargs)` — async prompt invocation

**Middleware**
- `app.add_middleware(fn)` and `@app.middleware` decorator
- `InvocationContext` dataclass — carries `primitive`, `name`, `kwargs`, and `metadata` through the chain
- `build_chain(middleware, terminus)` — ASP.NET Core-style functional composition
- Middleware applies to all six invocation methods (three sync, three async)
- Sync invocation fast path: no event loop overhead when no middleware is registered

**Plugin system**
- `app.register_plugin(plugin)` — duck-typed; any object with `setup(app)` is valid
- `Plugin` base class — optional convenience with no-op lifecycle defaults
- Optional plugin metadata: `name`, `version`, `description`, `requires`
- Startup hooks (`on_startup`) run in registration order before the server starts
- Shutdown hooks (`on_shutdown`) run in reverse order after the server stops;
  exceptions are logged without aborting remaining hooks

**Shared execution pipeline**
- `execution.py` — `invoke_sync` and `invoke_async` shared by all three primitives
- Exception chaining preserved on all execution errors (`__cause__`)
- Optional normalization hook applied after handler return

**Documentation**
- `ARCHITECTURE.md` — canonical reference explaining why the framework is designed as it is
- `GOVERNANCE.md` — API stability policy, versioning, deprecation, and plugin policy
- `CONTRIBUTING.md` updated with full contribution workflow
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, GitHub issue templates and PR template

### Changed

- `app.list_tools()` now returns `list[Tool]` instead of `list[str]`, consistent with
  `list_resources()` and `list_prompts()`
- `BridgeConfig.log_level` removed; logging configuration belongs in a plugin, not the core
- Exception hierarchy example in README updated to cover all three primitives
- Architecture diagram updated to include all modules
- CI workflow updated to install `bridgemcp[mcp,dev]` so adapter tests run in CI

### Fixed

- Full test suite: 415 tests, 100% pass rate (up from 67 in 0.1.0a1)
- Adapter tests were silently skipped in CI — now run with `mcp` extra installed

### Known limitations

- No authentication support for the HTTP transport.
- Async resources opened in plugin `on_startup()` hooks cannot be shared with
  request handlers because startup and the FastMCP server run in separate event loops.

---

## [0.1.0a1] — 2026-06-28

Internal alpha. Tools only. Not published to PyPI.

### Added

- `BridgeMCP` application class
- `@app.tool` decorator (bare and keyword-argument forms)
- `app.call(tool_name, **kwargs)` for direct tool invocation
- `BridgeConfig` (Pydantic, frozen)
- `ToolRegistry`, `Tool` frozen dataclass
- `BridgeMCPError` exception hierarchy — Tools only
- `app.run()` (stdio) and `app.run_http()` (HTTP/SSE)
- `build_mcp_server(app)` — programmatic FastMCP access
- 67 tests

[0.2.0]: https://github.com/Arsie-codes/bridgemcp/releases/tag/v0.2.0
[0.1.0a1]: https://github.com/Arsie-codes/bridgemcp/releases/tag/v0.1.0-alpha
