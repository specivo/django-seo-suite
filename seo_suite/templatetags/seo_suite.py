"""Template tags that render the resolved metadata into ``<head>``.

``{% seo_head %}`` renders the whole block; granular tags render one piece each.
All read the finalized metadata from the template context (``seo``) or
``request.seo``, resolving on the spot as a last resort.
"""

from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

from ..context import attach_seo
from ..metadata import FinalizedSeoMetadata
from ..providers.registry import renderer_registry
from ..schema import render_jsonld_blocks
from ..signals import seo_head_rendering

register = template.Library()


def _get_seo(context) -> FinalizedSeoMetadata | None:
    """Resolve the metadata for the current template context."""
    seo = context.get("seo")
    if seo is not None:
        # SimpleLazyObject from the context processor resolves on access.
        return seo
    request = context.get("request")
    if request is not None:
        return attach_seo(request)
    return None


def _collect_extra_head(context, seo) -> list:
    fragments: list = []
    if seo is not None and getattr(seo, "extra_head", None):
        fragments.extend(seo.extra_head)
    request = context.get("request")
    for renderer in renderer_registry.get_all():
        try:
            fragment = renderer(request, seo)
        except Exception:  # noqa: BLE001
            continue
        if fragment:
            fragments.append(mark_safe(fragment))
    responses = seo_head_rendering.send(sender=None, request=request, metadata=seo)
    for _receiver, result in responses:
        if not result:
            continue
        if isinstance(result, (list, tuple)):
            fragments.extend(mark_safe(r) for r in result if r)
        else:
            fragments.append(mark_safe(result))
    return fragments


@register.inclusion_tag("seo_suite/head.html", takes_context=True)
def seo_head(context):
    seo = _get_seo(context)
    return {
        "seo": seo,
        "jsonld_blocks": render_jsonld_blocks(getattr(seo, "jsonld", None)) if seo else [],
        "extra_fragments": _collect_extra_head(context, seo),
    }


@register.inclusion_tag("seo_suite/_title.html", takes_context=True)
def seo_title(context):
    return {"seo": _get_seo(context)}


@register.inclusion_tag("seo_suite/_meta.html", takes_context=True)
def seo_meta(context):
    return {"seo": _get_seo(context)}


@register.inclusion_tag("seo_suite/_canonical.html", takes_context=True)
def seo_canonical(context):
    return {"seo": _get_seo(context)}


@register.inclusion_tag("seo_suite/_hreflang.html", takes_context=True)
def seo_hreflang(context):
    return {"seo": _get_seo(context)}


@register.inclusion_tag("seo_suite/_opengraph.html", takes_context=True)
def seo_opengraph(context):
    return {"seo": _get_seo(context)}


@register.inclusion_tag("seo_suite/_twitter.html", takes_context=True)
def seo_twitter(context):
    return {"seo": _get_seo(context)}


@register.inclusion_tag("seo_suite/_jsonld.html", takes_context=True)
def seo_jsonld(context):
    seo = _get_seo(context)
    return {"jsonld_blocks": render_jsonld_blocks(getattr(seo, "jsonld", None)) if seo else []}


@register.inclusion_tag("seo_suite/_extra_head.html", takes_context=True)
def seo_extra_head(context):
    seo = _get_seo(context)
    return {"extra_fragments": _collect_extra_head(context, seo)}
