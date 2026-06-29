# BridgeMCP Architecture

This document is the canonical reference for contributors and maintainers. It explains **why** the framework is designed the way it is, not merely what the code does.

---

## Philosophy

BridgeMCP exists to answer one question: *how should a Python developer expose application logic to an AI client without coupling their code to a protocol they don't control?*

The Model Context Protocol defines three primitives — Tools, Resources, and Prompts. Every MCP server must speak this protocol. But the protocol will evolve, the SDK will be updated, and the transport options will multiply. A framework that ties business logic directly to protocol types creates a maintenance burden that grows with every SDK release.

BridgeMCP's answer is **strict layering**: your handlers are plain Python functions, the framework's registries are plain Python data structures, and the protocol translation happens exclusively in a single adapter module. The protocol could be swapped entirely without touching a single handler or registry.

A secondary philosophy: **minimal core, extensible ecosystem**. Every feature that is not universally required — logging, metrics, authentication, database integration, caching — belongs in a plugin, not in the framework. The core provides the contracts; plugins fulfill specific requirements.

---

## Core Design Principles

### 1. Transport independence

`BridgeMCP` and all registry classes have zero knowledge of MCP, FastMCP, or any protocol type. They deal in plain Python types: `str`, `dict`, `list`, `bytes`, `Callable`. A server without the `mcp` extra installed can register tools, call them, and test them end-to-end. No protocol knowledge required until `app.run()`.

### 2. Single public entry point

`BridgeMCP` in `application.py` is the entire public surface. Every decorator, invocation method, introspection method, and lifecycle hook is accessed through one object. There is no reason for a developer building an MCP server to import from any internal module.

### 3. Protocol knowledge is quarantined

Everything that touches FastMCP — type conversions, SDK-specific parameters, `__wrapped__` chain following, the `mcp_server.version` internal attribute — lives exclusively in `adapters/mcp.py`. This is enforced by convention and verified by the Graphify dependency graph. If a PR introduces an import of `mcp` or `fastmcp` anywhere outside `adapters/`, it should be rejected.

### 4. Composition over configuration

Middleware is composed with `build_chain()`. Plugins extend functionality through `setup(app)`. Neither approach requires subclassing `BridgeMCP` or modifying the framework internals. A plugin that adds authentication adds middleware; a plugin that adds logging adds middleware; a plugin that connects to Redis opens the connection in `on_startup`. The core does not need to know any of this.

### 5. Errors are typed and chained

Every failure mode has its own exception class. The original exception is always available via `__cause__`. This is not ceremony — it makes a meaningful difference when a tool handler raises deep inside user code and a middleware layer needs to distinguish between a `ToolNotFoundError` (a framework error the developer should fix) and a `ToolExecutionError` (a handler error that may need retry logic or user-facing messaging).

### 6. Duck typing for extensibility contracts

`register_plugin` accepts any object with a `setup(app)` method. Lifecycle hooks are collected with `getattr`, not `isinstance`. The `Plugin` base class exists purely for documentation and IDE autocompletion, not as a gate. This means a plugin can be a class, an instance, a function-based object, or anything else — the framework does not care.

---

## Layered Architecture

```
┌─────────────────────────────────────────┐
│   External caller (developer code)      │
│   app.call("greet", name="Alice")       │
└────────────────────┬────────────────────┘
                     │ public API
┌────────────────────▼────────────────────┐
│   BridgeMCP  (application.py)           │
│   Registry lookup + middleware dispatch │
└──────────┬──────────────────────────────┘
           │ InvocationContext
┌──────────▼──────────────────────────────┐
│   Middleware chain  (middleware.py)      │
│   build_chain([mw1, mw2], terminus)     │
└──────────┬──────────────────────────────┘
           │ ctx
┌──────────▼──────────────────────────────┐
│   Execution pipeline  (execution.py)    │
│   invoke_sync / invoke_async            │
└──────────┬──────────────────────────────┘
           │ fn(**kwargs)
┌──────────▼──────────────────────────────┐
│   Handler  (developer's function)       │
│   def greet(name: str) -> str: ...      │
└─────────────────────────────────────────┘

Transport layer (separate execution path):

┌─────────────────────────────────────────┐
│   BridgeMCP.run() / run_http()          │
└────────────────────┬────────────────────┘
                     │ delegates
┌────────────────────▼────────────────────┐
│   adapters/mcp.py                       │
│   build_mcp_server() → FastMCP          │
│   _with_lifecycle() for hooks           │
└────────────────────┬────────────────────┘
                     │ wraps handlers as
                     │ FastMCP tools/resources/prompts
┌────────────────────▼────────────────────┐
│   FastMCP / MCP SDK  (external)         │
└─────────────────────────────────────────┘
```

