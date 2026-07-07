"""core/tools/httpd.py — Apache HTTP Server management via apachectl and systemctl.

Supported operations
--------------------
  status      (READ)  — show httpd service status via apachectl status.
  configtest  (READ)  — validate Apache configuration syntax via apachectl configtest.
  start       (WRITE) — start the httpd service via systemctl.
  stop        (WRITE) — stop the httpd service via systemctl.
  restart     (WRITE) — restart the httpd service via systemctl.
  vhost_list  (READ)  — list configured virtual hosts via apachectl -S.
  mod_status  (READ)  — fetch live server metrics from mod_status via curl to localhost.

Permission mapping:
  READ  : status, configtest, vhost_list, mod_status
  WRITE : start, stop, restart

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.  The mod_status
      op shells out to the local curl binary pointing at 127.0.0.1 — the
      target is a locally-running httpd process, not a remote host.
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

def _op_status(args: dict[str, Any]) -> ToolResult:
    """apachectl status — show httpd service status."""
    result = run_subprocess(["apachectl", "status"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Apache HTTP Server is running and responding to status queries."
    else:
        summary = f"Apache status check failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_configtest(args: dict[str, Any]) -> ToolResult:
    """apachectl configtest — validate Apache configuration syntax."""
    result = run_subprocess(["apachectl", "configtest"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Apache configuration syntax is valid (Syntax OK)."
    else:
        summary = f"Apache configuration test failed (exit {result.exit_code}); check the error output for syntax problems."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_start(args: dict[str, Any]) -> ToolResult:
    """systemctl start httpd — start the httpd service."""
    result = run_subprocess(["systemctl", "start", "httpd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Apache HTTP Server started."
    else:
        summary = f"Failed to start Apache HTTP Server (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_stop(args: dict[str, Any]) -> ToolResult:
    """systemctl stop httpd — stop the httpd service."""
    result = run_subprocess(["systemctl", "stop", "httpd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Apache HTTP Server stopped."
    else:
        summary = f"Failed to stop Apache HTTP Server (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_restart(args: dict[str, Any]) -> ToolResult:
    """systemctl restart httpd — restart the httpd service."""
    result = run_subprocess(["systemctl", "restart", "httpd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Apache HTTP Server restarted."
    else:
        summary = f"Failed to restart Apache HTTP Server (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_vhost_list(args: dict[str, Any]) -> ToolResult:
    """apachectl -S — list configured virtual hosts and their settings."""
    result = run_subprocess(["apachectl", "-S"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        vhost_count = result.stdout.count("port ")
        summary = f"Virtual host listing retrieved; {vhost_count} port binding(s) found."
    else:
        summary = f"Failed to retrieve virtual host configuration (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_mod_status(args: dict[str, Any]) -> ToolResult:
    """curl 127.0.0.1/server-status?auto — fetch live server metrics from mod_status."""
    result = run_subprocess(
        ["curl", "--silent", "--max-time", "5", "http://127.0.0.1/server-status?auto"],
        timeout=15,
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Apache mod_status metrics retrieved from the local server."
    else:
        summary = (
            f"Failed to retrieve mod_status metrics from 127.0.0.1 (exit {result.exit_code}); "
            "ensure mod_status is enabled and httpd is running."
        )
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
    "status":      _op_status,
    "configtest":  _op_configtest,
    "start":       _op_start,
    "stop":        _op_stop,
    "restart":     _op_restart,
    "vhost_list":  _op_vhost_list,
    "mod_status":  _op_mod_status,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an httpd operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never raises (I9) — unknown ops and subprocess failures
    both degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for httpd tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

HTTPD_SPEC = ToolSpec(
    name="httpd",
    description="Manage and inspect the Apache HTTP Server via apachectl and systemctl.",
    ops={
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show Apache HTTP Server service status.",
        ),
        "configtest": OpSpec(
            op_name="configtest",
            permission_class=OpClass.READ,
            args=[],
            description="Validate Apache configuration file syntax.",
        ),
        "start": OpSpec(
            op_name="start",
            permission_class=OpClass.WRITE,
            args=[],
            description="Start the Apache HTTP Server service.",
        ),
        "stop": OpSpec(
            op_name="stop",
            permission_class=OpClass.WRITE,
            args=[],
            description="Stop the Apache HTTP Server service.",
        ),
        "restart": OpSpec(
            op_name="restart",
            permission_class=OpClass.WRITE,
            args=[],
            description="Restart the Apache HTTP Server service.",
        ),
        "vhost_list": OpSpec(
            op_name="vhost_list",
            permission_class=OpClass.READ,
            args=[],
            description="List configured virtual hosts and their port bindings.",
        ),
        "mod_status": OpSpec(
            op_name="mod_status",
            permission_class=OpClass.READ,
            args=[],
            description="Fetch live server metrics from the local mod_status endpoint.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(HTTPD_SPEC)
