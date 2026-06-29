"""
Plugin infrastructure for BridgeMCP.

Plugins extend BridgeMCP without modifying the core framework.  They
register tools, resources, prompts, and middleware through the same public
API that application code uses, and optionally declare async lifecycle hooks
that run before the server starts (``on_startup``) and after it stops
(``on_shutdown``).

Duck typing
-----------
BridgeMCP does not require plugins to inherit from :class:`Plugin`.
Any object that exposes a ``setup(app)`` method is a valid plugin.
``on_startup`` and ``on_shutdown`` are collected automatically when present.

The :class:`Plugin` base class is provided as optional convenience.  It
documents the full plugin interface and provides no-op defaults for all
lifecycle methods so that subclasses only need to override what they use.

Optional metadata
-----------------
Plugins may expose the following class-level attributes.  None are required
by the framework in Phase 17, but they leave room for future discovery
mechanisms and ecosystem tooling without a breaking API change:

* ``name`` — human-readable plugin name (``str | None``)
* ``version`` — plugin version string, e.g. ``"1.2.0"`` (``str | None``)
* ``description`` — one-line description of what the plugin provides
  (``str | None``)
* ``requires`` — sequence of BridgeMCP version specifiers this plugin
  requires, e.g. ``[">=0.3.0"]`` (``Sequence[str]``)

Example
-------
Minimal plugin without inheritance::

    class LoggingPlugin:
        name = "logging"
        version = "1.0.0"
        description = "Logs every tool, resource, and prompt invocation."

        def __init__(self, level: str = "INFO") -> None:
            self._level = level

        def setup(self, app) -> None:
            import logging
            logger = logging.getLogger(app.name)
            logger.setLevel(self._level)
            level = self._level

            async def log_invocations(ctx, next):
                logger.log(logging.getLevelName(level), "[%s] %s", ctx.primitive, ctx.name)
                return await next(ctx)

            app.add_middleware(log_invocations)

    app.register_plugin(LoggingPlugin(level="DEBUG"))
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bridgemcp.application import BridgeMCP


class Plugin:
    """Optional base class for BridgeMCP plugins.

    Provides no-op defaults for all three lifecycle methods.  Inherit from
    this class for IDE autocompletion and self-documenting code, or skip
    inheritance entirely and rely on duck typing — both are supported.

    BridgeMCP never calls ``isinstance(plugin, Plugin)``.

    Class-level metadata attributes (all optional, default to ``None``
    or an empty tuple):

    Attributes:
        name: Human-readable plugin name.
        version: Plugin version string.
        description: One-line description of what this plugin provides.
        requires: Sequence of BridgeMCP version specifiers this plugin
            needs, e.g. ``(">=0.3.0",)``.  The framework does not
            validate these in Phase 17; they are reserved for future
            tooling.
    """

    name: str | None = None
    version: str | None = None
    description: str | None = None
    requires: Sequence[str] = ()

    def setup(self, app: BridgeMCP) -> None:
        """Register tools, resources, prompts, and middleware with *app*.

        Called immediately when :meth:`BridgeMCP.register_plugin` is
        invoked.  This method is synchronous and runs before any event
        loop exists.

        Do not call ``app.run()``, ``app.call()``, or ``app.acall()``
        here — those are invocation methods that assume a fully
        configured server.
        """

    async def on_startup(self, app: BridgeMCP) -> None:
        """Open connections and initialise async resources.

        Called by the transport adapter after the event loop starts but
        before the server accepts requests.  Override to open database
        connection pools, warm caches, connect to external services, etc.

        Hooks run in registration order.  A startup exception propagates
        immediately and aborts server startup.
        """

    async def on_shutdown(self, app: BridgeMCP) -> None:
        """Release async resources acquired in ``on_startup``.

        Called by the transport adapter after the server stops accepting
        requests.  Override to close database connections, flush buffers,
        disconnect from external services, etc.

        Hooks run in reverse registration order.  Exceptions are logged
        but do not prevent remaining hooks from running.
        """
