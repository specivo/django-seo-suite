"""Build on-page ``hreflang`` alternates from the same source as sitemaps.

``build_hreflang_alternates`` uses Django's ``translate_url`` so it works with
``i18n_patterns``: for a path it produces one ``HreflangAlt`` per configured
language (plus an optional ``x-default``). Use it from a view's
``get_seo_metadata`` to populate ``hreflang``; the ``{% seo_hreflang %}`` tag and
the sitemap alternates then agree because both derive from ``LANGUAGES``.
"""

from __future__ import annotations

from django.conf import settings as django_settings

from .conf import get_settings
from .metadata import HreflangAlt


def build_hreflang_alternates(path, request=None, *, languages=None, include_x_default=None):
    from django.urls import translate_url

    if languages is None:
        languages = [code for code, _name in getattr(django_settings, "LANGUAGES", [])]
    if include_x_default is None:
        include_x_default = get_settings()["HREFLANG_X_DEFAULT"]

    def _abs(url: str) -> str:
        return request.build_absolute_uri(url) if request is not None else url

    alternates = [HreflangAlt(code, _abs(translate_url(path, code))) for code in languages]

    if include_x_default:
        default_lang = getattr(django_settings, "LANGUAGE_CODE", None)
        if default_lang:
            alternates.append(HreflangAlt("x-default", _abs(translate_url(path, default_lang))))
    return alternates
