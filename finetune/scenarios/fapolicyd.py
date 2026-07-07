"""finetune/scenarios/fapolicyd.py — Scenario corpus for the 'fapolicyd' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  status      READ   — show fapolicyd service status
  list_rules  READ   — list loaded fapolicyd rules
  allow       WRITE  — add an allow rule for a path
  deny        WRITE  — add a deny rule for a path (can block critical paths)
  update      WRITE  — reload fapolicyd rules via fapolicyd-cli --update

Coverage targets
----------------
  >= 40 entries total across all 5 operations.
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
    """Return the live permission class for a fapolicyd operation."""
    return registry.get("fapolicyd").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # status  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="fapolicyd-status-0001",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is fapolicyd running?",
        notes="Basic health check for the fapolicyd daemon.",
    ),
    Scenario(
        id="fapolicyd-status-0002",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show me the status of the file access policy daemon",
        notes="Sysadmin checking whether the file access enforcement service is up.",
    ),
    Scenario(
        id="fapolicyd-status-0003",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="check if fapolicyd is active and enforcing",
        notes="Compliance check confirming fapolicyd is running.",
    ),
    Scenario(
        id="fapolicyd-status-0004",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="a script was blocked from running — first check if fapolicyd is up",
        notes="Diagnostic: verify daemon state before investigating a blocked execution.",
    ),
    Scenario(
        id="fapolicyd-status-0005",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="users are getting permission denied on binaries — is fapolicyd blocking them?",
        notes="Diagnostic: correlate access denials with fapolicyd service state.",
    ),
    Scenario(
        id="fapolicyd-status-0006",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check fapolicyd status and then list rules if it is running",
        notes="Multi-step: status then list_rules — confirm daemon is up before querying rules.",
    ),
    Scenario(
        id="fapolicyd-status-0007",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="what is the current state of fapolicyd on this host?",
        notes="General status query from a security audit perspective.",
    ),
    Scenario(
        id="fapolicyd-status-0008",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="the CIS benchmark requires fapolicyd to be running — verify it",
        notes="Compliance-driven status check.",
    ),
    Scenario(
        id="fapolicyd-status-0009",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="has fapolicyd crashed or failed recently?",
        notes="Stability check — looking for failed state or recent service restarts.",
    ),
    Scenario(
        id="fapolicyd-status-0010",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="show fapolicyd status and then reload the rules if the service is healthy",
        notes="Multi-step: status gating a subsequent update operation.",
    ),

    # =========================================================================
    # list_rules  (READ) — 9 entries
    # =========================================================================

    Scenario(
        id="fapolicyd-list_rules-0001",
        tool="fapolicyd",
        operation="list_rules",
        permission_class=_pc("list_rules"),
        complexity="single",
        user_input="list all fapolicyd rules",
        notes="Inspect the full set of loaded rules.",
    ),
    Scenario(
        id="fapolicyd-list_rules-0002",
        tool="fapolicyd",
        operation="list_rules",
        permission_class=_pc("list_rules"),
        complexity="single",
        user_input="show me the current file access policy rules",
        notes="Review loaded policy before making changes.",
    ),
    Scenario(
        id="fapolicyd-list_rules-0003",
        tool="fapolicyd",
        operation="list_rules",
        permission_class=_pc("list_rules"),
        complexity="diagnostic",
        user_input="I need to see the fapolicyd rules — something is blocking /usr/local/bin/myapp",
        notes="Diagnostic: inspect rules to find what is denying a specific binary.",
    ),
    Scenario(
        id="fapolicyd-list_rules-0004",
        tool="fapolicyd",
        operation="list_rules",
        permission_class=_pc("list_rules"),
        complexity="single",
        user_input="dump the fapolicyd rule list for review",
        notes="Security audit: export rule list for external review.",
    ),
    Scenario(
        id="fapolicyd-list_rules-0005",
        tool="fapolicyd",
        operation="list_rules",
        permission_class=_pc("list_rules"),
        complexity="multi",
        user_input="list all fapolicyd rules and check whether any deny /usr/bin/python3",
        notes="Multi-step: list rules then search for a specific deny entry.",
    ),
    Scenario(
        id="fapolicyd-list_rules-0006",
        tool="fapolicyd",
        operation="list_rules",
        permission_class=_pc("list_rules"),
        complexity="diagnostic",
        user_input="after adding a new allow rule show the full rule list to confirm it was added",
        notes="Post-change verification: list rules after an allow operation.",
    ),
    Scenario(
        id="fapolicyd-list_rules-0007",
        tool="fapolicyd",
        operation="list_rules",
        permission_class=_pc("list_rules"),
        complexity="single",
        user_input="what rules does fapolicyd have loaded right now?",
        notes="Operator query about current enforcement state.",
    ),
    Scenario(
        id="fapolicyd-list_rules-0008",
        tool="fapolicyd",
        operation="list_rules",
        permission_class=_pc("list_rules"),
        complexity="diagnostic",
        user_input="a new package was installed and some binaries are now blocked — show the fapolicyd rules",
        notes="Diagnostic: inspect rules after a package install to find unexpected denials.",
    ),
    Scenario(
        id="fapolicyd-list_rules-0009",
        tool="fapolicyd",
        operation="list_rules",
        permission_class=_pc("list_rules"),
        complexity="single",
        user_input="use fapolicyd-cli to show the current rule list",
        notes="Direct CLI-phrased request to list rules.",
    ),

    # =========================================================================
    # allow  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="fapolicyd-allow-0001",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="single",
        user_input="allow /usr/local/bin/myapp to run",
        notes="WRITE: add an allow rule for a locally installed application.",
    ),
    Scenario(
        id="fapolicyd-allow-0002",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="single",
        user_input="add a fapolicyd allow rule for /opt/app/bin/server",
        notes="WRITE: allow a third-party application binary.",
    ),
    Scenario(
        id="fapolicyd-allow-0003",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="multi",
        user_input="allow /usr/local/sbin/custom-script and then reload the rules",
        notes="Multi-step: allow then update to activate the new rule.",
    ),
    Scenario(
        id="fapolicyd-allow-0004",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="diagnostic",
        user_input="fapolicyd is blocking /usr/bin/python3 — add an allow rule for it",
        notes="Diagnostic-triggered WRITE: allow a blocked interpreter.",
    ),
    Scenario(
        id="fapolicyd-allow-0005",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="single",
        user_input="whitelist /usr/share/java/bin/java in fapolicyd",
        notes="WRITE: allow a JVM binary installed outside the default trust set.",
    ),
    Scenario(
        id="fapolicyd-allow-0006",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="single",
        user_input="add /opt/monitoring/collector to the fapolicyd allow list",
        notes="WRITE: allow a monitoring collector binary.",
    ),
    Scenario(
        id="fapolicyd-allow-0007",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="multi",
        user_input="allow /usr/local/bin/deploy-script and then verify by listing the rules",
        notes="Multi-step: allow then list_rules to confirm the entry was added.",
    ),
    Scenario(
        id="fapolicyd-allow-0008",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="diagnostic",
        user_input="the backup job failed because fapolicyd blocked /usr/bin/tar — create an allow rule",
        notes="Diagnostic-triggered WRITE: allow a standard utility that was inadvertently blocked.",
    ),
    Scenario(
        id="fapolicyd-allow-0009",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="single",
        user_input="permit /opt/vendor/bin/healthcheck to execute",
        notes="WRITE: allow a vendor health check binary.",
    ),
    Scenario(
        id="fapolicyd-allow-0010",
        tool="fapolicyd",
        operation="allow",
        permission_class=_pc("allow"),
        complexity="single",
        user_input="add a fapolicyd allow rule for /usr/libexec/platform-python",
        notes="WRITE: allow the system Python used by system scripts on RHEL-compatible hosts.",
    ),

    # =========================================================================
    # deny  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="fapolicyd-deny-0001",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="single",
        user_input="deny /tmp/suspicious_binary from executing",
        notes=(
            "WRITE: block execution of a suspicious file dropped in /tmp. "
            "Confirm this is not a critical path before applying."
        ),
    ),
    Scenario(
        id="fapolicyd-deny-0002",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="single",
        user_input="add a fapolicyd deny rule for /home/user/untrusted-tool",
        notes="WRITE: block an untrusted executable in a user home directory.",
    ),
    Scenario(
        id="fapolicyd-deny-0003",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="multi",
        user_input="deny /opt/old-app/run and then reload the policy",
        notes="Multi-step: deny then update to enforce the new rule immediately.",
    ),
    Scenario(
        id="fapolicyd-deny-0004",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="diagnostic",
        user_input="an attacker placed a binary in /var/tmp — block it with a fapolicyd deny rule",
        notes="Diagnostic-triggered WRITE: emergency block of a potentially malicious file.",
    ),
    Scenario(
        id="fapolicyd-deny-0005",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="single",
        user_input="block /usr/local/bin/old-version from being executed",
        notes="WRITE: deny a deprecated binary that should no longer run.",
    ),
    Scenario(
        id="fapolicyd-deny-0006",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="single",
        user_input="deny execution of /opt/test/experimental-binary",
        notes="WRITE: block a test binary from running on a production host.",
    ),
    Scenario(
        id="fapolicyd-deny-0007",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="multi",
        user_input="add a deny rule for /tmp/payload and list rules to confirm it appears",
        notes="Multi-step: deny then list_rules verification.",
    ),
    Scenario(
        id="fapolicyd-deny-0008",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="diagnostic",
        user_input="the security scan flagged /usr/local/lib/badlib.so — deny it in fapolicyd",
        notes="Diagnostic-triggered WRITE: block a library flagged by a security scan.",
    ),
    Scenario(
        id="fapolicyd-deny-0009",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="single",
        user_input="block /opt/downloaded-tool/run via fapolicyd",
        notes="WRITE: deny an untrusted downloaded executable from running.",
    ),
    Scenario(
        id="fapolicyd-deny-0010",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("deny"),
        complexity="single",
        user_input="add a fapolicyd deny entry for /srv/uploads/script.sh",
        notes="WRITE: block a user-uploaded script from executing on the server.",
    ),

    # =========================================================================
    # update  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="fapolicyd-update-0001",
        tool="fapolicyd",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="reload the fapolicyd rules",
        notes="WRITE: apply pending rule changes by reloading.",
    ),
    Scenario(
        id="fapolicyd-update-0002",
        tool="fapolicyd",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="tell fapolicyd to re-read its configuration",
        notes="WRITE: reload after editing /etc/fapolicyd/rules.d/ files manually.",
    ),
    Scenario(
        id="fapolicyd-update-0003",
        tool="fapolicyd",
        operation="update",
        permission_class=_pc("update"),
        complexity="multi",
        user_input="add an allow rule for /opt/app/bin/start and then reload fapolicyd",
        notes="Multi-step: allow then update — the reload is needed to activate the new rule.",
    ),
    Scenario(
        id="fapolicyd-update-0004",
        tool="fapolicyd",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="run fapolicyd-cli --update to apply the rule changes",
        notes="WRITE: explicit CLI-phrased update request.",
    ),
    Scenario(
        id="fapolicyd-update-0005",
        tool="fapolicyd",
        operation="update",
        permission_class=_pc("update"),
        complexity="diagnostic",
        user_input="I edited the fapolicyd rules file but the policy has not changed — reload it",
        notes="Diagnostic: reload to pick up manual rule file edits.",
    ),
    Scenario(
        id="fapolicyd-update-0006",
        tool="fapolicyd",
        operation="update",
        permission_class=_pc("update"),
        complexity="multi",
        user_input="reload fapolicyd and then list rules to confirm the changes took effect",
        notes="Multi-step: update then list_rules to verify.",
    ),
    Scenario(
        id="fapolicyd-update-0007",
        tool="fapolicyd",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="notify fapolicyd to pick up the new deny rule",
        notes="WRITE: reload after a deny rule was added.",
    ),
    Scenario(
        id="fapolicyd-update-0008",
        tool="fapolicyd",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="refresh the fapolicyd policy database",
        notes="WRITE: reload to refresh after a trust database update.",
    ),
    Scenario(
        id="fapolicyd-update-0009",
        tool="fapolicyd",
        operation="update",
        permission_class=_pc("update"),
        complexity="diagnostic",
        user_input="a new package was installed but fapolicyd is still blocking it — reload the rules",
        notes="Diagnostic: reload after package install to refresh the trust database.",
    ),
]


# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("fapolicyd").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "fapolicyd", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("fapolicyd").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