---

## Module Responsibilities

### `bridgemcp/application.py` — `BridgeMCP`

The single public entry point. Responsibilities:

- **Decorator registration**: `@app.tool`, `@app.resource(uri=...)`, `@app.prompt`
- **Invocation**: `call()`, `acall()`, `read_resource()`, `aread_resource()`, `render_prompt()`, `arender_prompt()`
- **Introspection**: `list_tools()`, `list_resources()`, `list_prompts()`
- **Middleware registration**: `add_middleware()`, `@app.middleware`
- **Plugin registration**: `register_plugin()`
- **Transport delegation**: `run()`, `run_http()` — delegates to `adapters/mcp.py`
- **Chain execution helpers**: `_run_chain()` (async), `_run_sync_chain()` (sync)

`BridgeMCP` delegates **all storage** to the three registries and **all invocation mechanics** to `execution.py`. Its own code is coordination logic only.

### `bridgemcp/execution.py` — Execution pipeline

The shared handler invocation pipeline. Responsibilities:

- `invoke_sync(fn, kwargs, *, error_cls, label, normalize=None, normalize_error=...)` — calls a sync handler, catches exceptions into `error_cls`, optionally normalizes the output
- `invoke_async(fn, kwargs, *, is_async, error_cls, label, normalize=None, normalize_error=...)` — same for async context; handles both sync and async handlers

This module is intentionally narrow. It does **not** know about registries, protocols, middleware, or configuration. Adding any of those would be a responsibility violation.

### `bridgemcp/middleware.py` — Middleware types and composition

Zero framework imports. Responsibilities:

- `InvocationContext` dataclass — carries `primitive`, `name`, `kwargs`, and `metadata` through the chain
- `Next` — type alias for the next callable in the chain
- `MiddlewareFn` — type alias for a middleware function
- `build_chain(middleware, terminus)` — composes a list of middleware around a terminal handler

The default-argument trick in `build_chain` (`_mw=mw, _inner=inner`) is intentional: Python closures capture variables by reference in loops, so without the trick every step in the chain would reference the same (final) values of `mw` and `inner`.

### `bridgemcp/plugin.py` — Plugin contract

Zero runtime framework imports (`BridgeMCP` is imported under `TYPE_CHECKING` only). Responsibilities:

- `Plugin` base class with no-op defaults for all three lifecycle methods
- Optional metadata attributes: `name`, `version`, `description`, `requires`
- Documentation of the duck-typing contract: any object with `setup(app)` is valid

### `bridgemcp/tools/`, `bridgemcp/resources/`, `bridgemcp/prompts/` — Registry packages

Each package follows the same pattern:

| File | Contents |
|---|---|
| `__init__.py` | Re-exports the public record type (`Tool`, `Resource`, `Prompt`) |
| `registry.py` | Immutable record dataclass + registry class |
| `normalize.py` *(resources, prompts only)* | Output normalization logic |

Registries are keyed by name or URI. Duplicate detection happens at registration time. The `list()` method preserves insertion order (Python dict iteration order is stable since 3.7).

**Why the normalize modules?** Resources can return `str`, `bytes`, or arbitrary objects. Prompts can return `str`, `PromptMessage`, or `list[PromptMessage]`. The normalization logic belongs in the primitive package, not in `execution.py` (which should not know what a `PromptMessage` is) and not in `application.py` (which should not be cluttered with serialization logic).

### `bridgemcp/config/` — Configuration

`BridgeConfig` is currently an empty Pydantic `frozen=True` model. It exists as a stable, versioned extension point. When a future feature genuinely requires user-configurable framework behavior, it belongs here. Configuration always lives in one place, passed once at construction time, and never mutated.

**Why empty now?** The only field that was ever added (`log_level`) was removed because it made a promise the framework didn't keep: the value was validated but never read. Configuration that controls behavior no one observes is worse than no configuration at all.

### `bridgemcp/exceptions.py` — Exception hierarchy

