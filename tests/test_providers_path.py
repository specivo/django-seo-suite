"""PathProvider (seo_suite.contrib.seopath) resolution + specificity."""

import pytest
from django.apps import apps as _apps

from seo_suite.providers import Context
from seo_suite.resolver import Resolver

if not _apps.is_installed("seo_suite.contrib.seopath"):
    pytest.skip("seopath contrib app not installed", allow_module_level=True)

pytestmark = pytest.mark.django_db


@pytest.fixture
def SeoPath():
    from seo_suite.contrib.seopath.models import SeoPath

    return SeoPath


@pytest.fixture
def provider():
    from seo_suite.contrib.seopath.provider import PathProvider

    return PathProvider()


class TestPathMatch:
    def test_matches_by_path(self, SeoPath, provider):
        SeoPath.objects.create(path="/about/", title="About Us", description="d")
        md = provider.provide(Context(path="/about/", language="en"))
        assert md.title == "About Us"
        assert md.meta_description == "d"

    def test_no_match_returns_none(self, provider):
        assert provider.provide(Context(path="/missing/", language="en")) is None

    def test_no_path_returns_none(self, provider):
        assert provider.provide(Context(path=None)) is None


class TestSpecificity:
    def test_language_specific_beats_global(self, SeoPath, provider):
        SeoPath.objects.create(path="/p/", title="Global", language="")
        SeoPath.objects.create(path="/p/", title="English", language="en")
        md = provider.provide(Context(path="/p/", language="en"))
        assert md.title == "English"

    def test_site_specific_beats_global(self, SeoPath, provider):
        SeoPath.objects.create(path="/p/", title="AllSites", site_id=None)
        SeoPath.objects.create(path="/p/", title="Site5", site_id=5)
        md = provider.provide(Context(path="/p/", site_id=5, language=""))
        assert md.title == "Site5"

    def test_other_site_falls_back_to_global(self, SeoPath, provider):
        SeoPath.objects.create(path="/p/", title="AllSites", site_id=None)
        SeoPath.objects.create(path="/p/", title="Site5", site_id=5)
        md = provider.provide(Context(path="/p/", site_id=9, language=""))
        assert md.title == "AllSites"


class TestExtraJsonLd:
    def test_extra_jsonld_passed_through(self, SeoPath, provider):
        SeoPath.objects.create(path="/p/", extra_jsonld=[{"@type": "WebPage", "name": "x"}])
        md = provider.provide(Context(path="/p/"))
        assert md.jsonld == [{"@type": "WebPage", "name": "x"}]


class TestResolverIntegration:
    def test_path_layer_below_object(self, SeoPath):
        # Registered at app startup; resolver should include it under object/view.
        SeoPath.objects.create(path="/p/", title="FromPath", robots="noindex")

        class _Obj:
            def get_seo_metadata(self, context):
                from seo_suite.metadata import SeoMetadata

                return SeoMetadata.partial(title="FromObject")

        r = Resolver()
        result = r.resolve(Context(path="/p/", object=_Obj()))
        assert result.title == "FromObject"  # object beats path
        assert result.robots == "noindex"  # path field survives

    def test_path_only_resolution(self, SeoPath):
        SeoPath.objects.create(path="/solo/", title="Solo")
        r = Resolver()
        result = r.resolve(Context(path="/solo/"))
        assert result.title == "Solo"


class TestProviderRegisteredAtStartup:
    def test_pathprovider_in_registry(self):
        from seo_suite.providers.registry import provider_registry

        names = [type(p).__name__ for p in provider_registry.get_all()]
        assert "PathProvider" in names
