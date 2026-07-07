"""finetune/simulate/sssd.py — Rocky Linux 9 output simulator for the 'sssd' tool.

Public API
----------
simulate_sssd(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/sssd.py
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by make_context(),
           OR a profile dict — both are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real sssd / realm / id behaviour on Rocky Linux 9.
* Output reflects actual realm, sss_cache, id, and systemctl formats.
* Failure triggers are deterministic via hash-based scatter, matching the
  services.py pattern, so generated traces teach error handling.

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent/neural language).

INV-read-only-core: imports NOTHING from core/ and NOTHING from finetune.coreimports.
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


def _sssd_is_active(ctx: Any) -> bool:
    """Return True if sssd appears to be running in the given context."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return any("sssd" in s for s in active)
    if isinstance(ctx, str):
        return "sssd" in ctx
    return True  # assume running by default for realistic output


def _enrolled_domain(ctx: Any) -> str | None:
    """Return the enrolled realm domain from ctx, or None if not enrolled."""
    if isinstance(ctx, dict):
        return ctx.get("realm_domain", None)
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if "realm" in line.lower() and "domain" in line.lower():
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return None


def _domain_not_found(domain: str) -> bool:
    """Deterministically decide if a domain name triggers a failure."""
    lower = domain.lower()
    for tok in ("notfound", "noexist", "broken", "fail", "missing", "bogus", "invalid"):
        if tok in lower:
            return True
    h = int(hashlib.md5(domain.encode()).hexdigest(), 16)
    return h % 15 == 0


def _user_not_found(user: str) -> bool:
    """Deterministically decide if a user lookup should fail."""
    lower = user.lower()
    for tok in ("notfound", "noexist", "missing", "bogus", "unknown", "fail"):
        if tok in lower:
            return True
    h = int(hashlib.md5(user.encode()).hexdigest(), 16)
    return h % 10 == 0


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

def _sim_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)
    active = _sssd_is_active(ctx)

    if active:
        stdout = (
            "● sssd.service - System Security Services Daemon\n"
            "     Loaded: loaded (/usr/lib/systemd/system/sssd.service; enabled; preset: disabled)\n"
            "     Active: active (running) since Mon 2026-07-06 00:01:12 UTC; 6h 22min ago\n"
            "   Main PID: 1243 (sssd)\n"
            "     Status: \"Starting up...\"\n"
            "      Tasks: 5 (limit: 23168)\n"
            "     Memory: 36.8M\n"
            "        CPU: 2.318s\n"
            "     CGroup: /system.slice/sssd.service\n"
            "             ├─1243 /usr/sbin/sssd -i --logger=files\n"
            "             ├─1260 /usr/libexec/sssd/sssd_be --domain corp.example.com --uid 0 --gid 0\n"
            "             └─1261 /usr/libexec/sssd/sssd_nss --uid 0 --gid 0\n"
            f"\n"
            f"Jul 06 00:01:12 {host} systemd[1]: Started System Security Services Daemon.\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="The sssd daemon is active and running.",
        )
    else:
        stdout = (
            "○ sssd.service - System Security Services Daemon\n"
            "     Loaded: loaded (/usr/lib/systemd/system/sssd.service; disabled; preset: disabled)\n"
            "     Active: inactive (dead)\n"
        )
        return _make_result(
            exit_code=3,
            stdout=stdout,
            stderr="",
            summary="The sssd daemon is loaded but currently inactive.",
        )


def _sim_id_lookup(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    user = args.get("user", "testuser")

    if _user_not_found(user):
        stderr = f"id: '{user}': no such user\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Identity lookup failed for '{user}' (exit 1).",
        )

    # Deterministic UID/GID based on username
    uid = 10000 + (sum(ord(c) for c in user) % 50000)
    gid = uid
    domain = "corp.example.com"
    # Simulate domain user vs local user
    h = int(hashlib.md5(user.encode()).hexdigest(), 16)
    is_domain_user = (h % 3) != 0

    if is_domain_user:
        stdout = (
            f"uid={uid}({user}@{domain}) gid={gid}(domain users@{domain}) "
            f"groups={gid}(domain users@{domain}),10001(linuxadmins@{domain})\n"
        )
    else:
        stdout = (
            f"uid={uid}({user}) gid={gid}({user}) groups={gid}({user})\n"
        )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Identity information retrieved for '{user}'.",
    )


def _sim_cache_flush(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    active = _sssd_is_active(ctx)

    if not active:
        stderr = "sss_cache: SSSD is not running — cannot flush the cache.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="sssd cache flush failed — the sssd daemon is not running (exit 1).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="The sssd cache was flushed successfully.",
    )


def _sim_realm_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    domain = _enrolled_domain(ctx) or "corp.example.com"

    # Determine if enrolled based on ctx
    enrolled = True
    if isinstance(ctx, dict):
        enrolled = ctx.get("realm_enrolled", True)

    if not enrolled:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="No realms are currently enrolled on this host.",
        )

    stdout = (
        f"{domain}\n"
        f"  type: kerberos\n"
        f"  realm-name: {domain.upper()}\n"
        f"  domain-name: {domain}\n"
        f"  configured: kerberos-member\n"
        f"  server-software: active-directory\n"
        f"  client-software: sssd\n"
        f"  required-package: oddjob\n"
        f"  required-package: oddjob-mkhomedir\n"
        f"  required-package: sssd\n"
        f"  required-package: adcli\n"
        f"  required-package: samba-common-tools\n"
        f"  login-formats: %U@{domain}\n"
        f"  login-policy: allow-realm-logins\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Enrolled realm information retrieved.",
    )


def _sim_realm_join(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    domain = args.get("domain", "corp.example.com")

    if _domain_not_found(domain):
        stderr = (
            f"realm: Couldn't join realm: Failed to join the domain '{domain}'.\n"
            f"See: journalctl UNIT=realmd.service\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to join domain '{domain}' (exit 1).",
        )

    # Successful join — realm join prints nothing to stdout on success
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Host successfully enrolled in domain '{domain}'.",
    )


def _sim_realm_leave(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    domain = args.get("domain", "corp.example.com")

    if _domain_not_found(domain):
        stderr = (
            f"realm: Couldn't leave realm: Not enrolled in domain '{domain}'.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to leave domain '{domain}' (exit 1).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=(
            f"Host removed from domain '{domain}'. "
            "Domain account logins are no longer available on this host."
        ),
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "status": _sim_status,
    "id_lookup": _sim_id_lookup,
    "cache_flush": _sim_cache_flush,
    "realm_list": _sim_realm_list,
    "realm_join": _sim_realm_join,
    "realm_leave": _sim_realm_leave,
}


def simulate_sssd(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'sssd' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in
           core/tools/sssd.py.
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
            f"simulate_sssd: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
