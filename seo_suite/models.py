"""Core models.

The package keeps the SEO *metadata* layer model-free (the mixins are abstract),
but the database-backed **robots.txt** workflow lives here: one table where each
row is a retained version, with a single active version served per site. This is
deliberately standalone — it does not go through the SEO metadata resolver.
"""

from __future__ import annotations

from django.db import models, transaction
from django.utils import timezone

from .conf import get_settings


class RobotsTxt(models.Model):
    """A single version of ``robots.txt``.

    Each edit is a new row, so the full history is retained. Exactly one row per
    ``site_id`` is active (the served version). Switching is done via
    :meth:`activate`, and the single-active invariant is enforced at the database
    level by a unique constraint on ``active_marker`` (NULL for inactive rows,
    a per-scope value for the active one). This works on every Django-supported
    backend, because unique constraints allow multiple NULLs but only one of each
    non-NULL value.
    """

    version = models.PositiveIntegerField(
        default=1, editable=False, help_text="Per-site version number, assigned automatically."
    )
    content = models.TextField(blank=True, help_text="The robots.txt body.")
    is_active = models.BooleanField(default=False, db_index=True, help_text="The version currently served.")
    site_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Leave blank to apply to all sites.",
    )
    label = models.CharField(max_length=255, blank=True, help_text="Short name, e.g. 'Block /staging'.")
    note = models.TextField(blank=True, help_text="Why this change was made (shown in history).")
    created_by = models.CharField(max_length=150, blank=True, help_text="Username of who created this version.")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True, help_text="When this version was made live.")
    # Enforces "one active per site" at the DB level: NULL for inactive rows (many
    # allowed), a per-scope value for the single active row. Maintained by save().
    # null=True is required (not blank ""): the unique constraint must treat
    # inactive rows as DISTINCT, which only NULL gives — multiple "" would collide.
    active_marker = models.CharField(max_length=64, null=True, blank=True, editable=False)  # noqa: DJ001

    class Meta:
        app_label = "seo_suite"
        verbose_name = "robots.txt version"
        verbose_name_plural = "robots.txt versions"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["site_id", "is_active"])]
        constraints = [
            models.UniqueConstraint(
                fields=["active_marker"],
                name="seo_suite_robots_single_active_per_scope",
            )
        ]

    def __str__(self) -> str:
        scope = f"site {self.site_id}" if self.site_id is not None else "all sites"
        state = "active" if self.is_active else "inactive"
        return f"robots.txt v{self.version} ({scope}, {state})"

    def save(self, *args, **kwargs):
        if self._state.adding and not kwargs.pop("_keep_version", False):
            self.version = self._next_version(self.site_id)
        # Keep the uniqueness marker in lock-step with is_active/site_id. A second
        # active row for the same scope now raises IntegrityError instead of
        # silently creating a duplicate, even when activate() is bypassed.
        self.active_marker = self._active_marker_value()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "is_active" in update_fields and "active_marker" not in update_fields:
            kwargs["update_fields"] = list(update_fields) + ["active_marker"]
        super().save(*args, **kwargs)

    def _active_marker_value(self) -> str | None:
        if not self.is_active:
            return None
        return "global" if self.site_id is None else f"site:{self.site_id}"

    @classmethod
    def _next_version(cls, site_id) -> int:
        current = cls.objects.filter(site_id=site_id).aggregate(m=models.Max("version"))["m"]
        return (current or 0) + 1

    @transaction.atomic
    def activate(self, username: str = "") -> None:
        """Make this version the live one for its site; deactivate siblings."""
        # Deactivate the current active sibling first (clearing its marker) so the
        # unique constraint doesn't trip when this row becomes active.
        (
            type(self)
            .objects.filter(site_id=self.site_id, is_active=True)
            .exclude(pk=self.pk)
            .update(is_active=False, active_marker=None)
        )
        self.is_active = True
        self.activated_at = timezone.now()
        if username and not self.created_by:
            self.created_by = username
        self.save(update_fields=["is_active", "activated_at", "created_by", "active_marker"])
        invalidate_robots_cache(self.site_id)

    @classmethod
    def get_active(cls, site_id=None) -> RobotsTxt | None:
        """Active version for ``site_id``, falling back to the global one."""
        active = cls.objects.filter(is_active=True)
        row = active.filter(site_id=site_id).first()
        if row is None and site_id is not None:
            row = active.filter(site_id__isnull=True).first()
        return row

    def render(self, request=None) -> str:
        """The served body: content (or fallback) plus any ``Sitemap:`` lines."""
        settings = get_settings()
        body = self.content if self.content.strip() else settings["ROBOTS_TXT_FALLBACK"]
        lines = [body.rstrip("\n")]
        for url in settings["ROBOTS_SITEMAP_URLS"] or []:
            lines.append(f"Sitemap: {_absolute(url, request)}")
        return "\n".join(lines) + "\n"


def _absolute(url: str, request) -> str:
    if url.startswith(("http://", "https://")) or request is None:
        return url
    return request.build_absolute_uri(url)


def invalidate_robots_cache(site_id) -> None:
    """Drop the cached rendered robots.txt for a site (no-op if caching off)."""
    from .cache import invalidate_robots

    invalidate_robots(site_id)
