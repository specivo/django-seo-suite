from django.apps import AppConfig


class SeoPathConfig(AppConfig):
    name = "seo_suite.contrib.seopath"
    label = "seo_suite_seopath"
    verbose_name = "SEO Suite — Path rules"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from seo_suite.providers.registry import provider_registry

        from .provider import PathProvider

        provider_registry.register(PathProvider(), name="seo_suite.contrib.seopath.PathProvider")