```
BridgeMCPError
├── RegistrationError          # startup-time errors
│   ├── ToolRegistrationError
│   ├── ResourceRegistrationError
│   └── PromptRegistrationError
├── NotFoundError              # runtime lookup failures
│   ├── ToolNotFoundError
│   ├── ResourceNotFoundError
│   └── PromptNotFoundError
├── ExecutionError             # runtime handler failures
│   ├── ToolExecutionError
│   ├── ResourceExecutionError
│   └── PromptExecutionError
└── ConfigurationError        # framework configuration errors
```

Every execution error wraps the original exception via `raise error_cls(...) from exc`. The original is always accessible via `__cause__`.

**Catch hierarchy design**: middleware that wants to log all failures catches `BridgeMCPError`. Middleware that wants to retry transient handler failures catches `ExecutionError`. Client code that wants to distinguish "tool not found" from "tool crashed" catches `ToolNotFoundError` vs `ToolExecutionError`.

### `bridgemcp/adapters/mcp.py` — Protocol adapter

The only file that imports `mcp` or `fastmcp`. Responsibilities:

- `build_mcp_server(app)` — constructs a `FastMCP` instance from a `BridgeMCP` app
- `run_stdio(app)` / `run_http(app, *, host, port)` — wrap `build_mcp_server()` with `_with_lifecycle()`
- `_register_tools/resources/prompts` — iterate the registries and register each primitive
- `_register_tool/resource/prompt` — wrap individual handlers and register with FastMCP
- `_invoke_startup_hooks` / `_invoke_shutdown_hooks` — async hook invocation
- `_with_lifecycle(app, run_fn)` — orchestrates startup → run_fn → shutdown

---

## Execution Pipeline

When a developer calls `app.call("greet", name="Alice")`:

1. **Registry lookup** — `ToolRegistry.get("greet")` → `Tool` object or `ToolNotFoundError`
2. **Async guard** — if `tool.is_async`, raise immediately (use `acall()` instead)
3. **Context creation** — `InvocationContext(primitive="tool", name="greet", kwargs={"name": "Alice"})`
4. **Chain execution** — `_run_sync_chain(ctx, direct)`:
   - *Fast path (no middleware)*: calls `direct(ctx)` directly, zero overhead
   - *Slow path (middleware registered)*: wraps `direct` in an async terminus, runs via `asyncio.run()`
5. **Handler invocation** — `invoke_sync(tool.fn, ctx.kwargs, error_cls=ToolExecutionError, label="greet")`
6. **Return** — raw result returned to the caller unchanged

The async path (`acall()`) is identical except steps 2 and 4 are replaced by a single `await _run_chain(ctx, terminus)` where the terminus awaits `invoke_async`.

---

## Middleware Pipeline

Middleware is composed at call time, not at registration time:

```python
# Registration
app.add_middleware(logging_mw)
app.add_middleware(timing_mw)

# At call time, build_chain produces:
# logging_mw → timing_mw → terminus
```

First registered = outermost. This mirrors ASP.NET Core and Django middleware conventions.

`build_chain` is O(n) and allocation-free beyond the closure list. The fast path in `_run_chain` / `_run_sync_chain` skips `build_chain` entirely when `self._middleware` is empty — essential for production performance when no middleware is registered.

**Sync/async bridging**: middleware is always async. Synchronous invocation methods (`call()`, `read_resource()`, `render_prompt()`) bridge to async via `asyncio.run()` when middleware is present. This requires that the calling thread has no running event loop — which is the correct assumption for synchronous server code. Calling a sync method from inside a running event loop is already incorrect; the async methods exist precisely for that case.

---

## Plugin Architecture

A plugin is any object with a `setup(app: BridgeMCP) -> None` method. That method receives the application and may call any public API on it — register tools, resources, prompts, and middleware.

```python
class MetricsPlugin:
    def setup(self, app):
        app.add_middleware(self._metrics_middleware)

    async def on_startup(self, app):
        self._client = MetricsClient(endpoint="...")

    async def on_shutdown(self, app):
        await self._client.flush()
        await self._client.close()

    async def _metrics_middleware(self, ctx, next):
        start = time.perf_counter()
        try:
            return await next(ctx)
        finally:
            elapsed = time.perf_counter() - start
            self._client.record(ctx.primitive, ctx.name, elapsed)
```

The `Plugin` base class provides no-op defaults for all three lifecycle methods. It is never checked with `isinstance`. Its only purpose is documentation and IDE autocompletion.

