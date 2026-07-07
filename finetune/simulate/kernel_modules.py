"""finetune/simulate/kernel_modules.py — Rocky Linux 9 output simulator for the 'kernel_modules' tool.

Public API
----------
simulate_kernel_modules(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 5 real operations declared in core/tools/kernel_modules.py
           (lsmod, modinfo, modprobe, rmmod, modules-load.d)
    args : dict of op arguments (may be {} for lsmod which takes no args)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Checked via isinstance; both forms are supported.

Realism model
-------------
* Exit codes mirror real lsmod/modinfo/modprobe/rmmod behaviour on Rocky 9.
* Failure triggers are deterministic: module names containing "notfound",
  "noexist", "broken", "bogus", or "missing" produce realistic error output.
  A hash-based ~15% scatter adds variety among otherwise-plausible names.
* The lsmod simulator generates a realistic kernel module table with a set of
  common Rocky 9 / RHEL 9 modules.
* The rmmod simulator produces "in use" errors for modules that appear in the
  module table with a non-zero "used by" count.

I2 compliance
-------------
All `summary` strings are I2-clean (no AI/LLM/model/agent/agentic/neural/
inference language).

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (circular-dep guard).
The ToolResult shape is mirrored as a plain dict — no class dependency.
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
    """Extract hostname from ctx for realistic output."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky9.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky9"


def _module_not_found(module: str) -> bool:
    """Deterministically decide whether a module name should trigger a not-found error.

    Triggers: a known bad token in the name, OR a hash-based 15% scatter.
    """
    lower = module.lower()
    for tok in ("notfound", "noexist", "broken", "bogus", "missing", "fake", "invalid"):
        if tok in lower:
            return True
    h = int(hashlib.md5(module.encode()).hexdigest(), 16)
    return h % 20 == 0


# Known Rocky Linux 9 kernel module table (module, size, used_by_count, used_by_names)
_KNOWN_MODULES: list[tuple[str, int, int, str]] = [
    ("nf_conntrack",     180224, 3, "nf_nat,xt_conntrack,nft_ct"),
    ("nf_nat",           53248,  1, "xt_MASQUERADE"),
    ("nft_ct",           20480,  0, ""),
    ("xt_conntrack",     16384,  1, ""),
    ("br_netfilter",     28672,  0, ""),
    ("bridge",           229376, 1, "br_netfilter"),
    ("overlay",          139264, 0, ""),
    ("veth",             28672,  0, ""),
    ("iptable_nat",      16384,  1, ""),
    ("nf_defrag_ipv4",   16384,  1, "nf_conntrack"),
    ("nf_defrag_ipv6",   20480,  1, "nf_conntrack"),
    ("ip_tables",        32768,  2, "iptable_nat,iptable_filter"),
    ("x_tables",         45056,  4, "ip_tables,xt_conntrack,nf_nat,xt_MASQUERADE"),
    ("dm_mirror",        28672,  0, ""),
    ("dm_region_hash",   20480,  1, "dm_mirror"),
    ("dm_log",           20480,  2, "dm_mirror,dm_region_hash"),
    ("dm_mod",           176128, 4, "dm_mirror,dm_log,dm_region_hash"),
    ("xfs",             1835008, 1, ""),
    ("libcrc32c",        16384,  3, "nf_conntrack,nf_nat,xfs"),
    ("scsi_mod",        262144,  3, "sd_mod,scsi_transport_spi"),
    ("sd_mod",           65536,  3, ""),
    ("virtio_blk",       20480,  3, ""),
    ("virtio_net",       57344,  0, ""),
    ("virtio_pci",       28672,  0, ""),
    ("serio_raw",        16384,  0, ""),
    ("8021q",            36864,  0, ""),
    ("bonding",         176128,  0, ""),
    ("tun",              53248,  2, ""),
    ("dummy",            16384,  0, ""),
    ("kvm",             946176,  1, "kvm_intel"),
    ("kvm_intel",       393216,  0, ""),
    ("drm",            548864,   4, "drm_kms_helper"),
    ("fuse",           151552,   1, ""),
    ("bpfilter",         16384,  0, ""),
    ("sunrpc",          626688,  1, "nfs"),
]


