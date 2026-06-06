"""Append-only registries — the backbone of the extension system.

Extension packages (e.g. the paid ``django-seo-suite-pro``) register their
providers and head renderers here, typically from a ``seo_extensions.py`` module
that the app autodiscovery imports at startup. Registration is idempotent
(keyed by a stable dotted name) so double-discovery / autoreload is safe.
"""

from __future__ import annotations

from collections.abc import Callable

from . import Provider


def _dotted_name(obj: object) -> str:
    cls = obj if isinstance(obj, type) else type(obj)
    return f"{cls.__module__}.{cls.__qualname__}"


class ProviderRegistry:
    """Holds globally-registered providers, queryable in precedence order."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider, *, priority: int | None = None, name: str | None = None) -> Provider:
        if priority is not None:
            provider.priority = priority
        key = name or _dotted_name(provider)
        self._providers[key] = provider
        return provider

    def unregister(self, name_or_provider) -> None:
        key = name_or_provider if isinstance(name_or_provider, str) else _dotted_name(name_or_provider)
        self._providers.pop(key, None)

    def get_all(self) -> list[Provider]:
        """Registered providers sorted ascending by priority (stable)."""
        return sorted(self._providers.values(), key=lambda p: p.priority)

    def clear(self) -> None:
        self._providers.clear()

    def __len__(self) -> int:
        return len(self._providers)

    def __contains__(self, name_or_provider) -> bool:
        key = name_or_provider if isinstance(name_or_provider, str) else _dotted_name(name_or_provider)
        return key in self._providers


class RendererRegistry:
    """Named callables that contribute extra ``<head>`` fragments at render time.

    Each renderer is ``callable(context, finalized_metadata) -> str | SafeString``.
    """

    def __init__(self) -> None:
        self._renderers: dict[str, Callable] = {}

    def register(self, name: str, renderer: Callable) -> Callable:
        self._renderers[name] = renderer
        return renderer

    def unregister(self, name: str) -> None:
        self._renderers.pop(name, None)

    def get_all(self) -> list[Callable]:
        return [self._renderers[name] for name in sorted(self._renderers)]

    def clear(self) -> None:
        self._renderers.clear()

    def __len__(self) -> int:
        return len(self._renderers)


# Module-level singletons. These ARE the public registration surface.
provider_registry = ProviderRegistry()
renderer_registry = RendererRegistry()
