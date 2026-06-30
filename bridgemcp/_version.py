"""Single source of truth for the BridgeMCP version string.

Reads the version from installed package metadata so that pyproject.toml
is the only place a version number ever needs to be changed.

``importlib.metadata`` is Python standard library (3.8+). BridgeMCP
requires Python 3.11+, so no compatibility shim is needed.

The fallback "0.0.0" applies only when the package is not installed —
for example, when the source tree is placed on sys.path directly without
running ``pip install -e .``. Normal installs (including editable installs)
always resolve to the real version.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__: str = _pkg_version("bridgemcp-py")
except PackageNotFoundError:
    # Package is not installed. This happens when the source tree is placed on
    # sys.path directly (e.g. PYTHONPATH=.) without running `pip install -e .`.
    # Normal installs — including editable installs — always resolve above.
    __version__ = "__dev__"
