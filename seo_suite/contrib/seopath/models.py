"""Path-keyed SEO overrides — admin-editable metadata for arbitrary URLs.

No ContentType is involved: rows are keyed by URL path (+ optional site/language),
which naturally covers both model-backed pages and model-less views.
"""

from __future__ import annotations

from django.db import models

from ..base import AbstractSeoColumns


class AbstractSeoPath(AbstractSeoColumns):
    """Reusable base (fields + ``to_metadata``); extend it in your own app."""

    path = models.CharField(max_length=500, db_index=True, help_text="URL path, e.g. /about/")
    site_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Leave blank to apply to all sites.",
    )
    language = models.CharField(max_length=10, blank=True, help_text="Leave blank to apply to all languages.")

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.path


class SeoPath(AbstractSeoPath):
    class Meta:
        app_label = "seo_suite_seopath"
        verbose_name = "SEO path rule"
        verbose_name_plural = "SEO path rules"
        constraints = [
            models.UniqueConstraint(
                fields=["path", "site_id", "language"],
                name="seopath_unique_path_site_lang",
            )
        ]
        indexes = [models.Index(fields=["path", "site_id"])]
