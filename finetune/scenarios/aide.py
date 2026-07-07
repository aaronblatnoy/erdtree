"""finetune/scenarios/aide.py — Scenario corpus for the 'aide' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  check      READ   — compare live filesystem against the AIDE reference database
  init       WRITE  — initialise (or reinitialise) the AIDE reference database
  update     WRITE  — update the AIDE database to accept current changes as baseline
  db_status  READ   — show AIDE database file metadata

Coverage targets
----------------
  >= 40 entries total across all 4 operations.
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
# Compatible field names are EXACT so the Phase-13 JOIN can unify without renames.
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
    """Return the live permission class for an aide operation."""
    return registry.get("aide").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # check  (READ) — 12 entries
    # =========================================================================

    Scenario(
        id="aide-check-0001",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="single",
        user_input="run an aide integrity check on this server",
        notes="Basic integrity scan against the reference database.",
    ),
    Scenario(
        id="aide-check-0002",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="single",
        user_input="check if any system files have changed since the last aide baseline",
        notes="Post-change filesystem verification.",
    ),
    Scenario(
        id="aide-check-0003",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="single",
        user_input="run aide --check to verify filesystem integrity",
        notes="Admin explicitly requests the aide --check command.",
    ),
    Scenario(
        id="aide-check-0004",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="diagnostic",
        user_input="the security team thinks someone modified /etc/passwd — run an aide check to confirm",
        notes="Incident response: integrity check to detect unauthorized /etc/passwd modification.",
    ),
    Scenario(
        id="aide-check-0005",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="diagnostic",
        user_input="we had a suspected intrusion last night — run aide to check for file tampering",
        notes="Post-intrusion forensic integrity scan.",
    ),
    Scenario(
        id="aide-check-0006",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="multi",
        user_input="run an aide integrity check and then tell me which files changed",
        notes="Multi-step: check then summarise changed file list from output.",
    ),
    Scenario(
        id="aide-check-0007",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="single",
        user_input="verify system file integrity with aide",
        notes="General integrity verification request.",
    ),
    Scenario(
        id="aide-check-0008",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="diagnostic",
        user_input="compliance audit requires an aide check — run it and report any deviations",
        notes="Compliance-driven integrity check with result reporting.",
    ),
    Scenario(
        id="aide-check-0009",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="multi",
        user_input="run aide --check with a custom config at /etc/aide/aide-prod.conf and show me the report",
        notes="Multi-step: check with non-default config path, then present results.",
    ),
    Scenario(
        id="aide-check-0010",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="single",
        user_input="has anything in /etc changed since the aide baseline was created?",
        notes="Focused concern about /etc directory changes — aide check is the answer.",
    ),
    Scenario(
        id="aide-check-0011",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="diagnostic",
        user_input="the CIS benchmark requires daily aide checks — run one now and flag any failures",
        notes="CIS compliance-driven integrity check.",
    ),
    Scenario(
        id="aide-check-0012",
        tool="aide",
        operation="check",
        permission_class=_pc("check"),
        complexity="multi",
        user_input="check filesystem integrity with aide, and if there are changes, show which categories of files were affected",
        notes="Multi-step: run check then categorise findings (config, binary, log).",
    ),

    # =========================================================================
    # init  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="aide-init-0001",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="single",
        user_input="initialise the aide database on this newly built server",
        notes="WRITE: first-time aide database creation on a fresh host.",
    ),
    Scenario(
        id="aide-init-0002",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="single",
        user_input="run aide --init to create the reference baseline",
        notes="WRITE: explicit admin request to build the aide reference DB.",
    ),
    Scenario(
        id="aide-init-0003",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="multi",
        user_input="initialise the aide database and then move aide.db.new.gz into place",
        notes="Multi-step: init then activate the new database file.",
    ),
    Scenario(
        id="aide-init-0004",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="single",
        user_input="the aide database does not exist — create it",
        notes="WRITE: recover from missing DB by reinitialising.",
    ),
    Scenario(
        id="aide-init-0005",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="diagnostic",
        user_input="aide --check is failing because there is no database — what should I do?",
        notes="Diagnostic path that resolves with aide --init.",
    ),
    Scenario(
        id="aide-init-0006",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="single",
        user_input="re-initialise the aide baseline after we finished patching the system",
        notes="WRITE: post-patch DB re-creation to capture the patched state as the new baseline.",
    ),
    Scenario(
        id="aide-init-0007",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="multi",
        user_input="create a fresh aide database using /etc/aide/aide-custom.conf",
        notes="Multi-step: init with non-default config then verify the new DB file exists.",
    ),
    Scenario(
        id="aide-init-0008",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="single",
        user_input="set up aide on this host for the first time",
        notes="WRITE: new host onboarding — create the initial integrity baseline.",
    ),
    Scenario(
        id="aide-init-0009",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="single",
        user_input="the security policy requires a fresh aide baseline after every major OS upgrade — run it",
        notes="WRITE: post-upgrade DB reinitialisation per security policy.",
    ),
    Scenario(
        id="aide-init-0010",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="multi",
        user_input="initialise the aide database and then run a check to confirm it works",
        notes="Multi-step: init followed immediately by a check to validate the new DB.",
    ),
    Scenario(
        id="aide-init-0011",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="single",
        user_input="build the aide integrity database from scratch",
        notes="WRITE: equivalent of aide --init, starting fresh.",
    ),
    Scenario(
        id="aide-init-0012",
        tool="aide",
        operation="init",
        permission_class=_pc("init"),
        complexity="diagnostic",
        user_input="aide reports 'cannot open database' every time we run a check — fix it",
        notes="Diagnostic: missing DB error resolved by running aide --init.",
    ),

    # =========================================================================
    # update  (WRITE) — 11 entries
    # =========================================================================

    Scenario(
        id="aide-update-0001",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="update the aide database to accept the changes from today's package updates",
        notes="WRITE: post-dnf-update DB refresh to accept patched file hashes.",
    ),
    Scenario(
        id="aide-update-0002",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="run aide --update to set the current filesystem state as the new baseline",
        notes="WRITE: explicit admin request to update the aide DB.",
    ),
    Scenario(
        id="aide-update-0003",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="multi",
        user_input="update the aide database and then verify the new baseline with a check",
        notes="Multi-step: update then run a check against the new DB.",
    ),
    Scenario(
        id="aide-update-0004",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="I applied an approved config change to /etc/nginx/nginx.conf — update the aide reference",
        notes="WRITE: approved change acceptance into the aide baseline.",
    ),
    Scenario(
        id="aide-update-0005",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="diagnostic",
        user_input="aide keeps alerting on /etc/resolv.conf which we update via DHCP — suppress it by updating the baseline",
        notes="Diagnostic: recurring false-positive resolved by updating the DB after confirming the change is expected.",
    ),
    Scenario(
        id="aide-update-0006",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="refresh the aide integrity baseline after we deployed new application binaries",
        notes="WRITE: post-deployment DB update to accept new binary hashes.",
    ),
    Scenario(
        id="aide-update-0007",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="update aide after the kernel was updated to remove false positives on kernel modules",
        notes="WRITE: post-kernel-upgrade aide DB refresh.",
    ),
    Scenario(
        id="aide-update-0008",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="multi",
        user_input="update the aide database with the custom config at /etc/aide/aide-prod.conf",
        notes="Multi-step: update with non-default config then confirm success.",
    ),
    Scenario(
        id="aide-update-0009",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="the change window just closed — lock in the current filesystem state as the aide baseline",
        notes="WRITE: post-maintenance-window baseline acceptance.",
    ),
    Scenario(
        id="aide-update-0010",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="diagnostic",
        user_input="aide is flagging log rotation changes every day — update the baseline to reflect normal log rotation",
        notes="Diagnostic: suppress expected log rotation noise by updating the DB.",
    ),
    Scenario(
        id="aide-update-0011",
        tool="aide",
        operation="update",
        permission_class=_pc("update"),
        complexity="multi",
        user_input="run aide --update and show me a summary of what changed before committing to the new baseline",
        notes="Multi-step: update (which also reports changes) then summarise the diff.",
    ),

    # =========================================================================
    # db_status  (READ) — 11 entries
    # =========================================================================

    Scenario(
        id="aide-db_status-0001",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="single",
        user_input="when was the aide database last updated?",
        notes="Admin wants the modification timestamp of the AIDE DB file.",
    ),
    Scenario(
        id="aide-db_status-0002",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="single",
        user_input="does the aide database file exist on this host?",
        notes="Pre-check before running aide --check to confirm the DB is present.",
    ),
    Scenario(
        id="aide-db_status-0003",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="single",
        user_input="show me the aide database file information",
        notes="General DB metadata request — size, permissions, timestamp.",
    ),
    Scenario(
        id="aide-db_status-0004",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="diagnostic",
        user_input="aide --check is failing — is the database file there and does it have the right permissions?",
        notes="Diagnostic: verify DB file existence and permissions before debugging aide further.",
    ),
    Scenario(
        id="aide-db_status-0005",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="single",
        user_input="check the size of the aide database",
        notes="Admin wants to know the DB file size as a sanity check.",
    ),
    Scenario(
        id="aide-db_status-0006",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="multi",
        user_input="show the aide database file status and then tell me whether I need to update it",
        notes="Multi-step: check DB timestamp then advise if an update is overdue.",
    ),
    Scenario(
        id="aide-db_status-0007",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="single",
        user_input="is the aide db file readable by root only?",
        notes="Security check that the DB file has restrictive permissions (0600).",
    ),
    Scenario(
        id="aide-db_status-0008",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="diagnostic",
        user_input="the compliance report says the aide database is stale — when was it last modified?",
        notes="Compliance: check DB modification timestamp to determine staleness.",
    ),
    Scenario(
        id="aide-db_status-0009",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="single",
        user_input="check the status of /var/lib/aide/aide.db.gz",
        notes="Admin references the DB file path explicitly.",
    ),
    Scenario(
        id="aide-db_status-0010",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="multi",
        user_input="verify the aide database exists and then run a check",
        notes="Multi-step: confirm DB presence before triggering an integrity check.",
    ),
    Scenario(
        id="aide-db_status-0011",
        tool="aide",
        operation="db_status",
        permission_class=_pc("db_status"),
        complexity="diagnostic",
        user_input="aide keeps failing on this host and I do not know why — start by checking if the database file exists",
        notes="Diagnostic starting point: DB existence check before deeper investigation.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("aide").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "aide", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("aide").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
