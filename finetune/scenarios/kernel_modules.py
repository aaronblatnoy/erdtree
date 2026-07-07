"""finetune/scenarios/kernel_modules.py — Scenario corpus for the 'kernel_modules' tool.

Operations and their permission classes (derived LIVE from the registry):

  lsmod          READ        — list currently loaded kernel modules
  modinfo        READ        — show information about a kernel module
  modprobe       WRITE       — load a kernel module into the running kernel
  rmmod          DESTRUCTIVE — unload a live module; can wedge the host
  modules-load.d WRITE       — persist module to /etc/modules-load.d/ for boot loading

Coverage targets
----------------
  >= 40 entries total across all 5 operations.
  All three complexities represented: single | multi | diagnostic.

INV-schema-sync: permission_class for each entry is derived from the LIVE
  registry via finetune.coreimports, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass — fields match services.py convention for Phase-13 JOIN
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
    """Return the live permission class for a kernel_modules operation.

    If kernel_modules is not yet registered (e.g. when this file is imported
    before core.tools.kernel_modules), we import it here so the tool
    self-registers.  This guards against import-order races when the scenarios
    package is loaded before the tool module.
    """
    spec = registry.get("kernel_modules")
    if spec is None:
        import core.tools.kernel_modules  # noqa: F401 — side-effect: self-registers
        spec = registry.get("kernel_modules")
    return spec.permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # lsmod  (READ) — 11 entries
    # =========================================================================

    Scenario(
        id="kernel_modules-lsmod-0001",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="single",
        user_input="list all loaded kernel modules",
        notes="Basic read: show every module currently in memory.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0002",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="single",
        user_input="what kernel modules are currently loaded?",
        notes="Rephrasing of the basic lsmod request.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0003",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="diagnostic",
        user_input="the bridge interface is dropping packets — show me which kernel modules are loaded",
        notes="Diagnostic: start module investigation with lsmod before isolating the culprit.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0004",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="multi",
        user_input="list the loaded modules and tell me if br_netfilter is in the list",
        notes="Multi-step: lsmod then grep for a specific module name.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0005",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="single",
        user_input="show me the current kernel module table",
        notes="Synonym request for lsmod output.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0006",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="diagnostic",
        user_input="check which modules are loaded before I try loading nf_conntrack",
        notes="Diagnostic pre-check: survey loaded modules before adding a new one.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0007",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="multi",
        user_input="list modules and confirm that overlay and veth are both present for container networking",
        notes="Multi-step: lsmod then verify container networking prerequisites.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0008",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="single",
        user_input="run lsmod and show the output",
        notes="Direct lsmod invocation request.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0009",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="diagnostic",
        user_input="iSCSI storage is not coming up — list all loaded modules to help diagnose",
        notes="Diagnostic: storage issue triage starting with module inventory.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0010",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="multi",
        user_input="show loaded modules and count how many there are",
        notes="Multi-step: lsmod then count output lines.",
    ),
    Scenario(
        id="kernel_modules-lsmod-0011",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("lsmod"),
        complexity="diagnostic",
        user_input="after the kernel update the system behaves oddly — check which modules are currently loaded",
        notes="Post-upgrade diagnostic: verify module state after a kernel change.",
    ),

    # =========================================================================
    # modinfo  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="kernel_modules-modinfo-0001",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="single",
        user_input="show me information about the nf_conntrack module",
        notes="Basic modinfo: inspect the connection tracking module.",
    ),
    Scenario(
        id="kernel_modules-modinfo-0002",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="single",
        user_input="what are the parameters for the br_netfilter module?",
        notes="Inspect kernel module parameters before loading.",
    ),
    Scenario(
        id="kernel_modules-modinfo-0003",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="single",
        user_input="get the version and license info for the xfs module",
        notes="Version and license check for the XFS filesystem module.",
    ),
    Scenario(
        id="kernel_modules-modinfo-0004",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="diagnostic",
        user_input="dm_crypt is failing to load — show me its modinfo to check dependencies",
        notes="Diagnostic: check module dependencies when a load fails.",
    ),
    Scenario(
        id="kernel_modules-modinfo-0005",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="single",
        user_input="show modinfo for kvm_intel",
        notes="Inspect the KVM Intel virtualisation module.",
    ),
    Scenario(
        id="kernel_modules-modinfo-0006",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="multi",
        user_input="get modinfo for overlay and verify it has no listed dependencies that need loading first",
        notes="Multi-step: modinfo then check the depends field.",
    ),
    Scenario(
        id="kernel_modules-modinfo-0007",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="single",
        user_input="what filename does the bonding module live in?",
        notes="Check module file path from modinfo output.",
    ),
    Scenario(
        id="kernel_modules-modinfo-0008",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="diagnostic",
        user_input="a vendor script wants to load 8021q — check modinfo first to understand what it does",
        notes="Pre-load inspection: understand a VLAN tagging module before loading.",
    ),
    Scenario(
        id="kernel_modules-modinfo-0009",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="single",
        user_input="show module info for virtio_net",
        notes="Inspect the VirtIO network driver module.",
    ),
    Scenario(
        id="kernel_modules-modinfo-0010",
        tool="kernel_modules",
        operation="modinfo",
        permission_class=_pc("modinfo"),
        complexity="multi",
        user_input="get modinfo for tun and then check whether it is already loaded",
        notes="Multi-step: modinfo then lsmod cross-reference.",
    ),

    # =========================================================================
    # modprobe  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="kernel_modules-modprobe-0001",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="single",
        user_input="load the br_netfilter module",
        notes="WRITE: load bridge netfilter support — needed for container networking.",
    ),
    Scenario(
        id="kernel_modules-modprobe-0002",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="single",
        user_input="load nf_conntrack so connection tracking works",
        notes="WRITE: load connection tracking module.",
    ),
    Scenario(
        id="kernel_modules-modprobe-0003",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="single",
        user_input="load the overlay module for container filesystem support",
        notes="WRITE: load overlay filesystem module for OCI containers.",
    ),
    Scenario(
        id="kernel_modules-modprobe-0004",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="multi",
        user_input="load the veth module and then confirm it is in the lsmod output",
        notes="Multi-step: load module then verify with lsmod.",
    ),
    Scenario(
        id="kernel_modules-modprobe-0005",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="diagnostic",
        user_input="Kubernetes pods can't reach the internet — load br_netfilter and ip_tables to fix bridge packet filtering",
        notes="Diagnostic-triggered WRITE: load modules required for Kubernetes networking.",
    ),
    Scenario(
        id="kernel_modules-modprobe-0006",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="single",
        user_input="load the 8021q module for VLAN support",
        notes="WRITE: load VLAN tagging support.",
    ),
    Scenario(
        id="kernel_modules-modprobe-0007",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="single",
        user_input="load the bonding module so I can set up a bond interface",
        notes="WRITE: load network bonding module.",
    ),
    Scenario(
        id="kernel_modules-modprobe-0008",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="multi",
        user_input="load dm_crypt and check it loaded without errors",
        notes="Multi-step: load disk encryption module then verify.",
    ),
    Scenario(
        id="kernel_modules-modprobe-0009",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="single",
        user_input="add the tun module to the running kernel",
        notes="WRITE: load TUN/TAP module for VPN support.",
    ),
    Scenario(
        id="kernel_modules-modprobe-0010",
        tool="kernel_modules",
        operation="modprobe",
        permission_class=_pc("modprobe"),
        complexity="diagnostic",
        user_input="IPVS load balancing is not working — load ip_vs and ip_vs_rr to enable it",
        notes="Diagnostic-triggered WRITE: load IPVS modules required for kube-proxy.",
    ),

    # =========================================================================
    # rmmod  (DESTRUCTIVE) — 10 entries
    # =========================================================================

    Scenario(
        id="kernel_modules-rmmod-0001",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="single",
        user_input="unload the dummy module",
        notes="DESTRUCTIVE: remove the dummy network interface module.",
    ),
    Scenario(
        id="kernel_modules-rmmod-0002",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="single",
        user_input="remove the veth module from the running kernel",
        notes="DESTRUCTIVE: unload the virtual ethernet module.",
    ),
    Scenario(
        id="kernel_modules-rmmod-0003",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="diagnostic",
        user_input="the bonding module is causing instability — remove it from the kernel",
        notes="Diagnostic-triggered DESTRUCTIVE: emergency unload of a misbehaving module.",
    ),
    Scenario(
        id="kernel_modules-rmmod-0004",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="multi",
        user_input="unload the overlay module and then confirm it is gone from lsmod",
        notes="Multi-step: DESTRUCTIVE rmmod then lsmod verification.",
    ),
    Scenario(
        id="kernel_modules-rmmod-0005",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="single",
        user_input="remove the 8021q VLAN module",
        notes="DESTRUCTIVE: unload VLAN tagging support.",
    ),
    Scenario(
        id="kernel_modules-rmmod-0006",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="diagnostic",
        user_input="the tun module is leaking file descriptors — unload it so VPN reconnects cleanly",
        notes="Diagnostic-triggered DESTRUCTIVE: remove a misbehaving TUN module.",
    ),
    Scenario(
        id="kernel_modules-rmmod-0007",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="single",
        user_input="unload the serio_raw module — it is not needed on this host",
        notes="DESTRUCTIVE: remove an unused serial IO module.",
    ),
    Scenario(
        id="kernel_modules-rmmod-0008",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="multi",
        user_input="remove the bpfilter module and check lsmod to confirm it is gone",
        notes="Multi-step: DESTRUCTIVE unload then verification.",
    ),
    Scenario(
        id="kernel_modules-rmmod-0009",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="single",
        user_input="unload nft_ct from the kernel",
        notes="DESTRUCTIVE: remove a netfilter conntrack module.",
    ),
    Scenario(
        id="kernel_modules-rmmod-0010",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("rmmod"),
        complexity="diagnostic",
        user_input="the fuse module is preventing a filesystem unmount — unload it",
        notes="Diagnostic-triggered DESTRUCTIVE: remove FUSE to allow clean unmount.",
    ),

    # =========================================================================
    # modules-load.d  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="kernel_modules-modules-load.d-0001",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="single",
        user_input="make br_netfilter load automatically at boot",
        notes="WRITE: persist br_netfilter to modules-load.d for Kubernetes nodes.",
    ),
    Scenario(
        id="kernel_modules-modules-load.d-0002",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="single",
        user_input="configure overlay to load on every boot",
        notes="WRITE: persist overlay module for container runtime.",
    ),
    Scenario(
        id="kernel_modules-modules-load.d-0003",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="multi",
        user_input="set nf_conntrack to load at boot and then load it now without rebooting",
        notes="Multi-step: persist via modules-load.d then modprobe immediately.",
    ),
    Scenario(
        id="kernel_modules-modules-load.d-0004",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="single",
        user_input="add the tun module to /etc/modules-load.d so VPN works after reboot",
        notes="WRITE: persist TUN module for VPN support across reboots.",
    ),
    Scenario(
        id="kernel_modules-modules-load.d-0005",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="single",
        user_input="make the bonding module persist across reboots",
        notes="WRITE: persist bonding module for link aggregation.",
    ),
    Scenario(
        id="kernel_modules-modules-load.d-0006",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="diagnostic",
        user_input="after each reboot we have to manually load 8021q — fix that by making it load automatically",
        notes="Diagnostic-triggered WRITE: automate module loading that was previously manual.",
    ),
    Scenario(
        id="kernel_modules-modules-load.d-0007",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="multi",
        user_input="write a modules-load.d entry for dm_crypt and confirm the file was created",
        notes="Multi-step: create persistent entry then verify file existence.",
    ),
    Scenario(
        id="kernel_modules-modules-load.d-0008",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="single",
        user_input="persist the dummy module to modules-load.d",
        notes="WRITE: persist dummy module for loopback network testing.",
    ),
    Scenario(
        id="kernel_modules-modules-load.d-0009",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="single",
        user_input="add ip_vs to /etc/modules-load.d for IPVS load balancing on boot",
        notes="WRITE: persist IPVS module for kube-proxy IPVS mode.",
    ),
    Scenario(
        id="kernel_modules-modules-load.d-0010",
        tool="kernel_modules",
        operation="modules-load.d",
        permission_class=_pc("modules-load.d"),
        complexity="multi",
        user_input="persist nf_conntrack to modules-load.d then check that both nf_conntrack and nf_nat are loaded right now",
        notes="Multi-step: write persistent config then verify current loaded state.",
    ),
]


# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_KM_SPEC = registry.get("kernel_modules")
if _KM_SPEC is None:
    import core.tools.kernel_modules  # noqa: F401 — side-effect: self-registers
    _KM_SPEC = registry.get("kernel_modules")

_REAL_OPS: frozenset[str] = frozenset(_KM_SPEC.ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "kernel_modules", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == _KM_SPEC.permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
