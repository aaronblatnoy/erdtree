"""finetune/scenarios/selinux.py — Scenario corpus for the 'selinux' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  sestatus               READ    — show overall enforcement status
  getsebool              READ    — get a boolean value
  getenforce             READ    — get the current enforcement mode
  setenforce             WRITE   — set the enforcement mode
  setsebool              WRITE   — set a boolean, optionally persisting
  semanage_fcontext_list READ    — list file context mappings
  semanage_fcontext_add  WRITE   — add a file context mapping
  semanage_fcontext_delete DESTRUCTIVE — delete a file context mapping
  semanage_port_list     READ    — list port label mappings
  semanage_port_add      WRITE   — add a port label mapping
  semanage_port_delete   DESTRUCTIVE — delete a port label mapping
  semanage_user_list     READ    — list user mappings
  semanage_user_add      WRITE   — add a user mapping
  semanage_user_delete   DESTRUCTIVE — delete a user mapping
  restorecon             WRITE   — restore default file contexts
  chcon                  WRITE   — change the type component of a file context
  audit2allow            READ    — analyze denial log and suggest policy

Coverage targets
----------------
  >= 40 entries across all 17 operations.
  All three complexities represented: single | multi | diagnostic.

INV-schema-sync: permission_class is derived from the LIVE registry.
INV-read-only-core: imports only from finetune.coreimports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass (local — compatible field names for Phase-13 JOIN)
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
    """Return the live permission class for a selinux operation."""
    return registry.get("selinux").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # sestatus  (READ) — 3 entries
    # =========================================================================

    Scenario(
        id="selinux-sestatus-0001",
        tool="selinux",
        operation="sestatus",
        permission_class=_pc("sestatus"),
        complexity="single",
        user_input="show me the current SELinux status",
        notes="Simple read: sestatus output showing mode and policy name.",
    ),
    Scenario(
        id="selinux-sestatus-0002",
        tool="selinux",
        operation="sestatus",
        permission_class=_pc("sestatus"),
        complexity="diagnostic",
        user_input="I'm having permission denied errors on httpd — first tell me if SELinux is enabled and in enforcing mode",
        notes="Diagnostic first step: confirm enforcement before checking AVC denials.",
    ),
    Scenario(
        id="selinux-sestatus-0003",
        tool="selinux",
        operation="sestatus",
        permission_class=_pc("sestatus"),
        complexity="multi",
        user_input="check SELinux status and then list any recent denials",
        notes="Multi-step: status check followed by audit log review.",
    ),

    # =========================================================================
    # getsebool  (READ) — 3 entries
    # =========================================================================

    Scenario(
        id="selinux-getsebool-0001",
        tool="selinux",
        operation="getsebool",
        permission_class=_pc("getsebool"),
        complexity="single",
        user_input="is httpd_can_network_connect enabled?",
        notes="READ: check if httpd is allowed outbound connections.",
    ),
    Scenario(
        id="selinux-getsebool-0002",
        tool="selinux",
        operation="getsebool",
        permission_class=_pc("getsebool"),
        complexity="diagnostic",
        user_input="nginx can't connect to the database — check the httpd_can_network_connect boolean",
        notes="Diagnostic: boolean check as part of connectivity troubleshooting.",
    ),
    Scenario(
        id="selinux-getsebool-0003",
        tool="selinux",
        operation="getsebool",
        permission_class=_pc("getsebool"),
        complexity="single",
        user_input="what is the value of allow_execstack?",
        notes="READ: check a security-sensitive boolean for exec stack permission.",
    ),

    # =========================================================================
    # getenforce  (READ) — 2 entries
    # =========================================================================

    Scenario(
        id="selinux-getenforce-0001",
        tool="selinux",
        operation="getenforce",
        permission_class=_pc("getenforce"),
        complexity="single",
        user_input="is SELinux in enforcing or permissive mode right now?",
        notes="READ: quick enforcement mode check.",
    ),
    Scenario(
        id="selinux-getenforce-0002",
        tool="selinux",
        operation="getenforce",
        permission_class=_pc("getenforce"),
        complexity="diagnostic",
        user_input="before we change any policies, confirm that SELinux is enforcing",
        notes="Diagnostic pre-check before a policy change operation.",
    ),

    # =========================================================================
    # setenforce  (WRITE) — 3 entries
    # =========================================================================

    Scenario(
        id="selinux-setenforce-0001",
        tool="selinux",
        operation="setenforce",
        permission_class=_pc("setenforce"),
        complexity="single",
        user_input="put SELinux into permissive mode so I can test the application",
        notes="WRITE: setenforce 0 — runtime permissive; escalates DESTRUCTIVE via classifier.",
    ),
    Scenario(
        id="selinux-setenforce-0002",
        tool="selinux",
        operation="setenforce",
        permission_class=_pc("setenforce"),
        complexity="single",
        user_input="switch SELinux back to enforcing mode",
        notes="WRITE: setenforce 1 — restore enforcing after testing.",
    ),
    Scenario(
        id="selinux-setenforce-0003",
        tool="selinux",
        operation="setenforce",
        permission_class=_pc("setenforce"),
        complexity="multi",
        user_input="set SELinux to permissive, run the app test, then re-enable enforcing",
        notes="Multi-step: permissive for testing, then restore enforcing.",
    ),

    # =========================================================================
    # setsebool  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="selinux-setsebool-0001",
        tool="selinux",
        operation="setsebool",
        permission_class=_pc("setsebool"),
        complexity="single",
        user_input="enable httpd_can_network_connect for this session",
        notes="WRITE: runtime-only setsebool without -P.",
    ),
    Scenario(
        id="selinux-setsebool-0002",
        tool="selinux",
        operation="setsebool",
        permission_class=_pc("setsebool"),
        complexity="single",
        user_input="permanently allow httpd to connect to the network — survive reboots",
        notes="WRITE: setsebool -P for persistent change across reboots.",
    ),
    Scenario(
        id="selinux-setsebool-0003",
        tool="selinux",
        operation="setsebool",
        permission_class=_pc("setsebool"),
        complexity="diagnostic",
        user_input="postfix can't relay mail — check if httpd_can_sendmail is off and turn it on persistently",
        notes="Diagnostic: check boolean state, then enable persistently.",
    ),
    Scenario(
        id="selinux-setsebool-0004",
        tool="selinux",
        operation="setsebool",
        permission_class=_pc("setsebool"),
        complexity="single",
        user_input="disable allow_execstack persistently on this host",
        notes="WRITE: turn off a security-sensitive boolean permanently.",
    ),

    # =========================================================================
    # semanage_fcontext_list  (READ) — 2 entries
    # =========================================================================

    Scenario(
        id="selinux-semanage_fcontext_list-0001",
        tool="selinux",
        operation="semanage_fcontext_list",
        permission_class=_pc("semanage_fcontext_list"),
        complexity="single",
        user_input="list all file context rules in the policy",
        notes="READ: semanage fcontext -l to see current mappings.",
    ),
    Scenario(
        id="selinux-semanage_fcontext_list-0002",
        tool="selinux",
        operation="semanage_fcontext_list",
        permission_class=_pc("semanage_fcontext_list"),
        complexity="diagnostic",
        user_input="show the file context mappings so I can verify /srv/www is labeled correctly",
        notes="Diagnostic: review fcontext list before adding a restorecon fix.",
    ),

    # =========================================================================
    # semanage_fcontext_add  (WRITE) — 3 entries
    # =========================================================================

    Scenario(
        id="selinux-semanage_fcontext_add-0001",
        tool="selinux",
        operation="semanage_fcontext_add",
        permission_class=_pc("semanage_fcontext_add"),
        complexity="single",
        user_input="add a file context rule so /srv/www gets labeled as httpd_sys_content_t",
        notes="WRITE: add fcontext mapping for custom web root.",
    ),
    Scenario(
        id="selinux-semanage_fcontext_add-0002",
        tool="selinux",
        operation="semanage_fcontext_add",
        permission_class=_pc("semanage_fcontext_add"),
        complexity="multi",
        user_input="add the fcontext rule for /opt/myapp as httpd_sys_content_t then run restorecon to apply it",
        notes="Multi-step: add fcontext then restorecon to enforce the label.",
    ),
    Scenario(
        id="selinux-semanage_fcontext_add-0003",
        tool="selinux",
        operation="semanage_fcontext_add",
        permission_class=_pc("semanage_fcontext_add"),
        complexity="single",
        user_input="create a context mapping for the custom app directory /data/pgdata to postgresql_db_t",
        notes="WRITE: label a non-standard PostgreSQL data directory.",
    ),

    # =========================================================================
    # semanage_fcontext_delete  (DESTRUCTIVE) — 2 entries
    # =========================================================================

    Scenario(
        id="selinux-semanage_fcontext_delete-0001",
        tool="selinux",
        operation="semanage_fcontext_delete",
        permission_class=_pc("semanage_fcontext_delete"),
        complexity="single",
        user_input="remove the custom fcontext rule for /srv/old-app",
        notes="DESTRUCTIVE: deleting a mapping may break labeling for confined services.",
    ),
    Scenario(
        id="selinux-semanage_fcontext_delete-0002",
        tool="selinux",
        operation="semanage_fcontext_delete",
        permission_class=_pc("semanage_fcontext_delete"),
        complexity="multi",
        user_input="delete the fcontext entry for /opt/legacy(/.*)?  and then confirm the rule is gone",
        notes="Multi-step DESTRUCTIVE: delete then verify removal by listing.",
    ),

    # =========================================================================
    # semanage_port_list  (READ) — 2 entries
    # =========================================================================

    Scenario(
        id="selinux-semanage_port_list-0001",
        tool="selinux",
        operation="semanage_port_list",
        permission_class=_pc("semanage_port_list"),
        complexity="single",
        user_input="list all port label mappings in the policy",
        notes="READ: semanage port -l to see what types are assigned to which ports.",
    ),
    Scenario(
        id="selinux-semanage_port_list-0002",
        tool="selinux",
        operation="semanage_port_list",
        permission_class=_pc("semanage_port_list"),
        complexity="diagnostic",
        user_input="nginx can't bind to port 8443 — check what label is assigned to that port",
        notes="Diagnostic: list port mappings to identify a labeling conflict.",
    ),

    # =========================================================================
    # semanage_port_add  (WRITE) — 3 entries
    # =========================================================================

    Scenario(
        id="selinux-semanage_port_add-0001",
        tool="selinux",
        operation="semanage_port_add",
        permission_class=_pc("semanage_port_add"),
        complexity="single",
        user_input="allow nginx to bind port 8080 by labeling it as http_port_t",
        notes="WRITE: add http_port_t label to port 8080/tcp.",
    ),
    Scenario(
        id="selinux-semanage_port_add-0002",
        tool="selinux",
        operation="semanage_port_add",
        permission_class=_pc("semanage_port_add"),
        complexity="multi",
        user_input="add port 9200/tcp as http_port_t so Elasticsearch can bind it, then verify",
        notes="Multi-step: add port label then confirm with port list.",
    ),
    Scenario(
        id="selinux-semanage_port_add-0003",
        tool="selinux",
        operation="semanage_port_add",
        permission_class=_pc("semanage_port_add"),
        complexity="diagnostic",
        user_input="my custom app on port 3000/tcp is getting denied — label it as http_port_t",
        notes="Diagnostic-triggered WRITE: AVC denial for port bind, add label to fix.",
    ),

    # =========================================================================
    # semanage_port_delete  (DESTRUCTIVE) — 2 entries
    # =========================================================================

    Scenario(
        id="selinux-semanage_port_delete-0001",
        tool="selinux",
        operation="semanage_port_delete",
        permission_class=_pc("semanage_port_delete"),
        complexity="single",
        user_input="remove the port label we added for 8080/tcp",
        notes="DESTRUCTIVE: removing a port label can prevent confined services from binding.",
    ),
    Scenario(
        id="selinux-semanage_port_delete-0002",
        tool="selinux",
        operation="semanage_port_delete",
        permission_class=_pc("semanage_port_delete"),
        complexity="multi",
        user_input="delete the label for 9200/tcp and confirm with a port list that it is gone",
        notes="Multi-step DESTRUCTIVE: delete label then verify removal.",
    ),

    # =========================================================================
    # semanage_user_list  (READ) — 2 entries
    # =========================================================================

    Scenario(
        id="selinux-semanage_user_list-0001",
        tool="selinux",
        operation="semanage_user_list",
        permission_class=_pc("semanage_user_list"),
        complexity="single",
        user_input="list all SELinux user mappings",
        notes="READ: show the table of confined users and their roles.",
    ),
    Scenario(
        id="selinux-semanage_user_list-0002",
        tool="selinux",
        operation="semanage_user_list",
        permission_class=_pc("semanage_user_list"),
        complexity="diagnostic",
        user_input="check which SELinux roles are assigned to staff_u before granting sysadm_r",
        notes="Diagnostic: verify current user mapping before a WRITE change.",
    ),

    # =========================================================================
    # semanage_user_add  (WRITE) — 2 entries
    # =========================================================================

    Scenario(
        id="selinux-semanage_user_add-0001",
        tool="selinux",
        operation="semanage_user_add",
        permission_class=_pc("semanage_user_add"),
        complexity="single",
        user_input="add a new SELinux user dbadmin_u with role staff_r",
        notes="WRITE: create a confined user mapping for a database admin.",
    ),
    Scenario(
        id="selinux-semanage_user_add-0002",
        tool="selinux",
        operation="semanage_user_add",
        permission_class=_pc("semanage_user_add"),
        complexity="multi",
        user_input="add the auditor_u SELinux user with staff_r role and then confirm the mapping was created",
        notes="Multi-step: add user mapping then verify with user list.",
    ),

    # =========================================================================
    # semanage_user_delete  (DESTRUCTIVE) — 2 entries
    # =========================================================================

    Scenario(
        id="selinux-semanage_user_delete-0001",
        tool="selinux",
        operation="semanage_user_delete",
        permission_class=_pc("semanage_user_delete"),
        complexity="single",
        user_input="delete the dbadmin_u SELinux user mapping",
        notes="DESTRUCTIVE: removing a user mapping can break confined user logins.",
    ),
    Scenario(
        id="selinux-semanage_user_delete-0002",
        tool="selinux",
        operation="semanage_user_delete",
        permission_class=_pc("semanage_user_delete"),
        complexity="multi",
        user_input="remove the auditor_u user mapping and verify it is gone from the list",
        notes="Multi-step DESTRUCTIVE: delete user mapping then verify removal.",
    ),

    # =========================================================================
    # restorecon  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="selinux-restorecon-0001",
        tool="selinux",
        operation="restorecon",
        permission_class=_pc("restorecon"),
        complexity="single",
        user_input="restore the SELinux file contexts on /var/www/html",
        notes="WRITE: restorecon -Rv on the default web root.",
    ),
    Scenario(
        id="selinux-restorecon-0002",
        tool="selinux",
        operation="restorecon",
        permission_class=_pc("restorecon"),
        complexity="single",
        user_input="relabel /srv/myapp recursively to fix the context",
        notes="WRITE: restorecon on a custom app directory after moving files.",
    ),
    Scenario(
        id="selinux-restorecon-0003",
        tool="selinux",
        operation="restorecon",
        permission_class=_pc("restorecon"),
        complexity="diagnostic",
        user_input="httpd is getting AVC denials on /data/app — restore the contexts on that path",
        notes="Diagnostic-triggered WRITE: restorecon to fix labeling causing denials.",
    ),
    Scenario(
        id="selinux-restorecon-0004",
        tool="selinux",
        operation="restorecon",
        permission_class=_pc("restorecon"),
        complexity="multi",
        user_input="add the fcontext rule for /opt/webapp and then run restorecon to apply it",
        notes="Multi-step: semanage_fcontext_add then restorecon to enforce the new label.",
    ),

    # =========================================================================
    # chcon  (WRITE) — 3 entries
    # =========================================================================

    Scenario(
        id="selinux-chcon-0001",
        tool="selinux",
        operation="chcon",
        permission_class=_pc("chcon"),
        complexity="single",
        user_input="change the SELinux type on /opt/app/config.conf to httpd_sys_content_t",
        notes="WRITE: chcon for a single file without policy persistence.",
    ),
    Scenario(
        id="selinux-chcon-0002",
        tool="selinux",
        operation="chcon",
        permission_class=_pc("chcon"),
        complexity="diagnostic",
        user_input="nginx keeps getting denied reading /srv/certs — temporarily set it to httpd_sys_content_t",
        notes="Diagnostic-triggered WRITE: quick chcon to test if labeling is the cause.",
    ),
    Scenario(
        id="selinux-chcon-0003",
        tool="selinux",
        operation="chcon",
        permission_class=_pc("chcon"),
        complexity="multi",
        user_input="set /var/custom/data to var_t and then verify the context with ls -Z",
        notes="Multi-step: chcon then manual verification of the applied label.",
    ),

    # =========================================================================
    # audit2allow  (READ) — 3 entries
    # =========================================================================

    Scenario(
        id="selinux-audit2allow-0001",
        tool="selinux",
        operation="audit2allow",
        permission_class=_pc("audit2allow"),
        complexity="single",
        user_input="analyze the AVC denials and tell me what policy I need to add",
        notes="READ: audit2allow -a to suggest allow rules from recent denials.",
    ),
    Scenario(
        id="selinux-audit2allow-0002",
        tool="selinux",
        operation="audit2allow",
        permission_class=_pc("audit2allow"),
        complexity="diagnostic",
        user_input="httpd is failing after I moved the docroot — run audit2allow to see what policy changes are needed",
        notes="Diagnostic: use audit2allow to identify required policy after a config change.",
    ),
    Scenario(
        id="selinux-audit2allow-0003",
        tool="selinux",
        operation="audit2allow",
        permission_class=_pc("audit2allow"),
        complexity="multi",
        user_input="run audit2allow to get policy suggestions, then apply the fcontext fix and restore contexts",
        notes="Multi-step: read denial suggestions, then fix with fcontext_add and restorecon.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("selinux").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "selinux", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("selinux").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
