"""Versioned robots.txt: model, activation, serving, caching, admin."""

import pytest
from django.test import Client, override_settings

from seo_suite.models import RobotsTxt

pytestmark = pytest.mark.django_db


class TestVersioning:
    def test_version_auto_increments_per_site(self):
        a = RobotsTxt.objects.create(content="a")
        b = RobotsTxt.objects.create(content="b")
        assert (a.version, b.version) == (1, 2)

    def test_versions_independent_across_sites(self):
        g1 = RobotsTxt.objects.create(content="g1")  # site None
        s1 = RobotsTxt.objects.create(content="s1", site_id=5)
        g2 = RobotsTxt.objects.create(content="g2")
        s2 = RobotsTxt.objects.create(content="s2", site_id=5)
        assert (g1.version, g2.version) == (1, 2)
        assert (s1.version, s2.version) == (1, 2)


class TestActivation:
    def test_activate_sets_active_and_timestamp(self):
        r = RobotsTxt.objects.create(content="x")
        assert not r.is_active and r.activated_at is None
        r.activate("alice")
        r.refresh_from_db()
        assert r.is_active
        assert r.activated_at is not None

    def test_activate_deactivates_siblings_same_site(self):
        v1 = RobotsTxt.objects.create(content="1", site_id=1)
        v2 = RobotsTxt.objects.create(content="2", site_id=1)
        v1.activate()
        v2.activate()
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert not v1.is_active and v2.is_active
        # exactly one active for the site
        assert RobotsTxt.objects.filter(site_id=1, is_active=True).count() == 1

    def test_activation_isolated_between_sites(self):
        g = RobotsTxt.objects.create(content="g")
        s = RobotsTxt.objects.create(content="s", site_id=2)
        g.activate()
        s.activate()
        g.refresh_from_db()
        assert g.is_active and s.is_active  # different sites, both stay active


class TestSingleActiveConstraint:
    """The DB guarantees one active version per scope, even bypassing activate()."""

    def test_db_rejects_two_active_for_same_site(self):
        from django.db import IntegrityError, transaction

        RobotsTxt.objects.create(content="a", site_id=1, is_active=True)
        with pytest.raises(IntegrityError), transaction.atomic():
            RobotsTxt.objects.create(content="b", site_id=1, is_active=True)

    def test_db_rejects_two_active_global(self):
        from django.db import IntegrityError, transaction

        RobotsTxt.objects.create(content="a", is_active=True)  # site_id=None
        with pytest.raises(IntegrityError), transaction.atomic():
            RobotsTxt.objects.create(content="b", is_active=True)

    def test_many_inactive_rows_allowed(self):
        for i in range(5):
            RobotsTxt.objects.create(content=str(i), site_id=1)  # is_active=False
        assert RobotsTxt.objects.filter(site_id=1, is_active=False).count() == 5

    def test_active_global_and_active_site_coexist(self):
        RobotsTxt.objects.create(content="g", is_active=True)
        RobotsTxt.objects.create(content="s", site_id=1, is_active=True)
        assert RobotsTxt.objects.filter(is_active=True).count() == 2

    def test_marker_cleared_when_deactivated(self):
        v1 = RobotsTxt.objects.create(content="1", site_id=1)
        v2 = RobotsTxt.objects.create(content="2", site_id=1)
        v1.activate()
        v2.activate()  # must not trip the constraint while swapping
        v1.refresh_from_db()
        assert v1.active_marker is None and v2.active_marker == "site:1"


class TestGetActive:
    def test_site_specific_preferred(self):
        glob = RobotsTxt.objects.create(content="global")
        glob.activate()
        site = RobotsTxt.objects.create(content="site3", site_id=3)
        site.activate()
        assert RobotsTxt.get_active(3).content == "site3"

    def test_falls_back_to_global(self):
        glob = RobotsTxt.objects.create(content="global")
        glob.activate()
        assert RobotsTxt.get_active(99).content == "global"

    def test_none_when_nothing_active(self):
        RobotsTxt.objects.create(content="inactive")
        assert RobotsTxt.get_active(None) is None


