"""Sites-framework optionality.

``django.contrib.sites`` is never a hard dependency. ``get_current_site_id``
resolves the active site at runtime through a documented fallback chain so the
same code path serves single-site and multi-site deployments.
"""

from __future__ import annotations

from django.apps import apps as django_apps

from .conf import get_settings


def get_current_site_id(request=None) -> int | None:
    """Resolve the current site id, or ``None`` (single-site / all-sites).

    Order:
      1. ``SEO_SUITE['SITE_ID_RESOLVER']`` callable, if set.
      2. ``django.contrib.sites`` current site, if the app is installed.
      3. ``settings.SITE_ID``, if defined.
      4. ``None``.
    """
    settings = get_settings()
    resolver = settings["SITE_ID_RESOLVER"]
    if resolver is not None:
        return resolver(request)

    if django_apps.is_installed("django.contrib.sites"):
        try:
            from django.contrib.sites.shortcuts import get_current_site

            return get_current_site(request).id
        except Exception:  # noqa: BLE001 - misconfigured SITE_ID etc.
            pass

    from django.conf import settings as django_settings

    return getattr(django_settings, "SITE_ID", None)
