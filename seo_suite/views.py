"""Views shipped by the core app (currently just robots.txt)."""

from __future__ import annotations

from django.http import HttpResponse
from django.views import View

from .cache import get_robots, set_robots
from .conf import get_settings
from .models import RobotsTxt
from .sites import get_current_site_id


class RobotsTxtView(View):
    """Serve the active ``robots.txt`` for the current site as ``text/plain``."""

    def get(self, request, *args, **kwargs):
        site_id = get_current_site_id(request)

        body = get_robots(site_id)
        if body is None:
            active = RobotsTxt.get_active(site_id)
            if active is not None:
                body = active.render(request)
            else:
                fallback = get_settings()["ROBOTS_TXT_FALLBACK"].rstrip("\n") + "\n"
                body = fallback
            set_robots(site_id, body)

        return HttpResponse(body, content_type="text/plain")
