"""finetune/scenarios/httpd.py — Scenario corpus for the 'httpd' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  status      READ   — show httpd service status via apachectl status
  configtest  READ   — validate Apache configuration syntax
  start       WRITE  — start the httpd service via systemctl
  stop        WRITE  — stop the httpd service via systemctl
  restart     WRITE  — restart the httpd service via systemctl
  vhost_list  READ   — list configured virtual hosts via apachectl -S
  mod_status  READ   — fetch live server metrics from mod_status

Coverage targets
----------------
  >= 40 entries total across all 7 operations.
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
    """Return the live permission class for an httpd operation."""
    return registry.get("httpd").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # status  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="httpd-status-0001",
        tool="httpd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is Apache running?",
        notes="Simple health check on the httpd service.",
    ),
    Scenario(
        id="httpd-status-0002",
        tool="httpd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show me the status of the web server",
        notes="Generic status request for the httpd web server.",
    ),
    Scenario(
        id="httpd-status-0003",
        tool="httpd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="check if httpd is active on this host",
        notes="Direct status check on the httpd service unit.",
    ),
    Scenario(
        id="httpd-status-0004",
        tool="httpd",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="the website is returning 502 errors — what does the Apache status say?",
        notes="Diagnostic: check service state in response to a reported HTTP error.",
    ),
    Scenario(
        id="httpd-status-0005",
        tool="httpd",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="Apache seems unresponsive — quickly check its service status",
        notes="Diagnostic entry point for a suspected httpd outage.",
    ),
    Scenario(
        id="httpd-status-0006",
        tool="httpd",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check Apache status and tell me how long it has been running",
        notes="Multi-step: status check then parse uptime from output.",
    ),
    Scenario(
        id="httpd-status-0007",
        tool="httpd",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="what is the current state of the Apache HTTP Server?",
        notes="Explicit status request using the full Apache service name.",
    ),
    Scenario(
        id="httpd-status-0008",
        tool="httpd",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="we deployed a new SSL certificate — confirm the web server came back up after the config reload",
        notes="Post-deployment verification: confirm httpd is active after a cert change.",
    ),

    # =========================================================================
    # configtest  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="httpd-configtest-0001",
        tool="httpd",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="single",
        user_input="test the Apache config for syntax errors",
        notes="Standard pre-restart config validation.",
    ),
    Scenario(
        id="httpd-configtest-0002",
        tool="httpd",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="single",
        user_input="validate the httpd configuration before I restart it",
        notes="Config check before a WRITE op — common safe workflow.",
    ),
    Scenario(
        id="httpd-configtest-0003",
        tool="httpd",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="diagnostic",
        user_input="Apache failed to start — is there a syntax error in the config?",
        notes="Diagnostic: run configtest to identify why httpd will not start.",
    ),
    Scenario(
        id="httpd-configtest-0004",
        tool="httpd",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="multi",
        user_input="check the Apache config syntax and if it passes restart the server",
        notes="Multi-step: configtest gates the restart decision.",
    ),
    Scenario(
        id="httpd-configtest-0005",
        tool="httpd",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="single",
        user_input="run apachectl configtest and show me the output",
        notes="Direct configtest invocation.",
    ),
    Scenario(
        id="httpd-configtest-0006",
        tool="httpd",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="diagnostic",
        user_input="I edited a VirtualHost block and now Apache won't reload — check for config errors",
        notes="Diagnostic: configtest to find a bad VirtualHost directive.",
    ),
    Scenario(
        id="httpd-configtest-0007",
        tool="httpd",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="single",
        user_input="does the Apache configuration have any problems?",
        notes="General config health check.",
    ),
    Scenario(
        id="httpd-configtest-0008",
        tool="httpd",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="multi",
        user_input="verify the new SSL configuration is valid and then reload Apache",
        notes="Multi-step: validate SSL config then apply via restart.",
    ),

    # =========================================================================
    # start  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="httpd-start-0001",
        tool="httpd",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start Apache",
        notes="Simple WRITE: start the Apache web server.",
    ),
    Scenario(
        id="httpd-start-0002",
        tool="httpd",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="bring the httpd service up",
        notes="WRITE: bring httpd into the running state.",
    ),
    Scenario(
        id="httpd-start-0003",
        tool="httpd",
        operation="start",
        permission_class=_pc("start"),
        complexity="multi",
        user_input="start the web server and confirm it came up correctly",
        notes="Multi-step: start then status verification.",
    ),
    Scenario(
        id="httpd-start-0004",
        tool="httpd",
        operation="start",
        permission_class=_pc("start"),
        complexity="diagnostic",
        user_input="the website is down — start httpd if it is stopped",
        notes="Diagnostic-triggered WRITE: conditional start after status check.",
    ),
    Scenario(
        id="httpd-start-0005",
        tool="httpd",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start the Apache HTTP Server after the maintenance window",
        notes="WRITE: start httpd following a planned maintenance period.",
    ),
    Scenario(
        id="httpd-start-0006",
        tool="httpd",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start httpd so users can reach the application",
        notes="WRITE: start web server to restore user access.",
    ),
    Scenario(
        id="httpd-start-0007",
        tool="httpd",
        operation="start",
        permission_class=_pc("start"),
        complexity="multi",
        user_input="verify the Apache config is clean, then start the service",
        notes="Multi-step: configtest gate then start.",
    ),

    # =========================================================================
    # stop  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="httpd-stop-0001",
        tool="httpd",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="stop Apache",
        notes="WRITE: stop the httpd web server.",
    ),
    Scenario(
        id="httpd-stop-0002",
        tool="httpd",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="shut down httpd for the maintenance window",
        notes="WRITE: stop httpd for scheduled maintenance.",
    ),
    Scenario(
        id="httpd-stop-0003",
        tool="httpd",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="multi",
        user_input="stop the web server and verify it is no longer running",
        notes="Multi-step: stop then status confirmation.",
    ),
    Scenario(
        id="httpd-stop-0004",
        tool="httpd",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="diagnostic",
        user_input="Apache is consuming 100% CPU — stop it immediately",
        notes="Diagnostic-triggered WRITE: emergency stop of a runaway httpd process.",
    ),
    Scenario(
        id="httpd-stop-0005",
        tool="httpd",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="take the web server offline while I replace the TLS certificate",
        notes="WRITE: stop httpd during a certificate rotation.",
    ),
    Scenario(
        id="httpd-stop-0006",
        tool="httpd",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="stop the Apache service on this host — we are decommissioning it",
        notes="WRITE: stop httpd as part of a decommission workflow.",
    ),
    Scenario(
        id="httpd-stop-0007",
        tool="httpd",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="multi",
        user_input="stop httpd and then check the error log for the last entries",
        notes="Multi-step: stop then review final log lines.",
    ),

    # =========================================================================
    # restart  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="httpd-restart-0001",
        tool="httpd",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="restart Apache to apply the new configuration",
        notes="WRITE: reload updated httpd.conf via service restart.",
    ),
    Scenario(
        id="httpd-restart-0002",
        tool="httpd",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="bounce the web server after the SSL cert change",
        notes="WRITE: restart httpd after a certificate rotation.",
    ),
    Scenario(
        id="httpd-restart-0003",
        tool="httpd",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="multi",
        user_input="restart httpd and check the status afterwards to confirm it came back up",
        notes="Multi-step: restart followed by status verification.",
    ),
    Scenario(
        id="httpd-restart-0004",
        tool="httpd",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="diagnostic",
        user_input="Apache is leaking memory — restart it to clear the worker processes",
        notes="Diagnostic-triggered WRITE: restart as remediation for a memory leak.",
    ),
    Scenario(
        id="httpd-restart-0005",
        tool="httpd",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="restart the Apache HTTP Server to pick up the new VirtualHost config",
        notes="WRITE: restart httpd after a VirtualHost configuration change.",
    ),
    Scenario(
        id="httpd-restart-0006",
        tool="httpd",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="multi",
        user_input="test the config syntax and then restart Apache if there are no errors",
        notes="Multi-step: configtest gate then restart.",
    ),
    Scenario(
        id="httpd-restart-0007",
        tool="httpd",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="restart httpd after enabling the mod_rewrite module",
        notes="WRITE: restart to activate a newly enabled Apache module.",
    ),

    # =========================================================================
    # vhost_list  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="httpd-vhost_list-0001",
        tool="httpd",
        operation="vhost_list",
        permission_class=_pc("vhost_list"),
        complexity="single",
        user_input="list all the virtual hosts configured in Apache",
        notes="Enumerate active VirtualHost blocks via apachectl -S.",
    ),
    Scenario(
        id="httpd-vhost_list-0002",
        tool="httpd",
        operation="vhost_list",
        permission_class=_pc("vhost_list"),
        complexity="single",
        user_input="show me what VirtualHosts Apache is serving",
        notes="Display configured virtual hosts and their port bindings.",
    ),
    Scenario(
        id="httpd-vhost_list-0003",
        tool="httpd",
        operation="vhost_list",
        permission_class=_pc("vhost_list"),
        complexity="diagnostic",
        user_input="a new VirtualHost isn't being hit — list all configured vhosts to verify it was picked up",
        notes="Diagnostic: verify a VirtualHost definition appears in the live config.",
    ),
    Scenario(
        id="httpd-vhost_list-0004",
        tool="httpd",
        operation="vhost_list",
        permission_class=_pc("vhost_list"),
        complexity="single",
        user_input="what ports is Apache listening on?",
        notes="Check port bindings from virtual host listing output.",
    ),
    Scenario(
        id="httpd-vhost_list-0005",
        tool="httpd",
        operation="vhost_list",
        permission_class=_pc("vhost_list"),
        complexity="multi",
        user_input="list the virtual hosts and find which config file defines api.example.com",
        notes="Multi-step: list vhosts then identify the config source file for a specific domain.",
    ),
    Scenario(
        id="httpd-vhost_list-0006",
        tool="httpd",
        operation="vhost_list",
        permission_class=_pc("vhost_list"),
        complexity="diagnostic",
        user_input="check which VirtualHost is the default server on port 80",
        notes="Diagnostic: find the default VirtualHost by examining the -S output.",
    ),
    Scenario(
        id="httpd-vhost_list-0007",
        tool="httpd",
        operation="vhost_list",
        permission_class=_pc("vhost_list"),
        complexity="single",
        user_input="run apachectl -S and show me the virtual host summary",
        notes="Direct invocation of apachectl -S for a virtual host audit.",
    ),

    # =========================================================================
    # mod_status  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="httpd-mod_status-0001",
        tool="httpd",
        operation="mod_status",
        permission_class=_pc("mod_status"),
        complexity="single",
        user_input="show me Apache server metrics from mod_status",
        notes="Fetch live metrics from the local server-status endpoint.",
    ),
    Scenario(
        id="httpd-mod_status-0002",
        tool="httpd",
        operation="mod_status",
        permission_class=_pc("mod_status"),
        complexity="single",
        user_input="how many requests per second is Apache handling?",
        notes="Retrieve throughput metric from mod_status output.",
    ),
    Scenario(
        id="httpd-mod_status-0003",
        tool="httpd",
        operation="mod_status",
        permission_class=_pc("mod_status"),
        complexity="diagnostic",
        user_input="Apache is slow — check the server status metrics to see if we are hitting the worker limit",
        notes="Diagnostic: inspect BusyWorkers/IdleWorkers from mod_status.",
    ),
    Scenario(
        id="httpd-mod_status-0004",
        tool="httpd",
        operation="mod_status",
        permission_class=_pc("mod_status"),
        complexity="multi",
        user_input="get the Apache server status and tell me the current CPU load and request rate",
        notes="Multi-step: fetch mod_status then parse CPULoad and ReqPerSec.",
    ),
    Scenario(
        id="httpd-mod_status-0005",
        tool="httpd",
        operation="mod_status",
        permission_class=_pc("mod_status"),
        complexity="single",
        user_input="what is the Apache server uptime?",
        notes="Retrieve ServerUptimeSeconds from the mod_status auto-format output.",
    ),
    Scenario(
        id="httpd-mod_status-0006",
        tool="httpd",
        operation="mod_status",
        permission_class=_pc("mod_status"),
        complexity="diagnostic",
        user_input="traffic spiked — how many worker threads are active right now?",
        notes="Diagnostic: check BusyWorkers metric during a traffic surge.",
    ),
    Scenario(
        id="httpd-mod_status-0007",
        tool="httpd",
        operation="mod_status",
        permission_class=_pc("mod_status"),
        complexity="single",
        user_input="pull the Apache mod_status page for monitoring",
        notes="Standard monitoring pull of the server-status endpoint.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("httpd").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "httpd", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("httpd").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
