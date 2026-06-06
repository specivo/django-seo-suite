"""Resolver precedence, provider discovery, swappable class, defensive behavior."""

import pytest
from django.test import override_settings

from seo_suite.metadata import SeoMetadata
from seo_suite.providers import (
    PRECEDENCE_OBJECT,
    PRECEDENCE_PATH,
    Context,
    Provider,
)
from seo_suite.providers.registry import provider_registry
from seo_suite.resolver import BaseResolver, Resolver, get_resolver, reset_resolver


class _StubProvider(Provider):
    def __init__(self, metadata, priority):
        self.priority = priority
        self._metadata = metadata

    def provide(self, context):
        return self._metadata


class _DummyObject:
    def __init__(self, metadata):
        self._md = metadata

    def get_seo_metadata(self, context):
        return self._md


@pytest.fixture(autouse=True)
def _empty_registry():
    """These tests exercise resolver mechanics in isolation from contrib providers."""
    provider_registry.clear()
    yield


@pytest.fixture
def resolver():
    return Resolver()


class TestDefaults:
    def test_global_defaults_applied(self, resolver):
        # settings_test sets DEFAULTS title_suffix " | Example", robots index,follow
        result = resolver.resolve(Context(path="/"))
        assert result.title_suffix == " | Example"
        assert result.robots == "index,follow"

    def test_site_defaults_override_global(self, resolver):
        with override_settings(
            SEO_SUITE={
                "DEFAULTS": {"robots": "index,follow"},
                "SITE_DEFAULTS": {None: {"robots": "noindex"}},
            }
        ):
            result = resolver.resolve(Context(path="/"))
        assert result.robots == "noindex"


class TestPrecedence:
    def test_view_beats_object_beats_path(self, resolver):
        provider_registry.register(
            _StubProvider(SeoMetadata.partial(title="path"), PRECEDENCE_PATH)
        )
        obj = _DummyObject(SeoMetadata.partial(title="object"))
        view = _DummyObject(SeoMetadata.partial(title="view"))
        result = resolver.resolve(Context(path="/", object=obj, view=view))
        assert result.title == "view"

    def test_object_beats_path(self, resolver):
        provider_registry.register(
            _StubProvider(SeoMetadata.partial(title="path", meta_description="pd"), PRECEDENCE_PATH)
        )
        obj = _DummyObject(SeoMetadata.partial(title="object"))
        result = resolver.resolve(Context(path="/", object=obj))
        assert result.title == "object"
        assert result.meta_description == "pd"  # path's field survives

    def test_intermediate_priority_provider(self, resolver):
        # An extension provider at priority 35 sits between PATH(30) and OBJECT(40).
        provider_registry.register(
            _StubProvider(SeoMetadata.partial(title="path"), PRECEDENCE_PATH)
        )
        provider_registry.register(
            _StubProvider(SeoMetadata.partial(title="ext35"), 35)
        )
        result = resolver.resolve(Context(path="/"))
        assert result.title == "ext35"

        obj = _DummyObject(SeoMetadata.partial(title="object"))
        result2 = resolver.resolve(Context(path="/", object=obj))
        assert result2.title == "object"  # object (40) still wins over ext (35)


class TestProviderDiscovery:
    def test_no_registry_providers_means_no_db_layer(self, resolver):
        assert len(provider_registry) == 0
        result = resolver.resolve(Context(path="/"))
        # Only defaults contribute.
        assert result.title is None

    def test_abstaining_provider_ignored(self, resolver):
        provider_registry.register(_StubProvider(None, PRECEDENCE_PATH))
        result = resolver.resolve(Context(path="/"))
        assert result.title is None


class TestDefensiveBehavior:
    def test_failing_provider_does_not_break_resolution(self, resolver):
        class _Boom(Provider):
            priority = PRECEDENCE_PATH

            def provide(self, context):
                raise RuntimeError("boom")

        provider_registry.register(_Boom())
        obj = _DummyObject(SeoMetadata.partial(title="object"))
        result = resolver.resolve(Context(path="/", object=obj))
        assert result.title == "object"

    def test_failing_object_does_not_break_resolution(self, resolver):
        class _BadObj:
            def get_seo_metadata(self, context):
                raise ValueError("nope")

        result = resolver.resolve(Context(path="/", object=_BadObj()))
        assert result.robots == "index,follow"  # defaults still applied


class TestSwappableResolver:
    def test_get_resolver_uses_setting(self):
        with override_settings(SEO_SUITE={"RESOLVER_CLASS": "tests.test_resolver.CustomResolver"}):
            reset_resolver()
            r = get_resolver()
            assert isinstance(r, CustomResolver)
        reset_resolver()

    def test_default_resolver_is_resolver(self):
        reset_resolver()
        assert isinstance(get_resolver(), Resolver)


class CustomResolver(Resolver):
    """Used by TestSwappableResolver via import string."""

    def collect_layers(self, context):
        layers = super().collect_layers(context)
        layers.append((PRECEDENCE_OBJECT, SeoMetadata.partial(title="custom-injected")))
        return layers


class TestCustomResolverBehavior:
    def test_custom_resolver_injects_layer(self):
        r = CustomResolver()
        result = r.resolve(Context(path="/"))
        assert result.title == "custom-injected"


class TestBaseResolverContract:
    def test_base_collect_layers_not_implemented(self):
        with pytest.raises(NotImplementedError):
            BaseResolver().resolve(Context(path="/"))
