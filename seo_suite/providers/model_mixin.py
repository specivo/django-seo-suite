"""Model-level providers.

``SeoModelMixin`` adds a ``get_seo_metadata()`` to any model with NO database
columns of its own — it reads from a declarative ``SEO_FIELD_MAP`` and falls
back to conventional field names. This is the zero-overhead path: the object is
already loaded by the view, so no extra table and no join.

``SeoModelFieldsMixin`` is an abstract model adding editable ``seo_*`` columns for
teams that want admin-editable per-row SEO without a separate table. Because it
is abstract, the migration lives in the *consumer's* app — the base package
ships no migrations.
"""

from __future__ import annotations

from typing import Any

from django.db import models

from ..metadata import SeoMetadata

# field -> ordered list of source attribute names tried when not in SEO_FIELD_MAP
_CONVENTIONS: dict[str, tuple[str, ...]] = {
    "title": ("title", "name", "headline"),
    "h1": ("h1",),
    "meta_description": ("meta_description", "description", "summary", "excerpt"),
    "meta_keywords": ("meta_keywords", "keywords"),
    "og_image": ("og_image", "image", "cover_image", "photo", "thumbnail"),
}


def _resolve_source(obj: Any, source: str) -> Any:
    """Read ``source`` off ``obj``, normalizing file fields and callables."""
    value = getattr(obj, source, None)
    if value is None:
        return None
    # FieldFile / ImageFieldFile -> URL (only when a file is actually set).
    if hasattr(value, "url") and hasattr(value, "name"):
        try:
            return value.url if value.name else None
        except Exception:  # noqa: BLE001
            return None
    if callable(value):
        try:
            value = value()
        except Exception:  # noqa: BLE001
            return None
    # A blank text field means "the author had no opinion" -> treat as no value
    # so convention fallbacks continue. (Explicit empties come from class attrs /
    # SeoMetadata.partial(field=""), not from model field reads.)
    if isinstance(value, str) and value == "":
        return None
    return value


class SeoModelMixin:
    """Mix into a model to expose SEO metadata derived from its own fields."""

    #: Map SeoMetadata field name -> source attribute/method on the model.
    SEO_FIELD_MAP: dict[str, str] = {}
    #: Schema profile keys to render as JSON-LD for instances of this model.
    SEO_SCHEMA_PROFILES: list[str] = []

    def get_seo_metadata(self, context=None) -> SeoMetadata:
        kwargs: dict[str, Any] = {}
        for field in ("title", "h1", "meta_description", "meta_keywords", "og_image"):
            value = self._resolve_seo_field(field)
            if value is not None:
                kwargs[field] = value

        canonical = self._resolve_seo_canonical()
        if canonical is not None:
            kwargs["canonical_url"] = canonical

        schema = self._build_seo_schema(context)
        if schema:
            kwargs["jsonld"] = schema

        return SeoMetadata.partial(**kwargs)

    # ------------------------------------------------------------------ helpers
    def _resolve_seo_field(self, field: str) -> Any:
        mapped = self.SEO_FIELD_MAP.get(field)
        if mapped:
            return _resolve_source(self, mapped)
        for source in _CONVENTIONS.get(field, ()):  # conventional fallbacks
            value = _resolve_source(self, source)
            if value is not None:
                return value
        return None

    def _resolve_seo_canonical(self) -> Any:
        mapped = self.SEO_FIELD_MAP.get("canonical_url")
        if mapped:
            return _resolve_source(self, mapped)
        if hasattr(self, "get_absolute_url"):
            return _resolve_source(self, "get_absolute_url")
        return None

    def _build_seo_schema(self, context) -> list[dict]:
        profiles = list(self.SEO_SCHEMA_PROFILES or [])
        if not profiles:
            return []
        from ..schema import build_profiles

        return build_profiles(profiles, self, context)


class SeoColumnsMixin(models.Model):
    """Just the editable SEO columns — reusable as a base for extension models."""

    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)
    seo_keywords = models.CharField(max_length=255, blank=True)
    seo_robots = models.CharField(max_length=100, blank=True)
    seo_canonical = models.CharField(max_length=500, blank=True)
    seo_og_image = models.CharField(
        max_length=500, blank=True, help_text="URL or path to the social sharing image."
    )

    class Meta:
        abstract = True


class SeoModelFieldsMixin(SeoColumnsMixin, SeoModelMixin):
    """Abstract model: ``seo_*`` columns win, then fall back to conventions."""

    class Meta:
        abstract = True

    def get_seo_metadata(self, context=None) -> SeoMetadata:
        base = super().get_seo_metadata(context)  # conventions + schema
        columns = self._seo_column_metadata()
        return SeoMetadata.merge(base, columns)

    def _seo_column_metadata(self) -> SeoMetadata:
        kwargs: dict[str, Any] = {}
        mapping = {
            "seo_title": "title",
            "seo_description": "meta_description",
            "seo_keywords": "meta_keywords",
            "seo_robots": "robots",
            "seo_canonical": "canonical_url",
            "seo_og_image": "og_image",
        }
        for column, field in mapping.items():
            value = getattr(self, column, "")
            if value:  # blank ("") means "no opinion" -> stay UNSET
                kwargs[field] = value
        return SeoMetadata.partial(**kwargs)
