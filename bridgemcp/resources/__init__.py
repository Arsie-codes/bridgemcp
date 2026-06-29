"""
BridgeMCP resources package.

Exposes the Resource and ResourceContent records so developers can use
them in type hints if they need to inspect registered resources or
handle read results programmatically.

The ResourceRegistry itself is an internal implementation detail and
is not part of the public API.
"""

from .registry import Resource, ResourceContent

__all__ = ["Resource", "ResourceContent"]
