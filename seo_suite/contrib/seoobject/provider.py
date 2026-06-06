"""ObjectProvider: generic-relation SEO for allowlisted (third-party) models."""

from __future__ import annotations

from django.db.models import Q

from ...conf import get_settings
from ...providers import PRECEDENCE_OBJECT, Context, Provider


class ObjectProvider(Provider):
    priority = PRECEDENCE_OBJECT

    def provide(self, context: Context):
        obj = context.object
        if obj is None:
            return None
        meta = getattr(obj, "_meta", None)
        pk = getattr(obj, "pk", None)
        if meta is None or pk is None:
            return None

        label = f"{meta.app_label}.{meta.model_name}"
        if not self._is_allowlisted(label):
            return None  # no ContentType query for non-allowlisted models

        from django.contrib.contenttypes.models import ContentType

        from .models import SeoObject

        ct = ContentType.objects.get_for_model(obj)
        lang = context.language or ""
        qs = SeoObject.objects.filter(content_type=ct, object_id=pk)
        qs = qs.filter(Q(site_id=context.site_id) | Q(site_id__isnull=True))
        qs = qs.filter(Q(language=lang) | Q(language=""))
        candidates = list(qs)
        if not candidates:
            return None
        best = max(candidates, key=lambda row: self._specificity(row, context.site_id, lang))
        return best.to_metadata()

    @staticmethod
    def _is_allowlisted(label: str) -> bool:
        allow = get_settings()["OBJECT_MODELS"] or []
        return label in {item.lower() for item in allow}

    @staticmethod
    def _specificity(row, site_id, lang) -> int:
        score = 0
        if row.site_id is not None and row.site_id == site_id:
            score += 2
        if row.language and row.language == lang:
            score += 1
        return score
