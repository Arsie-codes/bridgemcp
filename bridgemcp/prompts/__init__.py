"""
BridgeMCP prompts package.

Exposes the Prompt, PromptArgument, and PromptMessage records so developers
can use them in type hints and write multi-turn prompt functions.

    from bridgemcp.prompts import PromptMessage

    @app.prompt
    def debug_session(error: str) -> list[PromptMessage]:
        return [
            PromptMessage(role="user",      content=f"Error: {error}"),
            PromptMessage(role="assistant", content="Share your code."),
        ]

The PromptRegistry itself is an internal implementation detail and is not
part of the public API.
"""

from .registry import Prompt, PromptArgument, PromptMessage

__all__ = ["Prompt", "PromptArgument", "PromptMessage"]
