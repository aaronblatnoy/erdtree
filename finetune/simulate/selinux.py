"""finetune/simulate/selinux.py — Rocky Linux 9 output simulator for the 'selinux' tool.

Public API
----------
simulate_selinux(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 17 real operations declared in core/tools/selinux.py
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict.  Both forms are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real command behaviour on Rocky Linux 9:
    0  — success
    1  — general error (mapping conflict, policy violation, permission error)
    2  — command syntax error
  127  — binary not found (sestatus/semanage not installed)
* stdout/stderr reflect real tool output formats: sestatus column layout,
  semanage tabular output, restorecon relabel lines, etc.
* Failure branches are deterministic via hash-based scatter so traces teach
  error handling.

I2 compliance
-------------
All `summary` strings are I2-clean: no AI/LLM/model/agent/agentic/neural language.

INV-read-only-core: imports NOTHING from core/ or finetune.coreimports.
The 4-key dict mirrors ToolResult with no class dependency.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _hash_fail(key: str, mod: int = 10, bucket: int = 0) -> bool:
    """Deterministic failure scatter: returns True ~(1/mod) of the time."""
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return h % mod == bucket


def _bool_known(boolean: str) -> bool:
    """Return False for clearly bogus boolean names."""
    lower = boolean.lower()
    for tok in ("notfound", "noexist", "bogus", "missing", "badname"):
        if tok in lower:
            return False
    return True


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------


def _sim_sestatus(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    # Occasionally simulate not-installed (exit 127)
    if _hash_fail("sestatus", mod=30, bucket=0):
        return _make_result(
            127, "", "bash: sestatus: command not found\n",
            "sestatus binary not found; policycoreutils may not be installed.",
        )
    stdout = (
        "SELinuxfs mount:                /sys/fs/selinux\n"
        "SELinux mount point:            /sys/fs/selinux\n"
        "SELinuxfs mount:                /sys/fs/selinux\n"
        "SELinux status:                 enabled\n"
        "SELinuxfs mount:                /sys/fs/selinux\n"
        "SELinux status:                 enabled\n"
        "SELinuxfs mount:                /sys/fs/selinux\n"
        "SELinux status:                 enabled\n"
        "SELinuxfs mount:                /sys/fs/selinux\n"
        "SELinux status:                 enabled\n"
        "SELinuxfs mount:                /sys/fs/selinux\n"
        "SELinux status:                 enabled\n"
        "SELinuxfs mount:                /sys/fs/selinux\n"
        "SELinux status:                 enabled\n"
        "SELinuxfs mount:                /sys/fs/selinux\n"
        "SELinux status:                 enabled\n"
        "SELinuxfs mount:                /sys/fs/selinux\n"
    )
    # Build clean realistic output
    stdout = (
        "SELinux status:                 enabled\n"
        "SELinuxfs mount:                /sys/fs/selinux\n"
        "SELinux mount point:            /sys/fs/selinux\n"
        "Loaded policy name:             targeted\n"
        "Current mode:                   enforcing\n"
        "Mode from config file:          enforcing\n"
        "Policy MLS status:              enabled\n"
        "Policy deny_unknown status:     allowed\n"
        "Memory protection checking:     actual (secure)\n"
        "Max kernel policy version:      33\n"
    )
    return _make_result(0, stdout, "", "Status retrieved.")


def _sim_getsebool(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    boolean = args.get("boolean", "unknown_bool")
    if not _bool_known(boolean):
        stderr = f"getsebool: error: {boolean}: No such file or directory\n"
        return _make_result(1, "", stderr, f"Boolean '{boolean}' not found.")

    # Simulate on/off based on hash
    val = "on" if int(hashlib.md5(boolean.encode()).hexdigest(), 16) % 2 == 0 else "off"
    stdout = f"{boolean} --> {val}\n"
    return _make_result(0, stdout, "", f"Boolean '{boolean}' value retrieved.")


def _sim_getenforce(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    # Check ctx for enforcing state
    if isinstance(ctx, dict):
        mode = ctx.get("selinux_mode", "Enforcing")
    elif isinstance(ctx, str) and "permissive" in ctx.lower():
        mode = "Permissive"
    else:
        mode = "Enforcing"
    return _make_result(0, f"{mode}\n", "", "Enforcement mode retrieved.")


def _sim_setenforce(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    mode = args.get("mode", "1")
    mode_label = "permissive" if mode == "0" else "enforcing"
    # setenforce 0 requires root; simulate permission error ~20% of time
    if _hash_fail(f"setenforce{mode}", mod=5, bucket=0):
        stderr = "setenforce: SELinux is disabled\n"
        return _make_result(
            1, "", stderr,
            f"Failed to set enforcement to {mode_label}; check that enforcement is not disabled in config.",
        )
    return _make_result(0, "", "", f"Enforcement set to {mode_label}.")


def _sim_setsebool(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    boolean = args.get("boolean", "unknown_bool")
    value = args.get("value", "on")
    persist = bool(args.get("persist", False))
    persist_note = " (persistent)" if persist else " (runtime only)"

    if not _bool_known(boolean):
        stderr = f"setsebool: error: No such file or directory: {boolean}\n"
        return _make_result(1, "", stderr, f"Failed to set boolean '{boolean}'.")

    if _hash_fail(f"setsebool{boolean}{value}", mod=15, bucket=0):
        stderr = "setsebool: error: Could not change active booleans.\n"
        return _make_result(
            1, "", stderr,
            f"Failed to set boolean '{boolean}' to {value}; check that policy allows this change.",
        )
    return _make_result(0, "", "", f"Boolean '{boolean}' set to {value}{persist_note}.")


def _sim_semanage_fcontext_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    stdout = (
        "\nSELinux fcontext                                   type               Context\n\n"
        "/                                                  directory          system_u:object_r:root_t:s0\n"
        "/.*                                                all files          system_u:object_r:default_t:s0\n"
        "/bin(/.*)?                                         all files          system_u:object_r:bin_t:s0\n"
        "/boot(/.*)?                                        all files          system_u:object_r:boot_t:s0\n"
        "/dev(/.*)?                                         all files          system_u:object_r:device_t:s0\n"
        "/etc(/.*)?                                         all files          system_u:object_r:etc_t:s0\n"
        "/home(/.*)?                                        all files          system_u:object_r:user_home_dir_t:s0\n"
        "/srv/www(/.*)?                                     all files          system_u:object_r:httpd_sys_content_t:s0\n"
        "/usr(/.*)?                                         all files          system_u:object_r:usr_t:s0\n"
        "/var(/.*)?                                         all files          system_u:object_r:var_t:s0\n"
    )
    return _make_result(0, stdout, "", "File context mappings listed.")


def _sim_semanage_fcontext_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    fcontext_type = args.get("fcontext_type", "httpd_sys_content_t")
    fcontext_spec = args.get("fcontext_spec", "/srv/app(/.*)?")

    if _hash_fail(f"fcontext_add{fcontext_spec}", mod=12, bucket=0):
        stderr = (
            f"ValueError: File context for {fcontext_spec!r} already defined.\n"
        )
        return _make_result(
            1, "", stderr,
            f"Failed to add file context '{fcontext_spec}'; mapping may already exist.",
        )
    return _make_result(
        0, "", "",
        f"File context '{fcontext_spec}' mapped to type '{fcontext_type}'.",
    )


def _sim_semanage_fcontext_delete(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    fcontext_spec = args.get("fcontext_spec", "/srv/app(/.*)?")

    if _hash_fail(f"fcontext_del{fcontext_spec}", mod=12, bucket=0):
        stderr = f"ValueError: File context for {fcontext_spec!r} is not defined.\n"
        return _make_result(
            1, "", stderr,
            f"Failed to delete file context '{fcontext_spec}'; no such mapping found.",
        )
    return _make_result(0, "", "", f"File context mapping '{fcontext_spec}' deleted.")


def _sim_semanage_port_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    stdout = (
        "\nSELinux Port Type              Proto    Port Number\n\n"
        "afs3_callback_port_t           tcp      7001\n"
        "afs3_callback_port_t           udp      7001\n"
        "http_port_t                    tcp      80, 81, 443, 488, 8008, 8009, 8443, 9000\n"
        "http_port_t                    udp      80\n"
        "mysqld_port_t                  tcp      1186, 3306, 63132-63164\n"
        "postgresql_port_t              tcp      5432\n"
        "redis_port_t                   tcp      6379\n"
        "ssh_port_t                     tcp      22\n"
        "smtp_port_t                    tcp      25, 465, 587\n"
        "unreserved_port_t              tcp      1024-32767\n"
        "unreserved_port_t              udp      1024-32767\n"
    )
    return _make_result(0, stdout, "", "Port label mappings listed.")


def _sim_semanage_port_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    port_type = args.get("port_type", "http_port_t")
    protocol = args.get("protocol", "tcp")
    port = args.get("port", "8080")

    if _hash_fail(f"port_add{port}{protocol}", mod=12, bucket=0):
        stderr = (
            f"ValueError: Port {port}/{protocol} already defined in policy, "
            "add it using a modification.\n"
        )
        return _make_result(
            1, "", stderr,
            f"Failed to add port label {port}/{protocol}; port may already be defined.",
        )
    return _make_result(0, "", "", f"Port {port}/{protocol} labeled as '{port_type}'.")


def _sim_semanage_port_delete(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    protocol = args.get("protocol", "tcp")
    port = args.get("port", "8080")

    if _hash_fail(f"port_del{port}{protocol}", mod=12, bucket=0):
        stderr = (
            f"ValueError: Port {port}/{protocol} is not defined in policy.\n"
        )
        return _make_result(
            1, "", stderr,
            f"Failed to delete port label for {port}/{protocol}; not defined in policy.",
        )
    return _make_result(0, "", "", f"Port label for {port}/{protocol} deleted.")


def _sim_semanage_user_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    stdout = (
        "\n                Labeling   MLS/       MLS/\n"
        "SELinux User    Prefix     MCS Level  MCS Range             SELinux Roles\n\n"
        "guest_u         user       s0         s0                    guest_r\n"
        "root            user       s0         s0-s0:c0.c1023        staff_r sysadm_r system_r unconfined_r\n"
        "staff_u         user       s0         s0-s0:c0.c1023        staff_r sysadm_r system_r unconfined_r\n"
        "sysadm_u        user       s0         s0-s0:c0.c1023        sysadm_r\n"
        "system_u        user       s0         s0-s0:c0.c1023        system_r unconfined_r\n"
        "unconfined_u    user       s0         s0-s0:c0.c1023        system_r unconfined_r\n"
        "user_u          user       s0         s0                    user_r\n"
        "xguest_u        user       s0         s0                    xguest_r\n"
    )
    return _make_result(0, stdout, "", "User mappings listed.")


def _sim_semanage_user_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    seuser = args.get("seuser", "newuser_u")
    roles = args.get("roles", "user_r")

    if _hash_fail(f"user_add{seuser}", mod=12, bucket=0):
        stderr = f"ValueError: SELinux user {seuser!r} is already defined.\n"
        return _make_result(
            1, "", stderr,
            f"Failed to add user '{seuser}'; user may already be defined.",
        )
    return _make_result(0, "", "", f"User '{seuser}' added with roles '{roles}'.")


def _sim_semanage_user_delete(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    seuser = args.get("seuser", "olduser_u")

    if _hash_fail(f"user_del{seuser}", mod=12, bucket=0):
        stderr = f"ValueError: SELinux user {seuser!r} is not defined.\n"
        return _make_result(
            1, "", stderr,
            f"Failed to delete user mapping '{seuser}'; user not found in policy.",
        )
    return _make_result(0, "", "", f"User mapping '{seuser}' deleted.")


def _sim_restorecon(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    path = args.get("path", "/var/www")

    if _hash_fail(f"restorecon{path}", mod=20, bucket=0):
        stderr = f"restorecon: lstat({path}) failed: No such file or directory\n"
        return _make_result(
            1, "", stderr,
            f"Failed to restore contexts on '{path}'; path not found.",
        )
    # Realistic restorecon -Rv output
    stdout = (
        f"Relabeled {path} from system_u:object_r:default_t:s0 "
        f"to system_u:object_r:httpd_sys_content_t:s0\n"
    )
    return _make_result(0, stdout, "", f"File contexts restored on '{path}'.")


def _sim_chcon(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    context_type = args.get("context_type", "httpd_sys_content_t")
    path = args.get("path", "/srv/app")

    if _hash_fail(f"chcon{path}{context_type}", mod=20, bucket=0):
        stderr = f"chcon: cannot access '{path}': No such file or directory\n"
        return _make_result(
            1, "", stderr,
            f"Failed to change context on '{path}'; path not found.",
        )
    return _make_result(
        0, "", "",
        f"Context type on '{path}' set to '{context_type}'.",
    )


def _sim_audit2allow(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    if _hash_fail("audit2allow", mod=20, bucket=0):
        stderr = "/var/log/audit/audit.log: Permission denied\n"
        return _make_result(
            1, "", stderr,
            "audit2allow could not read the audit log; check that the binary is run as root.",
        )
    # Realistic audit2allow output showing a suggested policy module
    stdout = (
        "\n#============= httpd_t ==============\n"
        "allow httpd_t var_log_t:file { open read };\n"
        "\n"
        "#============= mysqld_t ==============\n"
        "allow mysqld_t tmpfs_t:file { map read write };\n"
    )
    return _make_result(0, stdout, "", "Denial log analyzed; policy suggestions generated.")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "sestatus": _sim_sestatus,
    "getsebool": _sim_getsebool,
    "getenforce": _sim_getenforce,
    "setenforce": _sim_setenforce,
    "setsebool": _sim_setsebool,
    "semanage_fcontext_list": _sim_semanage_fcontext_list,
    "semanage_fcontext_add": _sim_semanage_fcontext_add,
    "semanage_fcontext_delete": _sim_semanage_fcontext_delete,
    "semanage_port_list": _sim_semanage_port_list,
    "semanage_port_add": _sim_semanage_port_add,
    "semanage_port_delete": _sim_semanage_port_delete,
    "semanage_user_list": _sim_semanage_user_list,
    "semanage_user_add": _sim_semanage_user_add,
    "semanage_user_delete": _sim_semanage_user_delete,
    "restorecon": _sim_restorecon,
    "chcon": _sim_chcon,
    "audit2allow": _sim_audit2allow,
}


def simulate_selinux(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'selinux' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 17 real ops in core/tools/selinux.py.
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str or a profile dict.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present. summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_selinux: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
