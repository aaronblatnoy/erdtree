"""finetune/simulate/hardware.py — Rocky Linux 9 output simulator for the 'hardware' tool.

Public API
----------
simulate_hardware(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 7 real operations declared in core/tools/hardware.py
           (cpu, memory, pci, usb, block, sensors, summary)
    args : dict of op arguments (all hardware ops take no required args; {} is fine)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict (same shape as finetune.context._PROFILES entries).
           Both forms are supported; ctx drives variation in outputs (hostname,
           hardware profile, running conditions).

Realism model
-------------
* lscpu output mirrors Rocky Linux 9 / x86_64 format (multi-socket or single,
  reflecting ctx where possible).
* free -h mirrors the kernel's GiB/MiB reporting format.
* lspci / lsusb mirror actual Broadcom/Intel/NVIDIA/VirtIO device lines.
* lsblk mirrors NAME/SIZE/TYPE/FSTYPE/MOUNTPOINT columns.
* sensors mirrors coretemp / nct6775 chip output.
* Failure cases:
    - cpu:     lscpu unavailable (no x86_64 arch module loaded)
    - memory:  free command not found (minimal container image)
    - pci:     lspci not installed (missing pciutils)
    - usb:     lsusb not installed (missing usbutils)
    - block:   lsblk returns non-zero (kernel sysfs mount problem)
    - sensors: sensors command not found or no sensors detected
    - summary: worst-exit-code propagation when one sub-command fails

I2 compliance
-------------
All `summary` strings are I2-clean (no AI/LLM/model/agent/ollama/inference).
The assert_no_ai_language guard is called on each returned summary so any
accidental violation is caught at simulation time.

INV-read-only-core: this module imports NOTHING from core/ directly.
It imports assert_no_ai_language from finetune.coreimports (the seam).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any

from finetune.coreimports import assert_no_ai_language


# ---------------------------------------------------------------------------
# Context-extraction helpers
# ---------------------------------------------------------------------------


def _ctx_str(ctx: Any) -> str:
    """Safely coerce ctx to a string for substring scanning."""
    if ctx is None:
        return ""
    if isinstance(ctx, str):
        return ctx
    if hasattr(ctx, "snapshot_text"):
        return str(ctx.snapshot_text)
    if hasattr(ctx, "to_prompt_text"):
        return str(ctx.to_prompt_text())
    return str(ctx)


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx if available, else return a generic default."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "prod-node-01")
    c = _ctx_str(ctx)
    for line in c.splitlines():
        if line.startswith("Hostname:") or line.startswith("hostname:"):
            return line.split(":", 1)[1].strip()
    return "prod-node-01"


def _hash_ctx(ctx: Any) -> int:
    """Stable integer hash of the ctx for deterministic variation."""
    return int(hashlib.sha256(_ctx_str(ctx).encode()).hexdigest(), 16)


def _is_db_host(ctx: Any) -> bool:
    c = _ctx_str(ctx).lower()
    return "postgres" in c or "mysql" in c or "mariadb" in c or "db" in _hostname(ctx).lower()


def _is_container_host(ctx: Any) -> bool:
    c = _ctx_str(ctx).lower()
    return "docker" in c or "podman" in c or "container" in c


def _mem_gb(ctx: Any) -> int:
    """Guess total RAM in GiB from ctx (default 16)."""
    c = _ctx_str(ctx)
    for line in c.splitlines():
        if "memory" in line.lower() and "gb" in line.lower():
            for tok in line.split():
                if tok.replace(".", "").isdigit():
                    return max(1, int(float(tok)))
    # DB hosts tend to have more RAM
    if _is_db_host(ctx):
        return 64
    h = _hash_ctx(ctx) % 4
    return [8, 16, 32, 64][h]


def _cpu_cores(ctx: Any) -> int:
    """Guess CPU core count from ctx."""
    if _is_db_host(ctx):
        return 32
    h = _hash_ctx(ctx) % 3
    return [4, 8, 16][h]


# ---------------------------------------------------------------------------
# Operation: cpu
# ---------------------------------------------------------------------------


def _op_cpu_success(ctx: Any) -> dict:
    cores = _cpu_cores(ctx)
    threads = cores * 2
    sockets = 2 if cores >= 16 else 1
    cores_per_socket = cores // sockets
    stdout = (
        f"Architecture:            x86_64\n"
        f"  CPU op-mode(s):        32-bit, 64-bit\n"
        f"  Address sizes:         46 bits physical, 48 bits virtual\n"
        f"  Byte Order:            Little Endian\n"
        f"CPU(s):                  {threads}\n"
        f"  On-line CPU(s) list:   0-{threads - 1}\n"
        f"Vendor ID:               GenuineIntel\n"
        f"  Model name:            Intel(R) Xeon(R) Gold 6248R CPU @ 3.00GHz\n"
        f"  CPU family:            6\n"
        f"  Model:                 85\n"
        f"  Thread(s) per core:    2\n"
        f"  Core(s) per socket:    {cores_per_socket}\n"
        f"  Socket(s):             {sockets}\n"
        f"  Stepping:              7\n"
        f"  CPU MHz:               3000.000\n"
        f"  CPU max MHz:           4000.0000\n"
        f"  CPU min MHz:           1200.0000\n"
        f"  BogoMIPS:              6000.00\n"
        f"  Virtualization:        VT-x\n"
        f"  L1d cache:             {cores * 32}K\n"
        f"  L1i cache:             {cores * 32}K\n"
        f"  L2 cache:              {cores * 1024}K\n"
        f"  L3 cache:              {cores * 2}M\n"
        f"Flags:                   fpu vme de pse tsc msr pae mce cx8 apic sep mtrr "
        f"pge mca cmov pat pse36 clflush dts acpi mmx fxsr sse sse2 ss ht tm pbe "
        f"syscall nx pdpe1gb rdtscp lm constant_tsc art arch_perfmon pebs bts "
        f"rep_good nopl xtopology nonstop_tsc cpuid aperfmperf pni pclmulqdq "
        f"dtes64 monitor ds_cpl vmx smx est tm2 ssse3 sdbg fma cx16 xtpr pdcm "
        f"pcid dca sse4_1 sse4_2 x2apic movbe popcnt tsc_deadline_timer aes "
        f"xsave avx f16c rdrand lahf_lm abm 3dnowprefetch cpuid_fault epb "
        f"cat_l3 cdp_l3 invpcid_single intel_ppin ssbd mba ibrs ibpb stibp "
        f"ibrs_enhanced tpr_shadow vnmi flexpriority ept vpid ept_ad fsgsbase "
        f"tsc_adjust bmi1 avx2 smep bmi2 erms invpcid cqm mpx rdt_a avx512f "
        f"avx512dq rdseed adx smap clflushopt clwb intel_pt avx512cd avx512bw "
        f"avx512vl xsaveopt xsavec xgetbv1 xsaves cqm_llc cqm_occup_llc "
        f"cqm_mbm_total cqm_mbm_local dtherm ida arat pln pts pku ospke "
        f"avx512_vnni md_clear flush_l1d arch_capabilities\n"
    )
    summary = f"CPU topology retrieved: {threads} logical processors across {sockets} socket(s)."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": stdout, "stderr": "", "summary": summary}


def _op_cpu_failure(ctx: Any) -> dict:
    stderr = "lscpu: command not found\n"
    summary = "CPU topology query failed: lscpu is not available on this host."
    assert_no_ai_language(summary)
    return {"exit_code": 127, "stdout": "", "stderr": stderr, "summary": summary}


# ---------------------------------------------------------------------------
# Operation: memory
# ---------------------------------------------------------------------------


def _op_memory_success(ctx: Any) -> dict:
    total_gb = _mem_gb(ctx)
    used_gb = max(1, int(total_gb * 0.45))
    free_gb = total_gb - used_gb
    # Swap
    swap_gb = min(total_gb, 8)
    swap_used_gb = 0
    stdout = (
        f"               total        used        free      shared  buff/cache   available\n"
        f"Mem:            {total_gb}Gi       {used_gb}Gi       {free_gb}Gi      148Mi"
        f"       {total_gb - used_gb - free_gb + 1}Gi       {free_gb}Gi\n"
        f"Swap:           {swap_gb}Gi          0B       {swap_gb}Gi\n"
    )
    summary = f"Memory usage retrieved: {used_gb} GiB used of {total_gb} GiB total; swap {swap_used_gb} GiB used of {swap_gb} GiB."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": stdout, "stderr": "", "summary": summary}


def _op_memory_failure(ctx: Any) -> dict:
    stderr = "bash: free: command not found\n"
    summary = "Memory usage query failed: free command is not available (minimal image)."
    assert_no_ai_language(summary)
    return {"exit_code": 127, "stdout": "", "stderr": stderr, "summary": summary}


# ---------------------------------------------------------------------------
# Operation: pci
# ---------------------------------------------------------------------------

_PCI_LINES_STANDARD = """\
00:00.0 Host bridge: Intel Corporation 440FX - 82441FX PMC [Natoma] (rev 02)
00:01.0 ISA bridge: Intel Corporation 82371SB PIIX3 ISA [Natoma/Triton II]
00:01.1 IDE interface: Intel Corporation 82371SB PIIX3 IDE [Natoma/Triton II]
00:01.3 Bridge: Intel Corporation 82371AB/EB/MB PIIX4 ACPI (rev 03)
00:02.0 VGA compatible controller: Cirrus Logic GD 5446
00:03.0 Ethernet controller: Intel Corporation 82540EM Gigabit Ethernet Controller (rev 03)
00:04.0 SCSI storage controller: LSI Logic / Symbios Logic 53c1030 PCI-X Fusion-MPT Dual Ultra320 SCSI (rev 01)
00:1f.2 SATA controller: Intel Corporation 82801 SATA Controller [AHCI mode] (rev 05)
"""

_PCI_LINES_NVME = """\
00:00.0 Host bridge: Intel Corporation Sky Lake-E DMI3 Registers (rev 04)
00:04.0 Signal processing controller: Intel Corporation Sky Lake-E CBDMA Registers (rev 04)
00:05.0 System peripheral: Intel Corporation Sky Lake-E MM e-DMI3 Registers (rev 04)
00:14.0 USB controller: Intel Corporation C620 Series Chipset Family USB 3.0 xHCI Controller (rev 09)
00:16.0 Communication controller: Intel Corporation C620 Series Chipset Family MEI Controller (rev 09)
00:17.0 SATA controller: Intel Corporation C620 Series Chipset Family SSATA Controller [AHCI mode] (rev 09)
01:00.0 Non-Volatile memory controller: Samsung Electronics Co Ltd NVMe SSD Controller SM981/PM981/PM983
02:00.0 Non-Volatile memory controller: Samsung Electronics Co Ltd NVMe SSD Controller SM981/PM981/PM983
03:00.0 Ethernet controller: Intel Corporation Ethernet Controller 10G X550T (rev 01)
04:00.0 Ethernet controller: Intel Corporation Ethernet Controller 10G X550T (rev 01)
"""


def _op_pci_success(ctx: Any) -> dict:
    h = _hash_ctx(ctx) % 2
    raw = _PCI_LINES_NVME if h == 0 else _PCI_LINES_STANDARD
    count = len([l for l in raw.splitlines() if l.strip()])
    summary = f"PCI device list retrieved ({count} device(s))."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": raw, "stderr": "", "summary": summary}


def _op_pci_failure(ctx: Any) -> dict:
    stderr = (
        "lspci: command not found\n"
        "Install pciutils to enable PCI device enumeration.\n"
    )
    summary = "PCI device query failed: lspci is not installed on this host."
    assert_no_ai_language(summary)
    return {"exit_code": 127, "stdout": "", "stderr": stderr, "summary": summary}


# ---------------------------------------------------------------------------
# Operation: usb
# ---------------------------------------------------------------------------

_USB_LINES_MINIMAL = """\
Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 002 Device 001: ID 1d6b:0001 Linux Foundation 1.1 root hub
"""

_USB_LINES_FULL = """\
Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 001 Device 002: ID 8087:0024 Intel Corp. Integrated Rate Matching Hub
Bus 001 Device 003: ID 046d:c52b Logitech, Inc. Unifying Receiver
Bus 002 Device 001: ID 1d6b:0001 Linux Foundation 1.1 root hub
Bus 002 Device 002: ID 0781:5571 SanDisk Corp. Cruzer Fit
Bus 003 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
"""


def _op_usb_success(ctx: Any) -> dict:
    h = _hash_ctx(ctx) % 2
    raw = _USB_LINES_FULL if h == 0 else _USB_LINES_MINIMAL
    count = len([l for l in raw.splitlines() if l.strip()])
    summary = f"USB device list retrieved ({count} device(s))."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": raw, "stderr": "", "summary": summary}


def _op_usb_failure(ctx: Any) -> dict:
    stderr = (
        "lsusb: command not found\n"
        "Install usbutils to enumerate USB devices.\n"
    )
    summary = "USB device query failed: lsusb is not installed on this host."
    assert_no_ai_language(summary)
    return {"exit_code": 127, "stdout": "", "stderr": stderr, "summary": summary}


# ---------------------------------------------------------------------------
# Operation: block
# ---------------------------------------------------------------------------

_BLOCK_SATA = """\
NAME        SIZE TYPE FSTYPE MOUNTPOINT
sda         500G disk
├─sda1      512M part vfat   /boot/efi
├─sda2        1G part xfs    /boot
└─sda3    498.5G part
  ├─rl-root  70G lvm  xfs    /
  ├─rl-swap   8G lvm  swap   [SWAP]
  └─rl-home 420G lvm  xfs    /home