**Why duck typing?** A plugin that is an instance method of a configuration object, a module-level singleton, or a dynamically-constructed class should all work without modification. Requiring inheritance creates accidental coupling between the plugin and the framework.

---

## Adapter Architecture

The adapter's job is translation, not coordination. Every translation decision lives here:

| Problem | Solution in the adapter |
|---|---|
| FastMCP schema generation requires parameter annotations | `functools.wraps` copies `__wrapped__`, `__annotations__`, `__doc__`; FastMCP's `func_metadata` follows `__wrapped__` |
| Resources must not appear as URI templates | Do NOT use `functools.wraps` on resource handlers (it would propagate the original signature, and FastMCP would detect parameters and treat the resource as a template) |
| FastMCP does not expose a public `version` parameter | Set `server._mcp_server.version = app.version` via the internal attribute (flagged with a comment to revisit when FastMCP adds a public API) |
| Prompt messages need MCP wire format | Convert each `PromptMessage(role, content)` to `{"role": ..., "content": {"type": "text", "text": ...}}` |

The adapter is the only place these decisions are made. If FastMCP changes its internal API, exactly one file changes.

**Known architectural constraint**: `build_mcp_server()` runs before startup hooks. Tools registered during `on_startup()` will not appear in the server. Resolving this requires FastMCP's lifespan integration (passing a lifespan context manager to `FastMCP()`). This should be addressed when a real plugin requires it, not preemptively.

---

## Registry Design

All three registries (`ToolRegistry`, `ResourceRegistry`, `PromptRegistry`) follow the same design:

- **Keyed by unique identifier** — tool name, resource URI, prompt name
- **Duplicate detection at registration time** — raises a typed `RegistrationError` before the server starts
- **Insertion order preserved** — `list()` returns in registration order
- **Immutable records** — `Tool`, `Resource`, `Prompt` are `@dataclass(frozen=True)`

The registry-record split is intentional. The record is a value object: pure data, no behavior, no methods. The registry is the container: storage and lookup only. Neither knows about the other's callers.

---

## Why FastMCP is Isolated

FastMCP is a production-quality MCP server implementation. It does one thing well: receive MCP protocol messages and dispatch them to registered handlers. BridgeMCP does not want to reimplement that.

But FastMCP's API may change between releases. It has internal attributes that BridgeMCP touches (`_mcp_server.version`). Its schema generation behavior is tied to how it reads `inspect.signature`. These are implementation details, not contracts.

If BridgeMCP let FastMCP types leak into `application.py` or the registries, every FastMCP major release would require changes throughout the framework. By quarantining FastMCP in `adapters/mcp.py`:

- FastMCP can be updated without touching the framework core
- A hypothetical `adapters/grpc.py` can be added without modifying any existing code
- Tests for `BridgeMCP`, the registries, the middleware, and the execution pipeline run without the `mcp` package installed

---

## Public API Guarantees

The following are **stable public contracts**. Changes to these require a major version bump:

```
# Construction
BridgeMCP(name, version, description, config)

# Decorators
@app.tool
@app.tool(name=..., description=...)
@app.resource(uri=..., name=..., description=..., mime_type=...)
@app.prompt
@app.prompt(name=..., description=...)

# Invocation (sync)
app.call(tool_name, **kwargs) -> Any
app.read_resource(uri) -> ResourceContent
app.render_prompt(name, **kwargs) -> list[PromptMessage]

# Invocation (async)
await app.acall(tool_name, **kwargs) -> Any
await app.aread_resource(uri) -> ResourceContent
await app.arender_prompt(name, **kwargs) -> list[PromptMessage]

# Introspection
app.list_tools() -> list[Tool]
app.list_resources() -> list[Resource]
app.list_prompts() -> list[Prompt]

# Middleware
app.add_middleware(fn: MiddlewareFn) -> None
@app.middleware

# Plugins
app.register_plugin(plugin: Any) -> None

# Transport
app.run() -> None
app.run_http(*, host, port) -> None

# Configuration
BridgeConfig()

# Middleware types
InvocationContext(primitive, name, kwargs, metadata)
MiddlewareFn
Next

# Plugin base class
Plugin.setup(app)
Plugin.on_startup(app)
Plugin.on_shutdown(app)

# Exception hierarchy
BridgeMCPError
RegistrationError / ToolRegistrationError / ResourceRegistrationError / PromptRegistrationError
NotFoundError / ToolNotFoundError / ResourceNotFoundError / PromptNotFoundError
ExecutionError / ToolExecutionError / ResourceExecutionError / PromptExecutionError
ConfigurationError

# Record types
Tool(name, fn, description, signature, return_annotation, is_async)
Resource(uri, name, fn, description, mime_type, is_async)
ResourceContent(content, mime_type)
Prompt(name, fn, description, arguments, is_async)
PromptMessage(role, content)
PromptArgument(name, description, required)
```

