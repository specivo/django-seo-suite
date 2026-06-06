import pytest


@pytest.fixture(autouse=True)
def _isolate_registries():
    """Isolate per-test registry/cache state without losing startup registrations.

    Snapshot the registries (which already contain any providers registered by
    installed contrib apps' ``ready()``) and restore them afterwards, so a test
    that registers an extra provider/profile doesn't leak into the next test.
    """
    from django.core.cache import cache

    from seo_suite.providers.registry import provider_registry, renderer_registry
    from seo_suite.resolver import reset_resolver
    from seo_suite.schema.registry import schema_registry

    saved_providers = dict(provider_registry._providers)
    saved_renderers = dict(renderer_registry._renderers)
    saved_profiles = dict(schema_registry._profiles)
    reset_resolver()
    cache.clear()
    yield
    provider_registry._providers.clear()
    provider_registry._providers.update(saved_providers)
    renderer_registry._renderers.clear()
    renderer_registry._renderers.update(saved_renderers)
    schema_registry._profiles.clear()
    schema_registry._profiles.update(saved_profiles)
    reset_resolver()
    cache.clear()
