"""JSON-LD schema profile library, declarative enablement, and serialization."""

import datetime
import json

from seo_suite.providers import Context
from seo_suite.providers.model_mixin import SeoModelMixin
from seo_suite.schema import build_profiles, default_serializer, schema_registry
from seo_suite.schema.registry import SchemaProfile

CTX = Context(path="/")


class _FakeArticle:
    headline = "Big News"
    summary = "Something happened"
    image = "/img/news.jpg"
    date_published = datetime.date(2026, 1, 2)
    updated_at = datetime.datetime(2026, 1, 3, 12, 0, 0)
    author = "Jane Doe"

    def get_absolute_url(self):
        return "/news/big/"


class TestFreeProfilesRegistered:
    def test_all_free_profiles_present(self):
        for key in ["WebPage", "WebSite", "Organization", "Person", "BreadcrumbList", "Article", "FAQPage", "Product"]:
            assert key in schema_registry


class TestWebPage:
    def test_webpage_basic(self):
        blocks = build_profiles(["WebPage"], _FakeArticle(), CTX)
        assert len(blocks) == 1
        wp = blocks[0]
        assert wp["@type"] == "WebPage"
        assert wp["@context"] == "https://schema.org"
        assert wp["name"] == "Big News"
        assert wp["url"] == "/news/big/"


class TestArticle:
    def test_article_fields(self):
        block = build_profiles(["Article"], _FakeArticle(), CTX)[0]
        assert block["@type"] == "Article"
        assert block["headline"] == "Big News"
        assert block["description"] == "Something happened"
        assert block["image"] == "/img/news.jpg"
        assert block["datePublished"] == "2026-01-02"
        assert block["dateModified"] == "2026-01-03T12:00:00"
        assert block["author"] == {"@type": "Person", "name": "Jane Doe"}


class TestBreadcrumbList:
    def test_from_get_breadcrumbs_tuples(self):
        class _Obj:
            def get_breadcrumbs(self):
                return [("Home", "/"), ("News", "/news/"), ("Big", "/news/big/")]

        block = build_profiles(["BreadcrumbList"], _Obj(), CTX)[0]
        assert block["@type"] == "BreadcrumbList"
        assert len(block["itemListElement"]) == 3
        assert block["itemListElement"][0] == {
            "@type": "ListItem",
            "position": 1,
            "name": "Home",
            "item": "/",
        }

    def test_skipped_when_no_breadcrumbs(self):
        assert build_profiles(["BreadcrumbList"], object(), CTX) == []


class TestFAQPage:
    def test_from_get_faqs_dicts(self):
        class _Obj:
            def get_faqs(self):
                return [{"question": "Q1?", "answer": "A1"}, {"q": "Q2?", "a": "A2"}]

        block = build_profiles(["FAQPage"], _Obj(), CTX)[0]
        assert block["@type"] == "FAQPage"
        assert len(block["mainEntity"]) == 2
        assert block["mainEntity"][0]["acceptedAnswer"]["text"] == "A1"


class TestProduct:
    def test_product_with_offer(self):
        class _Obj:
            name = "Gadget"
            description = "A nice gadget"
            sku = "SKU1"
            price = "19.99"
            currency = "USD"
            availability = "https://schema.org/InStock"

        block = build_profiles(["Product"], _Obj(), CTX)[0]
        assert block["name"] == "Gadget"
        assert block["sku"] == "SKU1"
        assert block["offers"] == {
            "@type": "Offer",
            "price": "19.99",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
        }


class TestOverrideHook:
    def test_get_schema_data_overrides_fields(self):
        class _Obj:
            title = "Original"

            def get_schema_data(self, key, context=None):
                if key == "WebPage":
                    return {"name": "Overridden", "extra": "x"}
                return {}

        block = build_profiles(["WebPage"], _Obj(), CTX)[0]
        assert block["name"] == "Overridden"
        assert block["extra"] == "x"


class TestUnknownProfile:
    def test_unknown_key_skipped(self):
        assert build_profiles(["DoesNotExist"], _FakeArticle(), CTX) == []


class TestDeclarativeEnablement:
    def test_model_mixin_builds_jsonld_from_profiles(self):
        class FakeArticleModel(SeoModelMixin):
            SEO_SCHEMA_PROFILES = ["Article"]
            headline = "Declared"
            summary = "desc"

            def get_absolute_url(self):
                return "/a/"

        md = FakeArticleModel().get_seo_metadata(CTX)
        assert isinstance(md.jsonld, list)
        assert md.jsonld[0]["@type"] == "Article"
        assert md.jsonld[0]["headline"] == "Declared"

    def test_no_profiles_means_no_jsonld(self):
        from seo_suite.metadata import UNSET

        class Plain(SeoModelMixin):
            title = "x"

        assert Plain().get_seo_metadata(CTX).jsonld is UNSET


class TestSerializer:
    def test_default_serializer_produces_valid_json(self):
        out = default_serializer({"@type": "WebPage", "name": "Hi & Bye"})
        # & is escaped to unicode; still valid JSON
        assert json.loads(out) == {"@type": "WebPage", "name": "Hi & Bye"}

    def test_serializer_escapes_angle_brackets(self):
        out = default_serializer({"x": "</script>"})
        assert "</script>" not in out
        assert "\\u003c" in out


class TestRegistryNamespacing:
    def test_register_namespaced_profile(self):
        class ProProduct(SchemaProfile):
            key = "pro:Product"

            def build(self, obj, context):
                return {"@type": "Product", "pro": True}

        schema_registry.register(ProProduct())
        try:
            block = build_profiles(["pro:Product"], object(), CTX)[0]
            assert block["pro"] is True
            # free Product still independent
            assert "pro:Product" in schema_registry
        finally:
            schema_registry.unregister("pro:Product")
