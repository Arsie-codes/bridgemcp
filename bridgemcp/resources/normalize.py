"""
Content normalization for BridgeMCP resource handlers.

Converts the raw Python value returned by a resource handler function
into a ResourceContent object with a str or bytes payload.

MIME type is passed through unchanged from the resource registration.
BridgeMCP does not infer MIME types from return values — set mime_type
explicitly on @app.resource if the client needs this information.
"""

from __future__ import annotations

import json
from typing import Any

from bridgemcp.resources.registry import ResourceContent


def normalize_content(
    raw: Any,
    *,
    uri: str,
    mime_type: str | None,
) -> ResourceContent:
    """
    Convert a resource handler's return value into a ``ResourceContent`` record.

    Supported return types and their conversions:

    - ``str``            — used as-is
    - ``bytes``          — used as-is
    - ``dict`` / ``list``— serialized with ``json.dumps``
    - Pydantic model     — serialized with ``model_dump_json()``
    - ``None``           — treated as an empty string
    - anything else      — coerced with ``str()``

    The ``mime_type`` is always passed through from the registration.
    It is never inferred from the return value.

    Args:
        raw: The raw value returned by the resource handler function.
        uri: The resource URI, echoed into the returned ``ResourceContent``.
        mime_type: The MIME type declared at registration time, or ``None``.

    Returns:
        A ``ResourceContent`` with ``content`` as ``str`` or ``bytes``.

    Raises:
        TypeError, ValueError: if ``json.dumps`` or ``model_dump_json()``
            cannot serialize the value. The caller is responsible for
            wrapping these in ``ResourceExecutionError``.
    """
    from pydantic import BaseModel

    if isinstance(raw, str):
        content: str | bytes = raw
    elif isinstance(raw, bytes):
        content = raw
    elif isinstance(raw, (dict, list)):
        content = json.dumps(raw)
    elif isinstance(raw, BaseModel):
        content = raw.model_dump_json()
    elif raw is None:
        content = ""
    else:
        content = str(raw)

    return ResourceContent(uri=uri, content=content, mime_type=mime_type)
