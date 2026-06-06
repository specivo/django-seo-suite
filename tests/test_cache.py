"""Resolved-payload caching, generation-counter invalidation, signal-on-hit."""

import pytest
from django.test import RequestFactory, override_settings

from seo_suite import cache as cache_module
from seo_suite.providers import Context
from seo_suite.resolver import Resolver
from seo_suite.signals import seo_cache_invalidate, seo_metadata_resolved
from tests.testapp.models import Page

rf = RequestFactory()
CACHE_ON = {"CACHE_TTL": 300, "DEFAULTS": {"robots": "index,follow"}}


class TestKeyConstruction:
    def test_no_object_means_no_key(self):
        assert cache_module.make_key(Context(path="/")) is None

    @pytest.mark.django_db
    def test_object_key_includes_identity(self):
        page = Page.objects.create(title="T", slug="t")
        with override_settings(SEO_SUITE=CACHE_ON):
            key = cache_module.make_key(Context(object=page, site_id=None, language="en"))
        assert "testapp.page" in key
        assert str(page.pk) in key


@pytest.mark.django_db
class TestCachingBehavior:
    def test_cache_hit_returns_stale_until_invalidated(self):
        page = Page.objects.create(title="Original", slug="p")
        with override_settings(SEO_SUITE=CACHE_ON):
            r = Resolver()
            first = r.resolve(Context(object=page, language="en"))
            assert first.title == "Original"

            # mutate in memory only (no save) -> key unchanged -> cache hit
            page.title = "Changed"
            second = r.resolve(Context(object=page, language="en"))
            assert second.title == "Original"  # served from cache

            # explicit invalidation bumps generation -> recompute
            cache_module.invalidate_instance(page)
            third = r.resolve(Context(object=page, language="en"))
            assert third.title == "Changed"

    def test_disabled_cache_always_recomputes(self):
        page = Page.objects.create(title="A", slug="q")
        r = Resolver()  # default CACHE_TTL=0
        r.resolve(Context(object=page, language="en"))
        page.title = "B"
        assert r.resolve(Context(object=page, language="en")).title == "B"

    def test_post_save_invalidates(self):
        page = Page.objects.create(title="First", slug="s")
        with override_settings(SEO_SUITE=CACHE_ON):
            r = Resolver()
            assert r.resolve(Context(object=page, language="en")).title == "First"
            page.title = "Second"
            page.save()  # post_save -> invalidation
            assert r.resolve(Context(object=page, language="en")).title == "Second"


@pytest.mark.django_db
class TestSignalFiresOnHitAndMiss:
    def test_resolved_signal_fires_each_resolve(self):
        page = Page.objects.create(title="X", slug="sig")
        calls = []

        def receiver(sender, metadata, context, **kwargs):
            calls.append(metadata.title)

        seo_metadata_resolved.connect(receiver, dispatch_uid="test_recv")
        try:
            with override_settings(SEO_SUITE=CACHE_ON):
                r = Resolver()
                r.resolve(Context(object=page, language="en"))  # miss
                r.resolve(Context(object=page, language="en"))  # hit
            assert len(calls) == 2  # fired on both
        finally:
            seo_metadata_resolved.disconnect(dispatch_uid="test_recv")

    def test_receiver_mutation_does_not_corrupt_cache(self):
        page = Page.objects.create(title="Base", slug="mut")
        state = {"mutate": True}

        def receiver(sender, metadata, context, **kwargs):
            if state["mutate"]:
                object.__setattr__(metadata, "title", "Mutated")

        seo_metadata_resolved.connect(receiver, dispatch_uid="test_mut")
        try:
            with override_settings(SEO_SUITE=CACHE_ON):
                r = Resolver()
                first = r.resolve(Context(object=page, language="en"))
                assert first.title == "Mutated"
                # Stop mutating; cache hit must return the un-mutated cached copy.
                state["mutate"] = False
                second = r.resolve(Context(object=page, language="en"))
                assert second.title == "Base"
        finally:
            seo_metadata_resolved.disconnect(dispatch_uid="test_mut")


@pytest.mark.django_db
class TestInvalidateSignal:
    def test_invalidate_signal_with_instance(self):
        page = Page.objects.create(title="One", slug="inv")
        with override_settings(SEO_SUITE=CACHE_ON):
            r = Resolver()
            r.resolve(Context(object=page, language="en"))
            page.title = "Two"
            seo_cache_invalidate.send(sender=None, instance=page)
            assert r.resolve(Context(object=page, language="en")).title == "Two"
