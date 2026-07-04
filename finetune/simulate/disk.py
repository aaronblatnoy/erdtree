"""finetune/simulate/disk.py — Rocky Linux 9 output simulator for the 'disk' tool.

Public API
----------
simulate_disk(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 9 real operations declared in core/tools/disk.py
           (usage, list, smart, mount, unmount, format, partition, wipe, dd_write)
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict (same shape as finetune.context._PROFILES entries).
           Checked via isinstance; both forms are supported.

Realism model
-------------
* Exit codes mirror real df/lsblk/smartctl/mount/umount/mkfs/parted/wipefs/dd:
    0  — success
    1  — general failure (permission denied, device busy)
    2  — smartctl: open device failed (device not accessible)
   32  — mount/umount: not mounted, already mounted, or device busy
* stdout/stderr reflect actual Rocky 9 tool output formats.
* Failure triggers are deterministic (hash-based or arg-based):
    - A device whose lowercase name contains "nodev", "missing", "bogus",
      "invalid", or "fail" triggers failure cases.
    - A ~15% hash-based scatter adds variety for otherwise valid devices.
* ctx awareness:
    - usage: if ctx has a 'disk_usage' key (list of dicts), those mount entries
      are reflected in the df output.
    - mount: if the device is already in mounted_devices, returns already-mounted.
    - unmount: if the target is NOT in mounted_devices, returns not-mounted.

I2 compliance
-------------
All `summary` strings are I2-clean.  Forbidden terms (ai, llm, model, agent,
neural, machine learning, gpt, ollama, inference) are absent from summaries.
The word "model" in particular must not appear in any summary — use "drive",
"device", or "disk" instead.

INV-read-only-core: this module imports NOTHING from core/ directly.
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _device_fails(device: str) -> bool:
    """Deterministically decide if a device name should trigger a failure.

    Triggers: the name contains a known bad-token, or a ~15% hash scatter.
    """
    lower = device.lower()
    for tok in ("nodev", "missing", "bogus", "invalid", "fail", "notfound", "bad"):
        if tok in lower:
            return True
    h = int(hashlib.md5(device.encode()).hexdigest(), 16)
    return h % 20 == 0  # ~5% scatter


def _mounted_devices(ctx: Any) -> list[str]:
    """Return a list of currently-mounted device paths or mount points from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("mounted_devices", []) + ctx.get("mounted_mounts", [])
    return []


def _disk_usage_rows(ctx: Any) -> list[dict]:
    """Return disk usage rows from ctx if available."""
    if isinstance(ctx, dict):
        return ctx.get("disk_usage", [])
    return []


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_usage(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """df -h [<path>] — free/used space per filesystem."""
    path = args.get("path", "")

    # Build a df-h style table
    header = "Filesystem      Size  Used Avail Use% Mounted on"
    rows_from_ctx = _disk_usage_rows(ctx)

    if path:
        # Check if path exists in context-supplied usage rows
        matching = [r for r in rows_from_ctx if path in r.get("mount", "")]
        if not matching and path not in ("/", "/boot", "/home", "/var", "/tmp", "/data"):
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=f"df: {path}: No such file or directory\n",
                summary=f"Space usage query for '{path}' failed; path not found.",
            )
        # Synthesize a single row for the matching path
        if matching:
            r = matching[0]
            row = (
                f"{r.get('device', '/dev/sda1'):<16s}"
                f"{r.get('size', '50G'):>4s}  "
                f"{r.get('used', '20G'):>4s} "
                f"{r.get('avail', '27G'):>5s} "
                f"{r.get('use_pct', '43%'):>4s} "
                f"{r.get('mount', path)}"
            )
        else:
            # Default single-path row
            row = f"/dev/sda1        50G   20G   27G  43% {path}"
        stdout = f"{header}\n{row}\n"
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Reported space usage for 1 filesystem at '{path}'.",
        )

    # All filesystems
    if rows_from_ctx:
        lines = [header]
        for r in rows_from_ctx:
            lines.append(
                f"{r.get('device', '/dev/sda1'):<16s}"
                f"{r.get('size', '50G'):>4s}  "
                f"{r.get('used', '20G'):>4s} "
                f"{r.get('avail', '27G'):>5s} "
                f"{r.get('use_pct', '43%'):>4s} "
                f"{r.get('mount', '/')}"
            )
        stdout = "\n".join(lines) + "\n"
        count = len(rows_from_ctx)
    else:
        # Default Rocky 9 layout
        stdout = (
            f"{header}\n"
            f"devtmpfs        1.8G     0  1.8G   0% /dev\n"
            f"tmpfs           1.9G     0  1.9G   0% /dev/shm\n"
            f"tmpfs           1.9G  9.4M  1.9G   1% /run\n"
            f"/dev/sda1        50G   14G   37G  28% /\n"
            f"/dev/sda2       477M  192M  256M  43% /boot\n"
            f"tmpfs           379M     0  379M   0% /run/user/1000\n"
        )
        count = 6

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Reported space usage for {count} filesystem(s).",
    )


