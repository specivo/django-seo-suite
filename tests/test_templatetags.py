"""Template tag rendering: full head, granular tags, escaping, overrides."""

import copy
import os

import pytest
from django.conf import settings as dj_settings
from django.template import Context, Template
from django.test import RequestFactory, override_settings

from seo_suite.metadata import HreflangAlt, SeoMetadata

rf = RequestFactory()


@pytest.fixture(autouse=True)
def _empty_registry():
    """Isolate tag rendering from any startup-registered DB providers."""
    from seo_suite.providers.registry import provider_registry

    provider_registry.clear()
    yield


def render(tpl: str, context: dict) -> str:
    return Template(tpl).render(Context(context))


def make_seo(**kwargs):
    return SeoMetadata.partial(**kwargs).finalize()


class TestSeoHead:
    def test_full_head_render(self):
        seo = make_seo(
            title="Home",
            title_suffix=" | Acme",
            meta_description="Welcome",
            robots="index,follow",
            canonical_url="https://acme.test/",
            og={"type": "website"},
        )
        out = render("{% load seo_suite %}{% seo_head %}", {"seo": seo, "request": rf.get("/")})
        assert "<title>Home | Acme</title>" in out
        assert '<meta name="description" content="Welcome">' in out
        assert '<meta name="robots" content="index,follow">' in out
        assert '<link rel="canonical" href="https://acme.test/">' in out
        assert '<meta property="og:type" content="website">' in out
        assert '<meta property="og:title" content="Home">' in out  # auto-populated

    def test_hreflang_render(self):
        seo = make_seo(
            title="x",
            hreflang=[HreflangAlt("en", "https://acme.test/en/"), HreflangAlt("x-default", "https://acme.test/")],
        )
        out = render("{% load seo_suite %}{% seo_hreflang %}", {"seo": seo})
        assert '<link rel="alternate" hreflang="en" href="https://acme.test/en/">' in out
        assert '<link rel="alternate" hreflang="x-default" href="https://acme.test/">' in out

    def test_twitter_card_defaults_render(self):
        seo = make_seo(title="x", og_image="https://acme.test/og.jpg")
        out = render("{% load seo_suite %}{% seo_twitter %}", {"seo": seo})
        assert '<meta name="twitter:card" content="summary_large_image">' in out
        assert '<meta name="twitter:image" content="https://acme.test/og.jpg">' in out


class TestJsonLd:
    def test_jsonld_rendered_in_script(self):
        seo = make_seo(jsonld=[{"@context": "https://schema.org", "@type": "WebPage", "name": "Hi"}])
        out = render("{% load seo_suite %}{% seo_jsonld %}", {"seo": seo})
        assert '<script type="application/ld+json">' in out
        assert '"@type": "WebPage"' in out

    def test_script_injection_escaped(self):
        seo = make_seo(jsonld=[{"@type": "WebPage", "name": "</script><script>alert(1)</script>"}])
        out = render("{% load seo_suite %}{% seo_jsonld %}", {"seo": seo})
        # The closing tag in data must be escaped, not break out of the block.
        assert "</script><script>alert" not in out
        assert "\\u003c/script\\u003e" in out


class TestGranularTags:
    def test_title_only(self):
        out = render("{% load seo_suite %}{% seo_title %}", {"seo": make_seo(title="T")})
        assert out.strip() == "<title>T</title>"

    def test_meta_only(self):
        out = render("{% load seo_suite %}{% seo_meta %}", {"seo": make_seo(meta_description="d", robots="noindex")})
        assert '<meta name="description" content="d">' in out
        assert '<meta name="robots" content="noindex">' in out

    def test_canonical_only(self):
        out = render("{% load seo_suite %}{% seo_canonical %}", {"seo": make_seo(canonical_url="/c/")})
        assert out.strip() == '<link rel="canonical" href="/c/">'


class TestMissingContextFallback:
    def test_resolves_on_the_spot_from_request(self):
        # No 'seo' in context; tag resolves via attach_seo(request).
        out = render("{% load seo_suite %}{% seo_meta %}", {"request": rf.get("/")})
        # default robots from settings_test DEFAULTS
        assert '<meta name="robots" content="index,follow">' in out


class TestTemplateOverride:
    def test_dirs_template_overrides_partial(self):
        templates = copy.deepcopy(dj_settings.TEMPLATES)
        override_dir = os.path.join(os.path.dirname(__file__), "override_templates")
        templates[0]["DIRS"] = [override_dir]
        with override_settings(TEMPLATES=templates):
            from django.template import engines

            engines._engines = {}  # force re-init with new DIRS
            out = render("{% load seo_suite %}{% seo_title %}", {"seo": make_seo(title="T")})
        engines._engines = {}
        assert 'data-overridden="1"' in out


class TestExtraHead:
    def test_extra_head_fragments_rendered(self):
        seo = make_seo(title="x", extra_head=["<meta name='verify' content='abc'>"])
        out = render("{% load seo_suite %}{% seo_extra_head %}", {"seo": seo, "request": rf.get("/")})
        assert "verify" in out
