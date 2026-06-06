"""Canonical-URL absolutization, honoring the CANONICAL_DOMAIN / HTTPS settings.

``make_canonicalizer(context)`` returns a callable that turns a path (or already
absolute URL) into the canonical absolute URL for the current request/site.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from .conf import get_settings


def _is_absolute(url: str) -> bool:
    return bool(urlsplit(url).scheme)


def make_canonicalizer(context):
    settings = get_settings()
    domain = settings["CANONICAL_DOMAIN"]
    force_https = settings["FORCE_HTTPS_CANONICAL"]
    request = getattr(context, "request", None)

    def canonicalize(url: str) -> str:
        if not url:
            return url
        if _is_absolute(url):
            if force_https:
                parts = urlsplit(url)
                if parts.scheme == "http":
                    return urlunsplit(("https", *parts[1:]))
            return url

        host = domain or (request.get_host() if request is not None else None)
        if not host:
            # Nothing to build an absolute URL from; return the path unchanged.
            return url
        if force_https:
            scheme = "https"
        elif request is not None:
            scheme = "https" if request.is_secure() else "http"
        else:
            scheme = "https"
        path = url if url.startswith("/") else "/" + url
        return f"{scheme}://{host}{path}"

    return canonicalize