sdb           2T disk
└─sdb1        2T part xfs    /data
"""

_BLOCK_NVME = """\
NAME          SIZE TYPE FSTYPE MOUNTPOINT
nvme0n1       1.8T disk
├─nvme0n1p1   512M part vfat   /boot/efi
├─nvme0n1p2     1G part xfs    /boot
└─nvme0n1p3   1.8T part
  ├─rl-root    50G lvm  xfs    /
  ├─rl-swap    16G lvm  swap   [SWAP]
  └─rl-data   1.7T lvm  xfs    /var/lib/pgsql
nvme1n1       1.8T disk
└─nvme1n1p1   1.8T part xfs    /backup
"""

_BLOCK_MINIMAL = """\
NAME    SIZE TYPE FSTYPE MOUNTPOINT
vda      20G disk
├─vda1  512M part vfat   /boot/efi
├─vda2    1G part xfs    /boot
└─vda3 18.5G part xfs    /
"""


def _op_block_success(ctx: Any) -> dict:
    h = _hash_ctx(ctx) % 3
    raw = [_BLOCK_NVME, _BLOCK_SATA, _BLOCK_MINIMAL][h]
    count = max(0, len([l for l in raw.splitlines() if l.strip()]) - 1)
    summary = f"Block device topology retrieved ({count} device(s))."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": raw, "stderr": "", "summary": summary}


def _op_block_failure(ctx: Any) -> dict:
    stderr = (
        "lsblk: failed to access sysfs directory: /sys/block: No such file or directory\n"
    )
    summary = "Block device query failed: sysfs is not accessible (exit 32)."
    assert_no_ai_language(summary)
    return {"exit_code": 32, "stdout": "", "stderr": stderr, "summary": summary}


# ---------------------------------------------------------------------------
# Operation: sensors
# ---------------------------------------------------------------------------

_SENSORS_CORETEMP = """\
coretemp-isa-0000
Adapter: ISA adapter
Package id 0:  +42.0°C  (high = +87.0°C, crit = +97.0°C)
Core 0:        +40.0°C  (high = +87.0°C, crit = +97.0°C)
Core 1:        +41.0°C  (high = +87.0°C, crit = +97.0°C)
Core 2:        +39.0°C  (high = +87.0°C, crit = +97.0°C)
Core 3:        +42.0°C  (high = +87.0°C, crit = +97.0°C)

