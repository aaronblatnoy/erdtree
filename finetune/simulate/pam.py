"""finetune/simulate/pam.py — Rocky Linux 9 output simulator for the 'pam' tool.

Public API
----------
simulate_pam(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 4 real operations declared in core/tools/pam.py
    args : dict of op arguments (may be {} for all-optional ops; defaults applied)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* pamd_audit   : produces realistic /etc/pam.d/<service> output mirroring Rocky 9
                 system-auth stack (auth/account/password/session lines).
* faillock_status : produces realistic faillock tally output per user; failure
                 branch returns non-zero exit when the faillock directory is
                 inaccessible.
* faillock_reset  : exits 0 on success; failure branch simulates a non-existent
                 user producing an error message.
* pam_auth_update : exits 0 on success; failure branch simulates a missing or
                 invalid profile name.

I2 compliance
-------------
All summary strings are I2-clean. No AI/LLM/model/agent language appears.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (avoids circular deps when
__init__.py imports simulate modules before coreimports is fully settled).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for use in realistic output lines."""
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


def _service_not_found(service: str) -> bool:
    """Deterministically decide if a pam.d service file should be missing."""
    lower = service.lower()
    for tok in ("notfound", "noexist", "missing", "bogus", "fake", "bad"):
        if tok in lower:
            return True
    h = int(hashlib.md5(service.encode()).hexdigest(), 16)
    return h % 15 == 0


def _user_not_found(user: str) -> bool:
    """Deterministically decide if a user should be absent from the tally DB."""
    lower = user.lower()
    for tok in ("notfound", "noexist", "missing", "ghost", "fake"):
        if tok in lower:
            return True
    h = int(hashlib.md5((user + "faillock").encode()).hexdigest(), 16)
    return h % 12 == 0


def _profile_invalid(profile: str) -> bool:
    """Deterministically decide if a pam-auth-update profile is invalid."""
    lower = profile.lower()
    for tok in ("invalid", "bad", "notfound", "noexist", "bogus"):
        if tok in lower:
            return True
    h = int(hashlib.md5((profile + "pau").encode()).hexdigest(), 16)
    return h % 10 == 0


# Realistic pam.d content templates keyed by service name segment
_PAMD_TEMPLATES: dict[str, str] = {
    "sshd": (
        "#%PAM-1.0\n"
        "auth       required     pam_sepermit.so\n"
        "auth       substack     password-auth\n"
        "auth       include      postlogin\n"
        "account    required     pam_nologin.so\n"
        "account    include      password-auth\n"
        "password   include      password-auth\n"
        "session    required     pam_selinux.so close\n"
        "session    required     pam_loginuid.so\n"
        "session    required     pam_selinux.so open env_params\n"
        "session    optional     pam_keyinit.so force revoke\n"
        "session    optional     pam_motd.so\n"
        "session    include      password-auth\n"
        "session    include      postlogin\n"
    ),
    "sudo": (
        "#%PAM-1.0\n"
        "auth       include      system-auth\n"
        "account    include      system-auth\n"
        "password   include      system-auth\n"
        "session    optional     pam_keyinit.so revoke\n"
        "session    required     pam_limits.so\n"
        "session    required     pam_unix.so\n"
    ),
    "login": (
        "#%PAM-1.0\n"
        "auth       required     pam_securetty.so\n"
        "auth       substack     system-auth\n"
        "auth       include      postlogin\n"
        "account    required     pam_nologin.so\n"
        "account    include      system-auth\n"
        "password   include      system-auth\n"
        "session    required     pam_selinux.so close\n"
        "session    required     pam_loginuid.so\n"
        "session    optional     pam_console.so\n"
        "session    required     pam_selinux.so open\n"
        "session    required     pam_namespace.so\n"
        "session    optional     pam_keyinit.so force revoke\n"
        "session    include      system-auth\n"
        "session    include      postlogin\n"
        "-session   optional     pam_ck_connector.so\n"
    ),
    "default": (
        "#%PAM-1.0\n"
        "auth       required     pam_env.so\n"
        "auth       sufficient   pam_unix.so nullok\n"
        "auth       required     pam_deny.so\n"
        "account    required     pam_unix.so\n"
        "password   sufficient   pam_unix.so nullok sha512 shadow\n"
        "password   required     pam_deny.so\n"
        "session    required     pam_unix.so\n"
    ),
}


