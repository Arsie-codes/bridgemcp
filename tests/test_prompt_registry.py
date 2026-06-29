"""
Tests for the BridgeMCP prompt registry.

Covers PromptArgument, PromptMessage, Prompt, PromptRegistry, and the
@app.prompt decorator. Mirrors the depth of test_resource_registry.py.
"""

from __future__ import annotations

import pytest

from bridgemcp import BridgeMCP
from bridgemcp.exceptions import PromptRegistrationError
from bridgemcp.prompts import Prompt, PromptArgument, PromptMessage
from bridgemcp.prompts.registry import PromptRegistry

# ---------------------------------------------------------------------------
# PromptMessage — immutability and fields
# ---------------------------------------------------------------------------


def test_prompt_message_stores_role_and_content():
    msg = PromptMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_prompt_message_assistant_role():
    msg = PromptMessage(role="assistant", content="I can help.")
    assert msg.role == "assistant"


def test_prompt_message_is_immutable():
    msg = PromptMessage(role="user", content="Hello")
    with pytest.raises((AttributeError, TypeError)):
        msg.content = "changed"  # type: ignore[misc]


def test_prompt_message_equality():
    a = PromptMessage(role="user", content="Hi")
    b = PromptMessage(role="user", content="Hi")
    assert a == b


def test_prompt_message_inequality_by_role():
    a = PromptMessage(role="user", content="Hi")
    b = PromptMessage(role="assistant", content="Hi")
    assert a != b


def test_prompt_message_inequality_by_content():
    a = PromptMessage(role="user", content="Hi")
    b = PromptMessage(role="user", content="Hello")
    assert a != b


# ---------------------------------------------------------------------------
# PromptArgument — immutability and fields
# ---------------------------------------------------------------------------


def test_prompt_argument_stores_all_fields():
    arg = PromptArgument(
        name="language", description="Target language.", required=True, annotation=str
    )
    assert arg.name == "language"
    assert arg.description == "Target language."
    assert arg.required is True
    assert arg.annotation is str


def test_prompt_argument_is_immutable():
    arg = PromptArgument(name="x", description=None, required=True, annotation=None)
    with pytest.raises((AttributeError, TypeError)):
        arg.name = "y"  # type: ignore[misc]


def test_prompt_argument_none_annotation():
    arg = PromptArgument(name="x", description=None, required=True, annotation=None)
    assert arg.annotation is None


def test_prompt_argument_none_description():
    arg = PromptArgument(name="x", description=None, required=False, annotation=str)
    assert arg.description is None


# ---------------------------------------------------------------------------
# PromptRegistry.register — name resolution
# ---------------------------------------------------------------------------


def test_register_uses_function_name_by_default():
    registry = PromptRegistry()

    def my_prompt() -> str:
        return ""

    prompt = registry.register(my_prompt)
    assert prompt.name == "my_prompt"


def test_register_explicit_name_overrides_function_name():
    registry = PromptRegistry()

    def fn() -> str:
        return ""

    prompt = registry.register(fn, name="code_review")
    assert prompt.name == "code_review"


def test_register_strips_whitespace_from_name():
    registry = PromptRegistry()

    def fn() -> str:
        return ""

    prompt = registry.register(fn, name="  code_review  ")
    assert prompt.name == "code_review"


def test_register_raises_for_empty_name():
    registry = PromptRegistry()

    def fn() -> str:
        return ""

    with pytest.raises(PromptRegistrationError, match="non-empty"):
        registry.register(fn, name="")


def test_register_raises_for_whitespace_only_name():
    registry = PromptRegistry()

    def fn() -> str:
        return ""

    with pytest.raises(PromptRegistrationError):
        registry.register(fn, name="   ")


def test_register_raises_for_duplicate_name():
    registry = PromptRegistry()

    def fn_a() -> str:
        return ""

    def fn_b() -> str:
        return ""

    registry.register(fn_a, name="review")
    with pytest.raises(PromptRegistrationError, match="already registered"):
        registry.register(fn_b, name="review")


