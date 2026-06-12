"""Merging the suite's admin apps into one 'SEO Suite' index section."""

import pytest

from seo_suite.admin_grouping import install_app_grouping, merge_seo_suite_apps


def _app(label, name, *model_names):
    return {
        "app_label": label,
        "name": name,
        "app_url": f"/admin/{label}/",
        "has_module_perms": True,
        "models": [
            {"name": m, "object_name": m, "admin_url": f"/admin/{label}/{m.lower()}/"} for m in model_names
        ],
    }


class TestMergeSeoSuiteApps:
    def test_family_apps_merged_into_one_section(self):
        app_list = [
            _app("auth", "Authentication and Authorization", "User", "Group"),
            _app("seo_suite", "SEO Suite", "RobotsTxt"),
            _app("seo_suite_seopath", "SEO Suite — Path rules", "SeoPath"),
            _app("seo_suite_seoobject", "SEO Suite — Object rules", "SeoObject"),
        ]

        merged = merge_seo_suite_apps(app_list)

        seo = [a for a in merged if a["app_label"] == "seo_suite"]
        assert len(seo) == 1
        assert seo[0]["name"] == "SEO Suite"
        assert {m["object_name"] for m in seo[0]["models"]} == {"RobotsTxt", "SeoPath", "SeoObject"}
        # no leftover contrib boxes
        assert not any(a["app_label"].startswith("seo_suite_") for a in merged)
        # unrelated apps untouched
        assert any(a["app_label"] == "auth" for a in merged)

    def test_merged_section_keeps_position_of_first_family_app(self):
        app_list = [
            _app("auth", "Authentication", "User"),
            _app("seo_suite", "SEO Suite", "RobotsTxt"),
            _app("seo_suite_seopath", "SEO Suite — Path rules", "SeoPath"),
            _app("blog", "Blog", "Post"),
        ]

        labels = [a["app_label"] for a in merge_seo_suite_apps(app_list)]

        assert labels == ["auth", "seo_suite", "blog"]

    def test_noop_when_only_one_family_app(self):
        app_list = [
            _app("auth", "Authentication", "User"),
            _app("seo_suite", "SEO Suite", "RobotsTxt"),
        ]

        assert merge_seo_suite_apps(app_list) == app_list

    def test_noop_without_family_apps(self):
        app_list = [_app("auth", "Authentication", "User"), _app("blog", "Blog", "Post")]

        assert merge_seo_suite_apps(app_list) == app_list


class _FakeSite:
    def __init__(self, app_list):
        self._app_list = app_list

    def get_app_list(self, request, app_label=None):
        return [dict(a, models=list(a["models"])) for a in self._app_list]


class TestInstallAppGrouping:
    def _app_list(self):
        return [
            _app("seo_suite", "SEO Suite", "RobotsTxt"),
            _app("seo_suite_seopath", "SEO Suite — Path rules", "SeoPath"),
        ]

    def test_wraps_get_app_list_to_merge(self):
        site = _FakeSite(self._app_list())

        install_app_grouping(site)
        result = site.get_app_list(request=None)

        seo = [a for a in result if a["app_label"] == "seo_suite"]
        assert len(seo) == 1
        assert {m["object_name"] for m in seo[0]["models"]} == {"RobotsTxt", "SeoPath"}

    def test_is_idempotent(self):
        site = _FakeSite(self._app_list())

        install_app_grouping(site)
        wrapped_once = site.get_app_list
        install_app_grouping(site)

        assert site.get_app_list is wrapped_once  # not double-wrapped

    def test_app_index_for_family_label_returns_merged_section(self):
        site = _FakeSite(self._app_list())
        install_app_grouping(site)

        # Navigating to /admin/seo_suite_seopath/ should still show the merged group.
        result = site.get_app_list(None, "seo_suite_seopath")

        assert len(result) == 1
        assert {m["object_name"] for m in result[0]["models"]} == {"RobotsTxt", "SeoPath"}


@pytest.mark.django_db
def test_default_admin_site_groups_the_suite():
    from django.apps import apps

    if not apps.is_installed("seo_suite.contrib.seopath"):
        pytest.skip("contrib apps not installed in this configuration")

    from django.contrib import admin
    from django.contrib.auth import get_user_model
    from django.test import RequestFactory

    user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
    request = RequestFactory().get("/admin/")
    request.user = user

    app_list = admin.site.get_app_list(request)

    seo_sections = [a for a in app_list if a["name"] == "SEO Suite"]
    assert len(seo_sections) == 1
    object_names = {m["object_name"] for m in seo_sections[0]["models"]}
    assert {"RobotsTxt", "SeoPath"} <= object_names
    # The standalone contrib boxes are gone.
    assert not any(a["app_label"].startswith("seo_suite_") for a in app_list)
