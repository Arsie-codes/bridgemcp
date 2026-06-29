"""
BridgeMCP — A production-ready Python framework for building MCP servers.
"""

from .application import BridgeMCP
from .exceptions import BridgeMCPError

__version__ = "0.2.0"

__all__ = ["BridgeMCP", "BridgeMCPError"]
