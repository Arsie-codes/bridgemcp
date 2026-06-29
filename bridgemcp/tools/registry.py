"""
Tool registry for BridgeMCP.

This module provides two things:
  - Tool: an immutable record describing a registered tool function
  - ToolRegistry: storage and lookup for all registered tools

Neither class knows anything about the MCP protocol, transports, or
serialization. They are pure Python data structures.
"""

from __future__ import annotations

import inspect
import typing
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bridgemcp.exceptions import ToolRegistrationError


@dataclass(frozen=True)
class Tool:
    """
    An immutable record describing a registered tool.

    Created automatically when a developer uses ``@app.tool``.
    Stores everything BridgeMCP needs to call the function and
    describe it to an MCP client.
    """

    name: str
    fn: Callable[..., Any]
    description: str | None
    signature: inspect.Signature
    return_annotation: type | None
    is_async: bool


class ToolRegistry:
    """
    Stores and retrieves registered tools.

    Tools are keyed by name. Registering two tools with the same name
    raises an error immediately so the conflict is caught at startup.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
    ) -> Tool:
        """
        Register a callable as a tool and return its Tool record.

        Args:
            fn: The function to register.
            name: Override the tool name. Defaults to the function name.
            description: Override the description. Defaults to the docstring.

        Returns:
            The created Tool record.

        Raises:
            ToolRegistrationError: If a tool with the same name is already registered.
        """
        tool_name = name if name is not None else fn.__name__

        if tool_name in self._tools:
            raise ToolRegistrationError(
                f"A tool named {tool_name!r} is already registered. "
                "Each tool must have a unique name."
            )

        # inspect.getdoc cleans up indentation from docstrings automatically.
        # If an explicit description was passed, use that instead.
        resolved_description = (
            description if description is not None else inspect.getdoc(fn)
        )

        sig = inspect.signature(fn)

        # get_type_hints resolves string annotations produced by
        # `from __future__ import annotations` back into real types.
        # We guard with try/except because resolution can fail if a type is
        # not importable in the function's module scope (e.g. a forward ref
        # to a class that hasn't been defined yet).
        try:
            hints = typing.get_type_hints(fn)
        except Exception:
            hints = {}

        return_annotation = hints.get("return")

        tool = Tool(
            name=tool_name,
            fn=fn,
            description=resolved_description,
            signature=sig,
            return_annotation=return_annotation,
            is_async=inspect.iscoroutinefunction(fn),
        )

        self._tools[tool_name] = tool
        return tool

    def get(self, name: str) -> Tool | None:
        """Return the Tool with the given name, or None if not found."""
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        """Return all registered tools in registration order."""
        return list(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        names = list(self._tools.keys())
        return f"ToolRegistry(tools={names!r})"
