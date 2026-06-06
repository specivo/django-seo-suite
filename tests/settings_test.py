"""Test settings for django-seo-suite.

The installed-apps set is configurable through environment variables so the CI
matrix can exercise the package with the Sites framework on/off and with the
optional contrib apps on/off:

    SEO_SUITE_TEST_SITES=1      -> add django.contrib.sites (+ SITE_ID)
    SEO_SUITE_TEST_SEOPATH=1    -> add seo_suite.contrib.seopath
    SEO_SUITE_TEST_SEOOBJECT=1  -> add seo_suite.contrib.seoobject
    SEO_SUITE_TEST_PRO=1        -> add tests.fakepro (extension-point probe app)
"""

import os


def _flag(name: str) -> bool:
    return os.environ.get(name, "") not in ("", "0", "false", "False")


SECRET_KEY = "seo-suite-test-secret-key"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "seo_suite",
    "tests.testapp",
]

if _flag("SEO_SUITE_TEST_SITES"):
    INSTALLED_APPS.insert(0, "django.contrib.sites")
    SITE_ID = 1

# Optional contrib apps are installed by default for the full local test run;
# the CI matrix sets SEO_SUITE_TEST_NO_CONTRIB=1 to prove the package works
# without them (see also tests/settings_minimal.py).
if not _flag("SEO_SUITE_TEST_NO_CONTRIB"):
    INSTALLED_APPS.append("seo_suite.contrib.seopath")
    INSTALLED_APPS.append("seo_suite.contrib.seoobject")

if _flag("SEO_SUITE_TEST_PRO"):
    INSTALLED_APPS.append("tests.fakepro")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "seo_suite.context.seo",
            ],
        },
    }
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

USE_TZ = True
USE_I18N = True
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("ru", "Russian"),
    ("th", "Thai"),
]

ROOT_URLCONF = "tests.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SEO_SUITE = {
    "DEFAULTS": {
        "title_suffix": " | Example",
        "robots": "index,follow",
    },
}
