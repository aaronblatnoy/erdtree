"""finetune/scenarios.py — thin re-export shim for the scenarios package.

Allows callers to write::

    from finetune.scenarios import ALL_SCENARIOS, Scenario, by_tool, ...

instead of::

    from finetune.scenarios import ALL_SCENARIOS, Scenario, by_tool, ...

Both forms resolve to the same objects; this shim exists so that code which
treats ``finetune.scenarios`` as a flat module (rather than a package) also
works, and so that the public surface is spelled out in one visible place.

This file is intentionally minimal — it contains NO logic.  All definitions
live in ``finetune/scenarios/__init__.py``.
"""

from finetune.scenarios import (  # noqa: F401 — re-exports
    ALL_SCENARIOS,
    Scenario,
    by_complexity,
    by_permission,
    by_tool,
)

# Re-export OpClass so callers can do:
#   from finetune.scenarios import OpClass
# without reaching into coreimports themselves.
from finetune.coreimports import OpClass  # noqa: F401

__all__ = [
    "Scenario",
    "ALL_SCENARIOS",
    "by_tool",
    "by_permission",
    "by_complexity",
    "OpClass",
]