def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT [<device>] — list block devices."""
    device = args.get("device", "")
    header = "NAME        SIZE TYPE FSTYPE MOUNTPOINT"

    if device:
        if _device_fails(device):
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=f"lsblk: {device}: not a block device\n",
                summary=f"Block device listing failed; '{device}' is not a recognised block device.",
            )
        # Single device tree
        dev_base = device.replace("/dev/", "")
        stdout = (
            f"{header}\n"
            f"{dev_base:<12s}238.5G disk\n"
            f"├─{dev_base}1      512M part vfat   /boot/efi\n"
            f"├─{dev_base}2      477M part ext4   /boot\n"
            f"└─{dev_base}3    237.5G part\n"
            f"  ├─{dev_base}3-1  20G lvm  xfs    /\n"
            f"  └─{dev_base}3-2 217G lvm  xfs    /var\n"
        )
        rows = 5
    else:
        stdout = (
            f"{header}\n"
            f"sda         238.5G disk\n"
            f"├─sda1        512M part vfat   /boot/efi\n"
            f"├─sda2        477M part ext4   /boot\n"
            f"└─sda3      237.5G part\n"
            f"  ├─sda3-1   100G lvm  xfs    /\n"
            f"  ├─sda3-2    50G lvm  xfs    /var\n"
            f"  ├─sda3-3    50G lvm  xfs    /data\n"
            f"  └─sda3-4  37.5G lvm  xfs    [SWAP]\n"
            f"sdb         465.8G disk\n"
            f"└─sdb1      465.8G part xfs    /backup\n"
            f"sr0           1.9G rom\n"
        )
        rows = 11

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Listed {rows} block device entry(ies).",
    )


def _sim_smart(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """smartctl -H -A <device> — drive health and attributes."""
    device = args.get("device", "/dev/sda")

    if _device_fails(device):
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=(
                f"smartctl 7.3 2022-02-28 r5338 [x86_64-linux-5.14.0-427.el9.x86_64] (local build)\n"
                f"Copyright (C) 2002-22, Bruce Allen, Christian Franke, www.smartmontools.org\n"
                f"\n"
                f"Smartctl open device: {device} failed: No such device\n"
            ),
            summary=f"Drive health check for '{device}' failed; device could not be opened.",
        )

    # Vary by device name: NVMe vs SATA
    is_nvme = "nvme" in device.lower()

    if is_nvme:
        stdout = (
            f"smartctl 7.3 2022-02-28 r5338 [x86_64-linux-5.14.0-427.el9.x86_64] (local build)\n"
            f"Copyright (C) 2002-22, Bruce Allen, Christian Franke, www.smartmontools.org\n"
            f"\n"
            f"=== START OF SMART DATA SECTION ===\n"
            f"SMART overall-health self-assessment test result: PASSED\n"
            f"\n"
            f"SMART/Health Information (NVMe Log 0x02)\n"
            f"Critical Warning:                   0x00\n"
            f"Temperature:                        35 Celsius\n"
            f"Available Spare:                    100%\n"
            f"Available Spare Threshold:          10%\n"
            f"Percentage Used:                    0%\n"
            f"Data Units Read:                    2,847,103 [1.45 TB]\n"
            f"Data Units Written:                 1,932,441 [989 GB]\n"
            f"Host Read Commands:                 48,271,034\n"
            f"Host Write Commands:                23,184,509\n"
            f"Controller Busy Time:               1,043\n"
            f"Power Cycles:                       47\n"
            f"Power On Hours:                     8,762\n"
            f"Unsafe Shutdowns:                   12\n"
            f"Media and Data Integrity Errors:    0\n"
            f"Error Information Log Entries:      0\n"
        )
        summary = f"Drive health for '{device}' is PASSED with no critical warnings."
    else:
        # Deterministically trigger a warning for some drives
        h = int(hashlib.md5((device + "smart_warn").encode()).hexdigest(), 16)
        has_pending = h % 8 == 0

        pending_line = "197 Current_Pending_Sector  0x0032   100   100   000    Old_age   Always       -       " + (
            "3" if has_pending else "0"
        )
        stdout = (
            f"smartctl 7.3 2022-02-28 r5338 [x86_64-linux-5.14.0-427.el9.x86_64] (local build)\n"
            f"Copyright (C) 2002-22, Bruce Allen, Christian Franke, www.smartmontools.org\n"
            f"\n"
            f"=== START OF READ SMART DATA SECTION ===\n"
            f"SMART overall-health self-assessment test result: {'PASSED' if not has_pending else 'FAILED!'}\n"
            f"\n"
            f"SMART Attributes Data Structure revision number: 16\n"
            f"Vendor Specific SMART Attributes with Thresholds:\n"
            f"ID# ATTRIBUTE_NAME          FLAG     VALUE WORST THRESH TYPE      UPDATED  WHEN_FAILED RAW_VALUE\n"
            f"  1 Raw_Read_Error_Rate     0x002f   200   200   051    Pre-fail  Always       -       0\n"
            f"  3 Spin_Up_Time            0x0027   177   174   021    Pre-fail  Always       -       1575\n"
            f"  4 Start_Stop_Count        0x0032   100   100   000    Old_age   Always       -       47\n"
            f"  5 Reallocated_Sector_Ct   0x0033   200   200   140    Pre-fail  Always       -       0\n"
            f"  9 Power_On_Hours          0x0032   094   094   000    Old_age   Always       -       4671\n"
            f" 12 Power_Cycle_Count       0x0032   100   100   000    Old_age   Always       -       47\n"
            f"190 Airflow_Temperature_Cel 0x0022   071   055   045    Old_age   Always       -       29\n"
            f"194 Temperature_Celsius     0x0022   121   097   000    Old_age   Always       -       29\n"
            f"{pending_line}\n"
            f"198 Offline_Uncorrectable   0x0030   100   253   000    Old_age   Offline      -       0\n"
            f"199 UDMA_CRC_Error_Count    0x003e   200   200   000    Old_age   Always       -       0\n"
            f"200 Multi_Zone_Error_Rate   0x0028   200   200   000    Old_age   Offline      -       0\n"
        )

        if has_pending:
            summary = f"Drive health for '{device}' shows a FAILED result with pending sectors; investigate immediately."
        else:
            summary = f"Drive health for '{device}' is PASSED with no reallocated or pending sectors."

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=summary,
    )


def _sim_mount(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """mount <device> <mount_point> — attach a filesystem."""
    device = args.get("device", "/dev/sdb1")
    mount_point = args.get("mount_point", "/mnt/data")
    mounted = _mounted_devices(ctx)

    # Check if already mounted
    if device in mounted or mount_point in mounted:
        return _make_result(
            exit_code=32,
            stdout="",
            stderr=f"mount: {device}: already mounted on {mount_point}.\n",
            summary=f"'{device}' is already mounted; no changes were made.",
        )

    # Check if device fails
    if _device_fails(device):
        return _make_result(
            exit_code=32,
            stdout="",
            stderr=f"mount: {device}: special device {device} does not exist.\n",
            summary=f"Failed to mount '{device}'; the device does not exist.",
        )

    # Check mount point exists (simulate a missing mount point)
    h = int(hashlib.md5((device + mount_point + "mount").encode()).hexdigest(), 16)
    if h % 10 == 0:
        return _make_result(
            exit_code=32,
            stdout="",
            stderr=f"mount: {mount_point}: mount point does not exist.\n",
            summary=f"Failed to mount '{device}' at '{mount_point}'; the mount point directory does not exist.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Mounted '{device}' at '{mount_point}'.",
    )


def _sim_unmount(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """umount <target> — detach a mounted filesystem."""
    target = args.get("target", "/mnt/data")
    mounted = _mounted_devices(ctx)

    # If mounted list is populated and target is NOT in it, it's not mounted
    if mounted and target not in mounted:
        return _make_result(
            exit_code=32,
            stdout="",
            stderr=f"umount: {target}: not mounted.\n",
            summary=f"'{target}' is not currently mounted; unmount had no effect.",
        )

    # Device busy (hash-based scatter)
    h = int(hashlib.md5((target + "umount").encode()).hexdigest(), 16)
    if h % 15 == 0:
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"umount: {target}: target is busy.\n",
            summary=f"Failed to unmount '{target}'; the filesystem is in use by one or more processes.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Unmounted '{target}' successfully.",
    )


def _sim_format(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """mkfs.<fstype> <device> — create a filesystem on a device."""
    device = args.get("device", "/dev/sdb1")
    fstype = args.get("fstype", "ext4")

    if _device_fails(device):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"mke2fs 1.46.5 (30-Dec-2021)\nmke2fs: Cannot open {device}: No such file or directory\n",
            summary=f"Failed to create a {fstype} filesystem on '{device}'; the device does not exist.",
        )

    # Permission denied scatter (mkfs needs root)
    h = int(hashlib.md5((device + fstype + "format").encode()).hexdigest(), 16)
    if h % 12 == 0:
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"mke2fs 1.46.5 (30-Dec-2021)\nmke2fs: Permission denied while trying to determine filesystem size of {device}\n",
            summary=f"Failed to create a {fstype} filesystem on '{device}'; permission denied.",
        )

    if fstype in ("ext4", "ext3", "ext2"):
        dev_size = "20480"  # 20 GiB in MB placeholder
        stdout = (
            f"mke2fs 1.46.5 (30-Dec-2021)\n"
            f"Creating filesystem with 5242880 4k blocks and 1310720 inodes\n"
            f"Filesystem UUID: a3f1c2d4-8b7e-4f9a-b3c1-d2e4f5a6b7c8\n"
            f"Superblock backups stored on blocks:\n"
            f"\t32768, 98304, 163840, 229376, 294912, 819200, 884736, 1605632, 2654208, 4096000\n"
            f"\n"
            f"Allocating group tables: done\n"
            f"Writing inode tables: done\n"
            f"Creating journal (32768 blocks): done\n"
            f"Writing superblocks and filesystem accounting information: done\n"
        )
    elif fstype == "xfs":
        stdout = (
            f"meta-data={device:<20s} isize=512    agcount=4, agsize=1310720 blks\n"
            f"         =                       sectsz=512   attr=2, projid32bit=1\n"
            f"         =                       crc=1        finobt=1, sparse=1, rmapbt=0\n"
            f"         =                       reflink=1    bigtime=1 inobtcount=1\n"
            f"data     =                       bsize=4096   blocks=5242880, imaxpct=25\n"
            f"         =                       sunit=0      swidth=0 blks\n"
            f"naming   =version 2              bsize=4096   ascii-ci=0, ftype=1\n"
            f"log      =internal log           bsize=4096   blocks=2560, version=2\n"
            f"         =                       sectsz=512   sunit=0 blks, lazy-count=1\n"
            f"realtime =none                   extsz=4096   blocks=0, rtextents=0\n"
        )
    else:
        stdout = (
            f"mkfs.{fstype}: filesystem '{device}' created successfully.\n"
        )

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Created a {fstype} filesystem on '{device}'.",
    )


def _sim_partition(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """parted <device> <command...> — change a device's partition table."""
    device = args.get("device", "/dev/sdb")
    raw_cmd = args.get("command") or []
    if isinstance(raw_cmd, str):
        parted_cmd = raw_cmd.split()
    else:
        parted_cmd = [str(c) for c in raw_cmd]
    cmd_str = " ".join(parted_cmd) if parted_cmd else "(no command)"

    if _device_fails(device):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"Error: Could not stat device {device} - No such file or directory.\n",
            summary=f"Partition table change on '{device}' failed; the device does not exist.",
        )

    # Simulate invalid command
    h = int(hashlib.md5((device + cmd_str + "partition").encode()).hexdigest(), 16)
    if parted_cmd and parted_cmd[0] not in (
        "mklabel", "mkpart", "rm", "resizepart", "set", "print", "unit", "name", "rescue"
    ):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"Error: {parted_cmd[0]}: unrecognised keyword\n",
            summary=f"Partition table change on '{device}' failed; '{parted_cmd[0]}' is not a valid parted command.",
        )

    if not parted_cmd or parted_cmd[0] == "print":
        stdout = (
            f"Model: ATA WDC WD10EZEX-60W (scsi)\n"
            f"Disk {device}: 1000GB\n"
            f"Sector size (logical/physical): 512B/4096B\n"
            f"Partition Table: gpt\n"
            f"Disk Flags:\n"
            f"\n"
            f"Number  Start   End     Size    File system  Name  Flags\n"
            f" 1      1049kB  538MB   537MB   fat32        EFI   boot, esp\n"
            f" 2      538MB   1075MB  537MB   ext4\n"
            f" 3      1075MB  1000GB  999GB\n"
        )
        summary = f"Printed partition table for '{device}'."
    elif parted_cmd[0] == "mklabel":
        label = parted_cmd[1] if len(parted_cmd) > 1 else "gpt"
        stdout = f"Information: You may need to update /etc/fstab.\n"
        summary = f"Applied a new {label} partition label to '{device}'."
    else:
        stdout = f"Information: You may need to update /etc/fstab.\n"
        summary = f"Applied partition table change to '{device}'."

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=summary,
    )


