"""
Tests for prompt invocation through BridgeMCP.app.render_prompt().

Covers the happy path, normalization of all supported return types,
missing prompts, async rejection, exception chaining, and invalid return values.
"""

from __future__ import annotations

import pytest

from bridgemcp import BridgeMCP
from bridgemcp.exceptions import PromptExecutionError, PromptNotFoundError
from bridgemcp.prompts import PromptMessage

# ---------------------------------------------------------------------------
# Happy path — render_prompt returns list[PromptMessage]
# ---------------------------------------------------------------------------


def test_render_prompt_returns_list():
    app = BridgeMCP(name="test")

    @app.prompt
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    result = app.render_prompt("greet", name="Alice")
    assert isinstance(result, list)


def test_render_prompt_list_contains_prompt_messages():
    app = BridgeMCP(name="test")

    @app.prompt
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    result = app.render_prompt("greet", name="Alice")
    assert all(isinstance(m, PromptMessage) for m in result)


# ---------------------------------------------------------------------------
# Normalization — str return
# ---------------------------------------------------------------------------


def test_str_return_normalized_to_single_user_message():
    """A str return value should produce [PromptMessage(role='user', content=str)]."""
    app = BridgeMCP(name="test")

    @app.prompt
    def ask() -> str:
        return "What is the weather today?"

    result = app.render_prompt("ask")
    assert len(result) == 1
    assert result[0].role == "user"
    assert result[0].content == "What is the weather today?"


def test_str_return_content_matches_exactly():
    app = BridgeMCP(name="test")

    @app.prompt
    def code_review(language: str, code: str) -> str:
        return f"Review this {language} code:\n\n{code}"

    result = app.render_prompt("code_review", language="Python", code="x = 1")
    assert result[0].content == "Review this Python code:\n\nx = 1"


# ---------------------------------------------------------------------------
# Normalization — PromptMessage return
# ---------------------------------------------------------------------------


def test_single_prompt_message_return_wrapped_in_list():
    """A single PromptMessage return should be wrapped in a one-element list."""
    app = BridgeMCP(name="test")

    @app.prompt
    def ask() -> PromptMessage:
        return PromptMessage(role="user", content="Hello")

    result = app.render_prompt("ask")
    assert len(result) == 1
    assert result[0] == PromptMessage(role="user", content="Hello")


def test_assistant_message_return_wrapped_in_list():
    app = BridgeMCP(name="test")

    @app.prompt
    def hint() -> PromptMessage:
        return PromptMessage(role="assistant", content="Here is a hint.")

    result = app.render_prompt("hint")
    assert len(result) == 1
    assert result[0].role == "assistant"


# ---------------------------------------------------------------------------
# Normalization — list[PromptMessage] return
# ---------------------------------------------------------------------------


def test_list_of_prompt_messages_returned_as_is():
    app = BridgeMCP(name="test")

    expected = [
        PromptMessage(role="user", content="First"),
        PromptMessage(role="assistant", content="Second"),
    ]

    @app.prompt
    def multi() -> list[PromptMessage]:
        return expected

    result = app.render_prompt("multi")
    assert result == expected


def test_multi_turn_prompt_preserves_roles():
    app = BridgeMCP(name="test")

    @app.prompt
    def debug_session(error: str) -> list[PromptMessage]:
        return [
            PromptMessage(role="user", content=f"Error: {error}"),
            PromptMessage(role="assistant", content="Share your code."),
            PromptMessage(role="user", content="Here it is."),
        ]

    result = app.render_prompt("debug_session", error="NPE")
    assert len(result) == 3
    assert result[0].role == "user"
    assert result[1].role == "assistant"
    assert result[2].role == "user"


def test_multi_turn_prompt_preserves_content():
    app = BridgeMCP(name="test")

    @app.prompt
    def setup(context: str) -> list[PromptMessage]:
        return [
            PromptMessage(role="user", content=f"Context: {context}"),
            PromptMessage(role="assistant", content="Understood."),
        ]

    result = app.render_prompt("setup", context="production outage")
    assert result[0].content == "Context: production outage"
    assert result[1].content == "Understood."


