"""View-level providers for class-based views.

``SeoViewMixin`` works for any CBV — including model-less ones (``TemplateView``)
and ``DetailView`` (where the object layer is resolved separately by the
resolver, so the view only needs to express its own overrides).

``SeoListViewMixin`` adds pagination-aware canonical + title for list/index pages.
"""

from __future__ import annotations

from typing import Any

from ..context import attach_seo
from ..metadata import SeoMetadata

# class attribute -> SeoMetadata field
_VIEW_ATTRS = {
    "seo_title": "title",
    "seo_title_suffix": "title_suffix",
    "seo_h1": "h1",
    "seo_description": "meta_description",
    "seo_keywords": "meta_keywords",
    "seo_robots": "robots",
    "seo_canonical": "canonical_url",
    "seo_og_image": "og_image",
}


class SeoViewMixin:
    """Declare SEO via class attrs or override ``get_seo_metadata``."""

    seo_title = None
    seo_title_suffix = None
    seo_h1 = None
    seo_description = None
    seo_keywords = None
    seo_robots = None
    seo_canonical = None
    seo_og_image = None
    #: Schema profile keys to render as JSON-LD for this view.
    seo_schema_profiles: list[str] = []

    def get_seo_metadata(self, context=None) -> SeoMetadata:
        kwargs: dict[str, Any] = {}
        for attr, field in _VIEW_ATTRS.items():
            value = getattr(self, attr, None)
            if value is not None:
                kwargs[field] = value

        title = self.get_seo_title(context)
        if title is not None:
            kwargs["title"] = title
        canonical = self.get_seo_canonical(context)
        if canonical is not None:
            kwargs["canonical_url"] = canonical

        schema = self._build_seo_schema(context)
        if schema:
            kwargs["jsonld"] = schema
        return SeoMetadata.partial(**kwargs)

    # -- overridable pieces ---------------------------------------------------
    def get_seo_title(self, context=None):
        return self.seo_title

    def get_seo_canonical(self, context=None):
        return self.seo_canonical

    def _build_seo_schema(self, context) -> list[dict]:
        profiles = list(self.seo_schema_profiles or [])
        if not profiles:
            return []
        from ..schema import build_profiles

        obj = getattr(self, "object", None)
        return build_profiles(profiles, obj, context)

    # -- context wiring -------------------------------------------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = getattr(self, "object", None)
        metadata = attach_seo(self.request, view=self, obj=obj)
        ctx.setdefault("seo", metadata)
        return ctx


class SeoListViewMixin(SeoViewMixin):
    """Pagination-aware canonical + title for list/index pages."""

    def get_seo_canonical(self, context=None):
        if self.seo_canonical is not None:
            return self.seo_canonical
        request = getattr(self, "request", None)
        if request is None:
            return None
        from ..conf import get_settings

        include_page = get_settings()["LIST_CANONICAL_INCLUDES_PAGE"]
        page = self._current_page(request)
        if include_page and page and page > 1:
            return f"{request.path}?page={page}"
        return request.path

    def get_seo_title(self, context=None):
        title = self.seo_title
        if title is None:
            return None
        request = getattr(self, "request", None)
        page = self._current_page(request) if request is not None else None
        if page and page > 1:
            return f"{title} – Page {page}"
        return title

    @staticmethod
    def _current_page(request) -> int | None:
        try:
            return int(request.GET.get("page", 1))
        except (TypeError, ValueError):
            return None