class TestRender:
    def test_render_uses_content(self):
        r = RobotsTxt.objects.create(content="User-agent: *\nDisallow: /private")
        assert "Disallow: /private" in r.render()

    def test_render_falls_back_to_setting_when_blank(self):
        r = RobotsTxt.objects.create(content="   ")
        with override_settings(SEO_SUITE={"ROBOTS_TXT_FALLBACK": "User-agent: *\nDisallow:"}):
            assert "Disallow:" in r.render()

    def test_sitemap_urls_appended(self):
        r = RobotsTxt.objects.create(content="User-agent: *\nAllow: /")
        with override_settings(SEO_SUITE={"ROBOTS_SITEMAP_URLS": ["https://ex.test/sitemap.xml"]}):
            out = r.render()
        assert "Sitemap: https://ex.test/sitemap.xml" in out


class TestView:
    def test_serves_active_content_as_plain_text(self):
        r = RobotsTxt.objects.create(content="User-agent: *\nDisallow: /secret")
        r.activate()
        resp = Client().get("/robots.txt")
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/plain")
        assert b"Disallow: /secret" in resp.content

    def test_fallback_when_no_active_version(self):
        with override_settings(SEO_SUITE={"ROBOTS_TXT_FALLBACK": "User-agent: *\nDisallow: /nope"}):
            resp = Client().get("/robots.txt")
        assert resp.status_code == 200
        assert b"Disallow: /nope" in resp.content


class TestCaching:
    CACHE = {"ROBOTS_CACHE_TTL": 300}

    def test_activation_busts_cache(self):
        v1 = RobotsTxt.objects.create(content="User-agent: *\nDisallow: /v1")
        v1.activate()
        with override_settings(SEO_SUITE=self.CACHE):
            client = Client()
            assert b"/v1" in client.get("/robots.txt").content  # warms cache
            v2 = RobotsTxt.objects.create(content="User-agent: *\nDisallow: /v2")
            v2.activate()  # post_save + activate bust the per-site key
            assert b"/v2" in client.get("/robots.txt").content

    def test_no_cache_reflects_db_each_request(self):
        v1 = RobotsTxt.objects.create(content="User-agent: *\nDisallow: /a")
        v1.activate()
        client = Client()  # default ROBOTS_CACHE_TTL=0
        assert b"/a" in client.get("/robots.txt").content
        v2 = RobotsTxt.objects.create(content="User-agent: *\nDisallow: /b")
        v2.activate()
        assert b"/b" in client.get("/robots.txt").content


class TestAdmin:
    def _admin(self):
        from django.contrib.admin.sites import AdminSite

        from seo_suite.admin import RobotsTxtAdmin

        return RobotsTxtAdmin(RobotsTxt, AdminSite())

    def _request(self, method="post"):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        request = getattr(RequestFactory(), method)("/")
        request.user = type("U", (), {"get_username": lambda self: "bob"})()
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_save_publishes_immediately(self):
        admin = self._admin()
        obj = RobotsTxt(content="User-agent: *\nDisallow: /new")
        admin.save_model(self._request(), obj, form=None, change=False)
        obj.refresh_from_db()
        assert obj.created_by == "bob"
        assert obj.is_active  # save = publish

    def test_save_snapshots_previous_active(self):
        admin = self._admin()
        first = RobotsTxt(content="v1")
        admin.save_model(self._request(), first, form=None, change=False)
        second = RobotsTxt(content="v2")
        admin.save_model(self._request(), second, form=None, change=False)
        first.refresh_from_db()
        second.refresh_from_db()
        assert not first.is_active and second.is_active  # previous kept as history
        assert RobotsTxt.objects.count() == 2  # nothing overwritten
        assert RobotsTxt.get_active(None).content == "v2"

    def test_existing_version_content_is_readonly(self):
        admin = self._admin()
        existing = RobotsTxt.objects.create(content="locked")
        ro = admin.get_readonly_fields(self._request("get"), obj=existing)
        assert "content" in ro and "site_id" in ro
        # but not when adding
        ro_add = admin.get_readonly_fields(self._request("get"), obj=None)
        assert "content" not in ro_add

    def test_add_form_prefills_current_content(self):
        admin = self._admin()
        live = RobotsTxt.objects.create(content="current body")
        live.activate()
        initial = admin.get_changeform_initial_data(self._request("get"))
        assert initial.get("content") == "current body"

    def test_activate_action_rolls_back(self):
        admin = self._admin()
        v1 = RobotsTxt.objects.create(content="old")
        v1.activate()
        v2 = RobotsTxt.objects.create(content="new")
        v2.activate()
        admin.activate_selected(self._request(), RobotsTxt.objects.filter(pk=v1.pk))
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.is_active and not v2.is_active  # rolled back to v1
