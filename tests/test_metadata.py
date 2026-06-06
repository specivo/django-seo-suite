"""Merge & finalize semantics — the three-state (UNSET / None / "") core."""

from seo_suite.metadata import UNSET, FinalizedSeoMetadata, HreflangAlt, SeoMetadata


class TestUnsetSentinel:
    def test_unset_is_falsy_and_singleton(self):
        assert not UNSET
        assert UNSET is UNSET
        from seo_suite.metadata import _Unset

        assert _Unset() is UNSET

    def test_repr(self):
        assert repr(UNSET) == "UNSET"


class TestPartial:
    def test_partial_sets_only_named_fields(self):
        md = SeoMetadata.partial(title="Hello")
        assert md.title == "Hello"
        assert md.meta_description is UNSET

    def test_partial_rejects_unknown_field(self):
        import pytest

        with pytest.raises(TypeError):
            SeoMetadata.partial(not_a_field="x")


class TestScalarMerge:
    def test_higher_overrides_lower(self):
        lo = SeoMetadata.partial(title="Low", robots="index,follow")
        hi = SeoMetadata.partial(title="High")
        merged = SeoMetadata.merge(lo, hi)
        assert merged.title == "High"
        assert merged.robots == "index,follow"  # untouched -> lower survives

    def test_unset_higher_keeps_lower(self):
        lo = SeoMetadata.partial(title="Low")
        hi = SeoMetadata.partial(meta_description="desc")
        merged = SeoMetadata.merge(lo, hi)
        assert merged.title == "Low"
        assert merged.meta_description == "desc"

    def test_explicit_none_overrides_lower(self):
        lo = SeoMetadata.partial(meta_description="from-object")
        hi = SeoMetadata.partial(meta_description=None)  # explicit "render nothing"
        merged = SeoMetadata.merge(lo, hi)
        assert merged.meta_description is None

    def test_explicit_empty_string_overrides_lower(self):
        lo = SeoMetadata.partial(robots="index,follow")
        hi = SeoMetadata.partial(robots="")
        merged = SeoMetadata.merge(lo, hi)
        assert merged.robots == ""


class TestDictMerge:
    def test_og_deep_merge_keeps_sibling_keys(self):
        lo = SeoMetadata.partial(og={"title": "T", "type": "article"})
        hi = SeoMetadata.partial(og={"image": "/a.jpg"})
        merged = SeoMetadata.merge(lo, hi)
        assert merged.og == {"title": "T", "type": "article", "image": "/a.jpg"}

    def test_og_higher_key_overrides(self):
        lo = SeoMetadata.partial(og={"title": "Low"})
        hi = SeoMetadata.partial(og={"title": "High"})
        assert SeoMetadata.merge(lo, hi).og == {"title": "High"}

    def test_og_unset_value_inside_dict_is_skipped(self):
        lo = SeoMetadata.partial(og={"title": "Low"})
        hi = SeoMetadata.partial(og={"title": UNSET, "image": "/x.jpg"})
        assert SeoMetadata.merge(lo, hi).og == {"title": "Low", "image": "/x.jpg"}


class TestListMerge:
    def test_hreflang_replaced_wholesale(self):
        lo = SeoMetadata.partial(hreflang=[HreflangAlt("en", "/en")])
        hi = SeoMetadata.partial(hreflang=[HreflangAlt("ru", "/ru")])
        assert SeoMetadata.merge(lo, hi).hreflang == [HreflangAlt("ru", "/ru")]

    def test_jsonld_accumulates(self):
        lo = SeoMetadata.partial(jsonld=[{"@type": "WebPage"}])
        hi = SeoMetadata.partial(jsonld=[{"@type": "BreadcrumbList"}])
        merged = SeoMetadata.merge(lo, hi)
        assert merged.jsonld == [{"@type": "WebPage"}, {"@type": "BreadcrumbList"}]

    def test_extra_head_accumulates(self):
        lo = SeoMetadata.partial(extra_head=["<meta a>"])
        hi = SeoMetadata.partial(extra_head=["<meta b>"])
        assert SeoMetadata.merge(lo, hi).extra_head == ["<meta a>", "<meta b>"]


class TestMergeAll:
    def test_fold_low_to_high(self):
        layers = [
            SeoMetadata.partial(title="default", robots="index,follow"),
            SeoMetadata.partial(title="object"),
            SeoMetadata.partial(title="view"),
        ]
        merged = SeoMetadata.merge_all(layers)
        assert merged.title == "view"
        assert merged.robots == "index,follow"

    def test_ignores_none_layers(self):
        merged = SeoMetadata.merge_all([None, SeoMetadata.partial(title="x"), None])
        assert merged.title == "x"


class TestFinalize:
    def test_unset_scalars_become_none(self):
        f = SeoMetadata().finalize()
        assert isinstance(f, FinalizedSeoMetadata)
        assert f.title is None
        assert f.meta_description is None
        assert f.hreflang == []
        assert f.jsonld == []

    def test_og_image_folds_into_og_and_twitter(self):
        f = SeoMetadata.partial(og_image="/cover.jpg").finalize()
        assert f.og["image"] == "/cover.jpg"
        assert f.twitter["image"] == "/cover.jpg"

    def test_twitter_card_defaults_to_large_image_when_image_present(self):
        f = SeoMetadata.partial(og_image="/cover.jpg").finalize()
        assert f.twitter["card"] == "summary_large_image"

    def test_twitter_card_defaults_to_summary_without_image(self):
        f = SeoMetadata.partial(title="x").finalize()
        assert f.twitter["card"] == "summary"

    def test_explicit_og_image_not_overwritten(self):
        f = SeoMetadata.partial(og_image="/a.jpg", og={"image": "/explicit.jpg"}).finalize()
        assert f.og["image"] == "/explicit.jpg"

    def test_canonicalizer_applied(self):
        f = SeoMetadata.partial(canonical_url="/page/").finalize(
            canonicalizer=lambda u: "https://example.com" + u
        )
        assert f.canonical_url == "https://example.com/page/"

    def test_full_title_combines_suffix(self):
        f = SeoMetadata.partial(title="Home", title_suffix=" | Acme").finalize()
        assert f.full_title == "Home | Acme"

    def test_full_title_empty_when_no_title(self):
        f = SeoMetadata.partial(title_suffix=" | Acme").finalize()
        assert f.full_title == ""