# ---------------------------------------------------------------------------
# Prompt argument passing — including 'name' kwarg (positional-only guard)
# ---------------------------------------------------------------------------


def test_render_prompt_passes_kwargs_to_handler():
    app = BridgeMCP(name="test")

    @app.prompt
    def template(x: str, y: str) -> str:
        return f"{x}-{y}"

    result = app.render_prompt("template", x="hello", y="world")
    assert result[0].content == "hello-world"


def test_render_prompt_works_when_prompt_has_name_parameter():
    """render_prompt(name, /) is positional-only; 'name' kwarg is safe to pass through."""
    app = BridgeMCP(name="test")

    @app.prompt
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    result = app.render_prompt("greet", name="Alice")
    assert result[0].content == "Hello, Alice!"


def test_render_prompt_works_with_zero_arg_handler():
    app = BridgeMCP(name="test")

    @app.prompt
    def intro() -> str:
        return "You are a helpful assistant."

    result = app.render_prompt("intro")
    assert result[0].content == "You are a helpful assistant."


def test_render_prompt_works_with_optional_arg():
    app = BridgeMCP(name="test")

    @app.prompt
    def summarize(max_words: int = 100) -> str:
        return f"Summarize in {max_words} words."

    result_default = app.render_prompt("summarize")
    assert "100" in result_default[0].content

    result_override = app.render_prompt("summarize", max_words=50)
    assert "50" in result_override[0].content


# ---------------------------------------------------------------------------
# PromptNotFoundError
# ---------------------------------------------------------------------------


def test_render_prompt_raises_for_unknown_name():
    app = BridgeMCP(name="test")
    with pytest.raises(PromptNotFoundError):
        app.render_prompt("nonexistent")


def test_render_prompt_not_found_message_contains_name():
    app = BridgeMCP(name="test")
    with pytest.raises(PromptNotFoundError, match="nonexistent"):
        app.render_prompt("nonexistent")


def test_render_prompt_not_found_message_lists_available_prompts():
    app = BridgeMCP(name="test")

    @app.prompt
    def existing() -> str:
        return ""

    with pytest.raises(PromptNotFoundError, match="existing"):
        app.render_prompt("typo")


def test_render_prompt_not_found_message_when_no_prompts_registered():
    app = BridgeMCP(name="test")
    with pytest.raises(PromptNotFoundError, match="No prompts are registered"):
        app.render_prompt("anything")


# ---------------------------------------------------------------------------
# PromptExecutionError — async handler
# ---------------------------------------------------------------------------


def test_render_prompt_raises_for_async_handler():
    """render_prompt() should raise PromptExecutionError for async handlers; use arender_prompt()."""
    app = BridgeMCP(name="test")

    @app.prompt
    async def async_prompt() -> str:
        return "async result"

    with pytest.raises(PromptExecutionError, match="arender_prompt"):
        app.render_prompt("async_prompt")


# ---------------------------------------------------------------------------
# arender_prompt — async execution
# ---------------------------------------------------------------------------


async def test_arender_prompt_returns_messages_from_sync_handler():
    """arender_prompt() should work with synchronous handlers."""
    app = BridgeMCP(name="test")

    @app.prompt
    def ask() -> str:
        return "Hello?"

    result = await app.arender_prompt("ask")
    assert result == [PromptMessage(role="user", content="Hello?")]


async def test_arender_prompt_returns_messages_from_async_handler():
    """arender_prompt() should work with asynchronous handlers."""
    app = BridgeMCP(name="test")

    @app.prompt
    async def ask() -> str:
        return "Hello from async?"

    result = await app.arender_prompt("ask")
    assert result == [PromptMessage(role="user", content="Hello from async?")]


async def test_arender_prompt_passes_kwargs_to_async_handler():
    app = BridgeMCP(name="test")

    @app.prompt
    async def greet(name: str) -> str:
        return f"Hello, {name}!"

    result = await app.arender_prompt("greet", name="Alice")
    assert result[0].content == "Hello, Alice!"