# ---------------------------------------------------------------------------
# PromptRegistry.register — description resolution
# ---------------------------------------------------------------------------


def test_register_uses_docstring_as_description():
    registry = PromptRegistry()

    def fn() -> str:
        """Generate a code review prompt."""
        return ""

    prompt = registry.register(fn)
    assert prompt.description == "Generate a code review prompt."


def test_register_explicit_description_overrides_docstring():
    registry = PromptRegistry()

    def fn() -> str:
        """Original docstring."""
        return ""

    prompt = registry.register(fn, description="Explicit description.")
    assert prompt.description == "Explicit description."


def test_register_description_is_none_when_no_docstring():
    registry = PromptRegistry()

    def fn() -> str:
        return ""

    prompt = registry.register(fn)
    assert prompt.description is None


# ---------------------------------------------------------------------------
# PromptRegistry.register — argument extraction
# ---------------------------------------------------------------------------


def test_register_extracts_argument_names():
    registry = PromptRegistry()

    def fn(language: str, code: str) -> str:
        return ""

    prompt = registry.register(fn)
    assert [a.name for a in prompt.arguments] == ["language", "code"]


def test_register_marks_required_when_no_default():
    registry = PromptRegistry()

    def fn(required_arg: str) -> str:
        return ""

    prompt = registry.register(fn)
    assert prompt.arguments[0].required is True


def test_register_marks_optional_when_default_exists():
    registry = PromptRegistry()

    def fn(optional_arg: str = "default") -> str:
        return ""

    prompt = registry.register(fn)
    assert prompt.arguments[0].required is False


def test_register_captures_type_annotation():
    registry = PromptRegistry()

    def fn(language: str, count: int) -> str:
        return ""

    prompt = registry.register(fn)
    assert prompt.arguments[0].annotation is str
    assert prompt.arguments[1].annotation is int


def test_register_annotation_is_none_when_unannotated():
    registry = PromptRegistry()

    def fn(x, y=10) -> str:  # type: ignore[no-untyped-def]
        return ""

    prompt = registry.register(fn)
    assert prompt.arguments[0].annotation is None
    assert prompt.arguments[1].annotation is None


def test_register_captures_complex_annotation():
    registry = PromptRegistry()

    def fn(items: list[str]) -> str:
        return ""

    prompt = registry.register(fn)
    assert prompt.arguments[0].annotation == list[str]


def test_register_argument_description_is_none():
    """Argument descriptions are always None in the MVP."""
    registry = PromptRegistry()

    def fn(language: str) -> str:
        return ""

    prompt = registry.register(fn)
    assert prompt.arguments[0].description is None


def test_register_zero_arguments_produces_empty_tuple():
    registry = PromptRegistry()

    def fn() -> str:
        return ""

    prompt = registry.register(fn)
    assert prompt.arguments == ()


def test_register_arguments_is_a_tuple():
    """arguments must be a tuple to satisfy Prompt frozen dataclass immutability."""
    registry = PromptRegistry()

    def fn(x: str) -> str:
        return ""

    prompt = registry.register(fn)
    assert isinstance(prompt.arguments, tuple)


# ---------------------------------------------------------------------------
# PromptRegistry.register — is_async tracking
# ---------------------------------------------------------------------------


def test_register_marks_sync_function_as_not_async():
    registry = PromptRegistry()

    def fn() -> str:
        return ""

    prompt = registry.register(fn)
    assert prompt.is_async is False


def test_register_marks_async_function_as_async():
    registry = PromptRegistry()

    async def fn() -> str:
        return ""

    prompt = registry.register(fn)
    assert prompt.is_async is True


# ---------------------------------------------------------------------------
# PromptRegistry — retrieval
# ---------------------------------------------------------------------------


def test_get_returns_registered_prompt():
    registry = PromptRegistry()

    def fn() -> str:
        return ""

    registry.register(fn, name="my_prompt")
    prompt = registry.get("my_prompt")
    assert prompt is not None
    assert prompt.name == "my_prompt"


