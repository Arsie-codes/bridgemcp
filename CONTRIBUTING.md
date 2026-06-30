# Contributing to BridgeMCP

Thank you for your interest in contributing.

## Development setup

```bash
git clone https://github.com/Arsie-codes/bridgemcp.git
cd bridgemcp
pip install -e '.[mcp,dev]'
```

## Running the tests

```bash
pytest                        # run all tests
pytest tests/test_invocation.py -v   # run one file verbosely
pytest -x                     # stop on first failure
```

The test suite requires no network access and no MCP client.

## Lint and format

```bash
ruff check bridgemcp tests    # linter (must pass before merge)
black bridgemcp tests         # formatter
black --check bridgemcp tests # check-only (what CI runs)
```

## Before opening a pull request

1. All existing tests pass.
2. New behaviour is covered by tests.
3. `ruff check` reports no issues.
4. `black --check` reports no changes needed.
5. The CHANGELOG entry under `[Unreleased]` describes the change.

## Project conventions

- One public entry point: `BridgeMCP` in `bridgemcp/application.py`.
- The MCP SDK is only ever imported inside `bridgemcp/adapters/mcp.py`.
- New exceptions inherit from `BridgeMCPError` in `bridgemcp/exceptions.py`.
- No placeholder code, no speculative features — only implement what is needed.
- Comments only when the *why* is non-obvious.

## Reporting bugs

Open an issue at https://github.com/Arsie-codes/bridgemcp/issues and include:
- Python version and OS
- BridgeMCP version (`pip show bridgemcp-py`)
- Minimal reproducer
- Expected vs actual behaviour
