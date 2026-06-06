"""Schema-profile ABC + registry.

A ``SchemaProfile`` turns an object + context into one JSON-LD dict. Profiles are
referenced by key (e.g. ``"Article"``, ``"pro:Product"``); a model/view enables
them via ``SEO_SCHEMA_PROFILES`` / ``seo_schema_profiles``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("seo_suite")


class SchemaProfile(ABC):
    """Builds a single JSON-LD object. ``key`` is how it is referenced."""

    key: str = ""

    @abstractmethod
    def build(self, obj, context) -> dict | None:
        """Return a JSON-LD dict, or ``None`` to emit nothing."""
        raise NotImplementedError


class SchemaRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, SchemaProfile] = {}

    def register(self, profile: SchemaProfile, *, key: str | None = None) -> SchemaProfile:
        resolved_key = key or profile.key
        if not resolved_key:
            raise ValueError("SchemaProfile must define a non-empty key")
        profile.key = resolved_key
        self._profiles[resolved_key] = profile
        return profile

    def unregister(self, key: str) -> None:
        self._profiles.pop(key, None)

    def get(self, key: str) -> SchemaProfile | None:
        return self._profiles.get(key)

    def keys(self) -> list[str]:
        return sorted(self._profiles)

    def clear(self) -> None:
        self._profiles.clear()

    def __contains__(self, key: str) -> bool:
        return key in self._profiles


schema_registry = SchemaRegistry()


def build_profiles(profile_keys, obj, context) -> list[dict]:
    """Build JSON-LD dicts for the given profile keys (unknown keys skipped)."""
    blocks: list[dict] = []
    for key in profile_keys or []:
        profile = schema_registry.get(key)
        if profile is None:
            logger.warning("Unknown SEO schema profile %r (not registered)", key)
            continue
        try:
            data = profile.build(obj, context)
        except Exception:  # noqa: BLE001 - a bad profile must not break the page
            logger.exception("Schema profile %r failed to build", key)
            continue
        if data:
            blocks.append(data)
    return blocks
