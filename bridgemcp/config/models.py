"""
Configuration models for BridgeMCP.

All configuration fields are validated at instantiation time through Pydantic.
If an invalid value is provided, a clear error is raised immediately rather
than surfacing as a confusing failure later during server startup.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BridgeConfig(BaseModel):
    """
    Configuration for a BridgeMCP application.

    Pass an instance of this class to ``BridgeMCP`` to customise behaviour.
    If no config is provided, sensible defaults are used automatically.

    Example::

        from bridgemcp import BridgeMCP
        from bridgemcp.config import BridgeConfig

        config = BridgeConfig()
        app = BridgeMCP(name="my-app", config=config)
    """

    # Prevent fields from being changed after the config is created.
    # Configuration should be set once at startup and remain stable.
    model_config = ConfigDict(frozen=True)
