"""finetune/scenarios/services.py — Scenario corpus for the 'services' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  status  READ   — show current status of a systemd unit
  start   WRITE  — start a unit
  stop    WRITE  — stop a unit
  restart WRITE  — restart a unit
  enable  WRITE  — enable a unit at boot
  disable WRITE  — disable a unit from starting at boot
  logs    READ   — tail recent journal entries for a unit
  mask    WRITE  — mask a unit so it cannot start

Coverage targets
----------------
  >= 60 entries total across all 8 operations.
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
# Compatible field names are EXACT so the P1 JOIN can unify without renames.
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
    """Return the live permission class for a services operation."""
    return registry.get("services").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # status  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="services-status-0001",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is nginx running?",
        notes="Simple health check on nginx.service.",
    ),
    Scenario(
        id="services-status-0002",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show me the status of sshd",
        notes="SSH daemon status check — common admin task.",
    ),
    Scenario(
        id="services-status-0003",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="what is the current state of postgresql.service?",
        notes="Database service status.",
    ),
    Scenario(
        id="services-status-0004",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="check whether firewalld is active",
        notes="Firewall service status check.",
    ),
    Scenario(
        id="services-status-0005",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is the cron service running on this host?",
        notes="Cron daemon health check.",
    ),
    Scenario(
        id="services-status-0006",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check the status of httpd and then tell me if it has any failed dependencies",
        notes="Multi-step: status then interpret output for dependency failures.",
    ),
    Scenario(
        id="services-status-0007",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="httpd is returning 503 errors — what does its service status say?",
        notes="Diagnostic: correlate application-level error with unit state.",
    ),
    Scenario(
        id="services-status-0008",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="my redis server seems unresponsive, check if the service is up",
        notes="Diagnostic entry point for a suspected service outage.",
    ),
    Scenario(
        id="services-status-0009",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show status for docker.service",
        notes="Container runtime service status.",
    ),
    Scenario(
        id="services-status-0010",
        tool="services",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="the application team says the API is down — start by checking the status of the api-gateway service",
        notes="Incident triage: status is the first diagnostic step.",
    ),

    # =========================================================================
    # logs  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="services-logs-0001",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="single",
        user_input="show me the last 50 log lines for nginx",
        notes="Default log tail for nginx.",
    ),
    Scenario(
        id="services-logs-0002",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="single",
        user_input="get the recent journal entries for sshd",
        notes="SSH daemon log retrieval.",
    ),
    Scenario(
        id="services-logs-0003",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="single",
        user_input="show me the last 100 lines from the postgresql service log",
        notes="Database service log — increased line count.",
    ),
    Scenario(
        id="services-logs-0004",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="diagnostic",
        user_input="httpd failed to start — pull its recent logs so I can see the error",
        notes="Diagnostic: fetch logs after a failed start to identify the cause.",
    ),
    Scenario(
        id="services-logs-0005",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="multi",
        user_input="show the last 200 log lines for docker.service and flag any error lines",
        notes="Multi-step: retrieve logs and analyse for errors.",
    ),
    Scenario(
        id="services-logs-0006",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="single",
        user_input="tail the firewalld logs",
        notes="Firewall service log tail.",
    ),
    Scenario(
        id="services-logs-0007",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="diagnostic",
        user_input="redis keeps crashing overnight — pull the last 500 log lines so we can find out why",
        notes="Diagnostic: large log pull for intermittent crash analysis.",
    ),
    Scenario(
        id="services-logs-0008",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="single",
        user_input="what did crond log in the last 50 entries?",
        notes="Scheduled task daemon log check.",
    ),
    Scenario(
        id="services-logs-0009",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="diagnostic",
        user_input="the backup job failed last night — show me the logs for backup-agent.service",
        notes="Diagnostic: post-failure log review for a backup service.",
    ),
    Scenario(
        id="services-logs-0010",
        tool="services",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="multi",
        user_input="pull the last 100 lines of auditd logs and tell me if there are any denied operations",
        notes="Multi-step: fetch audit daemon logs and interpret denial lines.",
    ),

    # =========================================================================
    # start  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="services-start-0001",
        tool="services",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start nginx",
        notes="Simple WRITE: start the nginx web server.",
    ),
    Scenario(
        id="services-start-0002",
        tool="services",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="bring up the postgresql service",
        notes="WRITE: start the database service.",
    ),
    Scenario(
        id="services-start-0003",
        tool="services",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start docker.service so I can run containers",
        notes="WRITE: start container runtime.",
    ),
    Scenario(
        id="services-start-0004",
        tool="services",
        operation="start",
        permission_class=_pc("start"),
        complexity="multi",
        user_input="start httpd and then check if it came up successfully",
        notes="Multi-step: start then status verification.",
    ),
    Scenario(
        id="services-start-0005",
        tool="services",
        operation="start",
        permission_class=_pc("start"),
        complexity="diagnostic",
        user_input="the API is unreachable — start the api-gateway.service if it is stopped",
        notes="Diagnostic-triggered WRITE: conditional start based on prior status check.",
    ),
    Scenario(
        id="services-start-0006",
        tool="services",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start the rsyslog service",
        notes="WRITE: start the system logging daemon.",
    ),
    Scenario(
        id="services-start-0007",
        tool="services",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="bring up chronyd so the clock syncs",
        notes="WRITE: start the NTP synchronisation daemon.",
    ),
    Scenario(
        id="services-start-0008",
        tool="services",
        operation="start",
        permission_class=_pc("start"),
        complexity="multi",
        user_input="start redis.service and verify it is listening on port 6379",
        notes="Multi-step: start then connectivity check.",
    ),
    Scenario(
        id="services-start-0009",
        tool="services",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start the auditd service",
        notes="WRITE: start the kernel audit daemon — security hardening context.",
    ),

    # =========================================================================
    # stop  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="services-stop-0001",
        tool="services",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="stop nginx",
        notes="WRITE: stop the web server.",
    ),
    Scenario(
        id="services-stop-0002",
        tool="services",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="shut down the postgresql service for maintenance",
        notes="WRITE: stop database service for scheduled maintenance window.",
    ),
    Scenario(
        id="services-stop-0003",
        tool="services",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="stop the docker daemon",
        notes="WRITE: stop container runtime.",
    ),
    Scenario(
        id="services-stop-0004",
        tool="services",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="multi",
        user_input="stop httpd and confirm it has exited cleanly",
        notes="Multi-step: stop then verify the unit is no longer active.",
    ),
    Scenario(
        id="services-stop-0005",
        tool="services",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="diagnostic",
        user_input="httpd is eating 100% CPU — stop it immediately",
        notes="Diagnostic-triggered WRITE: emergency stop of a runaway process via the service unit.",
    ),
    Scenario(
        id="services-stop-0006",
        tool="services",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="stop the redis cache service",
        notes="WRITE: stop the in-memory cache.",
    ),
    Scenario(
        id="services-stop-0007",
        tool="services",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="take the backup-agent.service offline",
        notes="WRITE: stop a custom backup agent service.",
    ),
    Scenario(
        id="services-stop-0008",
        tool="services",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="multi",
        user_input="stop the rsyslog service and then show its final status",
        notes="Multi-step: stop and confirm state post-stop.",
    ),

    # =========================================================================
    # restart  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="services-restart-0001",
        tool="services",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="restart nginx to pick up the new config",
        notes="WRITE: reload config via restart after an nginx.conf change.",
    ),
    Scenario(
        id="services-restart-0002",
        tool="services",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="bounce the sshd service",
        notes="WRITE: restart SSH daemon — common hardening step after config change.",
    ),
    Scenario(
        id="services-restart-0003",
        tool="services",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="restart postgresql to apply the new pg_hba.conf",
        notes="WRITE: restart database service after auth config change.",
    ),
    Scenario(
        id="services-restart-0004",
        tool="services",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="multi",
        user_input="restart httpd and check its status afterwards to make sure it came back up",
        notes="Multi-step: restart followed by status verification.",
    ),
    Scenario(
        id="services-restart-0005",
        tool="services",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="diagnostic",
        user_input="redis is returning stale data — restart it to flush the state",
        notes="Diagnostic-triggered WRITE: restart as a remediation step.",
    ),
    Scenario(
        id="services-restart-0006",
        tool="services",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="restart the firewalld daemon",
        notes="WRITE: restart firewall after a rule change.",
    ),
    Scenario(
        id="services-restart-0007",
        tool="services",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="restart rsyslog",
        notes="WRITE: restart system log daemon after config update.",
    ),
    Scenario(
        id="services-restart-0008",
        tool="services",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="multi",
        user_input="restart the api-gateway service and then pull the last 50 log lines to confirm it started cleanly",
        notes="Multi-step: restart then log review.",
    ),

    # =========================================================================
    # enable  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="services-enable-0001",
        tool="services",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable nginx so it starts automatically on boot",
        notes="WRITE: enable nginx at boot — post-install hardening step.",
    ),
    Scenario(
        id="services-enable-0002",
        tool="services",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="make sure sshd starts on boot",
        notes="WRITE: enable SSH daemon — essential for remote management.",
    ),
    Scenario(
        id="services-enable-0003",
        tool="services",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable postgresql.service at boot",
        notes="WRITE: ensure database service starts after a reboot.",
    ),
    Scenario(
        id="services-enable-0004",
        tool="services",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="set firewalld to start automatically",
        notes="WRITE: enable firewall — security hardening.",
    ),
    Scenario(
        id="services-enable-0005",
        tool="services",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="multi",
        user_input="enable auditd at boot and then start it now",
        notes="Multi-step: enable at boot then immediately start — security hardening.",
    ),
    Scenario(
        id="services-enable-0006",
        tool="services",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable chronyd so the clock stays in sync across reboots",
        notes="WRITE: enable NTP daemon at boot.",
    ),
    Scenario(
        id="services-enable-0007",
        tool="services",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="single",
        user_input="enable the fail2ban service at boot",
        notes="WRITE: enable intrusion prevention service — security hardening.",
    ),
    Scenario(
        id="services-enable-0008",
        tool="services",
        operation="enable",
        permission_class=_pc("enable"),
        complexity="multi",
        user_input="enable docker.service and confirm the symlink was created",
        notes="Multi-step: enable then verify via status.",
    ),

    # =========================================================================
    # disable  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="services-disable-0001",
        tool="services",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable cups so it does not start on boot",
        notes="WRITE: disable print spooler — attack surface reduction.",
    ),
    Scenario(
        id="services-disable-0002",
        tool="services",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable avahi-daemon at boot",
        notes="WRITE: disable mDNS service not needed on servers — hardening.",
    ),
    Scenario(
        id="services-disable-0003",
        tool="services",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="prevent bluetooth from starting automatically",
        notes="WRITE: disable Bluetooth on a headless server.",
    ),
    Scenario(
        id="services-disable-0004",
        tool="services",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable the rpcbind service so it does not boot with the system",
        notes="WRITE: disable RPC portmapper — hardening for non-NFS servers.",
    ),
    Scenario(
        id="services-disable-0005",
        tool="services",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="multi",
        user_input="disable the telnet service and verify it is no longer enabled",
        notes="Multi-step: disable then confirm — security hardening.",
    ),
    Scenario(
        id="services-disable-0006",
        tool="services",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable docker.service on this host — containers are handled by another node",
        notes="WRITE: disable container runtime on a non-container host.",
    ),
    Scenario(
        id="services-disable-0007",
        tool="services",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="diagnostic",
        user_input="the server is slow to boot — which services are enabled? disable postfix if this is not a mail server",
        notes="Diagnostic: identify unnecessary boot services, then disable.",
    ),
    Scenario(
        id="services-disable-0008",
        tool="services",
        operation="disable",
        permission_class=_pc("disable"),
        complexity="single",
        user_input="disable snapd.service",
        notes="WRITE: disable snap daemon on a Rocky Linux host where it is unwanted.",
    ),

    # =========================================================================
    # mask  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="services-mask-0001",
        tool="services",
        operation="mask",
        permission_class=_pc("mask"),
        complexity="single",
        user_input="mask the cups service so it can never start",
        notes="WRITE: hard-block print spooler — stronger than disable.",
    ),
    Scenario(
        id="services-mask-0002",
        tool="services",
        operation="mask",
        permission_class=_pc("mask"),
        complexity="single",
        user_input="mask avahi-daemon — we never want mDNS on this server",
        notes="WRITE: mask mDNS service — security hardening.",
    ),
    Scenario(
        id="services-mask-0003",
        tool="services",
        operation="mask",
        permission_class=_pc("mask"),
        complexity="single",
        user_input="permanently prevent rpcbind from starting on this host",
        notes="WRITE: mask RPC portmapper — hardening for NFS-free hosts.",
    ),
    Scenario(
        id="services-mask-0004",
        tool="services",
        operation="mask",
        permission_class=_pc("mask"),
        complexity="single",
        user_input="mask the bluetooth service",
        notes="WRITE: mask Bluetooth on a headless rack server.",
    ),
    Scenario(
        id="services-mask-0005",
        tool="services",
        operation="mask",
        permission_class=_pc("mask"),
        complexity="multi",
        user_input="mask telnet.socket and confirm it cannot be started",
        notes="Multi-step: mask then verify via status.",
    ),
    Scenario(
        id="services-mask-0006",
        tool="services",
        operation="mask",
        permission_class=_pc("mask"),
        complexity="diagnostic",
        user_input="the security scan flagged rsh.service as enabled — mask it now",
        notes="Diagnostic-triggered WRITE: mask insecure legacy service found in audit.",
    ),
    Scenario(
        id="services-mask-0007",
        tool="services",
        operation="mask",
        permission_class=_pc("mask"),
        complexity="single",
        user_input="mask ctrl-alt-del.target so someone cannot accidentally reboot the server",
        notes="WRITE: mask the emergency reboot target — common hardening step.",
    ),
    Scenario(
        id="services-mask-0008",
        tool="services",
        operation="mask",
        permission_class=_pc("mask"),
        complexity="single",
        user_input="mask nfs-server.service on this host that does not serve NFS",
        notes="WRITE: mask NFS server on a non-NFS host — attack surface reduction.",
    ),
    Scenario(
        id="services-mask-0009",
        tool="services",
        operation="mask",
        permission_class=_pc("mask"),
        complexity="multi",
        user_input="mask the debug-shell.service and then check the status to confirm",
        notes="Multi-step: mask emergency debug shell then verify — security hardening.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("services").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "services", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("services").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 60, f"Need >= 60 scenarios, got {len(SCENARIOS)}"
