"""
BridgeMCP — A production-ready Python framework for building MCP servers.
"""

from ._version import __version__ as __version__
from .application import BridgeMCP
from .exceptions import BridgeMCPError

__all__ = ["BridgeMCP", "BridgeMCPError"]
