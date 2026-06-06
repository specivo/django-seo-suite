from django.apps import AppConfig


class SeoObjectConfig(AppConfig):
    name = "seo_suite.contrib.seoobject"
    label = "seo_suite_seoobject"
    verbose_name = "SEO Suite — Object rules"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from seo_suite.providers.registry import provider_registry

        from .provider import ObjectProvider

        provider_registry.register(ObjectProvider(), name="seo_suite.contrib.seoobject.ObjectProvider")