The following are **internal** and carry no stability guarantee:
- `app._tool_registry`, `app._resource_registry`, `app._prompt_registry`
- `app._middleware`, `app._plugins`, `app._startup_hooks`, `app._shutdown_hooks`
- `app._run_chain()`, `app._run_sync_chain()`
- `adapters/mcp.py`: `_register_*`, `_invoke_*`, `_with_lifecycle`, `build_mcp_server` *(used in tests but not public API)*
- All `__pycache__` contents and internal module structure

---

## What Belongs Inside the Framework Core

The core should only grow when a requirement meets **all three** of the following criteria:

1. **Universal** — every BridgeMCP server would benefit from it, not just some
2. **Protocol-intrinsic** — it cannot be implemented as a plugin without special-casing inside the framework
3. **Stable** — the requirement is clear enough to define a public API contract for it

Examples of what that means in practice:

| Feature | Inside core? | Reason |
|---|---|---|
| Tool/Resource/Prompt primitives | Yes | Protocol-intrinsic and universal |
| Middleware chain | Yes | Cannot be a plugin without special-casing in application.py |
| Exception hierarchy | Yes | Required for middleware and caller error handling |
| Logging | No | Not universal; a plugin; belongs to each operator |
| Authentication | No | Not universal; transport-specific; a plugin |
| Metrics | No | Not universal; depends on operator's observability stack |
| Rate limiting | No | Middleware plugin |
| Retry logic | No | Middleware plugin |
| Database integration | No | Plugin; varies by stack |
| URI template resources | Maybe | Requires protocol introspection; evaluate when needed |
| Streaming responses | Maybe | Protocol-intrinsic if MCP adds it; evaluate at that time |

---

## What Should Always Be a Plugin

Any feature that answers yes to any of the following is a plugin, not a framework feature:

- Does it depend on infrastructure that differs between deployments? (databases, caches, queues)
- Does it require configuration that varies per operator? (log levels, auth secrets, rate limits)
- Could two servers reasonably disagree on whether they want it at all? (logging, metrics)
- Does it require a third-party dependency that not all servers need?

The plugin system is the correct answer to all of these. The middleware chain is powerful enough to implement logging, metrics, authentication, tracing, rate limiting, retry, and validation without any framework changes.

---

## Versioning Philosophy

BridgeMCP follows [Semantic Versioning](https://semver.org/):

- **Patch** (`0.1.x`) — bug fixes that do not change any public behavior
- **Minor** (`0.x.0`) — additive changes to the public API (new methods, new optional parameters, new record fields with backward-compatible defaults)
- **Major** (`x.0.0`) — breaking changes to the public API

The list of public contracts above is the reference for what constitutes a breaking change. Internal implementation details (`_` prefixed names, module structure below the public import paths) may change in minor releases.

Because the framework is in `0.x`, a `0.y.0` release may technically contain breaking changes per semver convention. In practice, breaking changes should still be minimized and documented explicitly in the CHANGELOG.

---

## Long-Term Maintenance Philosophy

**Resist accretion.** The greatest long-term risk to this framework is the gradual accumulation of features that individually seem reasonable but collectively create an unmaintainable surface. Every addition to the core should be weighed against the option of "implement this as a plugin instead."

**Prefer ecosystem growth over core growth.** A rich plugin ecosystem is more valuable than a larger framework. The plugin system exists precisely to make this possible without framework changes.

**Treat the dependency graph as a test.** The Graphify knowledge graph is run after every implementation phase. Any increase in edges between previously-separate modules, any new coupling from a low-level module to a high-level one, and any import cycles are architectural regressions — not cosmetic issues.

**The adapter is the escape valve.** When the MCP SDK adds a new capability (streaming, sampling, roots), the correct place to add it is the adapter. The core should not need to change unless the new capability requires a new primitive or a new invocation method.

**Keep the core boring.** The execution pipeline, the registries, the middleware composition, and the exception hierarchy should not change between releases. When contributors propose changes to these, ask whether the same outcome can be achieved in a plugin. Usually the answer is yes.
