"""finetune/scenarios/dnf_modules.py — Scenario corpus for the 'dnf_modules' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list     READ   — list available or installed module streams
  info     READ   — show detailed information about a module stream
  enable   WRITE  — enable a module stream
  disable  WRITE  — disable a module stream
  install  WRITE  — install a module profile
  reset    WRITE  — reset a module to its default state

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE scenarios are honestly labeled (permission_class from registry)
  so downstream traces teach the confirm-before-write gate.

INV-schema-sync:  permission_class for each entry is derived from the LIVE
  registry via finetune.coreimports, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass
# Compatible field names are EXACT so the P13 JOIN can unify without renames.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    id: str
    tool: str
    operation: str
    permission_class: OpClass
    complexity: Literal["single", "multi", "diagnostic"]
    user_input: str
    notes: str


# ---------------------------------------------------------------------------
# Live permission-class lookup — INV-schema-sync
# ---------------------------------------------------------------------------


def _pc(op: str) -> OpClass:
    """Return the live permission class for a dnf_modules operation."""
    return registry.get("dnf_modules").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="dnf_modules-list-0001",
        tool="dnf_modules",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all available dnf modules",
        notes="List all modules — no filter applied.",
    ),
    Scenario(
        id="dnf_modules-list-0002",
        tool="dnf_modules",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list available nodejs module streams",
        notes="Filtered list for nodejs module.",
    ),
    Scenario(
        id="dnf_modules-list-0003",
        tool="dnf_modules",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what postgresql module streams are available on this system?",
        notes="List postgresql module streams.",
    ),
    Scenario(
        id="dnf_modules-list-0004",
        tool="dnf_modules",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list all php module streams",
        notes="PHP module stream listing — common web stack question.",
    ),
    Scenario(
        id="dnf_modules-list-0005",
        tool="dnf_modules",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list all enabled modules and tell me which ones are active",
        notes="Multi-step: list then filter/interpret for enabled state.",
    ),
    Scenario(
        id="dnf_modules-list-0006",
        tool="dnf_modules",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="I need to know what python versions are available as modules before I install anything",
        notes="Diagnostic: list modules before committing to an install.",
    ),
    Scenario(
        id="dnf_modules-list-0007",
        tool="dnf_modules",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show the nginx module streams on this host",
        notes="Listing nginx module streams.",
    ),
    Scenario(
        id="dnf_modules-list-0008",
        tool="dnf_modules",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="what ruby module streams are available — I need to pick one before enabling",
        notes="Diagnostic: discovery before enabling a stream.",
    ),

    # =========================================================================
    # info  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="dnf_modules-info-0001",
        tool="dnf_modules",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me info about the nodejs:18 module",
        notes="Detailed info for a specific nodejs stream.",
    ),
    Scenario(
        id="dnf_modules-info-0002",
        tool="dnf_modules",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what profiles does the postgresql module offer?",
        notes="Info to discover available profiles.",
    ),
    Scenario(
        id="dnf_modules-info-0003",
        tool="dnf_modules",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="get details on the php:8.1 module stream",
        notes="Detailed info for php 8.1 stream.",
    ),
    Scenario(
        id="dnf_modules-info-0004",
        tool="dnf_modules",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="check the info for the ruby module and then decide which stream to enable",
        notes="Multi-step: info then enable decision.",
    ),
    Scenario(
        id="dnf_modules-info-0005",
        tool="dnf_modules",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me what packages are in the nginx:mainline module",
        notes="Info to inspect module package content.",
    ),
    Scenario(
        id="dnf_modules-info-0006",
        tool="dnf_modules",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="the team wants to install mariadb — show me the module info first",
        notes="Diagnostic: pre-install review of module metadata.",
    ),
    Scenario(
        id="dnf_modules-info-0007",
        tool="dnf_modules",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="get the details for the python39 module",
        notes="Info for a specific Python version module.",
    ),
    Scenario(
        id="dnf_modules-info-0008",
        tool="dnf_modules",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="I'm seeing conflicts with the container-tools module — show me its info",
        notes="Diagnostic: inspect module info to investigate a conflict.",
    ),

    # =========================================================================
    # enable  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="dnf_modules-enable-0001",
        tool="dnf_modules",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable the nodejs:18 module stream",
        notes="WRITE: enable a specific nodejs stream.",
    ),
    Scenario(
        id="dnf_modules-enable-0002",
        tool="dnf_modules",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="switch this server to use postgresql:15",
        notes="WRITE: enable postgresql 15 stream.",
    ),
    Scenario(
        id="dnf_modules-enable-0003",
        tool="dnf_modules",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable the php:8.2 module so I can install it",
        notes="WRITE: enable php 8.2 module stream.",
    ),
    Scenario(
        id="dnf_modules-enable-0004",
        tool="dnf_modules",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="multi",
        user_input="enable the nginx:mainline module and then install it",
        notes="Multi-step: enable stream then install profile.",
    ),
    Scenario(
        id="dnf_modules-enable-0005",
        tool="dnf_modules",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable ruby:3.1 module stream on this server",
        notes="WRITE: enable a ruby stream.",
    ),
    Scenario(
        id="dnf_modules-enable-0006",
        tool="dnf_modules",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="diagnostic",
        user_input="the app requires python 3.11 — enable the right module stream",
        notes="Diagnostic-triggered WRITE: enable the stream required by an application.",
    ),
    Scenario(
        id="dnf_modules-enable-0007",
        tool="dnf_modules",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable the mariadb:10.11 module",
        notes="WRITE: enable a MariaDB LTS stream.",
    ),
    Scenario(
        id="dnf_modules-enable-0008",
        tool="dnf_modules",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="multi",
        user_input="enable container-tools:rhel8 and check its status afterwards",
        notes="Multi-step: enable then verify with list or info.",
    ),

    # =========================================================================
    # disable  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="dnf_modules-disable-0001",
        tool="dnf_modules",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable the nodejs module stream",
        notes="WRITE: disable nodejs — stream will no longer be available.",
    ),
    Scenario(
        id="dnf_modules-disable-0002",
        tool="dnf_modules",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable the php:7.4 module — we're moving to 8.2",
        notes="WRITE: disable an older php stream before enabling a newer one.",
    ),
    Scenario(
        id="dnf_modules-disable-0003",
        tool="dnf_modules",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="turn off the postgresql:13 module stream",
        notes="WRITE: disable an older postgresql stream.",
    ),
    Scenario(
        id="dnf_modules-disable-0004",
        tool="dnf_modules",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="multi",
        user_input="disable the ruby:3.0 module and then enable ruby:3.1 in its place",
        notes="Multi-step: disable old stream, enable new stream.",
    ),
    Scenario(
        id="dnf_modules-disable-0005",
        tool="dnf_modules",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable the nginx:mainline module on this host",
        notes="WRITE: disable a module stream to prevent installs from it.",
    ),
    Scenario(
        id="dnf_modules-disable-0006",
        tool="dnf_modules",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="diagnostic",
        user_input="the security scan flagged the python:3.6 module as EOL — disable it",
        notes="Diagnostic-triggered WRITE: disable an EOL module stream after a security scan.",
    ),
    Scenario(
        id="dnf_modules-disable-0007",
        tool="dnf_modules",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable the mariadb module so we can use the packages tool to install from the base repo",
        notes="WRITE: disable a module stream to unblock base-repo package installation.",
    ),

    # =========================================================================
    # install  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="dnf_modules-install-0001",
        tool="dnf_modules",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install the nodejs:18 module with the default profile",
        notes="WRITE: install nodejs 18 default profile.",
    ),
    Scenario(
        id="dnf_modules-install-0002",
        tool="dnf_modules",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install postgresql:15 server profile",
        notes="WRITE: install specific profile of postgresql module.",
    ),
    Scenario(
        id="dnf_modules-install-0003",
        tool="dnf_modules",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install the php:8.2/common module profile",
        notes="WRITE: install a named profile of a php module.",
    ),
    Scenario(
        id="dnf_modules-install-0004",
        tool="dnf_modules",
        operation="install",
        permission_class=_pc("install"),
        complexity="multi",
        user_input="install the ruby:3.1 module and then verify it installed correctly",
        notes="Multi-step: install then verify via list or info.",
    ),
    Scenario(
        id="dnf_modules-install-0005",
        tool="dnf_modules",
        operation="install",
        permission_class=_pc("install"),
        complexity="diagnostic",
        user_input="the deployment script needs container-tools — install the module now",
        notes="Diagnostic-triggered WRITE: install module required by a deployment.",
    ),
    Scenario(
        id="dnf_modules-install-0006",
        tool="dnf_modules",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install the mariadb:10.11 module on this database server",
        notes="WRITE: install MariaDB LTS module.",
    ),
    Scenario(
        id="dnf_modules-install-0007",
        tool="dnf_modules",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install nginx via its module profile",
        notes="WRITE: install nginx through the module system.",
    ),

    # =========================================================================
    # reset  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="dnf_modules-reset-0001",
        tool="dnf_modules",
        operation="reset",
        permission_class=_pc("reset"),
        complexity="single",
        user_input="reset the nodejs module to its default state",
        notes="WRITE: reset module stream — returns to no-stream-selected state.",
    ),
    Scenario(
        id="dnf_modules-reset-0002",
        tool="dnf_modules",
        operation="reset",
        permission_class=_pc("reset"),
        complexity="single",
        user_input="reset the php module so I can switch to a different stream",
        notes="WRITE: reset php module before enabling a different stream.",
    ),
    Scenario(
        id="dnf_modules-reset-0003",
        tool="dnf_modules",
        operation="reset",
        permission_class=_pc("reset"),
        complexity="single",
        user_input="I need to change the postgresql stream — reset the module first",
        notes="WRITE: reset required before changing stream selection.",
    ),
    Scenario(
        id="dnf_modules-reset-0004",
        tool="dnf_modules",
        operation="reset",
        permission_class=_pc("reset"),
        complexity="multi",
        user_input="reset the ruby module and then enable ruby:3.1",
        notes="Multi-step: reset then enable a new stream.",
    ),
    Scenario(
        id="dnf_modules-reset-0005",
        tool="dnf_modules",
        operation="reset",
        permission_class=_pc("reset"),
        complexity="single",
        user_input="reset the nginx module to its default",
        notes="WRITE: reset nginx module stream.",
    ),
    Scenario(
        id="dnf_modules-reset-0006",
        tool="dnf_modules",
        operation="reset",
        permission_class=_pc("reset"),
        complexity="diagnostic",
        user_input="the mariadb module is in a broken state after a failed upgrade — reset it",
        notes="Diagnostic-triggered WRITE: reset a module stuck in a bad state.",
    ),
    Scenario(
        id="dnf_modules-reset-0007",
        tool="dnf_modules",
        operation="reset",
        permission_class=_pc("reset"),
        complexity="multi",
        user_input="reset the container-tools module and then list all modules to confirm the reset",
        notes="Multi-step: reset then confirm via list.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("dnf_modules").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "dnf_modules", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("dnf_modules").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
