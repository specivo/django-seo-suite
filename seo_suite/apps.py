"""App config: wires extension autodiscovery and cache invalidation at startup."""

from __future__ import annotations

from django.apps import AppConfig


class SeoSuiteConfig(AppConfig):
    name = "seo_suite"
    label = "seo_suite"
    verbose_name = "SEO Suite"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Imported lazily so importing the package never requires Django setup.
        from .cache import connect_invalidation, connect_robots_invalidation
        from .extension import autodiscover_extensions

        connect_invalidation()
        connect_robots_invalidation()
        autodiscover_extensions()
