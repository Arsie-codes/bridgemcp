"""
Tests for BridgeMCP plugin system — bridgemcp/plugin.py and
register_plugin() in bridgemcp/application.py.

Coverage:
  - Plugin base class defaults (metadata, no-op lifecycle methods)
  - Duck typing: plain objects without inheritance are valid plugins
  - register_plugin() calls setup() immediately
  - register_plugin() stores plugin in _plugins list
  - on_startup collected when present
  - on_shutdown collected when present
  - Multiple plugins, registration order preserved
  - Plugin registering tools, resources, prompts, and middleware
  - Plugin with constructor-injected configuration
  - Class-based plugin (inheriting Plugin)
  - Duck-typed plugin (no inheritance)
  - Lifecycle hooks stored but not called by register_plugin()
  - Optional metadata attributes (name, version, description, requires)
  - Plugin that short-circuits a tool via middleware
"""

from __future__ import annotations

from typing import Any

from bridgemcp import BridgeMCP
from bridgemcp.middleware import InvocationContext, Next
from bridgemcp.plugin import Plugin

# ---------------------------------------------------------------------------
# Plugin base class defaults
# ---------------------------------------------------------------------------


def test_plugin_base_class_name_default_is_none():
    assert Plugin.name is None


def test_plugin_base_class_version_default_is_none():
    assert Plugin.version is None


def test_plugin_base_class_description_default_is_none():
    assert Plugin.description is None


def test_plugin_base_class_requires_default_is_empty():
    assert Plugin.requires == ()


async def test_plugin_base_class_setup_is_noop():
    app = BridgeMCP(name="test")
    p = Plugin()
    p.setup(app)  # must not raise


async def test_plugin_base_class_on_startup_is_noop():
    app = BridgeMCP(name="test")
    p = Plugin()
    await p.on_startup(app)  # must not raise


async def test_plugin_base_class_on_shutdown_is_noop():
    app = BridgeMCP(name="test")
    p = Plugin()
    await p.on_shutdown(app)  # must not raise


# ---------------------------------------------------------------------------
# register_plugin — setup() is called immediately
# ---------------------------------------------------------------------------


def test_register_plugin_calls_setup():
    app = BridgeMCP(name="test")
    setup_called = []

    class MyPlugin:
        def setup(self, a):
            setup_called.append(a)

    app.register_plugin(MyPlugin())
    assert setup_called == [app]


def test_register_plugin_stores_plugin():
    app = BridgeMCP(name="test")

    class MyPlugin:
        def setup(self, a):
            pass

    p = MyPlugin()
    app.register_plugin(p)
    assert app._plugins == [p]


def test_register_plugin_multiple_preserves_order():
    app = BridgeMCP(name="test")
    registered = []

    class NamedPlugin:
        def __init__(self, tag):
            self.tag = tag

        def setup(self, a):
            registered.append(self.tag)

    pa, pb, pc = NamedPlugin("a"), NamedPlugin("b"), NamedPlugin("c")
    app.register_plugin(pa)
    app.register_plugin(pb)
    app.register_plugin(pc)

    assert registered == ["a", "b", "c"]
    assert app._plugins == [pa, pb, pc]


# ---------------------------------------------------------------------------
# Lifecycle hook collection
# ---------------------------------------------------------------------------


def test_on_startup_collected_when_present():
    app = BridgeMCP(name="test")

    class StartupPlugin:
        def setup(self, a):
            pass

        async def on_startup(self, a):
            pass

    p = StartupPlugin()
    app.register_plugin(p)
    assert app._startup_hooks == [p.on_startup]


def test_on_shutdown_collected_when_present():
    app = BridgeMCP(name="test")

    class ShutdownPlugin:
        def setup(self, a):
            pass

        async def on_shutdown(self, a):
            pass

    p = ShutdownPlugin()
    app.register_plugin(p)
    assert app._shutdown_hooks == [p.on_shutdown]


def test_both_hooks_collected_when_both_present():
    app = BridgeMCP(name="test")

    class FullPlugin:
        def setup(self, a):
            pass

        async def on_startup(self, a):
            pass

        async def on_shutdown(self, a):
            pass

    p = FullPlugin()
    app.register_plugin(p)
    assert len(app._startup_hooks) == 1
    assert len(app._shutdown_hooks) == 1


