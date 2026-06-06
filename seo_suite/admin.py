"""Admin for the versioned robots.txt workflow.

Save-to-publish: adding a version publishes it immediately and snapshots the
previously-active version as history. Existing versions are immutable (their
served content can't be edited in place), so the live robots.txt only ever
changes by adding a new version. Use the "Activate" action to roll back to an
older version.
"""

from __future__ import annotations

from django.contrib import admin, messages

from .models import RobotsTxt


@admin.register(RobotsTxt)
class RobotsTxtAdmin(admin.ModelAdmin):
    list_display = ("version", "label", "site_id", "is_active", "created_at", "activated_at", "created_by")
    list_filter = ("is_active", "site_id")
    search_fields = ("label", "note", "content")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    actions = ["activate_selected"]

    _status_fields = ("is_active", "version", "created_at", "activated_at", "created_by")

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            description = (
                "Saving publishes this immediately as the live robots.txt; "
                "the current version is kept as history."
            )
        else:
            description = (
                "Past versions are read-only. To change robots.txt, add a new "
                "version. Use the Activate action to roll back."
            )
        return (
            (None, {"fields": ("label", "site_id", "content", "note"), "description": description}),
            ("Status", {"fields": self._status_fields}),
        )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self._status_fields)
        if obj is not None:
            # Existing versions are immutable snapshots: lock the served body and scope.
            readonly += ["content", "site_id"]
        return readonly

    def get_changeform_initial_data(self, request):
        # Start a new version from the current live (global) content, so editing
        # and saving feels like "edit the current robots.txt".
        active = RobotsTxt.get_active(None)
        return {"content": active.content} if active else {}

    def save_model(self, request, obj, form, change):
        username = request.user.get_username()
        if not change:
            obj.created_by = username
            super().save_model(request, obj, form, change)
            obj.activate(username)  # publish now + snapshot the previous active version
            self.message_user(
                request,
                f"Published robots.txt v{obj.version} for {self._scope(obj)}.",
                level=messages.SUCCESS,
            )
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="Roll back to the selected version (re-publish it)")
    def activate_selected(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one version to activate.", level=messages.ERROR)
            return
        obj = queryset.first()
        obj.activate(request.user.get_username())
        self.message_user(
            request,
            f"Rolled back: robots.txt v{obj.version} is now live for {self._scope(obj)}.",
            level=messages.SUCCESS,
        )

    @staticmethod
    def _scope(obj) -> str:
        return f"site {obj.site_id}" if obj.site_id is not None else "all sites"
