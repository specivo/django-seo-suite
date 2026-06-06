"""The extension-point stability contract — what the paid package depends on.

Mechanism tests run everywhere. The install-and-go test runs only when the fake
"pro" app is installed (SEO_SUITE_TEST_PRO=1).
"""

import pytest
from django.apps import apps as _apps
from django.test import RequestFactory, override_settings

from seo_suite.context import resolve_seo
from seo_suite.providers import Context, Provider
from seo_suite.providers.registry import provider_registry, renderer_registry
from seo_suite.resolver import Resolver

rf = RequestFactory()
PRO_INSTALLED = _apps.is_installed("tests.fakepro")


# --------------------------------------------------------------------- mechanisms
class TestRegistryAppend:
    def test_register_and_unregister(self):
        class P(Provider):
            priority = 35

            def provide(self, context):
                return None

        p = P()
        provider_registry.register(p, name="probe")
        assert "probe" in provider_registry
        provider_registry.unregister("probe")
        assert "probe" not in provider_registry

    def test_registration_idempotent_by_name(self):
        class P(Provider):
            def provide(self, context):
                return None

        before = len(provider_registry)
        provider_registry.register(P(), name="dupe")
        provider_registry.register(P(), name="dupe")
        assert len(provider_registry) == before + 1
        provider_registry.unregister("dupe")

    def test_priority_ordering(self):
        order = []

        def make(pr):
            class P(Provider):
                priority = pr

                def provide(self, context):
                    order.append(pr)
                    return None

            return P()

        provider_registry.clear()
        provider_registry.register(make(50), name="hi")
        provider_registry.register(make(10), name="lo")
        provider_registry.register(make(35), name="mid")
        Resolver().resolve(Context(path="/"))
        assert order == [10, 35, 50]


class TestRendererInjection:
    def test_renderer_fragment_in_head(self):
        renderer_registry.register("probe_r", lambda request, seo: '<meta name="x" content="1">')
        from django.template import Context as TplContext
        from django.template import Template

        out = Template("{% load seo_suite %}{% seo_extra_head %}").render(
            TplContext({"request": rf.get("/")})
        )
        assert '<meta name="x" content="1">' in out


class TestSeoHeadRenderingSignal:
    def test_signal_fragment_collected(self):
        from seo_suite.signals import seo_head_rendering

        def receiver(sender, request, metadata, **kwargs):
            return '<meta name="sig" content="1">'

        seo_head_rendering.connect(receiver, dispatch_uid="probe_sig")
        try:
            from django.template import Context as TplContext
            from django.template import Template

            out = Template("{% load seo_suite %}{% seo_extra_head %}").render(
                TplContext({"request": rf.get("/")})
            )
            assert '<meta name="sig" content="1">' in out
        finally:
            seo_head_rendering.disconnect(dispatch_uid="probe_sig")


class TestAutodiscoverConvention:
    def test_seo_extensions_module_imported_at_startup(self):
        from tests.testapp import seo_extensions

        assert seo_extensions.DISCOVERED["count"] >= 1


class TestEntryPointLoading:
    def test_entry_point_callable_invoked(self, monkeypatch):
        called = {}

        class FakeEP:
            name = "fake"

            def load(self):
                def register():
                    called["ran"] = True

                return register

        import importlib.metadata as md

        monkeypatch.setattr(md, "entry_points", lambda group=None: [FakeEP()])
        from seo_suite.extension import _load_entry_points

        _load_entry_points()
        assert called.get("ran") is True

    def test_broken_entry_point_does_not_raise(self, monkeypatch):
        class BadEP:
            name = "bad"

            def load(self):
                raise RuntimeError("boom")

        import importlib.metadata as md

        monkeypatch.setattr(md, "entry_points", lambda group=None: [BadEP()])
        from seo_suite.extension import _load_entry_points

        _load_entry_points()  # must swallow the error


class TestSwappableResolverContract:
    def test_resolver_class_setting_respected(self):
        with override_settings(SEO_SUITE={"RESOLVER_CLASS": "tests.test_extension_points.TaggingResolver"}):
            from seo_suite.resolver import get_resolver, reset_resolver

            reset_resolver()
            assert isinstance(get_resolver(), TaggingResolver)
            reset_resolver()


class TaggingResolver(Resolver):
    pass


# --------------------------------------------------------------- install-and-go
@pytest.mark.skipif(not PRO_INSTALLED, reason="fakepro not installed (set SEO_SUITE_TEST_PRO=1)")
class TestInstallAndGo:
    def test_provider_registered_at_intermediate_priority(self):
        names = {type(p).__name__: p.priority for p in provider_registry.get_all()}
        assert "ProKeywordsProvider" in names
        assert names["ProKeywordsProvider"] == 35

    def test_pro_provider_participates_below_object(self):
        class _Obj:
            def get_seo_metadata(self, context):
                from seo_suite.metadata import SeoMetadata

                return SeoMetadata.partial(title="ObjTitle")

        result = resolve_seo(rf.get("/"), obj=_Obj())
        assert result.title == "ObjTitle"
        assert result.meta_keywords == "pro-keywords"  # pro provider contributed

    def test_pro_schema_profile_registered(self):
        from seo_suite.schema.registry import schema_registry

        assert "pro:Demo" in schema_registry

    def test_pro_renderer_and_signal(self):
        from django.template import Context as TplContext
        from django.template import Template

        from tests.fakepro import seo_extensions

        out = Template("{% load seo_suite %}{% seo_head %}").render(
            TplContext({"request": rf.get("/")})
        )
        assert 'name="pro-verify"' in out
        assert seo_extensions.EVENTS["resolved"] >= 1