def test_hooks_not_collected_when_absent():
    app = BridgeMCP(name="test")

    class MinimalPlugin:
        def setup(self, a):
            pass

    app.register_plugin(MinimalPlugin())
    assert app._startup_hooks == []
    assert app._shutdown_hooks == []


def test_register_plugin_does_not_call_startup_hook():
    """Lifecycle hooks are stored, not called, during registration."""
    app = BridgeMCP(name="test")
    called = []

    class StartupPlugin:
        def setup(self, a):
            pass

        async def on_startup(self, a):
            called.append(True)

    app.register_plugin(StartupPlugin())
    assert called == []


def test_multiple_plugins_hooks_collected_in_order():
    app = BridgeMCP(name="test")
    order: list[str] = []

    class PluginA:
        def setup(self, a):
            pass

        async def on_startup(self, a):
            order.append("A")

    class PluginB:
        def setup(self, a):
            pass

        async def on_startup(self, a):
            order.append("B")

    pa, pb = PluginA(), PluginB()
    app.register_plugin(pa)
    app.register_plugin(pb)
    assert app._startup_hooks == [pa.on_startup, pb.on_startup]


# ---------------------------------------------------------------------------
# Duck typing — no inheritance required
# ---------------------------------------------------------------------------


def test_duck_typed_plugin_without_inheritance():
    app = BridgeMCP(name="test")
    setup_called = []

    class PlainObject:
        def setup(self, a):
            setup_called.append(True)

    app.register_plugin(PlainObject())
    assert setup_called == [True]


def test_duck_typed_plugin_with_hooks_collected():
    app = BridgeMCP(name="test")

    class PlainObject:
        def setup(self, a):
            pass

        async def on_startup(self, a):
            pass

        async def on_shutdown(self, a):
            pass

    p = PlainObject()
    app.register_plugin(p)
    assert len(app._startup_hooks) == 1
    assert len(app._shutdown_hooks) == 1


def test_framework_does_not_isinstance_check():
    """register_plugin must accept non-Plugin objects."""
    app = BridgeMCP(name="test")

    class TotallyUnrelated:
        def setup(self, a):
            pass

    app.register_plugin(TotallyUnrelated())  # must not raise TypeError


# ---------------------------------------------------------------------------
# Plugin capabilities — tools
# ---------------------------------------------------------------------------


def test_plugin_can_register_tools():
    app = BridgeMCP(name="test")

    class MathPlugin:
        def setup(self, a):
            @a.tool
            def add(x: int, y: int) -> int:
                return x + y

    app.register_plugin(MathPlugin())
    assert any(t.name == "add" for t in app.list_tools())


def test_plugin_tool_is_invocable():
    app = BridgeMCP(name="test")

    class MathPlugin:
        def setup(self, a):
            @a.tool
            def multiply(x: int, y: int) -> int:
                return x * y

    app.register_plugin(MathPlugin())
    assert app.call("multiply", x=6, y=7) == 42


async def test_plugin_async_tool_is_invocable():
    app = BridgeMCP(name="test")

    class MathPlugin:
        def setup(self, a):
            @a.tool
            async def square(x: int) -> int:
                return x * x

    app.register_plugin(MathPlugin())
    assert await app.acall("square", x=9) == 81


# ---------------------------------------------------------------------------
# Plugin capabilities — resources
# ---------------------------------------------------------------------------


def test_plugin_can_register_resources():
    app = BridgeMCP(name="test")

    class DataPlugin:
        def setup(self, a):
            @a.resource(uri="data://plugin/info")
            def plugin_info() -> str:
                return "plugin data"

    app.register_plugin(DataPlugin())
    uris = [r.uri for r in app.list_resources()]
    assert "data://plugin/info" in uris


def test_plugin_resource_is_readable():
    app = BridgeMCP(name="test")

    class DataPlugin:
        def setup(self, a):
            @a.resource(uri="data://plugin/greeting")
            def greet() -> str:
                return "hello from plugin"

    app.register_plugin(DataPlugin())
    content = app.read_resource("data://plugin/greeting")
    assert content.content == "hello from plugin"


