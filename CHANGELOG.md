# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-06-12

### Added
- The admin index now renders core and the optional contrib apps (`seopath` /
  `seoobject`) as a single **SEO Suite** section instead of separate boxes. Wraps
  the default admin site's `get_app_list` at startup, independent of the admin's
  URL path. Disable with `SEO_SUITE["ADMIN_GROUP_APPS"] = False`; for a custom
  `AdminSite`, call `seo_suite.admin_grouping.install_app_grouping(site)`.

## [0.2.0] - 2026-06-09

### Added
- Optional `get_schema_image(key, context)` hook on objects. When present, its
  return value is used verbatim as a schema-profile's `image` field — a string,
  a schema.org `ImageObject` dict (e.g. `contentUrl` + `thumbnailUrl` + `width`/
  `height`), or a list of either. The `key` argument acts as a per-profile
  switch (return `None` to fall back to the convention bare-string or skip).
  Runs at resolve time, so the output rides the object resolution cache when
  `CACHE_TTL` is enabled. Fully backward compatible: with no hook, output is
  unchanged.

## [0.1.1] - 2026-06-06

### Added
- Official support for **Django 6.0**. The test suite passes unchanged on 6.0; CI now
  runs against the latest release of each supported Django line (4.2, 5.2, 6.0) rather
  than every 5.x minor.

### Changed
- Trove classifiers now advertise Django 4.2, 5.2, and 6.0 (the latest of each major
  series). The supported range is unchanged: Django 4.2+.

## [0.1.0] - 2026-06-06

Initial release.

### Added

- Core SEO metadata layer: a `SeoMetadata` value object resolved by a multi-provider
  `Resolver` (global → site → path → object → view precedence) and rendered into the
  document head by template tags. Sites-framework-optional and database-agnostic.
- Model and view mixins: `SeoModelMixin`, `SeoModelFieldsMixin`, `SeoViewMixin`,
  `SeoListViewMixin` (the core app ships no models of its own except robots.txt below).
- Template tags: `{% seo_head %}` plus the granular `{% seo_title %}`, `{% seo_meta %}`,
  `{% seo_canonical %}`, `{% seo_hreflang %}`, `{% seo_opengraph %}`, `{% seo_twitter %}`,
  `{% seo_jsonld %}`, `{% seo_extra_head %}`. All partials are overridable.
- JSON-LD schema profile library (`WebPage`, `WebSite`, `Organization`, `Person`,
  `BreadcrumbList`, `Article`, `FAQPage`, `Product`), enabled declaratively via
  `SEO_SCHEMA_PROFILES`.
- Open Graph and Twitter card output, auto-populated from page metadata and overridable.
- Sitemap integration (`SeoSitemap`, keeping `<loc>` equal to the canonical) and an
  hreflang helper (`build_hreflang_alternates`).
- Optional caching of resolved metadata with generation-counter invalidation.
- Extension points (semver-governed): provider/renderer/schema registries, swappable
  classes via import-string settings, signals, abstract base models, and
  `seo_extensions.py` autodiscovery plus the `seo_suite.extensions` entry-point group.
- Optional contrib apps: `seo_suite.contrib.seopath` (admin-editable SEO keyed by URL)
  and `seo_suite.contrib.seoobject` (SEO for third-party models via a generic relation,
  gated by an allowlist; the only place ContentTypes are used).
- Versioned `robots.txt`: database-backed history with exactly one active version per
  site (enforced by a unique constraint), a save-to-publish admin workflow with
  rollback, and an optional `Sitemap:` directive list. Served at `/robots.txt`.

### Requirements

- Django 4.2+ and Python 3.10+. The only hard dependency is Django.

[Unreleased]: https://github.com/specivo/django-seo-suite/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/specivo/django-seo-suite/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/specivo/django-seo-suite/releases/tag/v0.1.0
