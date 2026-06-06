from django.contrib import admin

from .models import SeoObject


@admin.register(SeoObject)
class SeoObjectAdmin(admin.ModelAdmin):
    list_display = ("content_type", "object_id", "site_id", "language", "title", "robots")
    list_filter = ("content_type", "site_id", "language")
    search_fields = ("title", "description", "object_id")
    raw_id_fields = ("content_type",)
