"""finetune/scenarios/__init__.py — canonical Scenario type + aggregated corpus.

This is the P1 JOIN: normalise every per-tool SCENARIOS list onto the single
canonical Scenario dataclass defined here, aggregate into ALL_SCENARIOS, and
expose filter helpers.

Load-bearing invariants enforced here
--------------------------------------
INV-schema-sync   permission_class is derived LIVE via the per-tool _pc()
                  helper in each sub-module; never hardcoded here.

INV-read-only-core  Only imports from finetune.coreimports and the sibling
                    per-tool modules; never directly from core/.

INV-offline         Imports cleanly with no network, no Ollama, no API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, TOOL_NAMES, registry

# ---------------------------------------------------------------------------
# Canonical Scenario dataclass.
#
# Every per-tool module (disk.py, docs.py, …) defines a structurally
# identical LOCAL Scenario so they can sanity-check themselves at import time.
# This is the ONE authoritative definition that the rest of the finetune/
# codebase should reference.  Per-tool instances are normalised onto this
# class by _normalise() during aggregation below.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """A single training scenario: one user request that the system should
    handle with a specific tool, operation, permission gate, and complexity.

    Fields
    ------
    id              Globally unique slug, e.g. ``services-status-0001``.
    tool            Registered tool name, e.g. ``"services"``.
    operation       Operation enum value, e.g. ``"status"``.
    permission_class  Live OpClass (READ / WRITE / DESTRUCTIVE).
    complexity      ``"single"`` (one tool call), ``"multi"`` (chained
                    calls), or ``"diagnostic"`` (triage/investigation flow).
    user_input      The natural-language user utterance that triggers the
                    scenario.  Operator/user text — NOT asserted I2-clean.
    notes           Free-text annotation for trace generation context.
                    Must not appear verbatim in assistant output.
    """

    id: str
    tool: str
    operation: str
    permission_class: OpClass
    complexity: Literal["single", "multi", "diagnostic"]
    user_input: str
    notes: str


# ---------------------------------------------------------------------------
# Import all per-tool scenario sub-modules (relative imports).
# Each module defines its own local Scenario dataclass (structurally
# identical to this one) and a SCENARIOS list that is sanity-checked at its
# own import time.  We re-normalise below to produce canonical instances.
# No circular dependency: sub-modules import from finetune.coreimports only.
# ---------------------------------------------------------------------------

from . import disk        # noqa: E402
from . import docs        # noqa: E402
from . import files       # noqa: E402
from . import firewall    # noqa: E402
from . import hardware    # noqa: E402
from . import logs        # noqa: E402
from . import network     # noqa: E402
from . import packages    # noqa: E402
from . import processes   # noqa: E402
from . import services    # noqa: E402
from . import users       # noqa: E402


# ---------------------------------------------------------------------------
# Normalise per-tool SCENARIOS onto the canonical Scenario class.
#
# All per-tool Scenario dataclasses are structurally identical, so we can
# unpack by field name.  Using explicit kwargs (not dataclasses.asdict)
# avoids any serialisation of OpClass enum values.
# ---------------------------------------------------------------------------


def _normalise(raw_list: list) -> list[Scenario]:
    """Convert a per-tool SCENARIOS list into canonical Scenario instances."""
    return [
        Scenario(
            id=s.id,
            tool=s.tool,
            operation=s.operation,
            permission_class=s.permission_class,
            complexity=s.complexity,
            user_input=s.user_input,
            notes=s.notes,
        )
        for s in raw_list
    ]


# ---------------------------------------------------------------------------
# Aggregation — ALL_SCENARIOS
#
# Order: alphabetical by tool name so the list is deterministic regardless
# of future sub-module additions.
# ---------------------------------------------------------------------------

ALL_SCENARIOS: list[Scenario] = (
    _normalise(disk.SCENARIOS)
    + _normalise(docs.SCENARIOS)
    + _normalise(files.SCENARIOS)
    + _normalise(firewall.SCENARIOS)
    + _normalise(hardware.SCENARIOS)
    + _normalise(logs.SCENARIOS)
    + _normalise(network.SCENARIOS)
    + _normalise(packages.SCENARIOS)
    + _normalise(processes.SCENARIOS)
    + _normalise(services.SCENARIOS)
    + _normalise(users.SCENARIOS)
)


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------


def by_tool(name: str) -> list[Scenario]:
    """Return all scenarios whose ``tool`` matches *name*.

    Example::

        read_scenarios = by_tool("services")
    """
    return [s for s in ALL_SCENARIOS if s.tool == name]


def by_permission(opclass: OpClass) -> list[Scenario]:
    """Return all scenarios whose ``permission_class`` matches *opclass*.

    Example::

        write_scenarios = by_permission(OpClass.WRITE)
    """
    return [s for s in ALL_SCENARIOS if s.permission_class == opclass]


def by_complexity(kind: str) -> list[Scenario]:
    """Return all scenarios whose ``complexity`` matches *kind*.

    *kind* must be one of ``"single"``, ``"multi"``, or ``"diagnostic"``.

    Example::

        diag = by_complexity("diagnostic")
    """
    return [s for s in ALL_SCENARIOS if s.complexity == kind]


# ---------------------------------------------------------------------------
# Acceptance assertions — fail loudly at import time if the corpus is broken.
#
# These are the same assertions that tests/finetune/test_scenarios.py runs
# explicitly so failures surface both at import time AND in CI.
# ---------------------------------------------------------------------------

# 1. Volume gate
assert len(ALL_SCENARIOS) >= 600, (
    f"ALL_SCENARIOS must contain >= 600 entries; got {len(ALL_SCENARIOS)}. "
    "Add more scenarios to the per-tool modules."
)

# 2. All 11 registered tool names have at least one scenario
_scenario_tools: frozenset[str] = frozenset(s.tool for s in ALL_SCENARIOS)
for _t in TOOL_NAMES:
    assert _t in _scenario_tools, (
        f"Tool {_t!r} is in the live registry but has no scenarios in "
        "ALL_SCENARIOS.  Add a per-tool scenario module."
    )

# 3. All 3 permission classes represented
_pclasses_present: frozenset[OpClass] = frozenset(
    s.permission_class for s in ALL_SCENARIOS
)
for _opc in (OpClass.READ, OpClass.WRITE, OpClass.DESTRUCTIVE):
    assert _opc in _pclasses_present, (
        f"Permission class {_opc!r} has no scenarios in ALL_SCENARIOS. "
        "At least one scenario must have a DESTRUCTIVE, WRITE, and READ op."
    )

# 4. All 3 complexities represented
_complexities_present: frozenset[str] = frozenset(
    s.complexity for s in ALL_SCENARIOS
)
for _c in ("single", "multi", "diagnostic"):
    assert _c in _complexities_present, (
        f"Complexity {_c!r} has no scenarios in ALL_SCENARIOS."
    )

# 5. Globally unique IDs
_all_ids: list[str] = [s.id for s in ALL_SCENARIOS]
_dup_ids = [i for i in set(_all_ids) if _all_ids.count(i) > 1]
assert len(_dup_ids) == 0, (
    f"Duplicate scenario ids detected across modules: {_dup_ids}"
)

# 6. Every scenario.tool is in the live TOOL_NAMES
for _s in ALL_SCENARIOS:
    assert _s.tool in TOOL_NAMES, (
        f"Scenario {_s.id!r}: tool {_s.tool!r} is not in the live "
        f"TOOL_NAMES {TOOL_NAMES}.  Is this scenario pointing at an "
        "unregistered tool?"
    )

# 7. Every scenario.operation is a real operation of its tool (live registry)
for _s in ALL_SCENARIOS:
    _real_ops: frozenset[str] = frozenset(registry.get(_s.tool).ops.keys())
    assert _s.operation in _real_ops, (
        f"Scenario {_s.id!r}: operation {_s.operation!r} is not a "
        f"registered op of tool {_s.tool!r}.  Live ops: {sorted(_real_ops)}.  "
        "Either the op name is misspelled or the tool schema has drifted."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "Scenario",
    "ALL_SCENARIOS",
    "by_tool",
    "by_permission",
    "by_complexity",
]
