"""Putting resolved metadata into the template context.

Two paths, lightest-first:

* ``attach_seo(request, view=..., object=...)`` — called by ``SeoViewMixin`` from
  ``get_context_data``. Resolves once and stashes the result on
  ``request.seo`` (memoized) so the template tags and the context processor all
  reuse it.
* ``seo`` context processor — a lazy fallback for pages rendered by views that
  don't use the mixin (FBVs, third-party views). It resolves on first template
  access only, so pages that never use ``{% seo_head %}`` pay nothing.
"""

from __future__ import annotations

from django.utils.functional import SimpleLazyObject

from .metadata import FinalizedSeoMetadata
from .providers import Context
from .resolver import get_resolver
from .sites import get_current_site_id

_CACHE_ATTR = "_seo_suite_metadata"


def resolve_seo(request=None, *, view=None, obj=None, language=None) -> FinalizedSeoMetadata:
    """Build a :class:`Context` and run the resolver. No caching of its own."""
    site_id = get_current_site_id(request)
    if language is None:
        language = _current_language(request)
    context = Context(
        request=request,
        view=view,
        object=obj,
        site_id=site_id,
        language=language,
    )
    return get_resolver().resolve(context)


def attach_seo(request, *, view=None, obj=None, language=None) -> FinalizedSeoMetadata:
    """Resolve metadata for the request and memoize it on the request object."""
    cached = getattr(request, _CACHE_ATTR, None)
    if cached is not None:
        return cached
    metadata = resolve_seo(request, view=view, obj=obj, language=language)
    try:
        setattr(request, _CACHE_ATTR, metadata)
    except Exception:  # noqa: BLE001 - request may be a non-standard object
        pass
    return metadata


def get_attached(request) -> FinalizedSeoMetadata | None:
    return getattr(request, _CACHE_ATTR, None)


def seo(request):
    """Context processor exposing a lazy ``seo`` variable to all templates."""

    def _resolve():
        return attach_seo(request)

    return {"seo": SimpleLazyObject(_resolve)}


def _current_language(request) -> str | None:
    try:
        from django.utils import translation

        return translation.get_language()
    except Exception:  # noqa: BLE001
        return None
