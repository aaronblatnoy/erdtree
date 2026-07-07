"""finetune/simulate/locale.py — Rocky Linux 9 output simulator for the 'locale' tool.

Public API
----------
simulate_locale(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/locale.py
    args : dict of op arguments (may be {} for all-optional ops)
    ctx  : system context string from make_context(), OR a profile dict —
           both forms are supported via isinstance checks.

Realism model
-------------
* localectl status and timedatectl status produce realistic Rocky 9 output.
* set-locale / set-keymap / set-timezone / set-ntp produce success or
  deterministic failure output based on input values.
* Failure triggers: locale/timezone name contains 'invalid', 'bad', 'bogus',
  'notfound', or 'noexist'.
* ctx is used to infer the current hostname for log-like output.

I2 compliance
-------------
All summary strings are I2-clean. No AI/LLM/model/agent language.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (to avoid circular deps).
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


def _current_locale(ctx: Any) -> str:
    """Extract current locale from ctx, or return a default."""
    if isinstance(ctx, dict):
        return ctx.get("locale", "en_US.UTF-8")
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("locale:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return "en_US.UTF-8"


def _current_timezone(ctx: Any) -> str:
    """Extract current timezone from ctx, or return a default."""
    if isinstance(ctx, dict):
        return ctx.get("timezone", "UTC")
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("timezone:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return "UTC"


def _is_invalid_locale(value: str) -> bool:
    """Deterministically decide if a locale/timezone value should be invalid."""
    lower = value.lower()
    for tok in ("invalid", "bad", "bogus", "notfound", "noexist", "broken"):
        if tok in lower:
            return True
    return False


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

def _sim_localectl_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    locale = _current_locale(ctx)
    # Rocky 9 localectl status output
    stdout = (
        f"   System Locale: LANG={locale}\n"
        f"       VC Keymap: us\n"
        f"      X11 Layout: us\n"
        f"       X11 Model: pc105\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Current locale and keyboard settings retrieved.",
    )


def _sim_set_locale(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    locale = args.get("locale", "en_US.UTF-8")

    if _is_invalid_locale(locale):
        stderr = f"Locale {locale!r} is not installed on the system.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to set locale to '{locale}' — locale not installed on this system.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"System locale set to '{locale}'.",
    )


def _sim_set_keymap(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    keymap = args.get("keymap", "us")

    if _is_invalid_locale(keymap):
        stderr = f"Keymap {keymap!r} is not available.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to set keymap to '{keymap}' — keymap not available.",
        )

    # Hash-based scatter for variety (~12%)
    h = int(hashlib.md5(keymap.encode()).hexdigest(), 16)
    if h % 17 == 0:
        stderr = f"Warning: keymap '{keymap}' may not be available in all virtual console environments.\n"
        return _make_result(
            exit_code=0,
            stdout="",
            stderr=stderr,
            summary=f"System keyboard layout set to '{keymap}' (minor compatibility warning noted).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"System keyboard layout set to '{keymap}'.",
    )


def _sim_timedatectl_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    tz = _current_timezone(ctx)
    # Rocky 9 timedatectl status output
    stdout = (
        f"               Local time: Fri 2026-07-04 12:00:00 {tz}\n"
        f"           Universal time: Fri 2026-07-04 12:00:00 UTC\n"
        f"                 RTC time: Fri 2026-07-04 12:00:00\n"
        f"                Time zone: {tz} (UTC, +0000)\n"
        f"System clock synchronized: yes\n"
        f"              NTP service: active\n"
        f"          RTC in local TZ: no\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Current date, time, timezone, and NTP synchronisation state retrieved.",
    )


def _sim_set_timezone(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    timezone = args.get("timezone", "UTC")

    if _is_invalid_locale(timezone):
        stderr = f"Failed to set time zone: Timezone {timezone!r} is not available.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to set timezone to '{timezone}' — timezone not recognised.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"System timezone set to '{timezone}'.",
    )


def _sim_set_ntp(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    enabled_raw = str(args.get("enabled", "true")).lower()
    if enabled_raw in ("true", "1", "yes", "on"):
        state = "enabled"
        val = "true"
    else:
        state = "disabled"
        val = "false"

    # Hash-based failure scatter (~8%) for NTP unavailability
    h = int(hashlib.md5(("ntp" + val).encode()).hexdigest(), 16)
    if h % 25 == 0:
        stderr = "Failed to set NTP: no NTP service available.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to set NTP — no NTP service is available on this host.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"NTP synchronisation {state}.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "localectl-status":   _sim_localectl_status,
    "set-locale":         _sim_set_locale,
    "set-keymap":         _sim_set_keymap,
    "timedatectl-status": _sim_timedatectl_status,
    "set-timezone":       _sim_set_timezone,
    "set-ntp":            _sim_set_ntp,
}


def simulate_locale(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'locale' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in the
           locale ToolSpec (localectl-status, set-locale, set-keymap,
           timedatectl-status, set-timezone, set-ntp).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict.

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
            f"simulate_locale: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
