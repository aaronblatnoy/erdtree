"""finetune/simulate/hostname.py — Rocky Linux 9 output simulator for the 'hostname' tool.

Public API
----------
simulate_hostname(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 4 real operations declared in core/tools/hostname.py
           (status, set-hostname, hosts-view, hosts-edit)
    args : dict of op arguments (may be {} for all-optional ops)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Checked via isinstance; both forms are supported.

Realism model
-------------
* Exit codes mirror real hostnamectl / cat / tee behaviour:
    0  — success
    1  — generic failure (permission denied, invalid hostname format, etc.)
* stdout/stderr reflect actual Rocky 9 hostnamectl output format.
* Failure triggers are deterministic: names containing "invalid", "bad",
  "fail", or names that begin with a hyphen or digit trigger failure branches.
  A ~15% hash-based scatter adds variety among otherwise valid names.
* ctx is used to extract the current hostname: if a dict, reads ctx["hostname"];
  if a string, parses "Hostname: <value>" lines.

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/agent/model/neural language).

INV-read-only-core: imports NOTHING from core/ directly.
Does not import finetune.coreimports (avoids circular deps at __init__ time).
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_hostname(ctx: Any) -> str:
    """Extract the current hostname from the context."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com")
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return "rocky-host.example.com"


def _hostname_short(ctx: Any) -> str:
    """Return just the short (unqualified) hostname."""
    return _get_hostname(ctx).split(".")[0]


def _hostname_invalid(name: str) -> bool:
    """Deterministically decide if a hostname should trigger a failure.

    Triggers: the token "invalid", "bad", "fail", or "broken" in the name;
    name starts with a hyphen or digit; OR a hash-based ~15% scatter.
    """
    lower = name.lower()
    for tok in ("invalid", "bad", "fail", "broken", "bogus"):
        if tok in lower:
            return True
    if name.startswith("-") or (name and name[0].isdigit()):
        return True
    # Hash-based scatter (~15%)
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 13 == 0


def _entry_invalid(entry: str) -> bool:
    """Deterministically decide if a hosts entry triggers a permission failure.

    In practice tee -a fails only on permission denied; simulate that for
    ~10% of entries to teach error handling.
    """
    h = int(hashlib.md5(entry.encode()).hexdigest(), 16)
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
    """Simulate: hostnamectl status"""
    fqdn = _get_hostname(ctx)
    short = fqdn.split(".")[0]
    # Build realistic hostnamectl status output (Rocky Linux 9 format)
    stdout = (
        f"   Static hostname: {fqdn}\n"
        f"         Icon name: computer-server\n"
        f"           Chassis: server\n"
        f"        Machine ID: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6\n"
        f"           Boot ID: f1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6\n"
        f"  Operating System: Rocky Linux 9.3 (Blue Onyx)\n"
        f"       CPE OS Name: cpe:/o:rocky:rocky:9::baseos\n"
        f"            Kernel: Linux 5.14.0-362.8.1.el9_3.x86_64\n"
        f"      Architecture: x86-64\n"
        f"   Hardware Vendor: (To be filled by O.E.M.)\n"
        f"    Hardware Model: (To be filled by O.E.M.)\n"
        f"  Firmware Version: 2.8.0\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"System hostname is '{fqdn}'.",
    )


def _sim_set_hostname(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: hostnamectl set-hostname <name>"""
    name = args.get("name", "localhost")

    if _hostname_invalid(name):
        # Simulate invalid hostname or permission denied
        stderr = (
            f"Failed to set hostname: Invalid hostname '{name}'. "
            "A valid hostname must consist of dot-separated labels of letters, "
            "digits, and hyphens, with no leading/trailing hyphens.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to set hostname to '{name}'; the name is not valid.",
        )

    # Success: hostnamectl set-hostname produces no stdout
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"System hostname set to '{name}'.",
    )


def _sim_hosts_view(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: cat /etc/hosts"""
    fqdn = _get_hostname(ctx)
    short = fqdn.split(".")[0]
    # Build a realistic /etc/hosts file
    stdout = (
        "# Hosts Database\n"
        "# Generated by NetworkManager\n"
        "127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4\n"
        "::1         localhost localhost.localdomain localhost6 localhost6.localdomain6\n"
        f"127.0.1.1   {fqdn} {short}\n"
    )
    line_count = stdout.count("\n")
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Hosts file contains {line_count} lines.",
    )


def _sim_hosts_edit(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: tee -a /etc/hosts (append a new entry)"""
    entry = args.get("entry", "")
    if not entry.endswith("\n"):
        entry = entry + "\n"

    if _entry_invalid(entry):
        stderr = "tee: /etc/hosts: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to append entry to /etc/hosts (exit 1).",
        )

    # tee outputs what it writes to stdout
    return _make_result(
        exit_code=0,
        stdout=entry,
        stderr="",
        summary=f"Appended entry to /etc/hosts: '{args.get('entry', '').strip()}'.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "status": _sim_status,
    "set-hostname": _sim_set_hostname,
    "hosts-view": _sim_hosts_view,
    "hosts-edit": _sim_hosts_edit,
}


def simulate_hostname(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'hostname' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 4 real ops declared in
           core/tools/hostname.py (status, set-hostname, hosts-view, hosts-edit).
    args : argument dict (may be sparse; defaults applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'hostname' key.

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
            f"simulate_hostname: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
