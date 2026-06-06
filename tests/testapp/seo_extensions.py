"""Probe module: proves the ``seo_extensions`` autodiscovery convention runs.

Deliberately registers nothing global (just records that it was imported), so it
doesn't perturb other tests.
"""

DISCOVERED = {"count": 0}
DISCOVERED["count"] += 1
