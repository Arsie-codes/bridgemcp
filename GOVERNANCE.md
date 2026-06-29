# BridgeMCP Governance

This document defines the project's philosophy, stability policies, and long-term maintenance goals. It is the canonical reference for decisions about what belongs in the framework, how the API evolves, and how the community participates.

---

## Project Philosophy

BridgeMCP exists to make it easy to expose Python application logic to AI clients through the Model Context Protocol, without coupling that logic to the protocol.

The framework's purpose is to be a stable, minimal foundation for an ecosystem of plugins and integrations. The core is intentionally small so that it can remain stable indefinitely. Everything that does not belong in every MCP server belongs in a plugin.

**The framework succeeds when you never have to think about it.** You write a Python function, decorate it with `@app.tool`, and BridgeMCP handles the rest. When you need observability, authentication, or database integration, you install a plugin. The framework itself stays out of the way.

---

## API Stability Policy

BridgeMCP's public API is defined in `ARCHITECTURE.md` under "Public API Guarantees." Every name in that list is a stable public contract.

**What is stable:**
- All public methods on `BridgeMCP`
- All decorator forms (`@app.tool`, `@app.resource`, `@app.prompt`, `@app.middleware`)
- All record types (`Tool`, `Resource`, `ResourceContent`, `Prompt`, `PromptMessage`, `PromptArgument`)
- All middleware types (`InvocationContext`, `MiddlewareFn`, `Next`, `build_chain`)
- The `Plugin` base class and its three lifecycle methods
- The full exception hierarchy
- `BridgeConfig`

**What is not stable:**
- Names beginning with `_` anywhere in the package
- Internal module structure below the public import paths (`bridgemcp.tools.registry` internals, etc.)
- `adapters/mcp.py` private functions (`_register_*`, `_invoke_*`, `_with_lifecycle`)
- `build_mcp_server` (accessible but not guaranteed to remain public)

If you use a private name in a plugin, your plugin may break on patch releases without notice.

---

## Semantic Versioning Policy

BridgeMCP follows [Semantic Versioning 2.0.0](https://semver.org/):

| Version increment | Meaning |
|---|---|
| **Patch** (`0.2.x`) | Bug fixes that do not change any public behavior. No migration required. |
| **Minor** (`0.x.0`) | Additive public API changes: new optional parameters, new record fields with backward-compatible defaults, new methods. Existing code continues to work unchanged. |
| **Major** (`x.0.0`) | Breaking changes to the public API. A migration guide is published with the release. |

While the project is in `0.x`, a minor version increment (`0.2.0` → `0.3.0`) may technically include breaking changes per semver convention. In practice, **BridgeMCP treats `0.x` minor versions as non-breaking** and reserves breaking changes for a `1.0.0` release. Any exception to this will be flagged explicitly in the CHANGELOG as a breaking change.

The first `1.0.0` release will happen when the project has at least six months of public usage with no major API changes required.

---

## Deprecation Policy

No public API will be removed without going through a two-release deprecation cycle:

1. **Deprecation release** — the old name remains fully functional. A `DeprecationWarning` is emitted at import or call time. The CHANGELOG documents the old name, the new name, and the removal target version.
2. **Removal release** — the old name is removed. The removal happens no sooner than one minor version after the deprecation.

Example: if `app.call()` were renamed in `0.3.0`, the old name would emit a `DeprecationWarning` in `0.3.0` and be removed in `0.4.0` at the earliest.

Bug fixes that change behavior to match documented behavior are not treated as breaking changes, even if existing code relied on the incorrect behavior.

---

## Plugin Policy

BridgeMCP has a two-tier plugin ecosystem:

### Official plugins

Official plugins are maintained in the `bridgemcp` GitHub organization, versioned independently, and named `bridgemcp-<name>` on PyPI. They follow the same code standards as the framework: full test coverage, typed, documented, and compatible with the current stable framework version.

Official plugins do not modify the framework core. They extend behavior through the public middleware and plugin API exclusively.

### Community plugins

Any package that uses BridgeMCP's plugin API can call itself a BridgeMCP plugin. Community plugins are listed in the repository's wiki (when it exists). To be listed, a plugin must:

- Work with the current stable BridgeMCP version
- Have a public repository
- Have at least minimal documentation

Community plugins are not reviewed, tested, or maintained by the BridgeMCP project. Users install them at their own discretion.

### What belongs in a plugin vs. the core

The framework core grows only when a requirement meets **all three** criteria:

1. **Universal** — every BridgeMCP server would benefit, not just some
2. **Protocol-intrinsic** — it cannot be implemented as a plugin without special-casing inside the framework
3. **Stable** — the requirement is clear enough to define a public API contract for it

When in doubt, implement it as a plugin first. If the plugin API turns out to be insufficient, that is evidence for a minimal core extension. Core additions based on hypothetical need will be declined.

---

## Contribution Philosophy

BridgeMCP welcomes contributions that improve the framework within its defined scope. The most valuable contributions are:

- **Bug fixes** — always welcome
- **Test coverage improvements** — always welcome
- **Documentation clarifications** — always welcome
- **Performance improvements** — welcome, with benchmarks
- **New core features** — require a proposal; see below

### Proposing a core feature

Open a GitHub issue describing:
1. The production use case that requires this change
2. Why it cannot be implemented as a plugin
3. The proposed public API
4. Any breaking changes

Features that can be implemented as plugins will be redirected to the plugin ecosystem. This is not a rejection — it is the correct architecture.

### Code standards

All contributions must:
- Pass `pytest` with no new test failures
- Pass `ruff check` with no issues
- Pass `black --check` with no changes
- Include tests for any new behavior
- Include a CHANGELOG entry under `[Unreleased]`
- Use type annotations consistently with the existing codebase

The framework uses `pyright` in strict mode. Type errors are treated as bugs.

### Review criteria

PRs are reviewed against these questions:
- Does this change belong in the core or in a plugin?
- Does this change respect the existing layering (no MCP imports outside `adapters/`)?
- Does this change increase coupling between previously-separate modules?
- Is the public API addition consistent with existing conventions?
- Does this change have adequate test coverage?

---

## Long-Term Maintenance Goals

**Stability first.** The most valuable thing BridgeMCP can offer its users is a stable API. A server written against BridgeMCP 0.2.0 should still work unchanged on BridgeMCP 0.5.0. Breaking changes are expensive for every downstream project.

**Minimal core, rich ecosystem.** The framework's surface area should not grow proportionally with its user base. Each new production use case is an opportunity for a plugin, not an opportunity to expand the core.

**Transport independence as a permanent constraint.** The MCP SDK is an implementation detail, not a dependency in the architectural sense. BridgeMCP code that directly imports from `mcp` or `fastmcp` outside of `adapters/mcp.py` is a bug, regardless of how convenient it might be.

**The dependency graph is an architectural test.** After every change, the Graphify knowledge graph is regenerated and inspected. Any new coupling between previously-independent modules, any import cycle, or any growth in god-node edge counts is treated as an architectural regression requiring justification.

**No speculative features.** Features are added when a real production use case requires them, not when they seem like good ideas. "We might need this later" is not sufficient justification.

**Community health.** BridgeMCP follows the Contributor Covenant Code of Conduct. All spaces — GitHub issues, PRs, discussions — are expected to be welcoming to contributors of all experience levels.
