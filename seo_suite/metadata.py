"""The ``SeoMetadata`` value object and its merge/finalize semantics.

A single immutable-ish dataclass carries every renderable SEO attribute. Several
*providers* each produce a partial ``SeoMetadata`` and the resolver merges them
in precedence order (low -> high).

Three-state fields are the crux of the design. Every field defaults to the
``UNSET`` sentinel:

* ``UNSET``  -> "this provider has no opinion": the lower-precedence value
  survives the merge.
* ``None`` / ``""`` -> "explicit empty": wins over lower precedence and renders
  nothing (e.g. a page that deliberately emits no meta description).

This distinction is why fields cannot simply default to ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any, NamedTuple


class _Unset:
    """Sentinel meaning 'no opinion expressed'. Falsy, singleton-ish."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "UNSET"

    def __reduce__(self):
        return (_Unset, ())


UNSET = _Unset()


class HreflangAlt(NamedTuple):
    """One ``<link rel="alternate" hreflang>`` entry. ``lang`` may be 'x-default'."""

    lang: str
    href: str


# Fields whose value is a dict and should be deep-merged key-by-key.
_DICT_FIELDS = ("og", "twitter")
# Fields whose value is a list and should be accumulated (appended) on merge.
_ACCUMULATE_FIELDS = ("jsonld", "extra_head")
# Fields whose value is a list and should be replaced wholesale (higher wins).
_REPLACE_LIST_FIELDS = ("hreflang",)


