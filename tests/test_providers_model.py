"""SeoModelMixin field-map / convention resolution and SeoModelFieldsMixin columns."""

from seo_suite.providers.model_mixin import _resolve_source
from tests.testapp.models import Category, MappedArticle, Page, Product


class TestConventions:
    def test_title_and_description_from_conventional_fields(self):
        page = Page(title="Hello", description="A page", slug="hello")
        md = page.get_seo_metadata()
        assert md.title == "Hello"
        assert md.meta_description == "A page"

    def test_canonical_from_get_absolute_url(self):
        page = Page(title="Hello", slug="hello")
        md = page.get_seo_metadata()
        assert md.canonical_url == "/pages/hello/"

    def test_title_from_name_convention(self):
        cat = Category(name="Widgets")
        md = cat.get_seo_metadata()
        assert md.title == "Widgets"

    def test_blank_description_stays_unset(self):
        from seo_suite.metadata import UNSET

        page = Page(title="Hi", description="", slug="hi")
        md = page.get_seo_metadata()
        # Empty string field -> no value -> UNSET (not explicit empty)
        assert md.meta_description is UNSET


class TestFieldMap:
    def test_explicit_map_wins(self):
        art = MappedArticle(headline="Head", blurb="Blurb text", image_url="/i.jpg")
        md = art.get_seo_metadata()
        assert md.title == "Head"
        assert md.meta_description == "Blurb text"
        assert md.og_image == "/i.jpg"


class TestResolveSource:
    def test_filefield_like_returns_url_when_present(self):
        class _FileLike:
            name = "x.jpg"
            url = "/media/x.jpg"

        class _Obj:
            image = _FileLike()

        assert _resolve_source(_Obj(), "image") == "/media/x.jpg"

    def test_filefield_like_returns_none_when_empty(self):
        class _FileLike:
            name = ""
            url = "/media/x.jpg"

        class _Obj:
            image = _FileLike()

        assert _resolve_source(_Obj(), "image") is None

    def test_callable_resolved(self):
        class _Obj:
            def get_absolute_url(self):
                return "/abs/"

        assert _resolve_source(_Obj(), "get_absolute_url") == "/abs/"

    def test_missing_attr_is_none(self):
        assert _resolve_source(object(), "nope") is None


class TestModelFieldsMixinColumns:
    def test_seo_column_overrides_convention(self):
        p = Product(name="Plain Name", seo_title="SEO Title", seo_description="SEO desc")
        md = p.get_seo_metadata()
        assert md.title == "SEO Title"
        assert md.meta_description == "SEO desc"

    def test_blank_column_falls_back_to_convention(self):
        p = Product(name="Plain Name")  # seo_title blank
        md = p.get_seo_metadata()
        assert md.title == "Plain Name"

    def test_robots_and_canonical_columns(self):
        p = Product(name="X", seo_robots="noindex", seo_canonical="/p/x/", seo_og_image="/og.jpg")
        md = p.get_seo_metadata()
        assert md.robots == "noindex"
        assert md.canonical_url == "/p/x/"
        assert md.og_image == "/og.jpg"


class TestMixinHasNoColumns:
    def test_seomodelmixin_adds_no_fields(self):
        # SeoModelMixin must not contribute DB columns.
        assert not any(f.name.startswith("seo_") for f in Page._meta.get_fields())
