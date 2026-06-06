"""Generic-relation SEO overrides — for third-party models you can't edit.

This is the ONLY place ContentTypes are used in the package. It is opt-in (the
app must be installed) and gated further by the ``SEO_SUITE['OBJECT_MODELS']``
allowlist, so no ContentType query happens for ordinary objects.
"""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from ..base import AbstractSeoColumns


class AbstractSeoObject(AbstractSeoColumns):
    """Reusable base; extend it in your own app to add columns/behavior."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")

    site_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    language = models.CharField(max_length=10, blank=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"SEO for {self.content_type}#{self.object_id}"


class SeoObject(AbstractSeoObject):
    class Meta:
        app_label = "seo_suite_seoobject"
        verbose_name = "SEO object rule"
        verbose_name_plural = "SEO object rules"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "site_id", "language"],
                name="seoobject_unique_object_site_lang",
            )
        ]
        indexes = [models.Index(fields=["content_type", "object_id"])]
