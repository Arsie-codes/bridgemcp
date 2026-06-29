"""
Resource registry for BridgeMCP.

This module provides three things:
  - Resource: an immutable record describing a registered resource function
  - ResourceContent: an immutable record holding the result of reading a resource
  - ResourceRegistry: storage and lookup for all registered resources

Neither class knows anything about the MCP protocol, transports, or
serialization. They are pure Python data structures.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bridgemcp.exceptions import ResourceRegistrationError


@dataclass(frozen=True)
class Resource:
    """
    An immutable record describing a registered resource.

    Created automatically when a developer uses ``@app.resource``.
    Stores everything BridgeMCP needs to serve the resource and
    describe it to an MCP client.
    """

    uri: str
    name: str
    fn: Callable[..., Any]
    description: str | None
    mime_type: str | None
    is_async: bool


@dataclass(frozen=True)
class ResourceContent:
    """
    An immutable record holding the result of reading a resource.

    Returned by ``app.read_resource()``. Carries the URI, serialized content,
    and the MIME type declared at registration time.

    ``content`` is always ``str`` or ``bytes``:
      - ``str``   maps to the ``text`` field in the MCP ``resources/read`` response.
      - ``bytes`` maps to the ``blob`` field (base64-encoded by the transport).
    """

    uri: str
    content: str | bytes
    mime_type: str | None


class ResourceRegistry:
    """
    Stores and retrieves registered resources.

    Resources are keyed by URI. Registering two resources with the same
    URI raises an error immediately so the conflict is caught at startup.
    """

    def __init__(self) -> None:
        self._resources: dict[str, Resource] = {}

    def register(
        self,
        fn: Callable[..., Any],
        *,
        uri: str,
        name: str | None = None,
        description: str | None = None,
        mime_type: str | None = None,
    ) -> Resource:
        """
        Register a callable as a resource and return its Resource record.

        Args:
            fn: The function to register.
            uri: The MCP URI for this resource. Must be a non-empty string.
                 Leading and trailing whitespace is stripped automatically.
            name: Human-readable display name shown to AI clients.
                  Defaults to the function name.
            description: Override the description. Defaults to the docstring.
            mime_type: Optional MIME type hint for the response content
                       (e.g. ``"application/json"``, ``"text/plain"``).

        Returns:
            The created Resource record.

        Raises:
            ResourceRegistrationError: If the URI is empty or whitespace-only,
                or if a resource with the same URI is already registered.
        """
        resolved_uri = uri.strip()
        if not resolved_uri:
            raise ResourceRegistrationError(
                f"A resource URI must be a non-empty string. Got: {uri!r}"
            )

        if resolved_uri in self._resources:
            raise ResourceRegistrationError(
                f"A resource with URI {resolved_uri!r} is already registered. "
                "Each resource must have a unique URI."
            )

        resolved_name = name if name is not None else fn.__name__

        # inspect.getdoc cleans up indentation from docstrings automatically.
        # If an explicit description was passed, use that instead.
        resolved_description = (
            description if description is not None else inspect.getdoc(fn)
        )

        resource = Resource(
            uri=resolved_uri,
            name=resolved_name,
            fn=fn,
            description=resolved_description,
            mime_type=mime_type,
            is_async=inspect.iscoroutinefunction(fn),
        )

        self._resources[resolved_uri] = resource
        return resource

    def get(self, uri: str) -> Resource | None:
        """Return the Resource with the given URI, or None if not found."""
        return self._resources.get(uri)

    def list(self) -> list[Resource]:
        """Return all registered resources in registration order."""
        return list(self._resources.values())

    def __len__(self) -> int:
        return len(self._resources)

    def __repr__(self) -> str:
        uris = list(self._resources.keys())
        return f"ResourceRegistry(resources={uris!r})"
