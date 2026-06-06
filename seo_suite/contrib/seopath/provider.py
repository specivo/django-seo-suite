"""PathProvider: resolve metadata from the SeoPath table by URL path."""

from __future__ import annotations

from django.db.models import Q

from ...providers import PRECEDENCE_PATH, Context, Provider
from .models import SeoPath


class PathProvider(Provider):
    priority = PRECEDENCE_PATH

    def provide(self, context: Context):
        path = context.path
        if not path:
            return None
        lang = context.language or ""
        qs = SeoPath.objects.filter(path=path)
        qs = qs.filter(Q(site_id=context.site_id) | Q(site_id__isnull=True))
        qs = qs.filter(Q(language=lang) | Q(language=""))
        candidates = list(qs)
        if not candidates:
            return None
        best = max(candidates, key=lambda row: self._specificity(row, context.site_id, lang))
        return best.to_metadata()

    @staticmethod
    def _specificity(row, site_id, lang) -> int:
        score = 0
        if row.site_id is not None and row.site_id == site_id:
            score += 2
        if row.language and row.language == lang:
            score += 1
        return score
