from django.contrib import admin

from .models import SeoPath


@admin.register(SeoPath)
class SeoPathAdmin(admin.ModelAdmin):
    list_display = ("path", "site_id", "language", "title", "robots")
    list_filter = ("site_id", "language", "robots")
    search_fields = ("path", "title", "description")
    fieldsets = (
        (None, {"fields": ("path", "site_id", "language")}),
        ("Metadata", {"fields": ("title", "description", "keywords", "robots", "canonical", "og_image")}),
        ("Structured data", {"fields": ("extra_jsonld",), "classes": ("collapse",)}),
    )
