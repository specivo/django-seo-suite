"""Resolved-payload caching with generation-counter invalidation.

When ``SEO_SUITE['CACHE_TTL'] > 0`` the resolver caches the *finalized* metadata
for object-backed resolutions, keyed by ``site:language:app.model:pk:vGEN`` (plus
the view class when present). A per-object generation counter is bumped on
save/delete, so a single ``incr`` invalidates every site/language/view variant
at once — no need to enumerate keys.

Django's cache pickles values, so ``cache.get`` returns a fresh copy each call;
per-request signal mutation of the returned metadata never corrupts the cache.

Resolutions with no stable object identity (list pages, model-less views) are
not cached here.
"""

from __future__ import annotations

from django.core.cache import caches

from .conf import get_settings
from .providers import Context


def cache_enabled() -> bool:
    return get_settings()["CACHE_TTL"] > 0


def _cache():
    return caches[get_settings()["CACHE_BACKEND"]]


def _prefix() -> str:
    return get_settings()["CACHE_KEY_PREFIX"]


def object_identity(context: Context) -> tuple[str, object] | None:
    obj = context.object
    if obj is None:
        return None
    pk = getattr(obj, "pk", None)
    meta = getattr(obj, "_meta", None)
    if pk is None or meta is None:
        return None
    return (f"{meta.app_label}.{meta.model_name}", pk)


def _generation_key(app_model: str, pk) -> str:
    return f"{_prefix()}:gen:{app_model}:{pk}"


def _generation(app_model: str, pk) -> int:
    return _cache().get(_generation_key(app_model, pk), 0)


def make_key(context: Context) -> str | None:
    ident = object_identity(context)
    if ident is None:
        return None
    app_model, pk = ident
    gen = _generation(app_model, pk)
    parts = [
        _prefix(),
        str(context.site_id),
        str(context.language),
        app_model,
        str(pk),
        f"v{gen}",
    ]
    if context.view is not None:
        parts.append(type(context.view).__qualname__)
    return ":".join(parts)


def cache_get(key: str):
    return _cache().get(key)


def cache_set(key: str, value) -> None:
    _cache().set(key, value, get_settings()["CACHE_TTL"])


def invalidate(app_model: str, pk) -> None:
    """Bump the object's generation counter so all cached variants expire."""
    gen_key = _generation_key(app_model, pk)
    cache = _cache()
    try:
        cache.incr(gen_key)
    except ValueError:
        cache.set(gen_key, 1)


def invalidate_instance(instance) -> None:
    meta = getattr(instance, "_meta", None)
    pk = getattr(instance, "pk", None)
    if meta is None or pk is None:
        return
    invalidate(f"{meta.app_label}.{meta.model_name}", pk)


def connect_invalidation() -> None:
    """Wire model save/delete + the public invalidate signal to invalidation.

    Idempotent (dispatch_uid guards), so calling it from every ``ready()`` is fine.
    """
    from django.db.models.signals import post_delete, post_save

    from .signals import seo_cache_invalidate

    post_save.connect(_on_model_change, dispatch_uid="seo_suite_invalidate_post_save")
    post_delete.connect(_on_model_change, dispatch_uid="seo_suite_invalidate_post_delete")
    seo_cache_invalidate.connect(_on_invalidate_signal, dispatch_uid="seo_suite_invalidate_signal")


def _on_model_change(sender, instance, **kwargs):
    # Connected globally; cheap isinstance gate keeps non-SEO saves fast.
    from .providers.model_mixin import SeoModelMixin

    if isinstance(instance, SeoModelMixin):
        invalidate_instance(instance)


def _on_invalidate_signal(sender, instance=None, identity=None, **kwargs):
    if instance is not None:
        invalidate_instance(instance)
        return
    if identity:
        app_model, _, pk = identity.rpartition(":")
        if app_model and pk:
            invalidate(app_model, pk)


# --- robots.txt rendered-body cache -------------------------------------------
# Keyed per serving-site, but with a single global generation counter folded in.
# Any RobotsTxt change bumps the generation, so every site's cached body expires
# at once — important because a global (site_id IS NULL) version can be served
# under many sites, and we can't enumerate which site keys to drop.


def robots_cache_enabled() -> bool:
    return get_settings()["ROBOTS_CACHE_TTL"] > 0


def _robots_gen_key() -> str:
    return f"{_prefix()}:robots:gen"


def _robots_gen() -> int:
    return _cache().get(_robots_gen_key(), 0)


def robots_cache_key(site_id) -> str:
    return f"{_prefix()}:robots:{site_id}:v{_robots_gen()}"


def get_robots(site_id):
    if not robots_cache_enabled():
        return None
    return _cache().get(robots_cache_key(site_id))


def set_robots(site_id, body: str) -> None:
    if not robots_cache_enabled():
        return
    _cache().set(robots_cache_key(site_id), body, get_settings()["ROBOTS_CACHE_TTL"])


def invalidate_robots(site_id=None) -> None:
    """Bump the global robots generation so every cached site body expires."""
    cache = _cache()
    try:
        cache.incr(_robots_gen_key())
    except ValueError:
        cache.set(_robots_gen_key(), 1)


def connect_robots_invalidation() -> None:
    """Bust the per-site robots cache whenever a RobotsTxt row changes."""
    from django.db.models.signals import post_delete, post_save

    from .models import RobotsTxt

    post_save.connect(_on_robots_change, sender=RobotsTxt, dispatch_uid="seo_suite_robots_post_save")
    post_delete.connect(_on_robots_change, sender=RobotsTxt, dispatch_uid="seo_suite_robots_post_delete")


def _on_robots_change(sender, instance, **kwargs):
    invalidate_robots(instance.site_id)