# ---------------------------------------------------------------------------
# Plugin capabilities — prompts
# ---------------------------------------------------------------------------


def test_plugin_can_register_prompts():
    app = BridgeMCP(name="test")

    class PromptPlugin:
        def setup(self, a):
            @a.prompt
            def greet(name: str) -> str:
                return f"Hello, {name}!"

    app.register_plugin(PromptPlugin())
    names = [p.name for p in app.list_prompts()]
    assert "greet" in names


def test_plugin_prompt_is_renderable():
    app = BridgeMCP(name="test")

    class PromptPlugin:
        def setup(self, a):
            @a.prompt
            def welcome(name: str) -> str:
                return f"Welcome, {name}!"

    app.register_plugin(PromptPlugin())
    messages = app.render_prompt("welcome", name="Alice")
    assert messages[0].content == "Welcome, Alice!"


# ---------------------------------------------------------------------------
# Plugin capabilities — middleware
# ---------------------------------------------------------------------------


def test_plugin_can_register_middleware():
    app = BridgeMCP(name="test")
    called = []

    @app.tool
    def ping() -> str:
        return "pong"

    class LoggingPlugin:
        def setup(self, a):
            async def log(ctx: InvocationContext, next: Next) -> Any:
                called.append(ctx.name)
                return await next(ctx)

            a.add_middleware(log)

    app.register_plugin(LoggingPlugin())
    app.call("ping")
    assert called == ["ping"]


def test_plugin_middleware_applies_to_all_primitives():
    app = BridgeMCP(name="test")
    log: list[tuple[str, str]] = []

    class TracingPlugin:
        def setup(self, a):
            async def trace(ctx: InvocationContext, next: Next) -> Any:
                log.append((ctx.primitive, ctx.name))
                return await next(ctx)

            a.add_middleware(trace)

    @app.tool
    def ping() -> str:
        return "pong"

    @app.resource(uri="data://x")
    def data() -> str:
        return "x"

    @app.prompt
    def greet() -> str:
        return "hi"

    app.register_plugin(TracingPlugin())

    app.call("ping")
    app.read_resource("data://x")
    app.render_prompt("greet")

    assert ("tool", "ping") in log
    assert ("resource", "data://x") in log
    assert ("prompt", "greet") in log


# ---------------------------------------------------------------------------
# Constructor-configured plugin
# ---------------------------------------------------------------------------


def test_plugin_with_constructor_config():
    app = BridgeMCP(name="test")
    recorded: list[str] = []

    class TaggingPlugin:
        def __init__(self, tag: str) -> None:
            self.tag = tag

        def setup(self, a):
            tag = self.tag

            async def annotate(ctx: InvocationContext, next: Next) -> Any:
                result = await next(ctx)
                recorded.append(f"{tag}:{ctx.name}")
                return result

            a.add_middleware(annotate)

    @app.tool
    def ping() -> str:
        return "pong"

    app.register_plugin(TaggingPlugin(tag="v1"))
    app.call("ping")
    assert recorded == ["v1:ping"]


# ---------------------------------------------------------------------------
# Multiple plugins interact cleanly
# ---------------------------------------------------------------------------


async def test_multiple_plugins_middleware_stacks():
    app = BridgeMCP(name="test")
    order: list[str] = []

    class PluginA:
        def setup(self, a):
            async def mw(ctx: InvocationContext, next: Next) -> Any:
                order.append("A")
                return await next(ctx)

            a.add_middleware(mw)

    class PluginB:
        def setup(self, a):
            async def mw(ctx: InvocationContext, next: Next) -> Any:
                order.append("B")
                return await next(ctx)

            a.add_middleware(mw)

    @app.tool
    def ping() -> str:
        return "pong"

    app.register_plugin(PluginA())
    app.register_plugin(PluginB())

    await app.acall("ping")
    assert order == ["A", "B"]


