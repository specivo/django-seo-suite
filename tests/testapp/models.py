from django.db import models

from seo_suite.providers.model_mixin import SeoModelFieldsMixin, SeoModelMixin


class Page(SeoModelMixin, models.Model):
    """Conventional fields: title/description + canonical via get_absolute_url."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    slug = models.SlugField(default="page")

    class Meta:
        app_label = "testapp"

    def get_absolute_url(self):
        return f"/pages/{self.slug}/"


class Category(SeoModelMixin, models.Model):
    """No ``title`` field — title resolves from the ``name`` convention."""

    name = models.CharField(max_length=200)

    class Meta:
        app_label = "testapp"


class MappedArticle(SeoModelMixin, models.Model):
    """Explicit SEO_FIELD_MAP overrides the conventions."""

    headline = models.CharField(max_length=200)
    blurb = models.TextField(blank=True)
    image_url = models.CharField(max_length=300, blank=True)

    SEO_FIELD_MAP = {
        "title": "headline",
        "meta_description": "blurb",
        "og_image": "image_url",
    }

    class Meta:
        app_label = "testapp"


class Product(SeoModelFieldsMixin, models.Model):
    """Editable seo_* columns win; fall back to ``name`` convention."""

    name = models.CharField(max_length=200)

    class Meta:
        app_label = "testapp"
