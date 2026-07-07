"""finetune/scenarios/chrony.py — Scenario corpus for the 'chrony' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  tracking  READ  — show current clock tracking statistics
  sources   READ  — list NTP sources and their reachability
  status    READ  — show the systemd status of chronyd
  makestep  WRITE — immediately step the system clock to NTP reference
  conf_view READ  — display /etc/chrony.conf
  conf_edit WRITE — overwrite /etc/chrony.conf with supplied content

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE scenarios honestly labeled so downstream traces teach the confirm gate.

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
# Scenario dataclass — field names/order match services.py for Phase-13 JOIN
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
    """Return the live permission class for a chrony operation."""
    return registry.get("chrony").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # tracking  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="chrony-tracking-0001",
        tool="chrony",
        operation="tracking",
        permission_class=_pc("tracking"),
        complexity="single",
        user_input="show me the current NTP tracking stats",
        notes="Basic clock tracking query — most common chrony inspection op.",
    ),
    Scenario(
        id="chrony-tracking-0002",
        tool="chrony",
        operation="tracking",
        permission_class=_pc("tracking"),
        complexity="single",
        user_input="what is the system clock offset right now?",
        notes="User asking about offset; tracking shows system time deviation.",
    ),
    Scenario(
        id="chrony-tracking-0003",
        tool="chrony",
        operation="tracking",
        permission_class=_pc("tracking"),
        complexity="single",
        user_input="check the NTP stratum and reference server for this host",
        notes="Tracking output shows reference ID and stratum.",
    ),
    Scenario(
        id="chrony-tracking-0004",
        tool="chrony",
        operation="tracking",
        permission_class=_pc("tracking"),
        complexity="diagnostic",
        user_input="our application timestamps are drifting — what does the clock tracking look like?",
        notes="Diagnostic: correlate application timestamp issues with clock offset.",
    ),
    Scenario(
        id="chrony-tracking-0005",
        tool="chrony",
        operation="tracking",
        permission_class=_pc("tracking"),
        complexity="single",
        user_input="is the clock synchronized to an NTP server?",
        notes="Check Leap status and reference ID to confirm synchronisation.",
    ),
    Scenario(
        id="chrony-tracking-0006",
        tool="chrony",
        operation="tracking",
        permission_class=_pc("tracking"),
        complexity="multi",
        user_input="check clock tracking and then tell me if the frequency error is within acceptable limits",
        notes="Multi-step: fetch tracking data and interpret frequency/skew fields.",
    ),
    Scenario(
        id="chrony-tracking-0007",
        tool="chrony",
        operation="tracking",
        permission_class=_pc("tracking"),
        complexity="diagnostic",
        user_input="the TLS certificate validation is failing due to time skew — run chronyc tracking first",
        notes="Diagnostic: time skew causing TLS failures; tracking is first diagnostic step.",
    ),
    Scenario(
        id="chrony-tracking-0008",
        tool="chrony",
        operation="tracking",
        permission_class=_pc("tracking"),
        complexity="single",
        user_input="show root delay and root dispersion for the NTP source",
        notes="Tracking shows root delay/dispersion; useful for assessing sync quality.",
    ),

    # =========================================================================
    # sources  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="chrony-sources-0001",
        tool="chrony",
        operation="sources",
        permission_class=_pc("sources"),
        complexity="single",
        user_input="list the NTP servers this host is using",
        notes="Basic sources query — shows configured and reachable NTP peers.",
    ),
    Scenario(
        id="chrony-sources-0002",
        tool="chrony",
        operation="sources",
        permission_class=_pc("sources"),
        complexity="single",
        user_input="which NTP source is currently selected as the reference?",
        notes="Sources output marks selected source with *.",
    ),
    Scenario(
        id="chrony-sources-0003",
        tool="chrony",
        operation="sources",
        permission_class=_pc("sources"),
        complexity="diagnostic",
        user_input="the clock seems to be drifting — are all the NTP sources reachable?",
        notes="Diagnostic: check Reach column in sources output for polling failures.",
    ),
    Scenario(
        id="chrony-sources-0004",
        tool="chrony",
        operation="sources",
        permission_class=_pc("sources"),
        complexity="single",
        user_input="show the stratum of each configured NTP server",
        notes="Sources lists each server's stratum.",
    ),
    Scenario(
        id="chrony-sources-0005",
        tool="chrony",
        operation="sources",
        permission_class=_pc("sources"),
        complexity="multi",
        user_input="show NTP sources and check whether any have a reach of zero",
        notes="Multi-step: list sources then analyse the Reach column for unreachable servers.",
    ),
    Scenario(
        id="chrony-sources-0006",
        tool="chrony",
        operation="sources",
        permission_class=_pc("sources"),
        complexity="single",
        user_input="verify that the pool.ntp.org servers are being used",
        notes="Sources shows pool members; verify expected servers appear.",
    ),
    Scenario(
        id="chrony-sources-0007",
        tool="chrony",
        operation="sources",
        permission_class=_pc("sources"),
        complexity="diagnostic",
        user_input="kerberos tickets are expiring too early — show the NTP sources to check sync",
        notes="Diagnostic: Kerberos time sensitivity; sources confirms NTP sync status.",
    ),
    Scenario(
        id="chrony-sources-0008",
        tool="chrony",
        operation="sources",
        permission_class=_pc("sources"),
        complexity="single",
        user_input="how many NTP sources does chrony have configured?",
        notes="Count rows in chronyc sources output.",
    ),

    # =========================================================================
    # status  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="chrony-status-0001",
        tool="chrony",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is chronyd running?",
        notes="Basic daemon health check.",
    ),
    Scenario(
        id="chrony-status-0002",
        tool="chrony",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show the chronyd service status",
        notes="systemctl status chronyd — confirm active/inactive and uptime.",
    ),
    Scenario(
        id="chrony-status-0003",
        tool="chrony",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="NTP seems to have stopped — check the chronyd service status first",
        notes="Diagnostic entry point when NTP sync appears broken.",
    ),
    Scenario(
        id="chrony-status-0004",
        tool="chrony",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check the chronyd status and then show the tracking output if it is running",
        notes="Multi-step: status first; tracking only if daemon is up.",
    ),
    Scenario(
        id="chrony-status-0005",
        tool="chrony",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="how long has chronyd been running?",
        notes="Status output shows active-since timestamp and uptime.",
    ),
    Scenario(
        id="chrony-status-0006",
        tool="chrony",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="cron jobs are failing because system time is wrong — is chronyd even active?",
        notes="Diagnostic: incorrect time suspected; status confirms daemon state.",
    ),
    Scenario(
        id="chrony-status-0007",
        tool="chrony",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="verify the NTP daemon is healthy before the maintenance window",
        notes="Pre-maintenance check: confirm chronyd is active and has been stable.",
    ),

    # =========================================================================
    # makestep  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="chrony-makestep-0001",
        tool="chrony",
        operation="makestep",
        permission_class=_pc("makestep"),
        complexity="single",
        user_input="force the clock to sync right now",
        notes="WRITE: immediate clock step — applies offset without waiting for gradual slew.",
    ),
    Scenario(
        id="chrony-makestep-0002",
        tool="chrony",
        operation="makestep",
        permission_class=_pc("makestep"),
        complexity="single",
        user_input="step the system clock to the NTP reference immediately",
        notes="WRITE: makestep — user explicitly wants a hard clock correction.",
    ),
    Scenario(
        id="chrony-makestep-0003",
        tool="chrony",
        operation="makestep",
        permission_class=_pc("makestep"),
        complexity="diagnostic",
        user_input="the clock is 5 minutes off after the VM was paused — fix it now",
        notes="Diagnostic-triggered WRITE: large offset after VM resume; makestep is the correct remedy.",
    ),
    Scenario(
        id="chrony-makestep-0004",
        tool="chrony",
        operation="makestep",
        permission_class=_pc("makestep"),
        complexity="multi",
        user_input="step the clock and then verify the offset is small via chronyc tracking",
        notes="Multi-step: makestep then tracking to confirm correction.",
    ),
    Scenario(
        id="chrony-makestep-0005",
        tool="chrony",
        operation="makestep",
        permission_class=_pc("makestep"),
        complexity="single",
        user_input="synchronise the clock right away — we cannot wait for gradual adjustment",
        notes="WRITE: immediate step when slew rate would take too long.",
    ),
    Scenario(
        id="chrony-makestep-0006",
        tool="chrony",
        operation="makestep",
        permission_class=_pc("makestep"),
        complexity="diagnostic",
        user_input="kerberos authentication is broken because the clock is 4 minutes ahead — step it",
        notes="Diagnostic: Kerberos max skew exceeded; makestep is the remediation.",
    ),
    Scenario(
        id="chrony-makestep-0007",
        tool="chrony",
        operation="makestep",
        permission_class=_pc("makestep"),
        complexity="single",
        user_input="run chronyc makestep to correct the time offset",
        notes="WRITE: explicit chronyc makestep request.",
    ),
    Scenario(
        id="chrony-makestep-0008",
        tool="chrony",
        operation="makestep",
        permission_class=_pc("makestep"),
        complexity="multi",
        user_input="check the clock offset first, and if it is over 1 second step the clock",
        notes="Multi-step: tracking read then conditional makestep write.",
    ),

    # =========================================================================
    # conf_view  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="chrony-conf_view-0001",
        tool="chrony",
        operation="conf_view",
        permission_class=_pc("conf_view"),
        complexity="single",
        user_input="show me the chrony configuration file",
        notes="Display /etc/chrony.conf — common first step before editing.",
    ),
    Scenario(
        id="chrony-conf_view-0002",
        tool="chrony",
        operation="conf_view",
        permission_class=_pc("conf_view"),
        complexity="single",
        user_input="what NTP pool servers are configured in chrony.conf?",
        notes="Read conf to find pool/server lines.",
    ),
    Scenario(
        id="chrony-conf_view-0003",
        tool="chrony",
        operation="conf_view",
        permission_class=_pc("conf_view"),
        complexity="diagnostic",
        user_input="chrony is not syncing — show me the config to check the server list",
        notes="Diagnostic: inspect conf for misconfigured or missing server entries.",
    ),
    Scenario(
        id="chrony-conf_view-0004",
        tool="chrony",
        operation="conf_view",
        permission_class=_pc("conf_view"),
        complexity="multi",
        user_input="read the chrony config and then tell me if makestep is enabled",
        notes="Multi-step: read conf and check for makestep directive.",
    ),
    Scenario(
        id="chrony-conf_view-0005",
        tool="chrony",
        operation="conf_view",
        permission_class=_pc("conf_view"),
        complexity="single",
        user_input="display /etc/chrony.conf",
        notes="Direct file display request.",
    ),
    Scenario(
        id="chrony-conf_view-0006",
        tool="chrony",
        operation="conf_view",
        permission_class=_pc("conf_view"),
        complexity="diagnostic",
        user_input="the NTP pool address changed — show the current chrony.conf before we update it",
        notes="Diagnostic pre-check before editing: read current conf to see the old pool entry.",
    ),

    # =========================================================================
    # conf_edit  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="chrony-conf_edit-0001",
        tool="chrony",
        operation="conf_edit",
        permission_class=_pc("conf_edit"),
        complexity="single",
        user_input="update chrony.conf to point at our internal NTP server at 10.0.0.1",
        notes="WRITE: replace pool lines with an internal server directive.",
    ),
    Scenario(
        id="chrony-conf_edit-0002",
        tool="chrony",
        operation="conf_edit",
        permission_class=_pc("conf_edit"),
        complexity="single",
        user_input="add iburst to the NTP server line in chrony.conf",
        notes="WRITE: edit conf to add iburst for faster initial sync.",
    ),
    Scenario(
        id="chrony-conf_edit-0003",
        tool="chrony",
        operation="conf_edit",
        permission_class=_pc("conf_edit"),
        complexity="multi",
        user_input="view the current chrony config and then replace the public pool with our private NTP server",
        notes="Multi-step: read conf then write updated version with private server.",
    ),
    Scenario(
        id="chrony-conf_edit-0004",
        tool="chrony",
        operation="conf_edit",
        permission_class=_pc("conf_edit"),
        complexity="single",
        user_input="configure chrony to allow the local subnet to query NTP",
        notes="WRITE: add an allow directive to chrony.conf for local subnet access.",
    ),
    Scenario(
        id="chrony-conf_edit-0005",
        tool="chrony",
        operation="conf_edit",
        permission_class=_pc("conf_edit"),
        complexity="diagnostic",
        user_input="the host drifts overnight — set a tighter makestep threshold in chrony.conf",
        notes="Diagnostic-triggered WRITE: tighten makestep to correct large overnight drift.",
    ),
    Scenario(
        id="chrony-conf_edit-0006",
        tool="chrony",
        operation="conf_edit",
        permission_class=_pc("conf_edit"),
        complexity="single",
        user_input="enable NTS (Network Time Security) in chrony.conf for the upstream server",
        notes="WRITE: add nts keyword to the server line for authenticated NTP.",
    ),
    Scenario(
        id="chrony-conf_edit-0007",
        tool="chrony",
        operation="conf_edit",
        permission_class=_pc("conf_edit"),
        complexity="multi",
        user_input="set chrony to use the datacenter NTP server and then restart chronyd to apply the change",
        notes="Multi-step: write conf then restart chronyd service to activate new config.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("chrony").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "chrony", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("chrony").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
