"""Stand-in for what a paid extension package ships.

Exercises every public extension point through the single ``seo_suite.extension``
import surface, proving an extension can hook in via the ``seo_extensions.py``
autodiscovery convention with no changes to the base package.
"""

from seo_suite.extension import (
    PRECEDENCE_OBJECT,
    PRECEDENCE_PATH,
    Provider,
    SeoMetadata,
    provider_registry,
    renderer_registry,
    seo_metadata_resolved,
)
from seo_suite.schema.registry import SchemaProfile, schema_registry

# Record side effects so tests can assert the hooks ran.
EVENTS = {"resolved": 0}


# (a) provider registered at an intermediate priority (between PATH and OBJECT)
class ProKeywordsProvider(Provider):
    priority = (PRECEDENCE_PATH + PRECEDENCE_OBJECT) // 2  # 35

    def provide(self, context):
        return SeoMetadata.partial(meta_keywords="pro-keywords")


# (d) namespaced schema profile (a "schema pack")
class ProDemoProfile(SchemaProfile):
    key = "pro:Demo"

    def build(self, obj, context):
        return {"@context": "https://schema.org", "@type": "Thing", "name": "pro-demo"}


# (g) head renderer injecting an extra fragment
def _verification_tag(request, seo):
    return '<meta name="pro-verify" content="token">'


# (c) signal receiver
def _on_resolved(sender, metadata, context, **kwargs):
    EVENTS["resolved"] += 1


def register():
    provider_registry.register(ProKeywordsProvider(), name="tests.fakepro.ProKeywordsProvider")
    schema_registry.register(ProDemoProfile())
    renderer_registry.register("pro_verify", _verification_tag)
    seo_metadata_resolved.connect(_on_resolved, dispatch_uid="fakepro_on_resolved")


# Autodiscovery imports this module and we register immediately.
register()
