# django-seo-suite

[![PyPI](https://img.shields.io/pypi/v/django-seo-suite)](https://pypi.org/project/django-seo-suite/)
[![Python](https://img.shields.io/pypi/pyversions/django-seo-suite)](https://pypi.org/project/django-seo-suite/)
[![Django](https://img.shields.io/pypi/frameworkversions/django/django-seo-suite)](https://pypi.org/project/django-seo-suite/)
[![License](https://img.shields.io/pypi/l/django-seo-suite)](https://github.com/specivo/django-seo-suite/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-specivo.io-c49a3c)](https://specivo.io/docs/django-seo-suite/)

A lightweight, extensible **SEO metadata layer for Django**. It gives any project
one consistent way to attach and render the full set of SEO attributes —
`<title>`, `<h1>`, meta description/keywords/robots, canonical URL, hreflang
alternates, JSON-LD schema and Open Graph / Twitter cards — across models,
class-based views (including listing and model-less views), and even third-party
models you can't edit.

- **No required apps.** The core ships a **single migration** (the versioned
  `robots.txt` table) and works without `django.contrib.sites` (detected at runtime).
- **One dependency:** Django (4.2+). Python 3.10+.
- **Multi-provider resolver.** Metadata is merged from several sources by a clear
  precedence, then rendered by template tags.
- **Built for extension.** A separate package can add capability through stable,
  documented hooks — no forking, no monkeypatching.

## Install

```bash
pip install django-seo-suite
```

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "seo_suite",
    # optional, admin-editable overrides:
    "seo_suite.contrib.seopath",     # SEO keyed by URL path
    "seo_suite.contrib.seoobject",   # SEO for third-party models (uses ContentTypes)
]

TEMPLATES = [{
    # ...
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "seo_suite.context.seo",     # enables {% seo_head %} everywhere
    ]},
}]
```

Then run migrations (the core app ships one migration for the `robots.txt` table):

```bash
python manage.py migrate
```

## Quickstart

**On a model you own:**

```python
from django.db import models
from seo_suite.mixins import SeoModelMixin

class Article(SeoModelMixin, models.Model):
    title = models.CharField(max_length=200)
    summary = models.TextField()
    cover = models.ImageField(upload_to="covers/")
    slug = models.SlugField()

    SEO_FIELD_MAP = {"meta_description": "summary", "og_image": "cover"}
    SEO_SCHEMA_PROFILES = ["Article", "BreadcrumbList"]

    def get_absolute_url(self):
        return f"/articles/{self.slug}/"
```

`title`/`description`/`image` fall back to conventional field names automatically;
`SEO_FIELD_MAP` overrides them; `get_absolute_url` becomes the canonical URL.

**On a view:**

```python
from django.views.generic import DetailView, ListView
from seo_suite.mixins import SeoViewMixin, SeoListViewMixin

class ArticleDetail(SeoViewMixin, DetailView):
    model = Article
    # the object's metadata is used automatically; view attrs override it

class ArticleList(SeoListViewMixin, ListView):     # model-less views work too
    model = Article
    seo_title = "All Articles"                     # becomes "All Articles – Page 2" when paginated
```

**In your base template:**

```django
{% load seo_suite %}
<head>
  {% seo_head %}            {# title, meta, canonical, hreflang, OG, Twitter, JSON-LD #}
</head>
```

Need finer control? Use the granular tags: `{% seo_title %}`, `{% seo_meta %}`,
`{% seo_canonical %}`, `{% seo_hreflang %}`, `{% seo_opengraph %}`,
`{% seo_twitter %}`, `{% seo_jsonld %}`, `{% seo_extra_head %}`. Every partial in
`templates/seo_suite/` is overridable by shipping your own.

## How resolution works

Metadata is merged from lowest to highest precedence (higher wins per field;
JSON-LD and extra-head fragments accumulate):

| Precedence | Source |
|-----------:|--------|
| 10 | `SEO_SUITE["DEFAULTS"]` (global) |
| 20 | `SEO_SUITE["SITE_DEFAULTS"][site_id]` |
| 30 | `seopath.SeoPath` row matching the URL path *(optional app)* |
| 40 | the object's `get_seo_metadata()` (model mixin) or `seoobject` row |
| 50 | the view's `get_seo_metadata()` / `seo_*` attributes |

A field left "unset" defers to lower precedence; an explicit `None`/`""` wins and
renders nothing.

## JSON-LD schema library

Enable ready-made schema.org profiles declaratively — no template editing:

```python
class FaqPage(SeoModelMixin, models.Model):
    SEO_SCHEMA_PROFILES = ["WebPage", "FAQPage"]
    def get_faqs(self):
        return [{"question": "…", "answer": "…"}]
```

Free profiles: `WebPage`, `WebSite`, `Organization`, `Person`, `BreadcrumbList`,
`Article`, `FAQPage`, `Product`. An object can supply or override fields via
`get_schema_data(key, context)`.

## Sitemaps & hreflang

```python
from seo_suite.sitemaps import SeoSitemap

class ArticleSitemap(SeoSitemap):
    i18n = True
    alternates = True
    x_default = True
    def items(self):
        return Article.objects.all()
```

`SeoSitemap` sets each `<loc>` to the page's resolved canonical, so the sitemap
URL always matches `rel="canonical"`. For on-page alternates,
`seo_suite.hreflang.build_hreflang_alternates(path, request)` produces the same
`LANGUAGES`-driven set the sitemap uses.

## Versioned robots.txt

Serve `robots.txt` from the database with a full version history, so a traffic
regression can be traced to a specific change. Add the route to your root urlconf:

```python
# urls.py
urlpatterns = [
    # ...
    path("", include("seo_suite.urls")),   # serves /robots.txt
]
```

Then manage versions in the Django admin. Adding a version (the form is pre-filled
with the current live content) **publishes it on save**; the version it replaces is
kept as a read-only history row. To roll back, run the **"Roll back"** action on an
earlier version. Exactly one version is live per site, enforced at the database
level. Every version records `created_at`, `activated_at`, and the author, so the
admin changelist is a timeline you can line up against your analytics. When no
version is active, the view serves `SEO_SUITE["ROBOTS_TXT_FALLBACK"]`;
`SEO_SUITE["ROBOTS_SITEMAP_URLS"]` are appended as `Sitemap:` lines.

## Settings (`SEO_SUITE`)

| Key | Default | Purpose |
|-----|---------|---------|
| `RESOLVER_CLASS` | `seo_suite.resolver.Resolver` | swap the resolver |
| `SITE_ID_RESOLVER` | `None` | custom current-site callable |
| `DEFAULTS` | `{robots, og.type, ...}` | global metadata seed |
| `SITE_DEFAULTS` | `{}` | per-site metadata seed |
| `CANONICAL_DOMAIN` / `FORCE_HTTPS_CANONICAL` | `None` / `True` | canonical absolutization |
| `LIST_CANONICAL_INCLUDES_PAGE` | `True` | paginated-list canonical policy |
| `HREFLANG_X_DEFAULT` | `True` | emit `x-default` |
| `CACHE_TTL` | `0` | cache resolved payload (0 = off) |
| `OBJECT_MODELS` | `[]` | allowlist `"app.model"` for `seoobject` |
| `DEFAULT_SCHEMA_PROFILES` | `[]` | profiles applied site-wide |
| `ROBOTS_TXT_FALLBACK` | `"User-agent: *\nAllow: /"` | served when no robots.txt version is active |
| `ROBOTS_SITEMAP_URLS` | `[]` | URLs appended to robots.txt as `Sitemap:` lines |
| `ROBOTS_CACHE_TTL` | `0` | cache served robots.txt (0 = off) |

## Extending the suite (public contract)

These are versioned, stable APIs an extension package may rely on:

- **Registries** — `provider_registry.register(provider, priority=…)`,
  `renderer_registry.register(name, callable)`.
- **Swappable classes** — `SEO_SUITE["RESOLVER_CLASS"]`, `["JSONLD_SERIALIZER"]`.
- **Signals** — `seo_metadata_resolved` (mutation allowed), `seo_cache_invalidate`,
  `seo_head_rendering`.
- **Schema profiles** — `schema_registry.register(profile)` with namespaced keys.
- **Abstract models** — `AbstractSeoPath`, `AbstractSeoObject`, `SeoColumnsMixin`.
- **Autodiscovery** — ship a top-level `seo_extensions.py` (imported at startup)
  or publish an entry point in the `seo_suite.extensions` group.
- **Templates** — override any `templates/seo_suite/*` partial.

Everything imports from one surface:

```python
# my_extension/seo_extensions.py
from seo_suite.extension import PRECEDENCE_PATH, Provider, SeoMetadata, provider_registry

class MyProvider(Provider):
    priority = 35
    def provide(self, context):
        return SeoMetadata.partial(meta_description="…")

provider_registry.register(MyProvider())
```

## Development

```bash
pip install -e ".[dev]"
pytest                                   # contrib apps on, sites off
SEO_SUITE_TEST_SITES=1 pytest            # sites framework on
SEO_SUITE_TEST_NO_CONTRIB=1 pytest       # core only
SEO_SUITE_TEST_PRO=1 pytest              # with a fake extension package
ruff check seo_suite tests
tox                                      # full Python × Django matrix
```

## License

MIT.
