"""Fold the suite's admin apps into a single 'SEO Suite' index section.

Django groups the admin index by Django app, so the optional contrib apps
(``seopath`` / ``seoobject``) render as their own boxes, separate from core.
:func:`merge_seo_suite_apps` rewrites a ``get_app_list`` result so every
``seo_suite*`` app collapses into one ``SEO Suite`` group, and
:func:`install_app_grouping` wraps a site's ``get_app_list`` to apply it.

The default admin site is wrapped automatically at startup
(:meth:`seo_suite.apps.SeoSuiteConfig.ready`). Disable with
``SEO_SUITE["ADMIN_GROUP_APPS"] = False``; for a custom ``AdminSite`` call
``install_app_grouping(your_site)`` yourself.
"""

from __future__ import annotations

import functools

SECTION_NAME = "SEO Suite"
_PRIMARY_LABEL = "seo_suite"


def _is_family(app_label: str) -> bool:
    return app_label == _PRIMARY_LABEL or app_label.startswith(_PRIMARY_LABEL + "_")


def merge_seo_suite_apps(app_list: list[dict]) -> list[dict]:
    """Collapse every ``seo_suite*`` app dict into one ``SEO Suite`` group.

    Returns a new list (the input is left untouched). The merged group keeps the
    position of the first family app; its models are the union of the family's
    models, sorted by name. A list with one or zero family apps is returned
    unchanged.
    """
    family = {a["app_label"] for a in app_list if _is_family(a["app_label"])}
    if len(family) <= 1:
        return app_list

    template = next((a for a in app_list if a["app_label"] == _PRIMARY_LABEL), None)
    if template is None:
        template = next(a for a in app_list if a["app_label"] in family)

    models: list[dict] = []
    for app in app_list:
        if app["app_label"] in family:
            models.extend(app["models"])
    models.sort(key=lambda m: str(m.get("name", "")))

    merged = dict(template)
    merged["name"] = SECTION_NAME
    merged["models"] = models

    result: list[dict] = []
    inserted = False
    for app in app_list:
        if app["app_label"] in family:
            if not inserted:
                result.append(merged)
                inserted = True
            continue
        result.append(app)
    return result


def install_app_grouping(site) -> None:
    """Wrap ``site.get_app_list`` so the suite renders as one section. Idempotent."""
    if getattr(site, "_seo_suite_app_grouping", False):
        return
    original = site.get_app_list

    @functools.wraps(original)
    def get_app_list(request, app_label=None):
        # On a contrib app's own index page, still show the merged section by
        # computing from the full (unfiltered) list rather than the lone app.
        if app_label is not None and _is_family(app_label):
            merged = merge_seo_suite_apps(original(request))
            return [a for a in merged if a["app_label"] == _PRIMARY_LABEL]
        return merge_seo_suite_apps(original(request, app_label))

    site.get_app_list = get_app_list
    site._seo_suite_app_grouping = True
