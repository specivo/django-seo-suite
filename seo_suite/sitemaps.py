"""``SeoSitemap`` — a ``django.contrib.sitemaps.Sitemap`` base that reuses the
resolved SEO canonical for each URL, so sitemap ``<loc>`` always matches the
page's ``rel="canonical"`` (a common, hard-to-spot SEO bug otherwise).

Hreflang is delegated to Django's built-in sitemap support — set ``i18n``,
``alternates`` and ``x_default`` on your subclass::

    class ArticleSitemap(SeoSitemap):
        i18n = True
        alternates = True
        x_default = True
        def items(self):
            return Article.objects.filter(published=True)
"""

from __future__ import annotations

from urllib.parse import urlsplit

from django.contrib.sitemaps import Sitemap

from .metadata import UNSET

_LASTMOD_FIELDS = ("updated_at", "modified", "date_modified", "updated", "last_modified")


class SeoSitemap(Sitemap):
    """Sitemap whose ``location`` is the object's resolved SEO canonical."""

    def location(self, item):
        canonical = self._seo_canonical(item)
        if canonical:
            parts = urlsplit(canonical)
            path = parts.path or "/"
            return f"{path}?{parts.query}" if parts.query else path
        return super().location(item)

    def lastmod(self, item):
        for attr in _LASTMOD_FIELDS:
            value = getattr(item, attr, None)
            if value:
                return value
        return None

    @staticmethod
    def _seo_canonical(item):
        getter = getattr(item, "get_seo_metadata", None)
        if not callable(getter):
            return None
        try:
            canonical = getter().canonical_url
        except Exception:  # noqa: BLE001
            return None
        if canonical in (None, UNSET, ""):
            return None
        return canonical
