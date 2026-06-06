"""JSON-LD serialization + the schema-profile registry.

The free profile *library* lives in :mod:`seo_suite.schema.profiles` and is
registered on import. Extension packages register additional (namespaced)
profiles, e.g. ``pro:Product``.
"""

from __future__ import annotations

import json

from django.utils.safestring import SafeString, mark_safe

from .registry import SchemaProfile, build_profiles, schema_registry

__all__ = [
    "SchemaProfile",
    "schema_registry",
    "build_profiles",
    "default_serializer",
    "render_jsonld_blocks",
]


def default_serializer(data) -> SafeString:
    """Serialize one JSON-LD dict to a string safe to embed in <script>.

    Escapes ``<``, ``>`` and ``&`` to their unicode forms so a ``</script>`` in
    user data cannot break out of the script element.
    """
    raw = json.dumps(data, ensure_ascii=False, sort_keys=False, default=str)
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return mark_safe(raw)  # noqa: S308 - escaped above


def render_jsonld_blocks(jsonld_list) -> list[SafeString]:
    """Serialize each JSON-LD dict using the configured serializer."""
    from ..conf import get_settings

    serializer = get_settings()["JSONLD_SERIALIZER"]
    blocks = []
    for item in jsonld_list or []:
        if item:
            blocks.append(serializer(item))
    return blocks


# Register the free profile library.
from . import profiles as _profiles  # noqa: E402,F401