nct6792-isa-0290
Adapter: ISA adapter
in0:            +0.90 V  (min =  +0.00 V, max =  +1.74 V)
fan1:         1260 RPM  (min =    0 RPM)
fan2:         1380 RPM  (min =    0 RPM)
SYSTIN:        +34.0°C  (high =  +0.0°C, hyst =  +0.0°C)  ALARM
CPUTIN:        +44.0°C  (high = +80.0°C, hyst = +75.0°C)
AUXTIN0:      +105.0°C  (high = +80.0°C, hyst = +75.0°C)  ALARM
"""

_SENSORS_HOT = """\
coretemp-isa-0000
Adapter: ISA adapter
Package id 0:  +81.0°C  (high = +87.0°C, crit = +97.0°C)
Core 0:        +79.0°C  (high = +87.0°C, crit = +97.0°C)
Core 1:        +80.0°C  (high = +87.0°C, crit = +97.0°C)
Core 2:        +81.0°C  (high = +87.0°C, crit = +97.0°C)
Core 3:        +82.0°C  (high = +87.0°C, crit = +97.0°C)  HIGH

nct6792-isa-0290
Adapter: ISA adapter
fan1:         2840 RPM  (min =    0 RPM)
fan2:         2780 RPM  (min =    0 RPM)
CPUTIN:        +84.0°C  (high = +80.0°C, hyst = +75.0°C)  ALARM
"""


def _op_sensors_success(ctx: Any) -> dict:
    h = _hash_ctx(ctx) % 2
    raw = _SENSORS_HOT if h == 0 else _SENSORS_CORETEMP
    alarm = "ALARM" in raw or "HIGH" in raw
    if alarm:
        summary = "Hardware sensor readings retrieved; at least one temperature threshold exceeded."
    else:
        summary = "Hardware sensor readings retrieved; all temperatures within normal range."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": raw, "stderr": "", "summary": summary}


def _op_sensors_failure_not_found(ctx: Any) -> dict:
    stderr = "bash: sensors: command not found\n"
    summary = "Sensor readings failed: the sensors command is not installed (lm_sensors package missing)."
    assert_no_ai_language(summary)
    return {"exit_code": 127, "stdout": "", "stderr": stderr, "summary": summary}


def _op_sensors_failure_no_sensors(ctx: Any) -> dict:
    stdout = "No sensors found!\nMake sure you loaded all the kernel drivers you need.\n"
    summary = "Sensor readings completed but no hardware sensors were detected on this host."
    assert_no_ai_language(summary)
    return {"exit_code": 1, "stdout": stdout, "stderr": "", "summary": summary}


# ---------------------------------------------------------------------------
# Operation: summary (combined cpu + memory + block)
# ---------------------------------------------------------------------------


def _op_summary_success(ctx: Any) -> dict:
    cores = _cpu_cores(ctx)
    threads = cores * 2
    total_gb = _mem_gb(ctx)
    used_gb = max(1, int(total_gb * 0.45))
    h = _hash_ctx(ctx) % 3
    blk = [_BLOCK_NVME, _BLOCK_SATA, _BLOCK_MINIMAL][h]
    blk_count = max(0, len([l for l in blk.splitlines() if l.strip()]) - 1)

    cpu_block = (
        f"Architecture:            x86_64\n"
        f"CPU(s):                  {threads}\n"
        f"  Model name:            Intel(R) Xeon(R) Gold 6248R CPU @ 3.00GHz\n"
        f"  Thread(s) per core:    2\n"
        f"  Core(s) per socket:    {cores // (2 if cores >= 16 else 1)}\n"
        f"  Socket(s):             {2 if cores >= 16 else 1}\n"
        f"  CPU MHz:               3000.000\n"
    )
    mem_block = (
        f"               total        used        free      shared  buff/cache   available\n"
        f"Mem:            {total_gb}Gi       {used_gb}Gi       {total_gb - used_gb}Gi"
        f"      148Mi       1Gi       {total_gb - used_gb}Gi\n"
        f"Swap:           8Gi          0B       8Gi\n"
    )

    combined = (
        "=== CPU ===\n" + cpu_block.rstrip() +
        "\n\n=== MEMORY ===\n" + mem_block.rstrip() +
        "\n\n=== BLOCK DEVICES ===\n" + blk.rstrip() + "\n"
    )
    summary = (
        f"Hardware summary retrieved: {threads} logical processors, "
        f"{total_gb} GiB RAM ({used_gb} GiB in use), "
        f"{blk_count} block device(s) visible."
    )
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": combined, "stderr": "", "summary": summary}


def _op_summary_partial_failure(ctx: Any) -> dict:
    """Simulate lscpu missing but memory + block succeed."""
    total_gb = _mem_gb(ctx)
    used_gb = max(1, int(total_gb * 0.45))
    h = _hash_ctx(ctx) % 3
    blk = [_BLOCK_NVME, _BLOCK_SATA, _BLOCK_MINIMAL][h]

    mem_block = (
        f"               total        used        free      shared  buff/cache   available\n"
        f"Mem:            {total_gb}Gi       {used_gb}Gi       {total_gb - used_gb}Gi"
        f"      148Mi       1Gi       {total_gb - used_gb}Gi\n"
        f"Swap:           8Gi          0B       8Gi\n"
    )
    combined = (
        "=== MEMORY ===\n" + mem_block.rstrip() +
        "\n\n=== BLOCK DEVICES ===\n" + blk.rstrip() + "\n"
    )
    stderr = "lscpu: command not found\n"
    summary = "Hardware summary partially retrieved: CPU data unavailable (lscpu missing), memory and block devices retrieved (worst exit 127)."
    assert_no_ai_language(summary)
    return {"exit_code": 127, "stdout": combined, "stderr": stderr, "summary": summary}


def _op_gpu_success(ctx: Any) -> dict:
    raw = ("index, name, memory.total [MiB], memory.used [MiB], utilization.gpu [%], driver_version\n"
           "0, NVIDIA L4, 23034 MiB, 412 MiB, 3 %, 550.90.07\n")
    summary = "1 GPU(s) detected."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": raw, "stderr": "", "summary": summary}


def _op_gpu_failure(ctx: Any) -> dict:
    summary = "No GPU found: no NVIDIA driver and no display-class PCI device."
    assert_no_ai_language(summary)
    return {"exit_code": 1, "stdout": "", "stderr": "nvidia-smi: command not found\n", "summary": summary}


def _op_memory_modules_success(ctx: Any) -> dict:
    raw = ("DIMM_A1: 32 GB DDR4 DIMM, rated 3200 MT/s, running 2933 MT/s, maker Samsung, part M393A4K40DB3-CWE, rank 2\n"
           "DIMM_B1: 32 GB DDR4 DIMM, rated 3200 MT/s, running 2933 MT/s, maker Samsung, part M393A4K40DB3-CWE, rank 2\n")
    summary = "2 memory module(s) installed of 4 slot(s)."
    assert_no_ai_language(summary)
    return {"exit_code": 0, "stdout": raw, "stderr": "", "summary": summary}


def _op_memory_modules_failure(ctx: Any) -> dict:
    summary = "Memory module details need firmware (DMI) table access, which is not available here."
    assert_no_ai_language(summary)
    return {"exit_code": 1, "stdout": "", "stderr": "/dev/mem: Permission denied\n", "summary": summary}


# ---------------------------------------------------------------------------
# Dispatch table — keyed on (op, variant)
# variant=0 → success, variant=1 → first failure, variant=2 → second failure
# ---------------------------------------------------------------------------

_SUCCESS_HANDLERS = {
    "cpu":     _op_cpu_success,
    "memory":  _op_memory_success,
    "pci":     _op_pci_success,
    "gpu":     _op_gpu_success,
    "memory_modules": _op_memory_modules_success,
    "usb":     _op_usb_success,
    "block":   _op_block_success,
    "sensors": _op_sensors_success,
    "summary": _op_summary_success,
}

_FAILURE_HANDLERS = {
    "cpu":     [_op_cpu_failure],
    "memory":  [_op_memory_failure],
    "pci":     [_op_pci_failure],
    "gpu":     [_op_gpu_failure],
    "memory_modules": [_op_memory_modules_failure],
    "usb":     [_op_usb_failure],
    "block":   [_op_block_failure],
    "sensors": [_op_sensors_failure_not_found, _op_sensors_failure_no_sensors],
    "summary": [_op_summary_partial_failure],
}

# Real op names as declared in core/tools/hardware.py
_REAL_OPS = frozenset(_SUCCESS_HANDLERS.keys())

# Probability of returning a failure case (hash-based, deterministic).
# Roughly 20% of calls return a failure to balance the corpus.
_FAILURE_THRESHOLD = 0.20


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def simulate_hardware(op: str, args: dict, ctx: Any) -> dict:
    """Return a realistic Rocky Linux 9 ToolResult dict for the given hardware op.

    Parameters
    ----------
    op   : hardware operation name (cpu, memory, pci, usb, block, sensors, summary)
    args : argument dict (all hardware ops take no required args; {} is fine)
    ctx  : system context (str, dict, or snapshot object)

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str)
    The summary is guaranteed I2-clean.

    Raises
    ------
    ValueError if op is not a known hardware operation.
    """
    if op not in _REAL_OPS:
        raise ValueError(
            f"simulate_hardware: unknown op '{op}'. "
            f"Known ops: {sorted(_REAL_OPS)}"
        )

    # Deterministic failure injection: use a hash of (op, ctx) so the same
    # (op, ctx) pair always returns the same variant, giving reproducible traces.
    h = _hash_ctx(ctx) ^ hash(op)
    failure_handlers = _FAILURE_HANDLERS[op]
    failure_roll = (h % 1000) / 1000.0

    if failure_roll < _FAILURE_THRESHOLD and failure_handlers:
        # Pick which failure handler deterministically.
        idx = (h // 1000) % len(failure_handlers)
        result = failure_handlers[idx](ctx)
    else:
        result = _SUCCESS_HANDLERS[op](ctx)

    # Final shape assertion — ensures the 4-key contract is always met.
    assert set(result.keys()) == {"exit_code", "stdout", "stderr", "summary"}, (
        f"simulate_hardware({op!r}) returned wrong keys: {set(result.keys())}"
    )
    return result
