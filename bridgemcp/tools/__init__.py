"""
BridgeMCP tools package.

Exposes the Tool record so developers can use it in type hints
if they need to inspect registered tools programmatically.

The ToolRegistry itself is an internal implementation detail and
is not part of the public API.
"""

from .registry import Tool

__all__ = ["Tool"]