@dataclass(frozen=True)
class SeoMetadata:
    """Partial or complete SEO metadata for a page."""

    title: Any = UNSET
    title_suffix: Any = UNSET
    h1: Any = UNSET
    meta_description: Any = UNSET
    meta_keywords: Any = UNSET
    robots: Any = UNSET
    canonical_url: Any = UNSET
    hreflang: Any = UNSET          # list[HreflangAlt]
    og: Any = UNSET                # dict[str, str]
    twitter: Any = UNSET           # dict[str, str]
    og_image: Any = UNSET          # str (url); folded into og/twitter on finalize
    jsonld: Any = UNSET            # list[dict]
    extra_head: Any = UNSET        # list[str | SafeString]

    # ------------------------------------------------------------------ build
    @classmethod
    def partial(cls, **kwargs: Any) -> SeoMetadata:
        """Construct metadata setting only the named fields (rest stay UNSET)."""
        unknown = set(kwargs) - {f.name for f in fields(cls)}
        if unknown:
            raise TypeError(f"Unknown SeoMetadata field(s): {', '.join(sorted(unknown))}")
        return cls(**kwargs)

    # ------------------------------------------------------------------ merge
    @classmethod
    def merge(cls, lower: SeoMetadata, higher: SeoMetadata) -> SeoMetadata:
        """Merge two layers; ``higher`` wins per-field where it has an opinion.

        Scalars: higher wins unless UNSET (so explicit None/"" overrides).
        og/twitter: deep-merged key by key (UNSET values skipped).
        hreflang: replaced wholesale when higher provides a list.
        jsonld/extra_head: accumulated (lower then higher).
        """
        merged: dict[str, Any] = {}
        for f in fields(cls):
            name = f.name
            lo = getattr(lower, name)
            hi = getattr(higher, name)
            if name in _DICT_FIELDS:
                merged[name] = _merge_dict(lo, hi)
            elif name in _ACCUMULATE_FIELDS:
                merged[name] = _merge_accumulate(lo, hi)
            elif name in _REPLACE_LIST_FIELDS:
                merged[name] = hi if hi is not UNSET else lo
            else:
                merged[name] = hi if hi is not UNSET else lo
        return cls(**merged)

    @classmethod
    def merge_all(cls, layers: list[SeoMetadata]) -> SeoMetadata:
        """Fold a low->high ordered list of layers into one."""
        result = cls()
        for layer in layers:
            if layer is None:
                continue
            result = cls.merge(result, layer)
        return result

    # --------------------------------------------------------------- finalize
    def finalize(self, *, canonicalizer=None) -> FinalizedSeoMetadata:
        """Resolve derived values and turn UNSET into render-ready blanks.

        * folds ``og_image`` into ``og['image']`` / ``twitter['image']``,
        * defaults ``twitter['card']`` based on image presence,
        * absolutizes ``canonical_url`` via the optional ``canonicalizer``,
        * converts remaining UNSET scalars to ``None`` and lists/dicts to empty.
        """
        title = _clean(self.title)
        description = _clean(self.meta_description)

        canonical = _clean(self.canonical_url)
        if canonical and canonicalizer is not None:
            canonical = canonicalizer(canonical)

        og = dict(self.og) if isinstance(self.og, dict) else {}
        twitter = dict(self.twitter) if isinstance(self.twitter, dict) else {}
        image = self.og_image if self.og_image not in (UNSET, None, "") else og.get("image")

        if image and not og.get("image"):
            og["image"] = image
        # Auto-populate the obvious social fields from page-level metadata so a
        # minimal page still produces decent OG/Twitter output. Explicit og/twitter
        # values always win (we only fill blanks).
        if title and not og.get("title"):
            og["title"] = title
        if description and not og.get("description"):
            og["description"] = description
        if canonical and not og.get("url"):
            og["url"] = canonical

        if image and not twitter.get("image"):
            twitter["image"] = image
        if not twitter.get("title") and og.get("title"):
            twitter["title"] = og["title"]
        if not twitter.get("description") and og.get("description"):
            twitter["description"] = og["description"]
        if "card" not in twitter or twitter.get("card") in (None, ""):
            twitter["card"] = "summary_large_image" if (twitter.get("image") or og.get("image")) else "summary"

        return FinalizedSeoMetadata(
            title=title,
            title_suffix=_clean(self.title_suffix) or "",
            h1=_clean(self.h1),
            meta_description=_clean(self.meta_description),
            meta_keywords=_clean(self.meta_keywords),
            robots=_clean(self.robots),
            canonical_url=canonical,
            hreflang=list(self.hreflang) if isinstance(self.hreflang, list) else [],
            og=og,
            twitter=twitter,
            jsonld=list(self.jsonld) if isinstance(self.jsonld, list) else [],
            extra_head=list(self.extra_head) if isinstance(self.extra_head, list) else [],
        )

    def with_values(self, **kwargs: Any) -> SeoMetadata:
        """Return a copy with the given fields replaced."""
        return replace(self, **kwargs)


def _clean(value: Any) -> Any:
    """UNSET -> None; otherwise pass through (None/"" preserved as explicit empty)."""
    return None if value is UNSET else value


def _merge_dict(lo: Any, hi: Any) -> Any:
    if hi is UNSET:
        return lo
    base = dict(lo) if isinstance(lo, dict) else {}
    if isinstance(hi, dict):
        for key, value in hi.items():
            if value is UNSET:
                continue
            base[key] = value
    return base


def _merge_accumulate(lo: Any, hi: Any) -> Any:
    if lo is UNSET and hi is UNSET:
        return UNSET
    combined: list[Any] = []
    if isinstance(lo, list):
        combined.extend(lo)
    if isinstance(hi, list):
        combined.extend(hi)
    return combined


@dataclass(frozen=True)
class FinalizedSeoMetadata:
    """Render-ready metadata: no UNSET, derived fields filled. What templates see."""

    title: Any
    title_suffix: str
    h1: Any
    meta_description: Any
    meta_keywords: Any
    robots: Any
    canonical_url: Any
    hreflang: list
    og: dict
    twitter: dict
    jsonld: list
    extra_head: list

    @property
    def full_title(self) -> str:
        """``title`` with the suffix appended (empty string when no title)."""
        if not self.title:
            return ""
        return f"{self.title}{self.title_suffix or ''}"

    def as_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)
