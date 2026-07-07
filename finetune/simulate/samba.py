"""finetune/simulate/samba.py — Rocky Linux 9 output simulator for the 'samba' tool.

Public API
----------
simulate_samba(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 7 real operations declared in core/tools/samba.py
    args : dict of op arguments (may be {} for all-optional ops)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real samba/systemctl behaviour on Rocky Linux 9.
* stdout/stderr reflect actual testparm, smbpasswd, net usershare output.
* Failure branches are deterministic via hash-based scatter.

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent/agentic/neural language).

INV-read-only-core: imports NOTHING from core/ directly.
Does NOT import finetune.coreimports (avoids circular deps at Phase-13 init).
"""

from __future__ import annotations

import hashlib
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


def _user_exists_in_samba(username: str, ctx: Any) -> bool:
    """Return True if the username appears in the samba context."""
    if isinstance(ctx, dict):
        users: list[str] = ctx.get("samba_users", [])
        return username in users
    if isinstance(ctx, str):
        return username in ctx
    return False


def _smbd_is_active(ctx: Any) -> bool:
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return any("smbd" in s for s in active)
    if isinstance(ctx, str):
        return "smbd" in ctx
    return False


def _nmbd_is_active(ctx: Any) -> bool:
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return any("nmbd" in s for s in active)
    if isinstance(ctx, str):
        return "nmbd" in ctx
    return False


def _should_fail(key: str, modulus: int = 8) -> bool:
    """Deterministic failure scatter (~1/modulus probability)."""
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return h % modulus == 0


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


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_smbd_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)
    smbd_active = _smbd_is_active(ctx)
    nmbd_active = _nmbd_is_active(ctx)

    if smbd_active and nmbd_active:
        stdout = (
            f"● smbd.service - Samba SMB Daemon\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/smbd.service; enabled; preset: disabled)\n"
            f"     Active: active (running) since Thu 2026-07-04 00:01:00 UTC; 8h ago\n"
            f"   Main PID: 2345 (smbd)\n"
            f"     Status: \"smbd: ready to serve connections...\"\n"
            f"      Tasks: 6 (limit: 23168)\n"
            f"     Memory: 32.4M\n"
            f"        CPU: 0.823s\n"
            f"     CGroup: /system.slice/smbd.service\n"
            f"             └─2345 /usr/sbin/smbd --foreground --no-process-group\n"
            f"\n"
            f"● nmbd.service - Samba NMB Daemon\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/nmbd.service; enabled; preset: disabled)\n"
            f"     Active: active (running) since Thu 2026-07-04 00:01:01 UTC; 8h ago\n"
            f"   Main PID: 2346 (nmbd)\n"
            f"     Memory: 8.1M\n"
        )
        return _make_result(0, stdout, "", "Samba daemons smbd and nmbd are active and running.")

    stderr = ""
    stdout = (
        f"○ smbd.service - Samba SMB Daemon\n"
        f"     Loaded: loaded (/usr/lib/systemd/system/smbd.service; disabled; preset: disabled)\n"
        f"     Active: inactive (dead)\n"
        f"\n"
        f"○ nmbd.service - Samba NMB Daemon\n"
        f"     Loaded: loaded (/usr/lib/systemd/system/nmbd.service; disabled; preset: disabled)\n"
        f"     Active: inactive (dead)\n"
    )
    return _make_result(3, stdout, stderr, "Samba daemon status check reported exit 3.")


def _sim_nmbd_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)
    active = _nmbd_is_active(ctx)

    if active:
        stdout = (
            f"● nmbd.service - Samba NMB Daemon\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/nmbd.service; enabled; preset: disabled)\n"
            f"     Active: active (running) since Thu 2026-07-04 00:01:01 UTC; 8h ago\n"
            f"   Main PID: 2346 (nmbd)\n"
            f"      Tasks: 1 (limit: 23168)\n"
            f"     Memory: 8.1M\n"
            f"        CPU: 0.102s\n"
            f"     CGroup: /system.slice/nmbd.service\n"
            f"             └─2346 /usr/sbin/nmbd --foreground --no-process-group\n"
            f"\n"
            f"Jul 04 00:01:01 {host} systemd[1]: Started Samba NMB Daemon.\n"
        )
        return _make_result(0, stdout, "", "nmbd is active and running.")

    stdout = (
        f"○ nmbd.service - Samba NMB Daemon\n"
        f"     Loaded: loaded (/usr/lib/systemd/system/nmbd.service; disabled; preset: disabled)\n"
        f"     Active: inactive (dead)\n"
    )
    return _make_result(3, stdout, "", "nmbd status check reported exit 3.")


