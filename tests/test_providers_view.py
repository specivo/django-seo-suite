"""SeoViewMixin / SeoListViewMixin and the view->context wiring."""

import pytest
from django.test import RequestFactory, override_settings
from django.views.generic import DetailView, ListView, TemplateView

from seo_suite.context import resolve_seo
from seo_suite.metadata import SeoMetadata
from seo_suite.providers.view_mixin import SeoListViewMixin, SeoViewMixin
from tests.testapp.models import Page

rf = RequestFactory()


class HomeView(SeoViewMixin, TemplateView):
    template_name = "noop.html"
    seo_title = "Home"
    seo_description = "Welcome"
    seo_robots = "index,follow"


class OverrideView(SeoViewMixin, TemplateView):
    template_name = "noop.html"

    def get_seo_metadata(self, context=None):
        return SeoMetadata.partial(title="Dynamic", meta_description="computed")


class PageListView(SeoListViewMixin, ListView):
    model = Page
    seo_title = "All Pages"


class PageDetailView(SeoViewMixin, DetailView):
    model = Page
    seo_title = "View Wins"


class TestClassAttrs:
    def test_attrs_become_metadata(self):
        view = HomeView()
        view.request = rf.get("/")
        md = view.get_seo_metadata()
        assert md.title == "Home"
        assert md.meta_description == "Welcome"
        assert md.robots == "index,follow"

    def test_override_get_seo_metadata(self):
        view = OverrideView()
        view.request = rf.get("/")
        md = view.get_seo_metadata()
        assert md.title == "Dynamic"
        assert md.meta_description == "computed"


class TestListViewPagination:
    def test_canonical_includes_page_when_paginated(self):
        view = PageListView()
        view.request = rf.get("/pages/?page=2")
        assert view.get_seo_canonical() == "/pages/?page=2"

    def test_canonical_is_path_on_first_page(self):
        view = PageListView()
        view.request = rf.get("/pages/")
        assert view.get_seo_canonical() == "/pages/"

    def test_title_gets_page_suffix(self):
        view = PageListView()
        view.request = rf.get("/pages/?page=3")
        assert view.get_seo_title() == "All Pages – Page 3"

    @override_settings(SEO_SUITE={"LIST_CANONICAL_INCLUDES_PAGE": False})
    def test_canonical_excludes_page_when_configured(self):
        view = PageListView()
        view.request = rf.get("/pages/?page=2")
        assert view.get_seo_canonical() == "/pages/"


@pytest.mark.django_db
class TestDetailViewDelegation:
    def test_view_overrides_object(self):
        page = Page.objects.create(title="Object Title", description="d", slug="p")
        view = PageDetailView()
        view.request = rf.get("/pages/p/")
        view.object = page
        result = resolve_seo(view.request, view=view, obj=page)
        # view title wins, object's canonical (get_absolute_url) survives
        assert result.title == "View Wins"
        assert result.canonical_url.endswith("/pages/p/")

    def test_object_fields_used_when_view_silent(self):
        page = Page.objects.create(title="Just Object", description="desc", slug="q")

        class SilentDetail(SeoViewMixin, DetailView):
            model = Page

        view = SilentDetail()
        view.request = rf.get("/pages/q/")
        view.object = page
        result = resolve_seo(view.request, view=view, obj=page)
        assert result.title == "Just Object"
        assert result.meta_description == "desc"


class TestContextWiring:
    def test_get_context_data_sets_seo(self):
        view = HomeView()
        view.request = rf.get("/")
        ctx = view.get_context_data()
        assert "seo" in ctx
        assert ctx["seo"].title == "Home"

    def test_attach_seo_memoized_on_request(self):
        from seo_suite.context import attach_seo, get_attached

        request = rf.get("/")
        view = HomeView()
        view.request = request
        first = attach_seo(request, view=view)
        assert get_attached(request) is first
        # second call returns the memoized instance
        assert attach_seo(request, view=view) is first
