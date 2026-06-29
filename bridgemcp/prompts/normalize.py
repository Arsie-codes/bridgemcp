"""
Message normalization for BridgeMCP prompt handlers.

Converts the raw Python value returned by a prompt handler function into
a canonical list[PromptMessage].

Unlike resource normalization, prompt normalization does not silently coerce
arbitrary types. Only str, PromptMessage, and list[PromptMessage] are accepted.
Any other return type is an error — returning a dict or bytes from a prompt
handler is always a developer mistake, not a valid edge case.
"""

from __future__ import annotations

from typing import Any

from bridgemcp.prompts.registry import PromptMessage


def normalize_messages(raw: Any) -> list[PromptMessage]:
    """
    Convert a prompt handler's return value into ``list[PromptMessage]``.

    Supported return types and their conversions:

    - ``str``              — wrapped in ``[PromptMessage(role="user", content=str)]``
    - ``PromptMessage``    — wrapped in a single-element list
    - ``list[PromptMessage]`` — used as-is (all elements validated)
    - anything else        — raises ``TypeError``

    Args:
        raw: The raw value returned by the prompt handler function.

    Returns:
        A list of ``PromptMessage`` objects. Never empty for valid input.

    Raises:
        TypeError: If the value cannot be normalized to ``list[PromptMessage]``,
            or if any element of a returned list is not a ``PromptMessage``.
            The caller is responsible for wrapping these in
            ``PromptExecutionError``.
    """
    if isinstance(raw, str):
        return [PromptMessage(role="user", content=raw)]

    if isinstance(raw, PromptMessage):
        return [raw]

    if isinstance(raw, list):
        for i, item in enumerate(raw):
            if not isinstance(item, PromptMessage):
                raise TypeError(
                    f"Expected list[PromptMessage] but element {i} is "
                    f"{type(item).__name__!r}: {item!r}"
                )
        return list(raw)

    raise TypeError(
        f"Cannot normalize {type(raw).__name__!r} to list[PromptMessage]. "
        "Prompt handlers must return str, PromptMessage, or list[PromptMessage]."
    )
