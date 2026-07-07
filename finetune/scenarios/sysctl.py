"""finetune/scenarios/sysctl.py — Scenario corpus for the 'sysctl' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list    READ  — list all kernel parameters (sysctl -a)
  get     READ  — read a single kernel parameter value
  set     WRITE — set a kernel parameter at runtime (sysctl -w; not persistent)
  persist WRITE — write a kernel parameter to /etc/sysctl.d/ and reload

Coverage targets
----------------
  >= 40 entries total across all 4 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE scenarios are honestly labeled (permission_class from registry).

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
    """Return the live permission class for a sysctl operation."""
    return registry.get("sysctl").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="sysctl-list-0001",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all kernel parameters",
        notes="Basic full listing of all sysctl knobs via sysctl -a.",
    ),
    Scenario(
        id="sysctl-list-0002",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list every kernel tunable on this system",
        notes="Operator wants a complete inventory of sysctl knobs.",
    ),
    Scenario(
        id="sysctl-list-0003",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="dump all kernel parameters and then tell me if vm.swappiness is set above 60",
        notes="Multi-step: full list then inspect a specific value.",
    ),
    Scenario(
        id="sysctl-list-0004",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="we suspect a misconfigured kernel parameter is causing packet drops — show me all network-related sysctl values",
        notes="Diagnostic: list all knobs, focus on net.* namespace.",
    ),
    Scenario(
        id="sysctl-list-0005",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what kernel tunables are currently active on this host?",
        notes="READ: snapshot of all live kernel settings.",
    ),
    Scenario(
        id="sysctl-list-0006",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="the security team wants a baseline of all kernel parameters before patching",
        notes="Diagnostic: security baseline capture via sysctl -a.",
    ),
    Scenario(
        id="sysctl-list-0007",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list all kernel params and flag any that differ from the hardening baseline",
        notes="Multi-step: list then compare against expected values.",
    ),
    Scenario(
        id="sysctl-list-0008",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show all vm.* kernel settings",
        notes="READ: list output filtered to vm namespace.",
    ),
    Scenario(
        id="sysctl-list-0009",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="after the OOM kill last night, I want to see all vm.* and kernel.* parameters",
        notes="Diagnostic: OOM post-mortem — review vm and kernel namespace knobs.",
    ),
    Scenario(
        id="sysctl-list-0010",
        tool="sysctl",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="get a full sysctl dump and then check if ip_forward is enabled",
        notes="Multi-step: full dump then targeted check for routing knob.",
    ),

    # =========================================================================
    # get  (READ) — 12 entries
    # =========================================================================

    Scenario(
        id="sysctl-get-0001",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="what is the current value of vm.swappiness?",
        notes="READ: check swap aggressiveness knob.",
    ),
    Scenario(
        id="sysctl-get-0002",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="is ip forwarding enabled on this host?",
        notes="READ: check net.ipv4.ip_forward — crucial for router/NAT hosts.",
    ),
    Scenario(
        id="sysctl-get-0003",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="what is kernel.randomize_va_space set to?",
        notes="READ: ASLR setting — security audit.",
    ),
    Scenario(
        id="sysctl-get-0004",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="check the value of net.ipv4.tcp_syncookies",
        notes="READ: SYN flood mitigation setting.",
    ),
    Scenario(
        id="sysctl-get-0005",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="what is fs.file-max on this server?",
        notes="READ: maximum open file descriptors — performance tuning.",
    ),
    Scenario(
        id="sysctl-get-0006",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="show me the current kernel.panic value",
        notes="READ: panic timeout — relevant for unattended restart behavior.",
    ),
    Scenario(
        id="sysctl-get-0007",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="multi",
        user_input="read net.core.somaxconn and tell me if it is sufficient for a high-traffic web server",
        notes="Multi-step: read then evaluate value against a performance threshold.",
    ),
    Scenario(
        id="sysctl-get-0008",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="diagnostic",
        user_input="connections are being dropped at peak load — check net.ipv4.tcp_max_syn_backlog",
        notes="Diagnostic: read backlog knob as part of connection-drop investigation.",
    ),
    Scenario(
        id="sysctl-get-0009",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="is kernel.dmesg_restrict enabled?",
        notes="READ: security hardening check — restrict dmesg to root.",
    ),
    Scenario(
        id="sysctl-get-0010",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="diagnostic",
        user_input="the node is swapping heavily — what is vm.overcommit_memory set to?",
        notes="Diagnostic: read memory overcommit policy during a swap pressure event.",
    ),
    Scenario(
        id="sysctl-get-0011",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="single",
        user_input="check the value of net.ipv4.conf.all.rp_filter",
        notes="READ: reverse path filtering — network security and anti-spoofing.",
    ),
    Scenario(
        id="sysctl-get-0012",
        tool="sysctl",
        operation="get",
        permission_class=_pc("get"),
        complexity="multi",
        user_input="read kernel.kptr_restrict and explain what it means for security",
        notes="Multi-step: read then interpret the security implication of the value.",
    ),

    # =========================================================================
    # set  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="sysctl-set-0001",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="set vm.swappiness to 10 to reduce swapping",
        notes="WRITE: tune swap aggressiveness for a memory-constrained host.",
    ),
    Scenario(
        id="sysctl-set-0002",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="enable ip forwarding now without a reboot",
        notes="WRITE: set net.ipv4.ip_forward=1 for a host acting as a router.",
    ),
    Scenario(
        id="sysctl-set-0003",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="increase net.core.somaxconn to 65535 for the load balancer",
        notes="WRITE: raise the socket listen backlog for high-concurrency workloads.",
    ),
    Scenario(
        id="sysctl-set-0004",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="set net.ipv4.tcp_syncookies to 1",
        notes="WRITE: enable SYN cookie protection against SYN flood attacks.",
    ),
    Scenario(
        id="sysctl-set-0005",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="multi",
        user_input="set vm.swappiness to 10 and then verify the new value",
        notes="Multi-step: set swappiness then read it back to confirm.",
    ),
    Scenario(
        id="sysctl-set-0006",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="diagnostic",
        user_input="connections are timing out — bump net.ipv4.tcp_keepalive_time to 300",
        notes="Diagnostic-triggered WRITE: adjust TCP keepalive as a remediation step.",
    ),
    Scenario(
        id="sysctl-set-0007",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="set kernel.randomize_va_space to 2 for full ASLR",
        notes="WRITE: enforce maximum ASLR randomisation — security hardening.",
    ),
    Scenario(
        id="sysctl-set-0008",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="raise fs.inotify.max_user_watches to 524288",
        notes="WRITE: increase inotify watch limit for workloads with many watched files.",
    ),
    Scenario(
        id="sysctl-set-0009",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="diagnostic",
        user_input="the application is running out of file handles — increase fs.file-max to 2097152",
        notes="Diagnostic-triggered WRITE: raise system-wide fd limit in response to EMFILE errors.",
    ),
    Scenario(
        id="sysctl-set-0010",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="single",
        user_input="set net.ipv4.conf.all.accept_redirects to 0 to disable ICMP redirects",
        notes="WRITE: harden against ICMP redirect attacks — network security.",
    ),
    Scenario(
        id="sysctl-set-0011",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="multi",
        user_input="disable IPv4 forwarding immediately and then confirm the value is 0",
        notes="Multi-step: set net.ipv4.ip_forward=0 then verify.",
    ),
    Scenario(
        id="sysctl-set-0012",
        tool="sysctl",
        operation="set",
        permission_class=_pc("set"),
        complexity="diagnostic",
        user_input="inotify limits are too low for the monitoring daemon — set fs.inotify.max_user_instances to 512",
        notes="Diagnostic-triggered WRITE: raise inotify instance cap for a monitoring tool.",
    ),

    # =========================================================================
    # persist  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="sysctl-persist-0001",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="single",
        user_input="make vm.swappiness=10 survive reboots",
        notes="WRITE: persist swappiness reduction to /etc/sysctl.d/.",
    ),
    Scenario(
        id="sysctl-persist-0002",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="single",
        user_input="permanently enable ip forwarding on this host",
        notes="WRITE: persist net.ipv4.ip_forward=1 for a router role.",
    ),
    Scenario(
        id="sysctl-persist-0003",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="single",
        user_input="persist net.core.somaxconn=65535 so the setting survives a reboot",
        notes="WRITE: persist socket backlog increase for a load balancer.",
    ),
    Scenario(
        id="sysctl-persist-0004",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="multi",
        user_input="write vm.overcommit_memory=1 to sysctl.d and then reload kernel parameters",
        notes="Multi-step: persist overcommit policy and verify reload.",
    ),
    Scenario(
        id="sysctl-persist-0005",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="single",
        user_input="add net.ipv4.tcp_syncookies=1 to /etc/sysctl.d/ for hardening",
        notes="WRITE: persist SYN cookie setting as part of a CIS benchmark remediation.",
    ),
    Scenario(
        id="sysctl-persist-0006",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="diagnostic",
        user_input="the swappiness keeps resetting to 60 after reboots — persist it to 10 permanently",
        notes="Diagnostic-triggered WRITE: operator noticed runtime change not surviving reboot.",
    ),
    Scenario(
        id="sysctl-persist-0007",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="single",
        user_input="persist kernel.randomize_va_space=2 for full ASLR across reboots",
        notes="WRITE: lock in maximum ASLR — security hardening persisted to drop-in.",
    ),
    Scenario(
        id="sysctl-persist-0008",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="multi",
        user_input="persist net.ipv4.conf.all.rp_filter=1 and then confirm the file was created",
        notes="Multi-step: persist rp_filter then verify the sysctl.d file exists.",
    ),
    Scenario(
        id="sysctl-persist-0009",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="single",
        user_input="write fs.inotify.max_user_watches=524288 to /etc/sysctl.d/99-inotify.conf",
        notes="WRITE: persist inotify limit with a specific drop-in filename.",
    ),
    Scenario(
        id="sysctl-persist-0010",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="diagnostic",
        user_input="we keep seeing EMFILE on this host after reboots — persist fs.file-max=2097152",
        notes="Diagnostic-triggered WRITE: persist fd limit fix so it survives reboots.",
    ),
    Scenario(
        id="sysctl-persist-0011",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="single",
        user_input="permanently disable ICMP redirects by persisting net.ipv4.conf.all.accept_redirects=0",
        notes="WRITE: persist ICMP redirect hardening — network security baseline.",
    ),
    Scenario(
        id="sysctl-persist-0012",
        tool="sysctl",
        operation="persist",
        permission_class=_pc("persist"),
        complexity="multi",
        user_input="persist vm.dirty_ratio=10 and vm.dirty_background_ratio=5 for database performance",
        notes="Multi-step: persist two write-back tunables for a database workload.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("sysctl").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "sysctl", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("sysctl").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
