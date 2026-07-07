"""finetune/scenarios/grub.py — Scenario corpus for the 'grub' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  info           READ        — show grubby entry/entries for a kernel or ALL
  default-kernel READ        — print the current default kernel path
  set-default    WRITE       — set the default boot kernel
  args-add       WRITE       — add kernel command-line arguments
  args-remove    WRITE       — remove kernel command-line arguments
  mkconfig       DESTRUCTIVE — regenerate /boot/grub2/grub.cfg
  set-password   WRITE       — set the GRUB bootloader password
  remove-kernel  DESTRUCTIVE — remove a kernel entry from the boot menu

Coverage targets
----------------
  >= 40 entries total across all 8 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios honestly labeled so traces teach the confirmation gate.

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
    """Return the live permission class for a grub operation."""
    return registry.get("grub").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # info  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="grub-info-0001",
        tool="grub",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me all the kernel entries in GRUB",
        notes="List all grubby entries using ALL.",
    ),
    Scenario(
        id="grub-info-0002",
        tool="grub",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what kernel arguments is the current kernel using?",
        notes="Read the args field from grubby --info=ALL.",
    ),
    Scenario(
        id="grub-info-0003",
        tool="grub",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me the GRUB entry for /boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64",
        notes="Targeted info query for a specific kernel path.",
    ),
    Scenario(
        id="grub-info-0004",
        tool="grub",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="the server failed to boot — what kernels are available in the GRUB menu?",
        notes="Diagnostic: check available boot entries after a boot failure.",
    ),
    Scenario(
        id="grub-info-0005",
        tool="grub",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="list all grub entries and tell me which one is set as default",
        notes="Multi-step: info then compare against default-kernel output.",
    ),
    Scenario(
        id="grub-info-0006",
        tool="grub",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="after the kernel update the box rebooted into the old kernel — show all GRUB entries",
        notes="Diagnostic: inspect entries after unexpected kernel selection.",
    ),
    Scenario(
        id="grub-info-0007",
        tool="grub",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what initrd image is the boot entry using?",
        notes="Read the initrd field from grubby --info output.",
    ),
    Scenario(
        id="grub-info-0008",
        tool="grub",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show grub boot entry index for the rescue kernel",
        notes="Read the index field to locate the rescue entry.",
    ),

    # =========================================================================
    # default-kernel  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="grub-default-kernel-0001",
        tool="grub",
        operation="default-kernel",
        permission_class=_pc("default-kernel"),
        complexity="single",
        user_input="which kernel will this host boot into by default?",
        notes="Simple READ: grubby --default-kernel.",
    ),
    Scenario(
        id="grub-default-kernel-0002",
        tool="grub",
        operation="default-kernel",
        permission_class=_pc("default-kernel"),
        complexity="single",
        user_input="show me the current default kernel",
        notes="READ: confirm current default kernel path.",
    ),
    Scenario(
        id="grub-default-kernel-0003",
        tool="grub",
        operation="default-kernel",
        permission_class=_pc("default-kernel"),
        complexity="diagnostic",
        user_input="we updated the kernel last week but the host is still booting the old one — what is the default kernel?",
        notes="Diagnostic: verify default kernel after a package update.",
    ),
    Scenario(
        id="grub-default-kernel-0004",
        tool="grub",
        operation="default-kernel",
        permission_class=_pc("default-kernel"),
        complexity="multi",
        user_input="check the default kernel and compare it with the running kernel to see if they match",
        notes="Multi-step: default-kernel then compare with uname -r.",
    ),
    Scenario(
        id="grub-default-kernel-0005",
        tool="grub",
        operation="default-kernel",
        permission_class=_pc("default-kernel"),
        complexity="single",
        user_input="print the path to the default boot kernel",
        notes="READ: retrieve the full path to the default kernel file.",
    ),
    Scenario(
        id="grub-default-kernel-0006",
        tool="grub",
        operation="default-kernel",
        permission_class=_pc("default-kernel"),
        complexity="diagnostic",
        user_input="after a failed kernel upgrade, confirm which kernel is set to boot by default",
        notes="Diagnostic: post-upgrade verification of the default boot target.",
    ),

    # =========================================================================
    # set-default  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="grub-set-default-0001",
        tool="grub",
        operation="set-default",
        permission_class=_pc("set-default"),
        complexity="single",
        user_input="set the default kernel to /boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64",
        notes="WRITE: set a specific kernel as the default boot target.",
    ),
    Scenario(
        id="grub-set-default-0002",
        tool="grub",
        operation="set-default",
        permission_class=_pc("set-default"),
        complexity="single",
        user_input="make the new kernel the default boot entry",
        notes="WRITE: switch default kernel after a package install.",
    ),
    Scenario(
        id="grub-set-default-0003",
        tool="grub",
        operation="set-default",
        permission_class=_pc("set-default"),
        complexity="multi",
        user_input="set the default kernel to the new version and then verify it took effect",
        notes="Multi-step: set-default then confirm via default-kernel.",
    ),
    Scenario(
        id="grub-set-default-0004",
        tool="grub",
        operation="set-default",
        permission_class=_pc("set-default"),
        complexity="diagnostic",
        user_input="the host is booting the wrong kernel — roll back the default to the previous version",
        notes="Diagnostic-triggered WRITE: revert default kernel after a regression.",
    ),
    Scenario(
        id="grub-set-default-0005",
        tool="grub",
        operation="set-default",
        permission_class=_pc("set-default"),
        complexity="single",
        user_input="switch the default boot kernel to the rescue entry",
        notes="WRITE: set the rescue kernel as default for next boot.",
    ),
    Scenario(
        id="grub-set-default-0006",
        tool="grub",
        operation="set-default",
        permission_class=_pc("set-default"),
        complexity="multi",
        user_input="change the default boot kernel to the newly patched version and confirm it was set correctly",
        notes="Multi-step: set-default then read back with grubby --default-kernel.",
    ),

    # =========================================================================
    # args-add  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="grub-args-add-0001",
        tool="grub",
        operation="args-add",
        permission_class=_pc("args-add"),
        complexity="single",
        user_input="add 'quiet' to the kernel boot arguments",
        notes="WRITE: add a single kernel argument to ALL entries.",
    ),
    Scenario(
        id="grub-args-add-0002",
        tool="grub",
        operation="args-add",
        permission_class=_pc("args-add"),
        complexity="single",
        user_input="enable IOMMU by adding 'intel_iommu=on iommu=pt' to the kernel command line",
        notes="WRITE: add IOMMU kernel arguments for SR-IOV/passthrough.",
    ),
    Scenario(
        id="grub-args-add-0003",
        tool="grub",
        operation="args-add",
        permission_class=_pc("args-add"),
        complexity="multi",
        user_input="add 'pcie_aspm=off' to the kernel arguments and then check the entry to confirm",
        notes="Multi-step: add arg then verify with grubby --info.",
    ),
    Scenario(
        id="grub-args-add-0004",
        tool="grub",
        operation="args-add",
        permission_class=_pc("args-add"),
        complexity="diagnostic",
        user_input="the host is having NVMe issues — add 'nvme_core.default_ps_max_latency_us=0' to the kernel arguments",
        notes="Diagnostic-triggered WRITE: add a kernel quirk to address a hardware issue.",
    ),
    Scenario(
        id="grub-args-add-0005",
        tool="grub",
        operation="args-add",
        permission_class=_pc("args-add"),
        complexity="single",
        user_input="add 'selinux=0' to the kernel arguments for this entry only",
        notes="WRITE: add SELinux-disable argument to a specific kernel entry.",
    ),
    Scenario(
        id="grub-args-add-0006",
        tool="grub",
        operation="args-add",
        permission_class=_pc("args-add"),
        complexity="multi",
        user_input="add 'transparent_hugepage=never' to all kernel entries and confirm it was applied",
        notes="Multi-step: add THP argument to ALL entries then verify.",
    ),

    # =========================================================================
    # args-remove  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="grub-args-remove-0001",
        tool="grub",
        operation="args-remove",
        permission_class=_pc("args-remove"),
        complexity="single",
        user_input="remove 'quiet' from the kernel boot arguments",
        notes="WRITE: remove a single kernel argument from the default entry.",
    ),
    Scenario(
        id="grub-args-remove-0002",
        tool="grub",
        operation="args-remove",
        permission_class=_pc("args-remove"),
        complexity="single",
        user_input="remove 'rhgb' from all kernel entries so we get verbose boot output",
        notes="WRITE: strip the graphical boot progress argument from all entries.",
    ),
    Scenario(
        id="grub-args-remove-0003",
        tool="grub",
        operation="args-remove",
        permission_class=_pc("args-remove"),
        complexity="multi",
        user_input="remove the 'pcie_aspm=off' argument we added last week and verify it is gone",
        notes="Multi-step: remove arg then confirm with grubby --info.",
    ),
    Scenario(
        id="grub-args-remove-0004",
        tool="grub",
        operation="args-remove",
        permission_class=_pc("args-remove"),
        complexity="diagnostic",
        user_input="the box won't boot cleanly since we added 'amd_iommu=on' — remove that argument",
        notes="Diagnostic-triggered WRITE: revert a kernel argument after a boot regression.",
    ),
    Scenario(
        id="grub-args-remove-0005",
        tool="grub",
        operation="args-remove",
        permission_class=_pc("args-remove"),
        complexity="single",
        user_input="remove 'selinux=0' from the kernel arguments to re-enable SELinux enforcement",
        notes="WRITE: reinstate SELinux by removing the disable argument.",
    ),
    Scenario(
        id="grub-args-remove-0006",
        tool="grub",
        operation="args-remove",
        permission_class=_pc("args-remove"),
        complexity="multi",
        user_input="strip 'crashkernel=auto' from all entries and replace with a fixed value",
        notes="Multi-step: remove crashkernel=auto then add a fixed crashkernel arg.",
    ),

    # =========================================================================
    # mkconfig  (DESTRUCTIVE) — 6 entries
    # =========================================================================

    Scenario(
        id="grub-mkconfig-0001",
        tool="grub",
        operation="mkconfig",
        permission_class=_pc("mkconfig"),
        complexity="single",
        user_input="regenerate the GRUB configuration file",
        notes="DESTRUCTIVE: rebuild grub.cfg after making changes to /etc/default/grub.",
    ),
    Scenario(
        id="grub-mkconfig-0002",
        tool="grub",
        operation="mkconfig",
        permission_class=_pc("mkconfig"),
        complexity="multi",
        user_input="after editing /etc/default/grub, regenerate the config and verify the timeout value changed",
        notes="Multi-step: mkconfig then inspect grub.cfg to confirm the change.",
    ),
    Scenario(
        id="grub-mkconfig-0003",
        tool="grub",
        operation="mkconfig",
        permission_class=_pc("mkconfig"),
        complexity="diagnostic",
        user_input="the GRUB menu is not showing all kernels — regenerate the config to pick them up",
        notes="Diagnostic-triggered DESTRUCTIVE: rebuild config to include newly installed kernels.",
    ),
    Scenario(
        id="grub-mkconfig-0004",
        tool="grub",
        operation="mkconfig",
        permission_class=_pc("mkconfig"),
        complexity="single",
        user_input="rebuild grub2-mkconfig to the EFI path /boot/efi/EFI/redhat/grub.cfg",
        notes="DESTRUCTIVE: rebuild config to the EFI boot path instead of the legacy BIOS path.",
    ),
    Scenario(
        id="grub-mkconfig-0005",
        tool="grub",
        operation="mkconfig",
        permission_class=_pc("mkconfig"),
        complexity="multi",
        user_input="change the GRUB timeout to 5 seconds in /etc/default/grub and then regenerate the config",
        notes="Multi-step: edit /etc/default/grub then run mkconfig.",
    ),
    Scenario(
        id="grub-mkconfig-0006",
        tool="grub",
        operation="mkconfig",
        permission_class=_pc("mkconfig"),
        complexity="diagnostic",
        user_input="a kernel update was installed but grub.cfg still references the old version — regenerate it",
        notes="Diagnostic-triggered DESTRUCTIVE: sync grub.cfg after a kernel update.",
    ),

    # =========================================================================
    # set-password  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="grub-set-password-0001",
        tool="grub",
        operation="set-password",
        permission_class=_pc("set-password"),
        complexity="single",
        user_input="set a GRUB bootloader password to protect boot entries from tampering",
        notes="WRITE: set grub2-setpassword as a security hardening step.",
    ),
    Scenario(
        id="grub-set-password-0002",
        tool="grub",
        operation="set-password",
        permission_class=_pc("set-password"),
        complexity="single",
        user_input="configure a GRUB password so only root can edit boot parameters",
        notes="WRITE: restrict boot parameter editing to authorized users.",
    ),
    Scenario(
        id="grub-set-password-0003",
        tool="grub",
        operation="set-password",
        permission_class=_pc("set-password"),
        complexity="multi",
        user_input="set a GRUB bootloader password and then verify that the user.cfg file was created",
        notes="Multi-step: set password then confirm /boot/grub2/user.cfg exists.",
    ),
    Scenario(
        id="grub-set-password-0004",
        tool="grub",
        operation="set-password",
        permission_class=_pc("set-password"),
        complexity="diagnostic",
        user_input="the security scan flagged that this host has no GRUB password — set one now",
        notes="Diagnostic-triggered WRITE: remediate a missing GRUB password finding.",
    ),
    Scenario(
        id="grub-set-password-0005",
        tool="grub",
        operation="set-password",
        permission_class=_pc("set-password"),
        complexity="single",
        user_input="update the GRUB password to comply with the new password policy",
        notes="WRITE: rotate the GRUB password as part of a security policy change.",
    ),
    Scenario(
        id="grub-set-password-0006",
        tool="grub",
        operation="set-password",
        permission_class=_pc("set-password"),
        complexity="multi",
        user_input="set the GRUB bootloader password and regenerate the config to enforce it",
        notes="Multi-step: set-password then mkconfig to write the superuser config.",
    ),

    # =========================================================================
    # remove-kernel  (DESTRUCTIVE) — 6 entries
    # =========================================================================

    Scenario(
        id="grub-remove-kernel-0001",
        tool="grub",
        operation="remove-kernel",
        permission_class=_pc("remove-kernel"),
        complexity="single",
        user_input="remove the old 4.x kernel from the GRUB menu",
        notes="DESTRUCTIVE: remove a superseded kernel entry from the boot menu.",
    ),
    Scenario(
        id="grub-remove-kernel-0002",
        tool="grub",
        operation="remove-kernel",
        permission_class=_pc("remove-kernel"),
        complexity="single",
        user_input="delete the /boot/vmlinuz-5.14.0-284.30.1.el9_2.x86_64 GRUB entry",
        notes="DESTRUCTIVE: remove a specific versioned kernel from the boot menu.",
    ),
    Scenario(
        id="grub-remove-kernel-0003",
        tool="grub",
        operation="remove-kernel",
        permission_class=_pc("remove-kernel"),
        complexity="multi",
        user_input="remove the oldest kernel from the GRUB menu and verify it no longer appears in the entry list",
        notes="Multi-step: remove-kernel then confirm with grubby --info=ALL.",
    ),
    Scenario(
        id="grub-remove-kernel-0004",
        tool="grub",
        operation="remove-kernel",
        permission_class=_pc("remove-kernel"),
        complexity="diagnostic",
        user_input="the GRUB menu has 5 old kernels taking up space — remove the two oldest ones",
        notes="Diagnostic-triggered DESTRUCTIVE: clean up stale kernel entries.",
    ),
    Scenario(
        id="grub-remove-kernel-0005",
        tool="grub",
        operation="remove-kernel",
        permission_class=_pc("remove-kernel"),
        complexity="single",
        user_input="remove the rescue kernel entry from GRUB",
        notes="DESTRUCTIVE: remove the rescue kernel entry — high-risk operation.",
    ),
    Scenario(
        id="grub-remove-kernel-0006",
        tool="grub",
        operation="remove-kernel",
        permission_class=_pc("remove-kernel"),
        complexity="multi",
        user_input="after confirming the new kernel boots cleanly, remove the old kernel entry from the menu",
        notes="Multi-step: verify current boot kernel then remove the previous entry.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("grub").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "grub", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("grub").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
