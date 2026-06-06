"""get_current_site_id fallback chain (Sites framework optional).

The default test settings install NO sites framework and set no SITE_ID, so the
single-site branch is exercised here. The sites-installed branch is covered by
the CI matrix (SEO_SUITE_TEST_SITES=1).
"""

import pytest
from django.apps import apps
from django.test import override_settings

from seo_suite.sites import get_current_site_id

SITES_INSTALLED = apps.is_installed("django.contrib.sites")


class TestSiteIdResolution:
    @pytest.mark.skipif(SITES_INSTALLED, reason="sites framework installed")
    def test_none_when_no_sites_and_no_site_id(self):
        assert get_current_site_id(None) is None

    @pytest.mark.skipif(not SITES_INSTALLED, reason="sites framework not installed")
    @pytest.mark.django_db
    def test_uses_current_site_when_installed(self):
        # settings_test sets SITE_ID=1 when sites is enabled.
        assert get_current_site_id(None) == 1

    @pytest.mark.skipif(SITES_INSTALLED, reason="sites would query for the Site row")
    @override_settings(SITE_ID=7)
    def test_uses_settings_site_id(self):
        assert get_current_site_id(None) == 7

    def test_custom_resolver_setting(self):
        with override_settings(SEO_SUITE={"SITE_ID_RESOLVER": "tests.test_sites_optional.fixed_site"}):
            assert get_current_site_id(None) == 42

    def test_resolver_receives_request(self):
        sentinel = object()
        captured = {}

        def _capture(request):
            captured["request"] = request
            return 1

        # exercise the resolver path with a callable injected via settings dict
        with override_settings(SEO_SUITE={"SITE_ID_RESOLVER": "tests.test_sites_optional.capturing_site"}):
            _CAPTURE_TARGET["fn"] = _capture
            assert get_current_site_id(sentinel) == 1
        assert captured["request"] is sentinel


def fixed_site(request):
    return 42


_CAPTURE_TARGET = {}


def capturing_site(request):
    return _CAPTURE_TARGET["fn"](request)
