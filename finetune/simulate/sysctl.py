"""finetune/simulate/sysctl.py — Rocky Linux 9 output simulator for the 'sysctl' tool.

Public API
----------
simulate_sysctl(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 4 real operations declared in core/tools/sysctl.py
           (list, get, set, persist)
    args : dict of op arguments (may be {} for all-optional ops)
    ctx  : system context string from make_context(), OR a profile dict —
           both forms supported via isinstance.

Realism model
-------------
* list: returns a representative subset of real sysctl -a output on Rocky 9
  (kernel.*, vm.*, net.*, fs.* namespaces).
* get: returns realistic output for known keys; unknown key → sysctl: cannot
  stat /proc/sys/<path>: No such file or directory (exit 255).
* set: success for valid-looking keys; failure (exit 1) for keys that contain
  "invalid", "bogus", "noexist", or whose hash-based scatter triggers it.
* persist: two-phase — tee write + sysctl --system reload, both can fail.

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent language).

INV-read-only-core: imports NOTHING from core/ directly.
Does not import finetune.coreimports (avoids circular deps when Phase-13
__init__ imports simulators before coreimports is fully settled).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


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


def _key_invalid(key: str) -> bool:
    """Deterministically decide if a key should trigger a not-found error."""
    lower = key.lower()
    for tok in ("invalid", "bogus", "noexist", "notfound", "missing", "fake"):
        if tok in lower:
            return True
    # A key with no dot is not a valid sysctl path
    if "." not in key:
        return True
    # Hash-based 15% scatter
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return h % 20 == 0


# Known kernel parameter values for realistic simulation
_KNOWN_VALUES: dict[str, str] = {
    "kernel.hostname":                    "rocky-host",
    "kernel.ostype":                      "Linux",
    "kernel.osrelease":                   "5.14.0-427.13.1.el9_4.x86_64",
    "kernel.version":                     "#1 SMP PREEMPT_DYNAMIC",
    "kernel.panic":                       "0",
    "kernel.sysrq":                       "16",
    "kernel.core_pattern":                "core",
    "kernel.modules_disabled":            "0",
    "kernel.kexec_load_disabled":         "0",
    "kernel.pid_max":                     "4194304",
    "kernel.threads-max":                 "63728",
    "kernel.ngroups_max":                 "65536",
    "kernel.randomize_va_space":          "2",
    "kernel.dmesg_restrict":              "1",
    "kernel.kptr_restrict":               "1",
    "net.ipv4.ip_forward":                "0",
    "net.ipv4.conf.all.rp_filter":        "1",
    "net.ipv4.conf.default.rp_filter":    "1",
    "net.ipv4.tcp_syncookies":            "1",
    "net.ipv4.conf.all.accept_redirects": "0",
    "net.ipv4.conf.all.send_redirects":   "0",
    "net.ipv4.tcp_fin_timeout":           "60",
    "net.ipv4.tcp_keepalive_time":        "7200",
    "net.ipv4.tcp_max_syn_backlog":       "4096",
    "net.ipv6.conf.all.disable_ipv6":     "0",
    "net.core.somaxconn":                 "4096",
    "net.core.netdev_max_backlog":        "1000",
    "vm.swappiness":                      "60",
    "vm.overcommit_memory":               "0",
    "vm.overcommit_ratio":                "50",
    "vm.dirty_ratio":                     "20",
    "vm.dirty_background_ratio":          "10",
    "vm.vfs_cache_pressure":              "100",
    "fs.file-max":                        "9223372036854775807",
    "fs.inotify.max_user_watches":        "8192",
    "fs.inotify.max_user_instances":      "128",
    "fs.suid_dumpable":                   "0",
}

# Representative sysctl -a output (subset for simulation)
_LIST_OUTPUT = """\
kernel.acct = 4 2 30
kernel.core_pattern = core
kernel.core_pipe_limit = 0
kernel.core_uses_pid = 0
kernel.ctrl-alt-del = 0
kernel.dmesg_restrict = 1
kernel.hostname = rocky-host
kernel.kexec_load_disabled = 0
kernel.kptr_restrict = 1
kernel.modules_disabled = 0
kernel.ngroups_max = 65536
kernel.osrelease = 5.14.0-427.13.1.el9_4.x86_64
kernel.ostype = Linux
kernel.panic = 0
kernel.pid_max = 4194304
kernel.randomize_va_space = 2
kernel.sysrq = 16
kernel.threads-max = 63728
fs.file-max = 9223372036854775807
fs.inotify.max_user_instances = 128
fs.inotify.max_user_watches = 8192
fs.suid_dumpable = 0
net.core.netdev_max_backlog = 1000
net.core.somaxconn = 4096
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.rp_filter = 1
net.ipv4.ip_forward = 0
net.ipv4.tcp_fin_timeout = 60
net.ipv4.tcp_keepalive_time = 7200
net.ipv4.tcp_max_syn_backlog = 4096
net.ipv4.tcp_syncookies = 1
net.ipv6.conf.all.disable_ipv6 = 0
vm.dirty_background_ratio = 10
vm.dirty_ratio = 20
vm.overcommit_memory = 0
vm.overcommit_ratio = 50
vm.swappiness = 60
vm.vfs_cache_pressure = 100
"""


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    count = _LIST_OUTPUT.count("\n")
    return _make_result(
        exit_code=0,
        stdout=_LIST_OUTPUT,
        stderr="",
        summary=f"Listed {count} kernel parameters.",
    )


def _sim_get(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    key = args.get("key", "kernel.hostname")

    if _key_invalid(key):
        # Convert dotted key to /proc/sys path for realistic error
        proc_path = "/proc/sys/" + key.replace(".", "/")
        stderr = (
            f"sysctl: cannot stat {proc_path}: No such file or directory\n"
        )
        return _make_result(
            exit_code=255,
            stdout="",
            stderr=stderr,
            summary=f"Kernel parameter '{key}' not found.",
        )

    value = _KNOWN_VALUES.get(key)
    if value is None:
        # Derive a plausible value from hash for unknown-but-valid-looking keys
        h = int(hashlib.md5(key.encode()).hexdigest(), 16)
        value = str(h % 32768)

    stdout = f"{key} = {value}\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Kernel parameter '{key}' = '{value}'.",
    )


def _sim_set(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    key = args.get("key", "vm.swappiness")
    value = args.get("value", "60")

    if _key_invalid(key):
        stderr = (
            f"sysctl: setting key \"{key}\": No such file or directory\n"
        )
        return _make_result(
            exit_code=255,
            stdout="",
            stderr=stderr,
            summary=f"Failed to set kernel parameter '{key}': key not found.",
        )

    # Hash-based failure scatter (~10%) for write errors
    h = int(hashlib.md5((key + "set").encode()).hexdigest(), 16)
    if h % 10 == 0:
        stderr = (
            f"sysctl: setting key \"{key}\": Read-only file system\n"
        )
        return _make_result(
            exit_code=255,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to set kernel parameter '{key}' to '{value}': "
                f"read-only file system."
            ),
        )

    stdout = f"{key} = {value}\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Kernel parameter '{key}' set to '{value}' (runtime only; not persistent).",
    )


def _sim_persist(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    key = args.get("key", "vm.swappiness")
    value = args.get("value", "60")
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", key)
    filename = args.get("filename") or f"99-{safe_name}.conf"
    if "/" in filename:
        filename = filename.rsplit("/", 1)[-1]
    filepath = f"/etc/sysctl.d/{filename}"

    if _key_invalid(key):
        stderr = f"tee: {filepath}: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to write '{key} = {value}' to {filepath}: permission denied.",
        )

    # Simulate tee writing the file
    tee_stdout = f"{key} = {value}\n"

    # Simulate sysctl --system reload output
    reload_stdout = (
        f"* Applying /usr/lib/sysctl.d/10-default.conf ...\n"
        f"* Applying /etc/sysctl.d/99-sysctl.conf ...\n"
        f"* Applying {filepath} ...\n"
        f"{key} = {value}\n"
        f"* Applying /etc/sysctl.conf ...\n"
    )

    return _make_result(
        exit_code=0,
        stdout=tee_stdout + reload_stdout,
        stderr="",
        summary=f"Kernel parameter '{key}' set to '{value}' and persisted to {filepath}.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list":    _sim_list,
    "get":     _sim_get,
    "set":     _sim_set,
    "persist": _sim_persist,
}


def simulate_sysctl(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'sysctl' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 4 real ops (list, get, set, persist).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either a snapshot_text str or a profile dict.

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
            f"simulate_sysctl: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
