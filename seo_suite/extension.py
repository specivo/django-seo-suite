"""Extension discovery + the public registration API re-exports.

Extension packages register their providers/renderers/schema-profiles either:

* from a top-level ``seo_extensions.py`` module in any installed app
  (imported here via ``autodiscover_modules``), or
* by publishing an entry point in the ``seo_suite.extensions`` group whose value
  is an import path to a module (or a zero-arg callable) that performs the
  registration.

Both paths are idempotent; registration keyed by dotted name tolerates being
run twice.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("seo_suite")

# Re-export the registration surface so extensions can do a single import.
from .metadata import UNSET, HreflangAlt, SeoMetadata  # noqa: E402,F401
from .providers import (  # noqa: E402,F401
    PRECEDENCE_GLOBAL,
    PRECEDENCE_OBJECT,
    PRECEDENCE_PATH,
    PRECEDENCE_SITE,
    PRECEDENCE_VIEW,
    Context,
    Provider,
)
from .providers.registry import provider_registry, renderer_registry  # noqa: E402,F401
from .signals import (  # noqa: E402,F401
    seo_cache_invalidate,
    seo_head_rendering,
    seo_metadata_resolved,
)

_discovered = False


def autodiscover_extensions(force: bool = False) -> None:
    global _discovered
    if _discovered and not force:
        return
    _discovered = True
    _autodiscover_modules()
    _load_entry_points()


def _autodiscover_modules() -> None:
    from django.utils.module_loading import autodiscover_modules

    try:
        autodiscover_modules("seo_extensions")
    except Exception:  # noqa: BLE001 - a broken extension must not break startup
        logger.exception("Error while autodiscovering seo_extensions modules")


def _load_entry_points() -> None:
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover - py<3.8 only
        return

    try:
        eps = entry_points(group="seo_suite.extensions")
    except TypeError:  # pragma: no cover - older importlib.metadata API
        eps = entry_points().get("seo_suite.extensions", [])

    for ep in eps:
        try:
            obj = ep.load()
            if callable(obj):
                obj()
        except Exception:  # noqa: BLE001
            logger.exception("Error loading seo_suite extension entry point %r", getattr(ep, "name", ep))
