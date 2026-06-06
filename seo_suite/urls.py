"""URLs for the core app. Include in your root urlconf to serve robots.txt::

    from django.urls import include, path

    urlpatterns = [
        # ...
        path("", include("seo_suite.urls")),
    ]
"""

from django.urls import path

from .views import RobotsTxtView

app_name = "seo_suite"

urlpatterns = [
    path("robots.txt", RobotsTxtView.as_view(), name="robots_txt"),
]
