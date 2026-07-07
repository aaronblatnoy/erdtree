"""core/tools/locale.py — locale and time-zone configuration via localectl and timedatectl.

Supported operations
--------------------
  localectl-status   (READ)   — show current locale, keymap, and X11 settings.
  set-locale         (WRITE)  — set the system locale (e.g. LANG=en_US.UTF-8).
  set-keymap         (WRITE)  — set the system keyboard layout.
  timedatectl-status (READ)   — show current date, time, timezone, and NTP state.
  set-timezone       (WRITE)  — set the system timezone (e.g. America/New_York).
  set-ntp            (WRITE)  — enable or disable NTP time synchronisation.

Permission mapping:
  READ  : localectl-status, timedatectl-status
  WRITE : set-locale, set-keymap, set-timezone, set-ntp

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.
"""

from __future__ import annotations

import re
from typing import Any

from core.agent.permissions import OpClass
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)

# ---------------------------------------------------------------------------
# SELinux hint detection (verbatim from services.py)
# ---------------------------------------------------------------------------

_SELINUX_HINT_RE = re.compile(
    r"AVC\s+avc:|Permission\s+denied|dontaudit|type=AVC|selinux",
    re.IGNORECASE,
)

_SELINUX_HINT = (
    "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
    "or 'journalctl -t setroubleshoot' for denial details."
)


def _maybe_selinux_hint(stderr: str) -> str:
    """Return a SELinux hint suffix if stderr looks like an AVC denial."""
    if _SELINUX_HINT_RE.search(stderr):
        return f"  {_SELINUX_HINT}"
    return ""


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_localectl_status(args: dict[str, Any]) -> ToolResult:
    """localectl status — show current locale and keymap settings."""
    result = run_subprocess(["localectl", "status"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Current locale and keyboard settings retrieved."
    else:
        summary = f"Failed to retrieve locale status (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_locale(args: dict[str, Any]) -> ToolResult:
    """localectl set-locale LANG=<locale> — set the system locale."""
    locale: str = args["locale"]
    result = run_subprocess(["localectl", "set-locale", locale])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"System locale set to '{locale}'."
    else:
        summary = f"Failed to set locale to '{locale}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_keymap(args: dict[str, Any]) -> ToolResult:
    """localectl set-keymap <keymap> — set the system keyboard layout."""
    keymap: str = args["keymap"]
    result = run_subprocess(["localectl", "set-keymap", keymap])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"System keyboard layout set to '{keymap}'."
    else:
        summary = f"Failed to set keymap to '{keymap}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_timedatectl_status(args: dict[str, Any]) -> ToolResult:
    """timedatectl status — show current date, time, timezone, and NTP state."""
    result = run_subprocess(["timedatectl", "status"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Current date, time, timezone, and NTP synchronisation state retrieved."
    else:
        summary = f"Failed to retrieve time/date status (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_timezone(args: dict[str, Any]) -> ToolResult:
    """timedatectl set-timezone <tz> — set the system timezone."""
    timezone: str = args["timezone"]
    result = run_subprocess(["timedatectl", "set-timezone", timezone])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"System timezone set to '{timezone}'."
    else:
        summary = f"Failed to set timezone to '{timezone}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_ntp(args: dict[str, Any]) -> ToolResult:
    """timedatectl set-ntp <true|false> — enable or disable NTP synchronisation."""
    enabled: str = args["enabled"]
    # Normalise bool-like values to the string timedatectl expects
    val = str(enabled).lower()
    if val in ("true", "1", "yes", "on"):
        val = "true"
    elif val in ("false", "0", "no", "off"):
        val = "false"
    result = run_subprocess(["timedatectl", "set-ntp", val])
    selinux = _maybe_selinux_hint(result.stderr)
    state = "enabled" if val == "true" else "disabled"
    if result.ok:
        summary = f"NTP synchronisation {state}."
    else:
        summary = f"Failed to set NTP to '{val}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "localectl-status":   _op_localectl_status,
    "set-locale":         _op_set_locale,
    "set-keymap":         _op_set_keymap,
    "timedatectl-status": _op_timedatectl_status,
    "set-timezone":       _op_set_timezone,
    "set-ntp":            _op_set_ntp,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a locale/time-zone operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for locale tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

LOCALE_SPEC = ToolSpec(
    name="locale",
    description="Manage system locale, keyboard layout, and time-zone settings via localectl and timedatectl.",
    ops={
        "localectl-status": OpSpec(
            op_name="localectl-status",
            permission_class=OpClass.READ,
            args=[],
            description="Show current locale, keyboard layout, and X11 settings.",
        ),
        "set-locale": OpSpec(
            op_name="set-locale",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="locale",
                    type=str,
                    required=True,
                    description="Locale specification (e.g. 'LANG=en_US.UTF-8' or 'en_US.UTF-8').",
                ),
            ],
            description="Set the system locale.",
        ),
        "set-keymap": OpSpec(
            op_name="set-keymap",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="keymap",
                    type=str,
                    required=True,
                    description="Keyboard layout name (e.g. 'us', 'de', 'gb').",
                ),
            ],
            description="Set the system keyboard layout.",
        ),
        "timedatectl-status": OpSpec(
            op_name="timedatectl-status",
            permission_class=OpClass.READ,
            args=[],
            description="Show current date, time, timezone, and NTP synchronisation state.",
        ),
        "set-timezone": OpSpec(
            op_name="set-timezone",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="timezone",
                    type=str,
                    required=True,
                    description="IANA timezone name (e.g. 'America/New_York', 'UTC', 'Europe/London').",
                ),
            ],
            description="Set the system timezone.",
        ),
        "set-ntp": OpSpec(
            op_name="set-ntp",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="enabled",
                    type=str,
                    required=True,
                    description="Enable or disable NTP: 'true' to enable, 'false' to disable.",
                ),
            ],
            description="Enable or disable NTP time synchronisation.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(LOCALE_SPEC)
