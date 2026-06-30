---
name: Bug report
about: Report something that is broken or behaving unexpectedly
title: '[Bug] '
labels: bug
assignees: ''
---

## Environment

- **BridgeMCP version**: <!-- e.g. 0.2.0 — run `python -c "import bridgemcp; print(bridgemcp.__version__)"` -->
- **Python version**: <!-- e.g. 3.12.3 -->
- **OS**: <!-- e.g. Ubuntu 22.04, macOS 14, Windows 11 -->
- **Installation**: <!-- e.g. `pip install bridgemcp-py[mcp]` or editable install -->

## What happened?

<!-- A clear description of the bug. -->

## What did you expect to happen?

<!-- A clear description of what you expected. -->

## Minimal reproducer

<!-- The smallest possible code that reproduces the bug. -->

```python
from bridgemcp import BridgeMCP

app = BridgeMCP(name="repro")

# ...

```

## Full traceback

<!-- Paste the full error output here, if applicable. -->

```
Traceback (most recent call last):
  ...
```

## Additional context

<!-- Anything else that might help — e.g. is this inside an async framework, behind a proxy, etc. -->