def test_get_returns_none_for_unknown_name():
    registry = PromptRegistry()
    assert registry.get("nonexistent") is None


def test_list_returns_all_prompts():
    registry = PromptRegistry()

    def fn_a() -> str:
        return ""

    def fn_b() -> str:
        return ""

    registry.register(fn_a, name="alpha")
    registry.register(fn_b, name="beta")
    names = [p.name for p in registry.list()]
    assert "alpha" in names
    assert "beta" in names


def test_list_preserves_registration_order():
    registry = PromptRegistry()

    for name in ["first", "second", "third"]:
        fn = lambda: ""  # noqa: E731
        fn.__name__ = name
        registry.register(fn, name=name)

    assert [p.name for p in registry.list()] == ["first", "second", "third"]


def test_list_returns_empty_when_no_prompts_registered():
    registry = PromptRegistry()
    assert registry.list() == []


def test_len_reflects_registered_count():
    registry = PromptRegistry()

    def fn_a() -> str:
        return ""

    def fn_b() -> str:
        return ""

    registry.register(fn_a)
    registry.register(fn_b)
    assert len(registry) == 2


def test_len_is_zero_for_empty_registry():
    registry = PromptRegistry()
    assert len(registry) == 0


def test_repr_contains_registered_names():
    registry = PromptRegistry()

    def code_review() -> str:
        return ""

    registry.register(code_review)
    assert "code_review" in repr(registry)


# ---------------------------------------------------------------------------
# @app.prompt — decorator behaviour
# ---------------------------------------------------------------------------


def test_app_prompt_bare_form_registers_prompt():
    app = BridgeMCP(name="test")

    @app.prompt
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    assert any(p.name == "greet" for p in app.list_prompts())


def test_app_prompt_keyword_form_registers_prompt():
    app = BridgeMCP(name="test")

    @app.prompt(name="review", description="Review code.")
    def code_review(language: str) -> str:
        return ""

    prompts = {p.name: p for p in app.list_prompts()}
    assert "review" in prompts
    assert prompts["review"].description == "Review code."


def test_app_prompt_returns_original_function():
    """The decorator must return the original function unchanged."""
    app = BridgeMCP(name="test")

    @app.prompt
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    # Callable directly without going through the framework
    assert greet(name="World") == "Hello, World!"


def test_app_prompt_raises_on_duplicate_name():
    app = BridgeMCP(name="test")

    @app.prompt
    def review() -> str:
        return ""

    with pytest.raises(PromptRegistrationError):

        @app.prompt(name="review")
        def another() -> str:
            return ""


# ---------------------------------------------------------------------------
# list_prompts — public method
# ---------------------------------------------------------------------------


def test_list_prompts_returns_prompt_objects():
    app = BridgeMCP(name="test")

    @app.prompt
    def greet() -> str:
        return ""

    prompts = app.list_prompts()
    assert len(prompts) == 1
    assert isinstance(prompts[0], Prompt)


def test_list_prompts_empty_when_no_prompts():
    app = BridgeMCP(name="test")
    assert app.list_prompts() == []


def test_list_prompts_preserves_registration_order():
    app = BridgeMCP(name="test")

    @app.prompt
    def alpha() -> str:
        return ""

    @app.prompt
    def beta() -> str:
        return ""

    @app.prompt
    def gamma() -> str:
        return ""

    assert [p.name for p in app.list_prompts()] == ["alpha", "beta", "gamma"]


def test_prompt_and_tool_registries_are_independent():
    """Registering prompts should not affect tools, and vice versa."""
    app = BridgeMCP(name="test")

    @app.tool
    def ping() -> str:
        return "pong"

    @app.prompt
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    assert [t.name for t in app.list_tools()] == ["ping"]
    assert [p.name for p in app.list_prompts()] == ["greet"]


def test_independent_app_instances_have_independent_prompt_registries():
    app_a = BridgeMCP(name="app-a")
    app_b = BridgeMCP(name="app-b")

    @app_a.prompt
    def greet() -> str:
        return ""

    assert app_b.list_prompts() == []
