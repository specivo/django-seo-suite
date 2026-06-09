"""The free JSON-LD schema-profile library.

Profiles registered here are available to every project out of the box::

    class Article(SeoModelMixin, models.Model):
        SEO_SCHEMA_PROFILES = ["Article", "BreadcrumbList"]

Each profile builds a JSON-LD dict from conventional object attributes. An
object may also implement ``get_schema_data(key, context) -> dict`` to supply or
override fields for a given profile, and ``get_breadcrumbs()`` / ``get_faqs()``
for the list-shaped profiles.

Profiles intentionally do NOT call ``get_seo_metadata`` (that would recurse);
they read object fields directly.
"""

from __future__ import annotations

import datetime
from typing import Any

from .registry import SchemaProfile, schema_registry

SCHEMA_CONTEXT = "https://schema.org"


def _isoformat(value: Any) -> Any:
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def _read(obj: Any, *names: str) -> Any:
    """First non-empty attribute among ``names`` (calling 0-arg callables)."""
    from ..providers.model_mixin import _resolve_source

    if obj is None:
        return None
    for name in names:
        value = _resolve_source(obj, name)
        if value not in (None, ""):
            return value
    return None


def _schema_overrides(obj: Any, key: str, context) -> dict:
    hook = getattr(obj, "get_schema_data", None)
    if callable(hook):
        try:
            data = hook(key, context)
        except TypeError:
            data = hook(key)
        except Exception:  # noqa: BLE001
            return {}
        return data or {}
    return {}


def _schema_image(obj: Any, key: str, context) -> Any:
    """Optional ``get_schema_image`` hook value for ``key`` (else ``None``).

    Returned verbatim — a string URL, an ``ImageObject`` dict, or a list of
    either. The ``key`` argument lets a project switch images on per profile by
    returning a value only for the keys it wants. Heavy hooks (thumbnail
    backends, dimension probes) run at resolve time, so the value rides the
    object resolution cache when ``CACHE_TTL`` is enabled.
    """
    hook = getattr(obj, "get_schema_image", None)
    if not callable(hook):
        return None
    try:
        return hook(key, context)
    except TypeError:
        return hook(key)
    except Exception:  # noqa: BLE001 - a bad hook must not break the page
        return None


def _canonical(obj: Any, context) -> Any:
    url = _read(obj, "get_absolute_url")
    if not url:
        return None
    request = getattr(context, "request", None)
    if request is not None and url.startswith("/"):
        from ..canonical import make_canonicalizer

        return make_canonicalizer(context)(url)
    return url


class _BaseProfile(SchemaProfile):
    type_name: str = ""

    def base(self) -> dict:
        return {"@context": SCHEMA_CONTEXT, "@type": self.type_name}

    def build(self, obj, context) -> dict | None:
        data = self.base()
        self.populate(data, obj, context)
        image = _schema_image(obj, self.key, context)
        if image not in (None, "", []):
            data["image"] = image
        data.update(_schema_overrides(obj, self.key, context))
        return data if self._is_meaningful(data) else None

    def populate(self, data: dict, obj, context) -> None:  # pragma: no cover - overridden
        pass

    def _is_meaningful(self, data: dict) -> bool:
        # More than just @context/@type means we have something to emit.
        return len(data) > 2


class WebPageProfile(_BaseProfile):
    key = "WebPage"
    type_name = "WebPage"

    def populate(self, data, obj, context):
        name = _read(obj, "seo_title", "title", "name", "headline")
        if name:
            data["name"] = name
        desc = _read(obj, "meta_description", "description", "summary", "excerpt")
        if desc:
            data["description"] = desc
        url = _canonical(obj, context)
        if url:
            data["url"] = url

    def _is_meaningful(self, data):
        return True  # WebPage is always reasonable to emit


class WebSiteProfile(_BaseProfile):
    key = "WebSite"
    type_name = "WebSite"

    def populate(self, data, obj, context):
        from ..conf import get_settings

        og = get_settings()["DEFAULTS"].get("og", {}) or {}
        name = og.get("site_name") or _read(obj, "site_name")
        if name:
            data["name"] = name
        request = getattr(context, "request", None)
        if request is not None:
            data["url"] = request.build_absolute_uri("/")

    def _is_meaningful(self, data):
        return True


class OrganizationProfile(_BaseProfile):
    key = "Organization"
    type_name = "Organization"

    def populate(self, data, obj, context):
        from ..conf import get_settings

        og = get_settings()["DEFAULTS"].get("og", {}) or {}
        name = og.get("site_name") or _read(obj, "name")
        if name:
            data["name"] = name
        request = getattr(context, "request", None)
        if request is not None:
            data["url"] = request.build_absolute_uri("/")


