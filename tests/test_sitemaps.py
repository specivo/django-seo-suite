"""SeoSitemap canonical/lastmod + hreflang helper + Django i18n alternates."""

import datetime
import types

from seo_suite.hreflang import build_hreflang_alternates
from seo_suite.metadata import HreflangAlt
from seo_suite.sitemaps import SeoSitemap


class _Item:
    def __init__(self, url, canonical=None, updated_at=None):
        self._url = url
        self._canonical = canonical
        self.updated_at = updated_at

    def get_absolute_url(self):
        return self._url

    def get_seo_metadata(self, context=None):
        from seo_suite.metadata import SeoMetadata

        if self._canonical is None:
            return SeoMetadata.partial()
        return SeoMetadata.partial(canonical_url=self._canonical)


class TestLocation:
    def test_location_uses_seo_canonical(self):
        sm = SeoSitemap()
        item = _Item("/fallback/", canonical="/canonical/path/")
        assert sm.location(item) == "/canonical/path/"

    def test_absolute_canonical_reduced_to_path(self):
        sm = SeoSitemap()
        item = _Item("/fallback/", canonical="https://example.com/abs/?x=1")
        assert sm.location(item) == "/abs/?x=1"

    def test_falls_back_to_get_absolute_url(self):
        sm = SeoSitemap()
        item = _Item("/fallback/")
        assert sm.location(item) == "/fallback/"


class TestLastmod:
    def test_lastmod_from_updated_at(self):
        sm = SeoSitemap()
        when = datetime.datetime(2026, 1, 1, 0, 0, 0)
        assert sm.lastmod(_Item("/x/", updated_at=when)) == when

    def test_lastmod_none_when_absent(self):
        sm = SeoSitemap()
        item = _Item("/x/")
        item.updated_at = None
        assert sm.lastmod(item) is None


class TestHreflangHelper:
    def test_non_i18n_path_one_alt_per_language(self):
        alts = build_hreflang_alternates("/plain/", include_x_default=False)
        langs = {a.lang for a in alts}
        assert langs == {"en", "ru", "th"}
        # not resolvable as i18n -> unchanged path
        assert all(a.href == "/plain/" for a in alts)

    def test_i18n_path_translated_per_language(self):
        alts = build_hreflang_alternates("/en/about/", include_x_default=False)
        by_lang = {a.lang: a.href for a in alts}
        assert by_lang["en"] == "/en/about/"
        assert by_lang["ru"] == "/ru/about/"
        assert by_lang["th"] == "/th/about/"

    def test_x_default_appended(self):
        alts = build_hreflang_alternates("/en/about/", include_x_default=True)
        assert HreflangAlt("x-default", "/en/about/") in alts  # LANGUAGE_CODE=en

    def test_absolute_with_request(self):
        from django.test import RequestFactory

        request = RequestFactory().get("/en/about/")
        alts = build_hreflang_alternates("/en/about/", request, include_x_default=False)
        assert alts[0].href.startswith("http://testserver/")


class TestI18nSitemapAlternates:
    def test_get_urls_emits_alternates_and_x_default(self):
        class _SM(SeoSitemap):
            i18n = True
            alternates = True
            x_default = True

            def items(self):
                return [_Item("/about/")]

        site = types.SimpleNamespace(domain="example.com", name="example.com")
        urls = _SM().get_urls(site=site, protocol="https")
        # i18n -> one entry per language
        assert len(urls) == 3
        entry = urls[0]
        assert "alternates" in entry
        hreflangs = {alt["lang_code"] for alt in entry["alternates"]}
        assert "x-default" in hreflangs