def _sim_testparm(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    # Scatter a failure branch
    if _should_fail("testparm", modulus=7):
        stderr = (
            "Load smb config files from /etc/samba/smb.conf\n"
            "ERROR: invalid parameter 'bogus option' in section 'global'\n"
            "rlimit_max: increasing rlimit_max (1024) to minimum Windows limit (16384)\n"
        )
        return _make_result(
            1, "", stderr,
            "smb.conf validation failed (exit 1); review the output for errors.",
        )

    stdout = (
        "Load smb config files from /etc/samba/smb.conf\n"
        "rlimit_max: increasing rlimit_max (1024) to minimum Windows limit (16384)\n"
        "Processing section \"[homes]\"\n"
        "Processing section \"[printers]\"\n"
        "Processing section \"[print$]\"\n"
        "Loaded services file OK.\n"
        "Server role: ROLE_STANDALONE\n"
        "\n"
        "[global]\n"
        "\tworkgroup = WORKGROUP\n"
        "\tserver string = Samba Server %v\n"
        "\tnetbios name = ROCKY-HOST\n"
        "\tsecurity = USER\n"
        "\tmap to guest = Bad User\n"
        "\tdns proxy = No\n"
        "\n"
        "[homes]\n"
        "\tcomment = Home Directories\n"
        "\tvalid users = %S\n"
        "\tbrowseable = No\n"
        "\tread only = No\n"
        "\tinherit acls = Yes\n"
    )
    return _make_result(0, stdout, "", "smb.conf syntax check passed; configuration is valid.")


def _sim_smbpasswd_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    username = args.get("username", "nobody")

    if _should_fail(f"add-{username}", modulus=9):
        stderr = f"Failed to add entry for user {username}.\n"
        return _make_result(
            1, "", stderr,
            f"Failed to add Samba user '{username}' (exit 1).",
        )

    stdout = (
        f"New SMB password:\n"
        f"Retype new SMB password:\n"
        f"Added user {username}.\n"
    )
    return _make_result(0, stdout, "", f"Samba user '{username}' added successfully.")


def _sim_smbpasswd_delete(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    username = args.get("username", "nobody")

    if not _user_exists_in_samba(username, ctx) and _should_fail(f"del-{username}", modulus=4):
        stderr = f"Failed to delete entry for user {username}.\n"
        return _make_result(
            1, "", stderr,
            f"Failed to remove Samba user '{username}' (exit 1).",
        )

    stdout = f"Deleted user {username}.\n"
    return _make_result(
        0, stdout, "",
        f"Samba user '{username}' removed from the Samba user database.",
    )


def _sim_usershare_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    if _should_fail("usershare_list", modulus=10):
        stderr = "net usershare: cannot open usershare directory /var/lib/samba/usershares: No such file or directory\n"
        return _make_result(
            255, "", stderr,
            "Failed to list usershares (exit 255).",
        )

    if isinstance(ctx, dict):
        shares: list[str] = ctx.get("samba_usershares", ["data", "backups"])
    else:
        shares = ["data", "backups"]

    stdout = "\n".join(shares) + "\n" if shares else ""
    count = len(shares)
    return _make_result(0, stdout, "", f"Listed {count} usershare(s).")


def _sim_usershare_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    name = args.get("name", "myshare")
    path = args.get("path", "/srv/share")
    comment = args.get("comment", "")
    acl = args.get("acl", "Everyone:R")

    if _should_fail(f"add-{name}-{path}", modulus=8):
        stderr = f"net usershare add: cannot share path {path}: Permission denied\n"
        return _make_result(
            255, "", stderr,
            f"Failed to add usershare '{name}' (exit 255).",
        )

    return _make_result(
        0, "", "",
        f"Usershare '{name}' pointing to '{path}' added successfully.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "smbd_status":      _sim_smbd_status,
    "nmbd_status":      _sim_nmbd_status,
    "testparm":         _sim_testparm,
    "smbpasswd_add":    _sim_smbpasswd_add,
    "smbpasswd_delete": _sim_smbpasswd_delete,
    "usershare_list":   _sim_usershare_list,
    "usershare_add":    _sim_usershare_add,
}


def simulate_samba(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'samba' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 7 real ops declared in
           core/tools/samba.py.
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either a snapshot_text str or a profile dict.

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
            f"simulate_samba: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