class PersonProfile(_BaseProfile):
    key = "Person"
    type_name = "Person"

    def populate(self, data, obj, context):
        name = _read(obj, "full_name", "name", "get_full_name")
        if name:
            data["name"] = name
        url = _canonical(obj, context)
        if url:
            data["url"] = url


class BreadcrumbListProfile(_BaseProfile):
    key = "BreadcrumbList"
    type_name = "BreadcrumbList"

    def populate(self, data, obj, context):
        crumbs = _read(obj, "get_breadcrumbs", "breadcrumbs")
        if not crumbs:
            return
        items = []
        for position, crumb in enumerate(crumbs, start=1):
            name, url = self._crumb_parts(crumb)
            if not name:
                continue
            element = {"@type": "ListItem", "position": position, "name": name}
            if url:
                element["item"] = url
            items.append(element)
        if items:
            data["itemListElement"] = items

    @staticmethod
    def _crumb_parts(crumb):
        if isinstance(crumb, dict):
            return crumb.get("name"), crumb.get("url") or crumb.get("item")
        if isinstance(crumb, (list, tuple)) and len(crumb) >= 2:
            return crumb[0], crumb[1]
        return None, None

    def _is_meaningful(self, data):
        return "itemListElement" in data


class ArticleProfile(_BaseProfile):
    key = "Article"
    type_name = "Article"

    def populate(self, data, obj, context):
        headline = _read(obj, "headline", "title", "name")
        if headline:
            data["headline"] = headline
        desc = _read(obj, "meta_description", "description", "summary", "excerpt")
        if desc:
            data["description"] = desc
        image = _read(obj, "og_image", "image", "cover_image", "thumbnail")
        if image:
            data["image"] = image
        published = _read(obj, "date_published", "published_at", "published", "pub_date", "created")
        if published:
            data["datePublished"] = _isoformat(published)
        modified = _read(obj, "date_modified", "modified", "updated_at", "updated")
        if modified:
            data["dateModified"] = _isoformat(modified)
        author = _read(obj, "author_name", "author")
        if author:
            data["author"] = {"@type": "Person", "name": str(author)}
        url = _canonical(obj, context)
        if url:
            data["mainEntityOfPage"] = url


class FAQPageProfile(_BaseProfile):
    key = "FAQPage"
    type_name = "FAQPage"

    def populate(self, data, obj, context):
        faqs = _read(obj, "get_faqs", "faqs")
        if not faqs:
            return
        entities = []
        for faq in faqs:
            question, answer = self._faq_parts(faq)
            if not (question and answer):
                continue
            entities.append(
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {"@type": "Answer", "text": answer},
                }
            )
        if entities:
            data["mainEntity"] = entities

    @staticmethod
    def _faq_parts(faq):
        if isinstance(faq, dict):
            return faq.get("question") or faq.get("q"), faq.get("answer") or faq.get("a")
        if isinstance(faq, (list, tuple)) and len(faq) >= 2:
            return faq[0], faq[1]
        return None, None

    def _is_meaningful(self, data):
        return "mainEntity" in data


class ProductProfile(_BaseProfile):
    key = "Product"
    type_name = "Product"

    def populate(self, data, obj, context):
        name = _read(obj, "name", "title")
        if name:
            data["name"] = name
        desc = _read(obj, "meta_description", "description", "summary")
        if desc:
            data["description"] = desc
        image = _read(obj, "og_image", "image", "cover_image")
        if image:
            data["image"] = image
        sku = _read(obj, "sku")
        if sku:
            data["sku"] = sku
        brand = _read(obj, "brand")
        if brand:
            data["brand"] = {"@type": "Brand", "name": str(brand)}
        price = _read(obj, "price")
        if price is not None:
            offer = {"@type": "Offer", "price": str(price)}
            currency = _read(obj, "currency", "price_currency")
            if currency:
                offer["priceCurrency"] = currency
            availability = _read(obj, "availability")
            if availability:
                offer["availability"] = availability
            data["offers"] = offer


_FREE_PROFILES = [
    WebPageProfile(),
    WebSiteProfile(),
    OrganizationProfile(),
    PersonProfile(),
    BreadcrumbListProfile(),
    ArticleProfile(),
    FAQPageProfile(),
    ProductProfile(),
]

for _profile in _FREE_PROFILES:
    schema_registry.register(_profile)
