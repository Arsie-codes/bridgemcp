"""
BridgeMCP configuration package.

Import BridgeConfig from here rather than from the internal models module.
The internal structure of this package may change; this public interface will not.
"""

from .models import BridgeConfig

__all__ = ["BridgeConfig"]
