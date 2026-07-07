"""finetune/scenarios/nginx.py — Scenario corpus for the 'nginx' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  configtest  READ   — validate nginx config with 'nginx -t'
  status      READ   — show current status of nginx.service
  start       WRITE  — start nginx.service
  stop        WRITE  — stop nginx.service
  restart     WRITE  — restart nginx.service
  reload      WRITE  — reload nginx config without dropping connections

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
    """Return the live permission class for an nginx operation."""
    return registry.get("nginx").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # configtest  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="nginx-configtest-0001",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="single",
        user_input="check if the nginx config is valid",
        notes="Basic syntax validation using 'nginx -t'.",
    ),
    Scenario(
        id="nginx-configtest-0002",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="single",
        user_input="test the nginx configuration before reloading",
        notes="Pre-reload config validation — safe READ op.",
    ),
    Scenario(
        id="nginx-configtest-0003",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="single",
        user_input="validate /etc/nginx/nginx.conf for syntax errors",
        notes="Explicit path configtest.",
    ),
    Scenario(
        id="nginx-configtest-0004",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="diagnostic",
        user_input="nginx failed to reload — run a config test so I can see what's wrong",
        notes="Diagnostic: configtest as the first step when reload fails.",
    ),
    Scenario(
        id="nginx-configtest-0005",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="multi",
        user_input="test the nginx config and if it passes then reload the service",
        notes="Multi-step: configtest gates the reload decision.",
    ),
    Scenario(
        id="nginx-configtest-0006",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="single",
        user_input="does the current nginx.conf have any errors?",
        notes="Natural-language configtest query.",
    ),
    Scenario(
        id="nginx-configtest-0007",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="diagnostic",
        user_input="I just edited the server block — verify the config is still valid",
        notes="Diagnostic: post-edit config check.",
    ),
    Scenario(
        id="nginx-configtest-0008",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="single",
        user_input="run nginx -t to check configuration syntax",
        notes="Explicit nginx -t command phrasing.",
    ),
    Scenario(
        id="nginx-configtest-0009",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="multi",
        user_input="verify the new site config at /etc/nginx/conf.d/app.conf before restarting nginx",
        notes="Multi-step: validate a specific include file before restart.",
    ),
    Scenario(
        id="nginx-configtest-0010",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("configtest"),
        complexity="diagnostic",
        user_input="nginx won't start — test the config to find the syntax error",
        notes="Diagnostic: configtest as triage step for a failed start.",
    ),

    # =========================================================================
    # status  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="nginx-status-0001",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is nginx running?",
        notes="Simple health check.",
    ),
    Scenario(
        id="nginx-status-0002",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show me the current status of nginx",
        notes="Status query — READ op, no confirmation required.",
    ),
    Scenario(
        id="nginx-status-0003",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="what is the state of the nginx service?",
        notes="Natural-language status query.",
    ),
    Scenario(
        id="nginx-status-0004",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="the website is returning 502 errors — check nginx status",
        notes="Diagnostic: status as first triage step for upstream errors.",
    ),
    Scenario(
        id="nginx-status-0005",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check nginx status and tell me if there are any worker processes running",
        notes="Multi-step: status then interpret worker process count.",
    ),
    Scenario(
        id="nginx-status-0006",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show nginx.service systemd status",
        notes="Explicit systemd unit status phrasing.",
    ),
    Scenario(
        id="nginx-status-0007",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="nginx crashed overnight — what does the service status show?",
        notes="Diagnostic: post-crash status check.",
    ),
    Scenario(
        id="nginx-status-0008",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is the web server up?",
        notes="Abbreviated web server status check.",
    ),
    Scenario(
        id="nginx-status-0009",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="after the upgrade, check if nginx is still active and healthy",
        notes="Diagnostic: post-upgrade health verification.",
    ),
    Scenario(
        id="nginx-status-0010",
        tool="nginx",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check nginx status and then show me the last 50 log lines if it is in a failed state",
        notes="Multi-step: status gates the log retrieval decision.",
    ),

    # =========================================================================
    # start  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="nginx-start-0001",
        tool="nginx",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start nginx",
        notes="WRITE: simple start of the nginx web server.",
    ),
    Scenario(
        id="nginx-start-0002",
        tool="nginx",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="bring nginx up — the site is currently down",
        notes="WRITE: start nginx to restore web service.",
    ),
    Scenario(
        id="nginx-start-0003",
        tool="nginx",
        operation="start",
        permission_class=_pc("start"),
        complexity="multi",
        user_input="start nginx and then check its status to confirm it came up",
        notes="Multi-step: start then status verification.",
    ),
    Scenario(
        id="nginx-start-0004",
        tool="nginx",
        operation="start",
        permission_class=_pc("start"),
        complexity="diagnostic",
        user_input="the web server is down — test the config first, and if it passes start nginx",
        notes="Diagnostic-triggered WRITE: configtest gates the start decision.",
    ),
    Scenario(
        id="nginx-start-0005",
        tool="nginx",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="launch the nginx service",
        notes="WRITE: start nginx, alternate phrasing.",
    ),
    Scenario(
        id="nginx-start-0006",
        tool="nginx",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="start the web server after the maintenance window",
        notes="WRITE: post-maintenance start.",
    ),
    Scenario(
        id="nginx-start-0007",
        tool="nginx",
        operation="start",
        permission_class=_pc("start"),
        complexity="multi",
        user_input="start nginx if it is not already running",
        notes="Multi-step: status check then conditional start.",
    ),
    Scenario(
        id="nginx-start-0008",
        tool="nginx",
        operation="start",
        permission_class=_pc("start"),
        complexity="single",
        user_input="turn nginx on",
        notes="WRITE: casual phrasing for starting the web server.",
    ),

    # =========================================================================
    # stop  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="nginx-stop-0001",
        tool="nginx",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="stop nginx",
        notes="WRITE: simple stop of the web server.",
    ),
    Scenario(
        id="nginx-stop-0002",
        tool="nginx",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="bring nginx down for maintenance",
        notes="WRITE: stop nginx for a scheduled maintenance window.",
    ),
    Scenario(
        id="nginx-stop-0003",
        tool="nginx",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="multi",
        user_input="stop nginx and confirm it has exited",
        notes="Multi-step: stop then status verification.",
    ),
    Scenario(
        id="nginx-stop-0004",
        tool="nginx",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="diagnostic",
        user_input="nginx is pegging the CPU — stop it immediately",
        notes="Diagnostic-triggered WRITE: emergency stop of a runaway nginx process.",
    ),
    Scenario(
        id="nginx-stop-0005",
        tool="nginx",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="shut down the web server",
        notes="WRITE: stop nginx, alternate phrasing.",
    ),
    Scenario(
        id="nginx-stop-0006",
        tool="nginx",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="take nginx offline before the SSL certificate rotation",
        notes="WRITE: stop nginx as part of a cert rotation procedure.",
    ),
    Scenario(
        id="nginx-stop-0007",
        tool="nginx",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="multi",
        user_input="stop nginx and then verify no worker processes remain",
        notes="Multi-step: stop then process check.",
    ),

    # =========================================================================
    # restart  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="nginx-restart-0001",
        tool="nginx",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="restart nginx",
        notes="WRITE: full restart of the nginx service.",
    ),
    Scenario(
        id="nginx-restart-0002",
        tool="nginx",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="bounce nginx to pick up the new SSL certificates",
        notes="WRITE: restart nginx after a certificate update.",
    ),
    Scenario(
        id="nginx-restart-0003",
        tool="nginx",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="multi",
        user_input="restart nginx and check its status to confirm it came back up cleanly",
        notes="Multi-step: restart then status verification.",
    ),
    Scenario(
        id="nginx-restart-0004",
        tool="nginx",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="diagnostic",
        user_input="nginx is behaving strangely — restart it to clear the issue",
        notes="Diagnostic-triggered WRITE: restart as a remediation step.",
    ),
    Scenario(
        id="nginx-restart-0005",
        tool="nginx",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="single",
        user_input="restart the web server after the config change",
        notes="WRITE: post-config-change restart.",
    ),
    Scenario(
        id="nginx-restart-0006",
        tool="nginx",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="multi",
        user_input="test the nginx config and if it is valid restart the service",
        notes="Multi-step: configtest then conditional restart.",
    ),
    Scenario(
        id="nginx-restart-0007",
        tool="nginx",
        operation="restart",
        permission_class=_pc("restart"),
        complexity="diagnostic",
        user_input="after patching the nginx package, restart the service and verify it is running",
        notes="Diagnostic: post-patch restart with verification.",
    ),

    # =========================================================================
    # reload  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="nginx-reload-0001",
        tool="nginx",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="single",
        user_input="reload nginx to apply the new virtual host config",
        notes="WRITE: graceful reload — no connection drop, picks up new config.",
    ),
    Scenario(
        id="nginx-reload-0002",
        tool="nginx",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="single",
        user_input="apply the nginx config changes without restarting",
        notes="WRITE: reload preferred over restart to avoid connection drops.",
    ),
    Scenario(
        id="nginx-reload-0003",
        tool="nginx",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="multi",
        user_input="test the nginx config first, then reload it gracefully",
        notes="Multi-step: configtest gates the reload to prevent broken reload.",
    ),
    Scenario(
        id="nginx-reload-0004",
        tool="nginx",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="single",
        user_input="send a SIGHUP to nginx to reload the config",
        notes="WRITE: operator knows the underlying signal; reload op covers it.",
    ),
    Scenario(
        id="nginx-reload-0005",
        tool="nginx",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="diagnostic",
        user_input="I updated the upstream block — reload nginx without dropping active connections",
        notes="Diagnostic-triggered WRITE: reload to apply upstream changes gracefully.",
    ),
    Scenario(
        id="nginx-reload-0006",
        tool="nginx",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="single",
        user_input="reload the nginx configuration",
        notes="WRITE: straightforward reload request.",
    ),
    Scenario(
        id="nginx-reload-0007",
        tool="nginx",
        operation="reload",
        permission_class=_pc("reload"),
        complexity="multi",
        user_input="reload nginx after updating the rate-limiting rules and verify the service is still running",
        notes="Multi-step: reload then status check to confirm service stability.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("nginx").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "nginx", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("nginx").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
