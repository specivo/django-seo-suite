"""Public signals — extension points for reacting to / mutating resolution.

* ``seo_metadata_resolved`` — sent after the resolver finalizes metadata, before
  render. Receivers MAY mutate the (mutable) ``metadata`` in place; this is the
  one signal where mutation is explicitly supported.
* ``seo_cache_invalidate`` — request to drop a cached resolution by ``identity``.
* ``seo_head_rendering`` — sent by ``{% seo_head %}``; receivers may return extra
  head fragments (collected by the tag).

Signal kwargs are part of the public contract. New kwargs may be added over time;
receivers must accept ``**kwargs``.
"""

from django.dispatch import Signal

# providing_args (informational): sender, metadata (FinalizedSeoMetadata), context
seo_metadata_resolved = Signal()

# providing_args: sender, identity (str)
seo_cache_invalidate = Signal()

# providing_args: sender, context, metadata
seo_head_rendering = Signal()
