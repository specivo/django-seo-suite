"""Convenience re-exports for the public mixin API.

Import these from your own ``models.py`` / ``views.py``::

    from seo_suite.mixins import SeoModelMixin, SeoViewMixin
"""

from .providers.model_mixin import (
    SeoColumnsMixin,
    SeoModelFieldsMixin,
    SeoModelMixin,
)
from .providers.view_mixin import SeoListViewMixin, SeoViewMixin

__all__ = [
    "SeoModelMixin",
    "SeoModelFieldsMixin",
    "SeoColumnsMixin",
    "SeoViewMixin",
    "SeoListViewMixin",
]
