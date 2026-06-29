"""
Tests for the BridgeMCP application class.

These tests cover construction, validation, default values,
and the developer-facing string representations.
"""

import pytest

from bridgemcp import BridgeMCP

# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_minimal_construction():
    """Creating an app with only a name should succeed."""
    app = BridgeMCP(name="my-app")

    assert app.name == "my-app"
    assert app.version == "0.1.0"
    assert app.description is None


def test_explicit_values_stored_correctly():
    """All explicitly provided values should be stored as-is after stripping."""
    app = BridgeMCP(
        name="Order Service",
        version="2.3.1",
        description="Handles customer orders",
    )

    assert app.name == "Order Service"
    assert app.version == "2.3.1"
    assert app.description == "Handles customer orders"


def test_name_whitespace_is_stripped():
    """Leading and trailing whitespace in name should be removed silently."""
    app = BridgeMCP(name="  my-app  ")

    assert app.name == "my-app"


def test_version_whitespace_is_stripped():
    """Leading and trailing whitespace in version should be removed silently."""
    app = BridgeMCP(name="my-app", version="  1.0.0  ")

    assert app.version == "1.0.0"


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------


def test_empty_name_raises():
    """An empty name string should raise ValueError."""
    with pytest.raises(ValueError, match="non-empty string"):
        BridgeMCP(name="")


def test_whitespace_only_name_raises():
    """A name containing only whitespace should raise ValueError."""
    with pytest.raises(ValueError, match="non-empty string"):
        BridgeMCP(name="   ")


def test_none_name_raises():
    """Passing None as name should raise ValueError."""
    with pytest.raises(ValueError, match="non-empty string"):
        BridgeMCP(name=None)  # type: ignore[arg-type]


def test_integer_name_raises():
    """Passing a non-string as name should raise ValueError."""
    with pytest.raises(ValueError, match="non-empty string"):
        BridgeMCP(name=42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Version validation
# ---------------------------------------------------------------------------


def test_empty_version_raises():
    """An empty version string should raise ValueError."""
    with pytest.raises(ValueError, match="non-empty string"):
        BridgeMCP(name="my-app", version="")


def test_whitespace_only_version_raises():
    """A version containing only whitespace should raise ValueError."""
    with pytest.raises(ValueError, match="non-empty string"):
        BridgeMCP(name="my-app", version="   ")


# ---------------------------------------------------------------------------
# Representation
# ---------------------------------------------------------------------------


def test_repr_without_description():
    """repr() should show name and version but omit description when not set."""
    app = BridgeMCP(name="my-app", version="1.0.0")

    assert repr(app) == "BridgeMCP(name='my-app', version='1.0.0')"


def test_repr_with_description():
    """repr() should include description when it is provided."""
    app = BridgeMCP(name="my-app", version="1.0.0", description="Demo server")

    assert (
        repr(app)
        == "BridgeMCP(name='my-app', version='1.0.0', description='Demo server')"
    )


def test_str_matches_repr():
    """str() should produce the same output as repr().

    BridgeMCP does not define __str__, so Python falls back to __repr__.
    This test documents that behavior explicitly so any future addition
    of __str__ is a conscious, visible decision rather than an accident.
    """
    app = BridgeMCP(name="my-app", version="1.0.0", description="Demo")

    assert str(app) == repr(app)
