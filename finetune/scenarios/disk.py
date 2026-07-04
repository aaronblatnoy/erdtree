"""finetune/scenarios/disk.py — Scenario corpus for the 'disk' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  usage     READ         — show disk usage (df-style)
  list      READ         — enumerate block devices (lsblk-style)
  smart     READ         — query SMART health data for a drive
  mount     WRITE        — mount a filesystem
  unmount   WRITE        — unmount a filesystem
  format    DESTRUCTIVE  — format a partition with a filesystem
  partition DESTRUCTIVE  — create or modify a partition table
  wipe      DESTRUCTIVE  — securely erase a block device
  dd_write  DESTRUCTIVE  — write a raw image to a block device (dd-style)

Coverage targets
----------------
  >= 60 entries total across all 9 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE/DESTRUCTIVE scenarios are honestly labeled so downstream traces
  teach the confirm-before-write and DESTROY-typed confirmation gates.

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
# Scenario dataclass
# Field names are EXACT so the P1 JOIN can unify without renames.
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
    """Return the live permission class for a disk operation."""
    return registry.get("disk").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # usage  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="disk-usage-0001",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="single",
        user_input="how much disk space is left on this server?",
        notes="Basic free-space check across all mounted filesystems.",
    ),
    Scenario(
        id="disk-usage-0002",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="single",
        user_input="show me disk usage for /var",
        notes="Usage check scoped to a specific mount point.",
    ),
    Scenario(
        id="disk-usage-0003",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="single",
        user_input="what percentage of / is used?",
        notes="Root filesystem utilization percentage.",
    ),
    Scenario(
        id="disk-usage-0004",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="single",
        user_input="check how full the /boot partition is",
        notes="Boot partition usage — relevant before kernel updates.",
    ),
    Scenario(
        id="disk-usage-0005",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="single",
        user_input="is /home running out of space?",
        notes="Home partition capacity check.",
    ),
    Scenario(
        id="disk-usage-0006",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="multi",
        user_input="check disk usage on all filesystems and flag anything over 80% full",
        notes="Multi-step: list all mounts, identify ones above threshold.",
    ),
    Scenario(
        id="disk-usage-0007",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="multi",
        user_input="show me disk usage and tell me which partition is closest to being full",
        notes="Multi-step: enumerate usage, rank by utilization percentage.",
    ),
    Scenario(
        id="disk-usage-0008",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="diagnostic",
        user_input="disk writes have been failing — show me available space on all partitions",
        notes="Diagnostic: full-disk condition causing write failures.",
    ),
    Scenario(
        id="disk-usage-0009",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="diagnostic",
        user_input="the database keeps crashing — is the data partition out of space?",
        notes="Diagnostic: correlate DB crashes with disk exhaustion.",
    ),
    Scenario(
        id="disk-usage-0010",
        tool="disk",
        operation="usage",
        permission_class=_pc("usage"),
        complexity="single",
        user_input="give me a summary of disk space across every mounted volume",
        notes="Full-system disk space summary.",
    ),

    # =========================================================================
    # list  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="disk-list-0001",
        tool="disk",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me all the block devices on this machine",
        notes="Enumerate all block devices (lsblk-style).",
    ),
    Scenario(
        id="disk-list-0002",
        tool="disk",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what drives are attached to this server?",
        notes="Physical drive discovery.",
    ),
    Scenario(
        id="disk-list-0003",
        tool="disk",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list all partitions including their sizes and filesystem types",
        notes="Partition inventory with filesystem metadata.",
    ),
    Scenario(
        id="disk-list-0004",
        tool="disk",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="is there an NVMe drive in this system?",
        notes="Check for NVMe device presence.",
    ),
    Scenario(
        id="disk-list-0005",
        tool="disk",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list all disks and then tell me which ones have no partitions yet",
        notes="Multi-step: list devices, filter unpartitioned ones.",
    ),
    Scenario(
        id="disk-list-0006",
        tool="disk",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list block devices and identify which ones are mounted vs unmounted",
        notes="Multi-step: cross-reference device list with mount state.",
    ),
    Scenario(
        id="disk-list-0007",
        tool="disk",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="I added a new disk but I can't find it — list all block devices",
        notes="Diagnostic: newly attached disk not showing up.",
    ),
    Scenario(
        id="disk-list-0008",
        tool="disk",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="something is using /dev/sdb but I don't know what — show me the full device tree",
        notes="Diagnostic: identify what is using a specific block device.",
    ),

    # =========================================================================
    # smart  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="disk-smart-0001",
        tool="disk",
        operation="smart",
        permission_class=_pc("smart"),
        complexity="single",
        user_input="check the health of /dev/sda",
        notes="SMART health query on primary disk.",
    ),
    Scenario(
        id="disk-smart-0002",
        tool="disk",
        operation="smart",
        permission_class=_pc("smart"),
        complexity="single",
        user_input="is /dev/nvme0n1 healthy?",
        notes="SMART check on NVMe drive.",
    ),
    Scenario(
        id="disk-smart-0003",
        tool="disk",
        operation="smart",
        permission_class=_pc("smart"),
        complexity="single",
        user_input="how many reallocated sectors does /dev/sdb have?",
        notes="Specific SMART attribute — reallocated sector count.",
    ),
    Scenario(
        id="disk-smart-0004",
        tool="disk",
        operation="smart",
        permission_class=_pc("smart"),
        complexity="single",
        user_input="what is the temperature of the main drive right now?",
        notes="Drive temperature from SMART data.",
    ),
    Scenario(
        id="disk-smart-0005",
        tool="disk",
        operation="smart",
        permission_class=_pc("smart"),
        complexity="multi",
        user_input="check SMART health on all drives and tell me if any are at risk of failure",
        notes="Multi-step: SMART on each device, summarize failure risk.",
    ),
    Scenario(
        id="disk-smart-0006",
        tool="disk",
        operation="smart",
        permission_class=_pc("smart"),
        complexity="multi",
        user_input="run a SMART self-test result check on /dev/sda and summarize the result",
        notes="Multi-step: query and interpret last self-test result.",
    ),
    Scenario(
        id="disk-smart-0007",
        tool="disk",
        operation="smart",
        permission_class=_pc("smart"),
        complexity="diagnostic",
        user_input="I/O errors keep appearing in dmesg — check SMART on /dev/sdb for pending sectors",
        notes="Diagnostic: correlate I/O errors with SMART pending sector count.",
    ),
    Scenario(
        id="disk-smart-0008",
        tool="disk",
        operation="smart",
        permission_class=_pc("smart"),
        complexity="diagnostic",
        user_input="the system is running slow — check disk health on /dev/sda to rule out drive failure",
        notes="Diagnostic: eliminate drive failure as cause of performance degradation.",
    ),

    # =========================================================================
    # mount  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="disk-mount-0001",
        tool="disk",
        operation="mount",
        permission_class=_pc("mount"),
        complexity="single",
        user_input="mount /dev/sdb1 at /mnt/data",
        notes="Basic mount operation on a data partition.",
    ),
    Scenario(
        id="disk-mount-0002",
        tool="disk",
        operation="mount",
        permission_class=_pc("mount"),
        complexity="single",
        user_input="mount the external USB drive at /mnt/backup",
        notes="Mount external USB storage for backup access.",
    ),
    Scenario(
        id="disk-mount-0003",
        tool="disk",
        operation="mount",
        permission_class=_pc("mount"),
        complexity="single",
        user_input="mount /dev/nvme0n1p2 read-only at /mnt/recovery",
        notes="Read-only mount for data recovery scenario.",
    ),
    Scenario(
        id="disk-mount-0004",
        tool="disk",
        operation="mount",
        permission_class=_pc("mount"),
        complexity="single",
        user_input="mount /dev/sdc1 as an ext4 filesystem at /srv/postgres",
        notes="Mount a specific filesystem type for a database directory.",
    ),
    Scenario(
        id="disk-mount-0005",
        tool="disk",
        operation="mount",
        permission_class=_pc("mount"),
        complexity="multi",
        user_input="mount the new data drive at /mnt/data and verify it shows up correctly",
        notes="Multi-step: mount then confirm with usage or list check.",
    ),
    Scenario(
        id="disk-mount-0006",
        tool="disk",
        operation="mount",
        permission_class=_pc("mount"),
        complexity="multi",
        user_input="I just added a second disk — partition it if needed, then mount it at /data",
        notes="Multi-step: may require partition step before mount.",
    ),
    Scenario(
        id="disk-mount-0007",
        tool="disk",
        operation="mount",
        permission_class=_pc("mount"),
        complexity="diagnostic",
        user_input="the /mnt/nfs share is gone — try to remount /dev/sdc1 at /mnt/nfs",
        notes="Diagnostic: remount after unexpected unmount.",
    ),
    Scenario(
        id="disk-mount-0008",
        tool="disk",
        operation="mount",
        permission_class=_pc("mount"),
        complexity="single",
        user_input="attach /dev/sdb2 to /mnt/logs so the logging service can write there",
        notes="Mount a partition to redirect logging writes.",
    ),

    # =========================================================================
    # unmount  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="disk-unmount-0001",
        tool="disk",
        operation="unmount",
        permission_class=_pc("unmount"),
        complexity="single",
        user_input="unmount /mnt/backup",
        notes="Unmount a backup mount point.",
    ),
    Scenario(
        id="disk-unmount-0002",
        tool="disk",
        operation="unmount",
        permission_class=_pc("unmount"),
        complexity="single",
        user_input="detach the USB drive at /mnt/usb before I pull it",
        notes="Safe unmount before physical removal of USB storage.",
    ),
    Scenario(
        id="disk-unmount-0003",
        tool="disk",
        operation="unmount",
        permission_class=_pc("unmount"),
        complexity="single",
        user_input="unmount /dev/sdb1",
        notes="Unmount by device path rather than mount point.",
    ),
    Scenario(
        id="disk-unmount-0004",
        tool="disk",
        operation="unmount",
        permission_class=_pc("unmount"),
        complexity="multi",
        user_input="unmount /mnt/data and confirm it is no longer mounted",
        notes="Multi-step: unmount then verify with list.",
    ),
    Scenario(
        id="disk-unmount-0005",
        tool="disk",
        operation="unmount",
        permission_class=_pc("unmount"),
        complexity="diagnostic",
        user_input="the filesystem at /mnt/archive is showing stale file handles — unmount it",
        notes="Diagnostic: stale NFS or device leading to unmount request.",
    ),
    Scenario(
        id="disk-unmount-0006",
        tool="disk",
        operation="unmount",
        permission_class=_pc("unmount"),
        complexity="single",
        user_input="safely unmount /mnt/postgres before I do maintenance",
        notes="Pre-maintenance unmount of a database storage mount.",
    ),
    Scenario(
        id="disk-unmount-0007",
        tool="disk",
        operation="unmount",
        permission_class=_pc("unmount"),
        complexity="multi",
        user_input="unmount /mnt/scratch and then wipe the device — it has old test data",
        notes="Multi-step: unmount before destructive wipe operation.",
    ),

    # =========================================================================
    # format  (DESTRUCTIVE) — 8 entries
    # =========================================================================

    Scenario(
        id="disk-format-0001",
        tool="disk",
        operation="format",
        permission_class=_pc("format"),
        complexity="single",
        user_input="format /dev/sdb1 as ext4",
        notes="Basic ext4 format on a data partition.",
    ),
    Scenario(
        id="disk-format-0002",
        tool="disk",
        operation="format",
        permission_class=_pc("format"),
        complexity="single",
        user_input="create an XFS filesystem on /dev/sdc2",
        notes="XFS format — common for high-throughput data workloads.",
    ),
    Scenario(
        id="disk-format-0003",
        tool="disk",
        operation="format",
        permission_class=_pc("format"),
        complexity="single",
        user_input="format the new drive partition /dev/nvme0n1p1 with ext4 and label it DATA",
        notes="Format with filesystem label on NVMe partition.",
    ),
    Scenario(
        id="disk-format-0004",
        tool="disk",
        operation="format",
        permission_class=_pc("format"),
        complexity="single",
        user_input="format /dev/sdb2 as swap space",
        notes="Create swap partition.",
    ),
    Scenario(
        id="disk-format-0005",
        tool="disk",
        operation="format",
        permission_class=_pc("format"),
        complexity="multi",
        user_input="format /dev/sdc1 as ext4 and then mount it at /srv/data",
        notes="Multi-step: format then mount the new filesystem.",
    ),
    Scenario(
        id="disk-format-0006",
        tool="disk",
        operation="format",
        permission_class=_pc("format"),
        complexity="multi",
        user_input="partition and format the new 2TB drive at /dev/sdd for use as a data volume",
        notes="Multi-step: partition table creation then format.",
    ),
    Scenario(
        id="disk-format-0007",
        tool="disk",
        operation="format",
        permission_class=_pc("format"),
        complexity="diagnostic",
        user_input="the filesystem on /dev/sdb1 is corrupted and unfixable — reformat it as ext4",
        notes="Diagnostic: irrecoverable filesystem corruption requiring reformat.",
    ),
    Scenario(
        id="disk-format-0008",
        tool="disk",
        operation="format",
        permission_class=_pc("format"),
        complexity="single",
        user_input="format /dev/sdc1 as vfat so I can use it in a cross-platform setup",
        notes="FAT32 format for interoperability with non-Linux systems.",
    ),

    # =========================================================================
    # partition  (DESTRUCTIVE) — 7 entries
    # =========================================================================

    Scenario(
        id="disk-partition-0001",
        tool="disk",
        operation="partition",
        permission_class=_pc("partition"),
        complexity="single",
        user_input="create a GPT partition table on /dev/sdb",
        notes="Initialize a fresh GPT partition table.",
    ),
    Scenario(
        id="disk-partition-0002",
        tool="disk",
        operation="partition",
        permission_class=_pc("partition"),
        complexity="single",
        user_input="create a single partition using the full disk on /dev/sdc",
        notes="Single full-disk partition — common for dedicated data drives.",
    ),
    Scenario(
        id="disk-partition-0003",
        tool="disk",
        operation="partition",
        permission_class=_pc("partition"),
        complexity="single",
        user_input="partition /dev/sdd with a 512MB EFI partition and the rest as a data partition",
        notes="EFI + data two-partition layout.",
    ),
    Scenario(
        id="disk-partition-0004",
        tool="disk",
        operation="partition",
        permission_class=_pc("partition"),
        complexity="multi",
        user_input="partition the new drive /dev/sde into a swap and data partition, then format both",
        notes="Multi-step: partition then format each resulting partition.",
    ),
    Scenario(
        id="disk-partition-0005",
        tool="disk",
        operation="partition",
        permission_class=_pc("partition"),
        complexity="multi",
        user_input="set up /dev/sdb with a GPT partition table, one ext4 partition, and mount it",
        notes="Multi-step: partition, format, and mount in sequence.",
    ),
    Scenario(
        id="disk-partition-0006",
        tool="disk",
        operation="partition",
        permission_class=_pc("partition"),
        complexity="diagnostic",
        user_input="the drive /dev/sdb shows a corrupt partition table — create a new GPT table",
        notes="Diagnostic: corrupt partition table requires rebuilding.",
    ),
    Scenario(
        id="disk-partition-0007",
        tool="disk",
        operation="partition",
        permission_class=_pc("partition"),
        complexity="single",
        user_input="create an MBR partition table on /dev/sdc for legacy BIOS compatibility",
        notes="MBR layout for systems without UEFI support.",
    ),

    # =========================================================================
    # wipe  (DESTRUCTIVE) — 7 entries
    # =========================================================================

    Scenario(
        id="disk-wipe-0001",
        tool="disk",
        operation="wipe",
        permission_class=_pc("wipe"),
        complexity="single",
        user_input="securely erase /dev/sdb before decommissioning it",
        notes="Secure wipe before retiring a drive.",
    ),
    Scenario(
        id="disk-wipe-0002",
        tool="disk",
        operation="wipe",
        permission_class=_pc("wipe"),
        complexity="single",
        user_input="wipe /dev/sdc so it has no recoverable data before shipping it back",
        notes="Data sanitization before physical return of leased hardware.",
    ),
    Scenario(
        id="disk-wipe-0003",
        tool="disk",
        operation="wipe",
        permission_class=_pc("wipe"),
        complexity="single",
        user_input="zero out /dev/sdd completely",
        notes="Full zero-fill wipe of a drive.",
    ),
    Scenario(
        id="disk-wipe-0004",
        tool="disk",
        operation="wipe",
        permission_class=_pc("wipe"),
        complexity="multi",
        user_input="unmount /mnt/scratch and then securely wipe the underlying device /dev/sdb1",
        notes="Multi-step: unmount before wipe to avoid busy-device errors.",
    ),
    Scenario(
        id="disk-wipe-0005",
        tool="disk",
        operation="wipe",
        permission_class=_pc("wipe"),
        complexity="multi",
        user_input="wipe /dev/sdc and then partition it fresh for the new workload",
        notes="Multi-step: wipe then repartition.",
    ),
    Scenario(
        id="disk-wipe-0006",
        tool="disk",
        operation="wipe",
        permission_class=_pc("wipe"),
        complexity="diagnostic",
        user_input="the drive /dev/sdb has filesystem errors we can't repair — wipe it and start fresh",
        notes="Diagnostic: unrecoverable filesystem, full wipe required.",
    ),
    Scenario(
        id="disk-wipe-0007",
        tool="disk",
        operation="wipe",
        permission_class=_pc("wipe"),
        complexity="single",
        user_input="erase the test drive /dev/sde before we repurpose it for production",
        notes="Wipe a repurposed test drive ahead of production use.",
    ),

    # =========================================================================
    # dd_write  (DESTRUCTIVE) — 7 entries
    # =========================================================================

    Scenario(
        id="disk-dd_write-0001",
        tool="disk",
        operation="dd_write",
        permission_class=_pc("dd_write"),
        complexity="single",
        user_input="write the Rocky Linux ISO to /dev/sdb to create a bootable USB",
        notes="Raw ISO write to USB drive for bootable installer.",
    ),
    Scenario(
        id="disk-dd_write-0002",
        tool="disk",
        operation="dd_write",
        permission_class=_pc("dd_write"),
        complexity="single",
        user_input="restore the disk image backup to /dev/sdc",
        notes="Restore a raw disk image to a block device.",
    ),
    Scenario(
        id="disk-dd_write-0003",
        tool="disk",
        operation="dd_write",
        permission_class=_pc("dd_write"),
        complexity="single",
        user_input="flash the firmware image to /dev/sdd",
        notes="Write a raw firmware image to a block device.",
    ),
    Scenario(
        id="disk-dd_write-0004",
        tool="disk",
        operation="dd_write",
        permission_class=_pc("dd_write"),
        complexity="multi",
        user_input="clone /dev/sda to /dev/sdb — copy the entire drive byte for byte",
        notes="Multi-step: full drive clone via raw write.",
    ),
    Scenario(
        id="disk-dd_write-0005",
        tool="disk",
        operation="dd_write",
        permission_class=_pc("dd_write"),
        complexity="multi",
        user_input="write the OS image to the new drive /dev/sdc and then verify it boots",
        notes="Multi-step: raw write then verify write integrity.",
    ),
    Scenario(
        id="disk-dd_write-0006",
        tool="disk",
        operation="dd_write",
        permission_class=_pc("dd_write"),
        complexity="diagnostic",
        user_input="the server won't boot — write a known-good image to /dev/sda to recover it",
        notes="Diagnostic: non-booting system recovery via raw image restore.",
    ),
    Scenario(
        id="disk-dd_write-0007",
        tool="disk",
        operation="dd_write",
        permission_class=_pc("dd_write"),
        complexity="single",
        user_input="write zeros to the first 512 bytes of /dev/sdb to clear the MBR",
        notes="Targeted raw write to erase the MBR of a drive.",
    ),
]
