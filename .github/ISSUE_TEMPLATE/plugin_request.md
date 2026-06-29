---
name: Plugin request
about: Suggest a new official plugin or request community plugin listing
title: '[Plugin] '
labels: plugin
assignees: ''
---

## Plugin name

<!-- e.g. bridgemcp-logging, bridgemcp-sqlalchemy -->

## What it does

<!-- One sentence. -->

## Use case

<!-- Describe a real production scenario that requires this plugin. -->

## Proposed plugin API

<!-- Sketch how a developer would use it. -->

```python
from bridgemcp import BridgeMCP
from bridgemcp_logging import LoggingPlugin  # example

app = BridgeMCP(name="my-server")
app.register_plugin(LoggingPlugin(level="INFO"))

```

## Type

- [ ] I am requesting an official plugin (maintained by the BridgeMCP project)
- [ ] I am requesting listing of an existing community plugin

## Existing community plugin URL

<!-- If this is a listing request, paste the repository URL here. -->