def _pamd_content(service: str) -> str:
    """Return a realistic pam.d file body for the given service name."""
    lower = service.lower()
    for key in ("sshd", "sudo", "login"):
        if key in lower:
            return _PAMD_TEMPLATES[key]
    return _PAMD_TEMPLATES["default"]


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_pamd_audit(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    service = args.get("service", "sshd")

    if _service_not_found(service):
        stderr = f"cat: /etc/pam.d/{service}: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"PAM configuration file for '{service}' was not found in /etc/pam.d/.",
        )

    content = _pamd_content(service)
    line_count = content.count("\n")
    return _make_result(
        exit_code=0,
        stdout=content,
        stderr="",
        summary=f"PAM configuration for '{service}' retrieved ({line_count} lines).",
    )


def _sim_faillock_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    user = args.get("user")

    if user and _user_not_found(user):
        # faillock still exits 0 for unknown users but prints nothing meaningful
        stdout = f"{user}:\n"
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"No faillock tallies found for user '{user}'.",
        )

    # Simulate failure directory inaccessible
    h = int(hashlib.md5(("status" + (user or "")).encode()).hexdigest(), 16)
    if h % 18 == 0:
        stderr = "faillock: Cannot open the tally directory /var/run/faillock: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to read faillock tallies; check permissions on /var/run/faillock (exit 1).",
        )

    if user:
        stdout = (
            f"{user}:\n"
            f"When                Type  Source                                           Valid\n"
            f"2026-07-05 14:23:10 RHOST 10.0.1.42                                        V\n"
            f"2026-07-05 14:23:55 RHOST 10.0.1.42                                        V\n"
        )
        summary = f"Faillock tallies for user '{user}' retrieved."
    else:
        stdout = (
            "alice:\n"
            "When                Type  Source                                           Valid\n"
            "2026-07-05 09:11:03 RHOST 10.0.2.5                                         V\n"
            "bob:\n"
            "When                Type  Source                                           Valid\n"
        )
        summary = "Faillock authentication failure tallies retrieved."

    return _make_result(exit_code=0, stdout=stdout, stderr="", summary=summary)


def _sim_faillock_reset(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    user = args.get("user")

    if user and _user_not_found(user):
        stderr = f"faillock: User '{user}' does not exist.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to reset faillock tallies; user '{user}' was not found (exit 1).",
        )

    if user:
        summary = f"Faillock tallies reset for user '{user}'."
    else:
        summary = "Faillock authentication failure tallies reset for all users."

    return _make_result(exit_code=0, stdout="", stderr="", summary=summary)


def _sim_pam_auth_update(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    profile = args.get("profile", "mkhomedir")
    action = args.get("action") or "enable"

    if action not in ("enable", "disable"):
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=f"pam-auth-update: unknown action '{action}'\n",
            summary=(
                f"Unknown action '{action}' for pam_auth_update; "
                "use 'enable' or 'disable'."
            ),
        )

    if _profile_invalid(profile):
        stderr = f"pam-auth-update: profile '{profile}' not found in /usr/share/pam-configs/\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"pam-auth-update failed to {action} profile '{profile}'; "
                "profile not found (exit 1)."
            ),
        )

    stdout = f"Enabling {profile} in PAM configuration.\n" if action == "enable" else f"Disabling {profile} in PAM configuration.\n"
    summary = (
        f"PAM profile '{profile}' {action}d via pam-auth-update. "
        "Verify login access in a separate session before closing this one."
    )
    return _make_result(exit_code=0, stdout=stdout, stderr="", summary=summary)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "pamd_audit":      _sim_pamd_audit,
    "faillock_status": _sim_faillock_status,
    "faillock_reset":  _sim_faillock_reset,
    "pam_auth_update": _sim_pam_auth_update,
}


def simulate_pam(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'pam' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 4 real ops declared in
           core/tools/pam.py (pamd_audit, faillock_status, faillock_reset,
           pam_auth_update).
    args : argument dict (may be sparse; per-op defaults are applied).
    ctx  : system context — either a snapshot_text str from make_context(),
           or a profile dict with 'hostname' and related keys.

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
            f"simulate_pam: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
