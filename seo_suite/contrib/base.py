"""Shared abstract columns for the DB-backed providers (seopath, seoobject)."""

from __future__ import annotations

from django.db import models

from ..metadata import SeoMetadata


class AbstractSeoColumns(models.Model):
    """The editable metadata columns + ``to_metadata`` conversion."""

    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    keywords = models.CharField(max_length=255, blank=True)
    robots = models.CharField(max_length=100, blank=True)
    canonical = models.CharField(max_length=500, blank=True)
    og_image = models.CharField(max_length=500, blank=True)
    extra_jsonld = models.JSONField(default=list, blank=True, help_text="List of JSON-LD objects.")

    class Meta:
        abstract = True

    def to_metadata(self) -> SeoMetadata:
        kwargs = {}
        if self.title:
            kwargs["title"] = self.title
        if self.description:
            kwargs["meta_description"] = self.description
        if self.keywords:
            kwargs["meta_keywords"] = self.keywords
        if self.robots:
            kwargs["robots"] = self.robots
        if self.canonical:
            kwargs["canonical_url"] = self.canonical
        if self.og_image:
            kwargs["og_image"] = self.og_image
        if self.extra_jsonld:
            kwargs["jsonld"] = list(self.extra_jsonld)
        return SeoMetadata.partial(**kwargs)
