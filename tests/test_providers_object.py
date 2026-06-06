"""ObjectProvider (seo_suite.contrib.seoobject) — GenericFK + allowlist gating."""

import pytest
from django.apps import apps as _apps
from django.test import override_settings

from seo_suite.providers import Context

if not _apps.is_installed("seo_suite.contrib.seoobject"):
    pytest.skip("seoobject contrib app not installed", allow_module_level=True)

pytestmark = pytest.mark.django_db


@pytest.fixture
def SeoObject():
    from seo_suite.contrib.seoobject.models import SeoObject

    return SeoObject


@pytest.fixture
def provider():
    from seo_suite.contrib.seoobject.provider import ObjectProvider

    return ObjectProvider()


def _make_seoobject(SeoObject, obj, **kwargs):
    from django.contrib.contenttypes.models import ContentType

    return SeoObject.objects.create(
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        **kwargs,
    )


class TestAllowlistGating:
    def test_not_allowlisted_returns_none_without_query(self, provider, django_assert_num_queries):
        from tests.testapp.models import Category

        cat = Category.objects.create(name="X")
        # No OBJECT_MODELS configured -> provider must not hit the DB.
        with django_assert_num_queries(0):
            assert provider.provide(Context(object=cat)) is None

    def test_allowlisted_model_resolves(self, SeoObject, provider):
        from tests.testapp.models import Category

        cat = Category.objects.create(name="X")
        _make_seoobject(SeoObject, cat, title="Override Title")
        with override_settings(SEO_SUITE={"OBJECT_MODELS": ["testapp.category"]}):
            md = provider.provide(Context(object=cat, language="en"))
        assert md.title == "Override Title"

    def test_allowlist_case_insensitive(self, SeoObject, provider):
        from tests.testapp.models import Category

        cat = Category.objects.create(name="X")
        _make_seoobject(SeoObject, cat, title="T")
        with override_settings(SEO_SUITE={"OBJECT_MODELS": ["testapp.Category"]}):
            md = provider.provide(Context(object=cat, language="en"))
        assert md.title == "T"


class TestObjectMatch:
    def test_no_row_returns_none(self, provider):
        from tests.testapp.models import Category

        cat = Category.objects.create(name="X")
        with override_settings(SEO_SUITE={"OBJECT_MODELS": ["testapp.category"]}):
            assert provider.provide(Context(object=cat)) is None

    def test_none_object_returns_none(self, provider):
        with override_settings(SEO_SUITE={"OBJECT_MODELS": ["testapp.category"]}):
            assert provider.provide(Context(object=None)) is None


class TestProviderRegisteredAtStartup:
    def test_objectprovider_in_registry(self):
        from seo_suite.providers.registry import provider_registry

        names = [type(p).__name__ for p in provider_registry.get_all()]
        assert "ObjectProvider" in names
