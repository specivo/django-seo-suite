from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path


def about(request):
    return HttpResponse("ok")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("seo_suite.urls")),  # serves /robots.txt
]

urlpatterns += i18n_patterns(
    path("about/", about, name="about"),
)