def test_multiple_plugins_tools_do_not_conflict():
    app = BridgeMCP(name="test")

    class PluginA:
        def setup(self, a):
            @a.tool
            def tool_a() -> str:
                return "a"

    class PluginB:
        def setup(self, a):
            @a.tool
            def tool_b() -> str:
                return "b"

    app.register_plugin(PluginA())
    app.register_plugin(PluginB())

    assert app.call("tool_a") == "a"
    assert app.call("tool_b") == "b"


# ---------------------------------------------------------------------------
# Plugin metadata attributes
# ---------------------------------------------------------------------------


def test_plugin_base_class_metadata_can_be_set_on_subclass():
    class MyPlugin(Plugin):
        name = "my-plugin"
        version = "2.0.0"
        description = "Does things."
        requires = (">=0.3.0",)

        def setup(self, a):
            pass

    p = MyPlugin()
    assert p.name == "my-plugin"
    assert p.version == "2.0.0"
    assert p.description == "Does things."
    assert p.requires == (">=0.3.0",)


def test_duck_typed_plugin_metadata_readable_by_caller():
    class VersionedPlugin:
        name = "versioned"
        version = "0.5.0"
        description = "A versioned plugin."
        requires = (">=0.2.0",)

        def setup(self, a):
            pass

    app = BridgeMCP(name="test")
    p = VersionedPlugin()
    app.register_plugin(p)

    stored = app._plugins[0]
    assert stored.name == "versioned"
    assert stored.version == "0.5.0"
    assert stored.description == "A versioned plugin."
    assert stored.requires == (">=0.2.0",)


def test_plugin_metadata_defaults_do_not_bleed_between_subclasses():
    class PluginA(Plugin):
        name = "plugin-a"

    class PluginB(Plugin):
        name = "plugin-b"

    assert PluginA.name != PluginB.name
    assert PluginA().name == "plugin-a"
    assert PluginB().name == "plugin-b"


def test_plugin_requires_defaults_to_empty_sequence():
    p = Plugin()
    assert len(p.requires) == 0


# ---------------------------------------------------------------------------
# Plugin inheriting from Plugin base class
# ---------------------------------------------------------------------------


def test_plugin_subclass_setup_called():
    app = BridgeMCP(name="test")
    called = []

    class ConcretePlugin(Plugin):
        def setup(self, a):
            called.append(True)

    app.register_plugin(ConcretePlugin())
    assert called == [True]


async def test_plugin_subclass_startup_collected():
    app = BridgeMCP(name="test")
    invoked = []

    class ConcretePlugin(Plugin):
        def setup(self, a):
            pass

        async def on_startup(self, a):
            invoked.append(True)

    p = ConcretePlugin()
    app.register_plugin(p)
    assert len(app._startup_hooks) == 1

    # Manually invoke to verify it works when the adapter eventually calls it
    await app._startup_hooks[0](app)
    assert invoked == [True]


async def test_plugin_subclass_shutdown_collected():
    app = BridgeMCP(name="test")
    invoked = []

    class ConcretePlugin(Plugin):
        def setup(self, a):
            pass

        async def on_shutdown(self, a):
            invoked.append(True)

    p = ConcretePlugin()
    app.register_plugin(p)
    assert len(app._shutdown_hooks) == 1

    await app._shutdown_hooks[0](app)
    assert invoked == [True]


# ---------------------------------------------------------------------------
# Plugin that short-circuits via middleware
# ---------------------------------------------------------------------------


def test_plugin_middleware_can_short_circuit():
    app = BridgeMCP(name="test")

    class CachingPlugin:
        def __init__(self, cache: dict) -> None:
            self._cache = cache

        def setup(self, a):
            cache = self._cache

            async def cached(ctx: InvocationContext, next: Next) -> Any:
                key = (ctx.name, repr(sorted(ctx.kwargs.items())))
                if key in cache:
                    return cache[key]
                result = await next(ctx)
                cache[key] = result
                return result

            a.add_middleware(cached)

    call_count = 0

    @app.tool
    def expensive(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 10

    cache: dict = {}
    app.register_plugin(CachingPlugin(cache=cache))

    result1 = app.call("expensive", x=5)
    result2 = app.call("expensive", x=5)

    assert result1 == 50
    assert result2 == 50
    assert call_count == 1
