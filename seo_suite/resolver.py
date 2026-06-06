"""The resolver: collect provider layers, merge by precedence, finalize, cache.

``BaseResolver`` defines the contract with small, individually-overridable
methods so extension packages can subclass and tweak one step (e.g.
``collect_layers``) via the ``SEO_SUITE['RESOLVER_CLASS']`` setting. ``Resolver``
is the shipped default.
"""

from __future__ import annotations

import logging

from .conf import get_settings
from .metadata import FinalizedSeoMetadata, SeoMetadata
from .providers import (
    PRECEDENCE_GLOBAL,
    PRECEDENCE_OBJECT,
    PRECEDENCE_SITE,
    PRECEDENCE_VIEW,
    Context,
)
from .providers.registry import provider_registry
from .signals import seo_metadata_resolved

logger = logging.getLogger("seo_suite")


def _dict_to_metadata(data) -> SeoMetadata | None:
    if not data:
        return None
    if isinstance(data, SeoMetadata):
        return data
    return SeoMetadata.partial(**data)


class BaseResolver:
    """Override points: ``collect_layers``, ``build_canonicalizer``, ``finalize``."""

    def resolve(self, context: Context) -> FinalizedSeoMetadata:
        finalized = self._cached_resolve(context)
        # The signal fires on every resolve (cache hit or miss). It runs AFTER
        # caching, so per-request mutation by receivers never leaks into the
        # cached value (Django returns a fresh copy from cache.get).
        self.dispatch_resolved(finalized, context)
        return finalized

    def _cached_resolve(self, context: Context) -> FinalizedSeoMetadata:
        from .cache import cache_enabled, cache_get, cache_set, make_key

        if not cache_enabled():
            return self.compute(context)
        key = make_key(context)
        if key is None:
            return self.compute(context)
        cached = cache_get(key)
        if cached is not None:
            return cached
        finalized = self.compute(context)
        cache_set(key, finalized)
        return finalized

    def compute(self, context: Context) -> FinalizedSeoMetadata:
        layers = self.collect_layers(context)
        merged = SeoMetadata.merge_all([md for _prio, md in layers])
        return self.finalize(merged, context)

    def collect_layers(self, context: Context) -> list[tuple[int, SeoMetadata]]:
        """Return ``(priority, metadata)`` pairs sorted low -> high (stable)."""
        raise NotImplementedError

    def finalize(self, merged: SeoMetadata, context: Context) -> FinalizedSeoMetadata:
        return merged.finalize(canonicalizer=self.build_canonicalizer(context))

    def build_canonicalizer(self, context: Context):
        return None

    def dispatch_resolved(self, finalized: FinalizedSeoMetadata, context: Context) -> None:
        seo_metadata_resolved.send(sender=type(self), metadata=finalized, context=context)


class Resolver(BaseResolver):
    """Default resolver implementing the documented precedence ladder."""

    def collect_layers(self, context: Context) -> list[tuple[int, SeoMetadata]]:
        settings = get_settings()
        layers: list[tuple[int, int, SeoMetadata]] = []
        seq = 0

        # 1. global defaults
        defaults = _dict_to_metadata(settings["DEFAULTS"])
        if defaults is not None:
            layers.append((PRECEDENCE_GLOBAL, seq, defaults))
            seq += 1

        # 2. site defaults
        site_defaults = settings["SITE_DEFAULTS"]
        site_layer = site_defaults.get(context.site_id)
        if site_layer is None:
            site_layer = site_defaults.get(None)
        site_md = _dict_to_metadata(site_layer)
        if site_md is not None:
            layers.append((PRECEDENCE_SITE, seq, site_md))
            seq += 1

        # 3. registry providers (path, generic object, extension providers)
        for provider in provider_registry.get_all():
            md = self._safe_provide(provider, context)
            if md is not None:
                layers.append((provider.priority, seq, md))
                seq += 1

        # 4. context object (owned model via SeoModelMixin)
        obj = context.object
        if obj is not None and hasattr(obj, "get_seo_metadata"):
            md = self._safe_object(obj, context)
            if md is not None:
                layers.append((PRECEDENCE_OBJECT, seq, md))
                seq += 1

        # 5. view override (SeoViewMixin)
        view = context.view
        if view is not None and hasattr(view, "get_seo_metadata"):
            md = self._safe_object(view, context)
            if md is not None:
                layers.append((PRECEDENCE_VIEW, seq, md))
                seq += 1

        layers.sort(key=lambda item: (item[0], item[1]))
        return [(prio, md) for prio, _seq, md in layers]

    def build_canonicalizer(self, context: Context):
        from .canonical import make_canonicalizer

        return make_canonicalizer(context)

    # ---- defensive provider invocation --------------------------------------
    def _safe_provide(self, provider, context) -> SeoMetadata | None:
        try:
            return provider.provide(context)
        except Exception:  # noqa: BLE001 - a bad provider must not break the page
            logger.exception("SEO provider %r failed", provider)
            return None

    def _safe_object(self, obj, context) -> SeoMetadata | None:
        try:
            return obj.get_seo_metadata(context)
        except Exception:  # noqa: BLE001
            logger.exception("get_seo_metadata on %r failed", obj)
            return None


_resolver_instance = None


def get_resolver() -> BaseResolver:
    """Instantiate (once) the resolver named by ``SEO_SUITE['RESOLVER_CLASS']``."""
    global _resolver_instance
    settings = get_settings()
    cls = settings["RESOLVER_CLASS"]
    if _resolver_instance is None or not isinstance(_resolver_instance, cls):
        _resolver_instance = cls()
    return _resolver_instance


def reset_resolver() -> None:
    """Drop the cached resolver instance (used after settings change / in tests)."""
    global _resolver_instance
    _resolver_instance = None