def _lsmod_table() -> str:
    """Generate a realistic lsmod output table."""
    header = f"{'Module':<30} {'Size':>8}  {'Used by'}"
    lines = [header]
    for name, size, used, by in _KNOWN_MODULES:
        col = f"{used}" if not by else f"{used} {by}"
        lines.append(f"{name:<30} {size:>8}  {col}")
    return "\n".join(lines) + "\n"


def _modinfo_block(module: str) -> str:
    """Generate a realistic modinfo output block."""
    kver = "5.14.0-427.13.1.el9_4.x86_64"
    base = module.replace("-", "_")
    return (
        f"filename:       /lib/modules/{kver}/kernel/net/netfilter/{base}.ko.xz\n"
        f"description:    {base.capitalize()} kernel support\n"
        f"license:        GPL\n"
        f"version:        {kver}\n"
        f"srcversion:     A1B2C3D4E5F6A7B8C9D0E1F\n"
        f"depends:        libcrc32c\n"
        f"retpoline:      Y\n"
        f"intree:         Y\n"
        f"name:           {base}\n"
        f"vermagic:       {kver} SMP preempt mod_unload modversions\n"
    )


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_lsmod(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    stdout = _lsmod_table()
    count = len(_KNOWN_MODULES)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Listed {count} loaded kernel modules.",
    )


def _sim_modinfo(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module = args.get("module", "unknown")

    if _module_not_found(module):
        stderr = f"modinfo: ERROR: Module {module} not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Module '{module}' was not found in the kernel module database.",
        )

    stdout = _modinfo_block(module)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Module information retrieved for '{module}'.",
    )


def _sim_modprobe(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module = args.get("module", "unknown")

    if _module_not_found(module):
        stderr = (
            f"modprobe: FATAL: Module {module} not found "
            f"in directory /lib/modules/5.14.0-427.13.1.el9_4.x86_64\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to load kernel module '{module}': module not found.",
        )

    # Hash-based scatter: a few modules fail with a dependency error
    h = int(hashlib.md5((module + "probe").encode()).hexdigest(), 16)
    if h % 15 == 0:
        stderr = (
            f"modprobe: ERROR: could not insert '{module}': "
            f"Operation not permitted\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to load kernel module '{module}' (exit 1).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Kernel module '{module}' loaded.",
    )


def _sim_rmmod(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module = args.get("module", "unknown")

    if _module_not_found(module):
        stderr = f"rmmod: ERROR: Module {module} is not currently loaded\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove kernel module '{module}': module is not loaded.",
        )

    # Check if the module appears in the known table as "in use"
    for name, _size, used, by in _KNOWN_MODULES:
        if name == module and used > 0:
            stderr = (
                f"rmmod: ERROR: Module {module} is in use by: {by}\n"
            )
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=stderr,
                summary=(
                    f"Failed to remove kernel module '{module}': "
                    f"the module is in use and cannot be unloaded."
                ),
            )

    # Hash-based scatter: some modules return "in use" generically
    h = int(hashlib.md5((module + "rmmod").encode()).hexdigest(), 16)
    if h % 8 == 0:
        stderr = f"rmmod: ERROR: Module {module} is in use\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to remove kernel module '{module}': "
                f"the module is in use."
            ),
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Kernel module '{module}' removed.",
    )


def _sim_modules_load_d(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module = args.get("module", "unknown")
    raw_filename = args.get("filename") or module
    safe_filename = raw_filename.replace("/", "_").replace("\\", "_")
    conf_path = f"/etc/modules-load.d/{safe_filename}.conf"

    # Simulate a permission-denied failure for root-required paths in non-root ctx
    h = int(hashlib.md5((module + "mld").encode()).hexdigest(), 16)
    if h % 18 == 0:
        stderr = f"tee: {conf_path}: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to write module '{module}' to '{conf_path}' (exit 1)."
            ),
        )

    stdout = module + "\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Module '{module}' written to '{conf_path}' for persistent loading at boot.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "lsmod":          _sim_lsmod,
    "modinfo":        _sim_modinfo,
    "modprobe":       _sim_modprobe,
    "rmmod":          _sim_rmmod,
    "modules-load.d": _sim_modules_load_d,
}


def simulate_kernel_modules(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'kernel_modules' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; one of: lsmod, modinfo, modprobe, rmmod, modules-load.d.
    args : argument dict (may be {} for lsmod; other ops need at least 'module').
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with host information.

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
            f"simulate_kernel_modules: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