async def test_arender_prompt_works_when_handler_has_name_parameter():
    """arender_prompt(name, /) is positional-only; 'name' kwarg is safe to pass through."""
    app = BridgeMCP(name="test")

    @app.prompt
    async def template(name: str) -> str:
        return f"Hello, {name}!"

    result = await app.arender_prompt("template", name="World")
    assert result[0].content == "Hello, World!"


async def test_arender_prompt_raises_not_found():
    app = BridgeMCP(name="test")

    with pytest.raises(PromptNotFoundError):
        await app.arender_prompt("nonexistent")


async def test_arender_prompt_wraps_exception_from_async_handler():
    app = BridgeMCP(name="test")

    @app.prompt
    async def broken() -> str:
        raise RuntimeError("async failure")

    with pytest.raises(PromptExecutionError, match="async failure"):
        await app.arender_prompt("broken")


async def test_arender_prompt_preserves_cause():
    app = BridgeMCP(name="test")
    original = ValueError("root cause")

    @app.prompt
    async def broken() -> str:
        raise original

    with pytest.raises(PromptExecutionError) as exc_info:
        await app.arender_prompt("broken")

    assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# PromptExecutionError — handler raises
# ---------------------------------------------------------------------------


def test_render_prompt_wraps_exception_in_prompt_execution_error():
    app = BridgeMCP(name="test")

    @app.prompt
    def broken() -> str:
        raise RuntimeError("something went wrong")

    with pytest.raises(PromptExecutionError):
        app.render_prompt("broken")


def test_render_prompt_execution_error_message_contains_prompt_name():
    app = BridgeMCP(name="test")

    @app.prompt
    def broken() -> str:
        raise RuntimeError("failure")

    with pytest.raises(PromptExecutionError, match="broken"):
        app.render_prompt("broken")


def test_render_prompt_execution_error_preserves_original_exception():
    app = BridgeMCP(name="test")
    original = ValueError("bad state")

    @app.prompt
    def broken() -> str:
        raise original

    with pytest.raises(PromptExecutionError) as exc_info:
        app.render_prompt("broken")

    assert exc_info.value.__cause__ is original


def test_render_prompt_execution_error_contains_original_message():
    app = BridgeMCP(name="test")

    @app.prompt
    def broken() -> str:
        raise RuntimeError("upstream unavailable")

    with pytest.raises(PromptExecutionError, match="upstream unavailable"):
        app.render_prompt("broken")


# ---------------------------------------------------------------------------
# PromptExecutionError — invalid return type
# ---------------------------------------------------------------------------


def test_render_prompt_raises_for_dict_return():
    """Returning a dict is always a developer mistake — not silently coerced."""
    app = BridgeMCP(name="test")

    @app.prompt
    def bad() -> dict:  # type: ignore[return-value]
        return {"role": "user", "content": "oops"}

    with pytest.raises(PromptExecutionError, match="could not be normalized"):
        app.render_prompt("bad")


def test_render_prompt_raises_for_none_return():
    """None is not a valid prompt return value."""
    app = BridgeMCP(name="test")

    @app.prompt
    def bad():
        return None

    with pytest.raises(PromptExecutionError, match="could not be normalized"):
        app.render_prompt("bad")


def test_render_prompt_raises_for_list_with_non_message_elements():
    app = BridgeMCP(name="test")

    @app.prompt
    def bad() -> list:
        return ["not a PromptMessage"]  # type: ignore[return-value]

    with pytest.raises(PromptExecutionError, match="could not be normalized"):
        app.render_prompt("bad")


def test_normalization_error_preserves_cause():
    app = BridgeMCP(name="test")

    @app.prompt
    def bad() -> list:
        return [42]  # type: ignore[return-value]

    with pytest.raises(PromptExecutionError) as exc_info:
        app.render_prompt("bad")

    assert exc_info.value.__cause__ is not None