def _sim_wipe(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """wipefs -a <device> — erase all filesystem signatures from a device."""
    device = args.get("device", "/dev/sdb")

    if _device_fails(device):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"wipefs: error: {device}: probing initialization failed: No such file or directory\n",
            summary=f"Failed to erase filesystem signatures from '{device}'; the device does not exist.",
        )

    # Permission denied scatter
    h = int(hashlib.md5((device + "wipe").encode()).hexdigest(), 16)
    if h % 10 == 0:
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"wipefs: error: {device}: open failed: Permission denied\n",
            summary=f"Failed to erase filesystem signatures from '{device}'; permission denied.",
        )

    # Normal success — wipefs prints the offsets it zeroed
    stdout = (
        f"{device}: 8 bytes were erased at offset 0x00000438 (ext4): 53 ef\n"
        f"{device}: 2 bytes were erased at offset 0x000001fe (dos): 55 aa\n"
        f"{device}: calling ioctl to re-read partition table: success\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Erased filesystem signatures from '{device}'.",
    )


def _sim_dd_write(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """dd if=<source> of=<device> [bs=...] — write source onto a device."""
    source = args.get("source", "/dev/zero")
    device = args.get("device", "/dev/sdb")
    bs = args.get("bs", "4M")

    # Source not found
    if "nofile" in source.lower() or "missing" in source.lower() or "bogus" in source.lower():
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"dd: failed to open '{source}': No such file or directory\n",
            summary=f"Failed to write to '{device}'; source '{source}' could not be opened.",
        )

    if _device_fails(device):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"dd: failed to open '{device}': No such file or directory\n",
            summary=f"Failed to write '{source}' onto '{device}'; the target device does not exist.",
        )

    # Permission denied scatter
    h = int(hashlib.md5((source + device + "dd").encode()).hexdigest(), 16)
    if h % 10 == 0:
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"dd: failed to open '{device}': Permission denied\n",
            summary=f"Failed to write '{source}' onto '{device}'; permission denied.",
        )

    # Realistic dd stderr (dd writes stats to stderr)
    # Simulate a ~20 GiB device
    stdout = ""
    stderr = (
        f"21474836480 bytes (21 GB, 20 GiB) copied, 47.3211 s, 454 MB/s\n"
        f"5120+0 records in\n"
        f"5120+0 records out\n"
        f"21474836480 bytes (21 GB, 20 GiB) copied, 47.3211 s, 454 MB/s\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr=stderr,
        summary=f"Wrote '{source}' onto '{device}' successfully.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "usage":     _sim_usage,
    "list":      _sim_list,
    "smart":     _sim_smart,
    "mount":     _sim_mount,
    "unmount":   _sim_unmount,
    "format":    _sim_format,
    "partition": _sim_partition,
    "wipe":      _sim_wipe,
    "dd_write":  _sim_dd_write,
}


def simulate_disk(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'disk' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 9 real ops declared in the
           disk ToolSpec (usage, list, smart, mount, unmount, format,
           partition, wipe, dd_write).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'mounted_devices', 'disk_usage', etc.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_disk: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
