"""Provider contract and the resolution ``Context``.

A *provider* turns a resolution context into a partial :class:`SeoMetadata`.
Providers are merged by the resolver in ascending ``priority`` order, so a
higher priority overrides a lower one per field.

The precedence ladder is public, semver-governed API. Extension packages may
register providers at intermediate priorities (e.g. 35, between PATH and
OBJECT) without the base package having to renumber.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..metadata import SeoMetadata

# Precedence constants (lower merges first, higher overrides).
PRECEDENCE_GLOBAL = 10
PRECEDENCE_SITE = 20
PRECEDENCE_PATH = 30
PRECEDENCE_OBJECT = 40
PRECEDENCE_VIEW = 50


@dataclass
class Context:
    """Everything a provider may need to resolve metadata for one request."""

    request: Any = None
    view: Any = None
    object: Any = None
    path: str | None = None
    site_id: int | None = None
    language: str | None = None
    extra: dict | None = None

    def __post_init__(self):
        if self.path is None and self.request is not None:
            self.path = getattr(self.request, "path", None)


@dataclass
class ProviderResult:
    """A provider's output: the metadata plus resolution hints."""

    metadata: SeoMetadata | None
    cacheable: bool = True


class Provider(ABC):
    """Base class for registry-registered providers.

    Context-derived providers (the view and model mixins) are not registered
    here; the resolver discovers them from the :class:`Context` directly.
    """

    priority: int = PRECEDENCE_GLOBAL
    cacheable: bool = True

    @abstractmethod
    def provide(self, context: Context) -> SeoMetadata | None:
        """Return partial metadata, or ``None`` to abstain."""
        raise NotImplementedError
