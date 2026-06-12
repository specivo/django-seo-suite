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
        self._install_admin_grouping()

    @staticmethod
    def _install_admin_grouping() -> None:
        """Render the suite's apps as one 'SEO Suite' admin section (opt-out)."""
        from django.apps import apps as django_apps

        if not django_apps.is_installed("django.contrib.admin"):
            return
        from .conf import get_settings

        if not get_settings()["ADMIN_GROUP_APPS"]:
            return
        from django.contrib import admin

        from .admin_grouping import install_app_grouping

        install_app_grouping(admin.site)
