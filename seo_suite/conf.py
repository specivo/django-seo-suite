"""Settings access for django-seo-suite.

Everything is configured through a single ``SEO_SUITE`` dict in the project's
settings module. This module merges that dict over the package defaults and
exposes typed accessors plus an ``import_from_string`` helper for the swappable
class settings (``RESOLVER_CLASS``, ``JSONLD_SERIALIZER`` ...).

The merged settings are cached and rebuilt automatically when Django emits the
``setting_changed`` signal (so ``override_settings`` works in tests).
"""

from __future__ import annotations

import copy
from importlib import import_module
from typing import Any

from django.core.signals import setting_changed
from django.dispatch import receiver
from django.utils.functional import cached_property
from django.utils.module_loading import import_string

# Keys whose dict values are deep-merged with the project's values rather than
# replaced wholesale.
_DEEP_MERGE_KEYS = {"DEFAULTS", "SITE_DEFAULTS"}

DEFAULTS: dict[str, Any] = {
    # --- resolution ---
    "RESOLVER_CLASS": "seo_suite.resolver.Resolver",
    "SITE_ID_RESOLVER": None,
    # --- default (lowest precedence) metadata seed ---
    "DEFAULTS": {
        "title_suffix": "",
        "robots": "index,follow",
        "og": {"type": "website"},
        "twitter": {},
    },
    "SITE_DEFAULTS": {},  # {site_id | None: {...partial metadata...}}
    # --- canonical / i18n ---
    "CANONICAL_DOMAIN": None,
    "FORCE_HTTPS_CANONICAL": True,
    "LIST_CANONICAL_INCLUDES_PAGE": True,
    "HREFLANG_X_DEFAULT": True,
    # --- caching ---
    "CACHE_TTL": 0,  # seconds; 0 disables caching entirely
    "CACHE_BACKEND": "default",
    "CACHE_KEY_PREFIX": "seosuite:v1",
    # --- robots.txt ---
    "ROBOTS_TXT_FALLBACK": "User-agent: *\nAllow: /",  # served when no active version exists
    "ROBOTS_SITEMAP_URLS": [],  # URLs appended to the output as "Sitemap:" lines
    "ROBOTS_CACHE_TTL": 0,  # seconds; 0 disables robots.txt caching
    # --- optional providers ---
    "OBJECT_MODELS": [],  # allowlist of "app_label.Model" for the seoobject provider
    # --- schema ---
    "DEFAULT_SCHEMA_PROFILES": [],
    "JSONLD_SERIALIZER": "seo_suite.schema.default_serializer",
}

# Settings expressed as dotted import strings, resolved lazily to objects.
_IMPORT_STRINGS = {"RESOLVER_CLASS", "JSONLD_SERIALIZER", "SITE_ID_RESOLVER"}


def import_from_string(value: Any, setting_name: str = "") -> Any:
    """Resolve a dotted path to the referenced object; pass through non-strings."""
    if value is None or not isinstance(value, str):
        return value
    try:
        return import_string(value)
    except ImportError as exc:  # pragma: no cover - defensive
        raise ImportError(f"Could not import '{value}' for SEO_SUITE setting '{setting_name}': {exc}") from exc


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class SeoSuiteSettings:
    """Lazy, cached view over ``settings.SEO_SUITE`` merged with the defaults."""

    @cached_property
    def _merged(self) -> dict[str, Any]:
        from django.conf import settings as django_settings

        user = getattr(django_settings, "SEO_SUITE", {}) or {}
        merged = copy.deepcopy(DEFAULTS)
        for key, value in user.items():
            if key in _DEEP_MERGE_KEYS and isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    def __getitem__(self, key: str) -> Any:
        value = self._merged[key]
        if key in _IMPORT_STRINGS:
            value = import_from_string(value, key)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self._merged:
            return default
        return self[key]

    def reload(self) -> None:
        self.__dict__.pop("_merged", None)


settings = SeoSuiteSettings()


def get_settings() -> SeoSuiteSettings:
    return settings


@receiver(setting_changed)
def _reload_on_change(*, setting=None, **kwargs):  # pragma: no cover - exercised indirectly
    if setting == "SEO_SUITE":
        settings.reload()


def import_module_safe(dotted_path: str):  # pragma: no cover - thin wrapper
    return import_module(dotted_path)
