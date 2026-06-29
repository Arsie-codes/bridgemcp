"""
Tests for BridgeConfig.

Covers construction, the frozen constraint, and passing a config to BridgeMCP.
"""

from bridgemcp import BridgeMCP
from bridgemcp.config import BridgeConfig

# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_default_construction_succeeds():
    """BridgeConfig() with no arguments should succeed."""
    config = BridgeConfig()
    assert isinstance(config, BridgeConfig)


# ---------------------------------------------------------------------------
# Integration — passing config to BridgeMCP
# ---------------------------------------------------------------------------


def test_bridgemcp_stores_provided_config():
    """A BridgeConfig passed to BridgeMCP should be accessible on the instance."""
    config = BridgeConfig()
    app = BridgeMCP(name="my-app", config=config)
    assert app.config is config


def test_bridgemcp_creates_default_config_when_none_provided():
    """When no config is given, BridgeMCP should create a default BridgeConfig."""
    app = BridgeMCP(name="my-app")
    assert isinstance(app.config, BridgeConfig)


def test_bridgemcp_default_configs_are_independent():
    """Two apps without explicit config should each get their own BridgeConfig instance."""
    app_one = BridgeMCP(name="app-one")
    app_two = BridgeMCP(name="app-two")
    assert app_one.config is not app_two.config
