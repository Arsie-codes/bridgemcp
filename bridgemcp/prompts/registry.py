"""
Prompt registry for BridgeMCP.

This module provides four things:
  - PromptArgument: describes one argument to a prompt, derived from the
                    function's parameter list at registration time
  - PromptMessage:  one role-tagged message in a rendered prompt
  - Prompt:         immutable record describing a registered prompt function
  - PromptRegistry: storage and lookup for all registered prompts

None of these classes know anything about the MCP protocol, transports, or
serialization. They are pure Python data structures.
"""

from __future__ import annotations

import inspect
import typing
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from bridgemcp.exceptions import PromptRegistrationError


@dataclass(frozen=True)
class PromptArgument:
    """
    Describes one argument to a prompt.

    Created automatically from the prompt function's parameter list when
    a prompt is registered. BridgeMCP does not require developers to declare
    arguments separately — they are derived from the function signature.

    Attributes:
        name: The parameter name, taken directly from the function signature.
        description: Per-argument description. Always ``None`` in the current
            release; a future phase may populate this from structured docstrings.
        required: ``True`` when the parameter has no default value.
        annotation: The raw Python type annotation, or ``None`` when the
            parameter is unannotated. May be a plain type (``int``, ``str``),
            a generic alias (``list[str]``), a union (``str | None``), or any
            other valid Python annotation object. Follows the same convention as
            ``inspect.Parameter.annotation``: typed as ``Any`` because Python
            annotations are not constrained to ``type``.
    """

    name: str
    description: str | None
    required: bool
    annotation: Any  # None when unannotated; otherwise the raw annotation object


@dataclass(frozen=True)
class PromptMessage:
    """
    One message in a rendered prompt.

    Prompt handlers return a list of these. Each message has a role and
    plain-text content, matching the MCP ``PromptMessage`` wire format.

    The ``role`` must be either ``"user"`` or ``"assistant"``. The ``Literal``
    type annotation communicates this constraint to type checkers; Python does
    not enforce it at runtime for frozen dataclasses.

    Example — a multi-turn conversation template::

        from bridgemcp.prompts import PromptMessage

        @app.prompt
        def debug_session(error: str) -> list[PromptMessage]:
            return [
                PromptMessage(role="user",      content=f"I'm seeing this error: {error}"),
                PromptMessage(role="assistant", content="I can help. Share your code."),
                PromptMessage(role="user",      content="Here it is: ..."),
            ]
    """

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class Prompt:
    """
    An immutable record describing a registered prompt.

    Created automatically when ``@app.prompt`` is used. Stores everything
    BridgeMCP needs to render the prompt and describe it to an MCP client.
    """

    name: str
    fn: Callable[..., Any]
    description: str | None
    arguments: tuple[PromptArgument, ...]
    is_async: bool


def _extract_arguments(fn: Callable[..., Any]) -> tuple[PromptArgument, ...]:
    """Derive ``PromptArgument`` records from a callable's parameter list.

    Uses ``typing.get_type_hints()`` to evaluate annotations so that string
    annotations produced by ``from __future__ import annotations`` are resolved
    back to their actual types in the function's own module namespace.
    """
    sig = inspect.signature(fn)
    try:
        # get_type_hints evaluates PEP 563 string annotations; excludes 'return'.
        hints = typing.get_type_hints(fn)
    except Exception:
        # Fallback for lambdas, built-ins, or functions with unresolvable annotations.
        hints = {}

    args = []
    for param_name, param in sig.parameters.items():
        annotation = hints.get(param_name)  # None when unannotated or unresolvable
        required = param.default is inspect.Parameter.empty
        args.append(
            PromptArgument(
                name=param_name,
                description=None,
                required=required,
                annotation=annotation,
            )
        )
    return tuple(args)


class PromptRegistry:
    """
    Stores and retrieves registered prompts.

    Prompts are keyed by name. Registering two prompts with the same name
    raises an error immediately so the conflict is caught at startup rather
    than during a live request.
    """

    def __init__(self) -> None:
        self._prompts: dict[str, Prompt] = {}

    def register(
        self,
        fn: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Prompt:
        """
        Register a callable as a prompt and return its ``Prompt`` record.

        Args:
            fn: The function to register.
            name: Display name for the prompt. Defaults to the function name.
                Leading and trailing whitespace is stripped automatically.
            description: Override the description. Defaults to the docstring.

        Returns:
            The created ``Prompt`` record.

        Raises:
            PromptRegistrationError: If the name is empty or whitespace-only,
                or if a prompt with the same name is already registered.
        """
        resolved_name = (name if name is not None else fn.__name__).strip()
        if not resolved_name:
            raise PromptRegistrationError(
                f"A prompt name must be a non-empty string. Got: {name!r}"
            )

        if resolved_name in self._prompts:
            raise PromptRegistrationError(
                f"A prompt named {resolved_name!r} is already registered. "
                "Each prompt must have a unique name."
            )

        # inspect.getdoc cleans up indentation from docstrings automatically.
        # If an explicit description was passed, use that instead.
        resolved_description = (
            description if description is not None else inspect.getdoc(fn)
        )

        prompt = Prompt(
            name=resolved_name,
            fn=fn,
            description=resolved_description,
            arguments=_extract_arguments(fn),
            is_async=inspect.iscoroutinefunction(fn),
        )

        self._prompts[resolved_name] = prompt
        return prompt

    def get(self, name: str) -> Prompt | None:
        """Return the ``Prompt`` with the given name, or ``None`` if not found."""
        return self._prompts.get(name)

    def list(self) -> list[Prompt]:
        """Return all registered prompts in registration order."""
        return list(self._prompts.values())

    def __len__(self) -> int:
        return len(self._prompts)

    def __repr__(self) -> str:
        names = list(self._prompts.keys())
        return f"PromptRegistry(prompts={names!r})"
