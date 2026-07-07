"""core/tools/nginx.py — nginx web server management tool.

Supported operations
--------------------
  configtest  (READ)  — validate the nginx configuration with 'nginx -t'.
  status      (READ)  — show the current status of the nginx.service unit.
  start       (WRITE) — start the nginx.service unit.
  stop        (WRITE) — stop the nginx.service unit.
  restart     (WRITE) — restart the nginx.service unit.
  reload      (WRITE) — reload the nginx configuration without dropping connections.

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
# SELinux hint detection (copy VERBATIM from services.py)
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

def _op_configtest(args: dict[str, Any]) -> ToolResult:
    """nginx -t [-c <config>] — validate the nginx configuration file."""
    config: str = args.get("config", "")
    if config:
        cmd = ["nginx", "-t", "-c", config]
        config_label = config
    else:
        cmd = ["nginx", "-t"]
        config_label = "default configuration"
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"nginx configuration test passed for {config_label}."
    else:
        summary = (
            f"nginx configuration test failed for {config_label} "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_status(args: dict[str, Any]) -> ToolResult:
    """systemctl status nginx.service"""
    result = run_subprocess(["systemctl", "status", "--no-pager", "nginx.service"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "nginx.service is active and running."
    else:
        summary = f"nginx.service reported status exit {result.exit_code}."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_start(args: dict[str, Any]) -> ToolResult:
    """systemctl start nginx.service"""
    result = run_subprocess(["systemctl", "start", "nginx.service"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "nginx.service started."
    else:
        summary = f"Failed to start nginx.service (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_stop(args: dict[str, Any]) -> ToolResult:
    """systemctl stop nginx.service"""
    result = run_subprocess(["systemctl", "stop", "nginx.service"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "nginx.service stopped."
    else:
        summary = f"Failed to stop nginx.service (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_restart(args: dict[str, Any]) -> ToolResult:
    """systemctl restart nginx.service"""
    result = run_subprocess(["systemctl", "restart", "nginx.service"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "nginx.service restarted."
    else:
        summary = f"Failed to restart nginx.service (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_reload(args: dict[str, Any]) -> ToolResult:
    """systemctl reload nginx.service"""
    result = run_subprocess(["systemctl", "reload", "nginx.service"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "nginx.service configuration reloaded without dropping connections."
    else:
        summary = f"Failed to reload nginx.service (exit {result.exit_code})."
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
    "configtest": _op_configtest,
    "status":     _op_status,
    "start":      _op_start,
    "stop":       _op_stop,
    "restart":    _op_restart,
    "reload":     _op_reload,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an nginx operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never raises (I9): unknown ops and subprocess failures both
    degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for nginx tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

NGINX_SPEC = ToolSpec(
    name="nginx",
    description="Manage the nginx web server: validate configuration and control the service.",
    ops={
        "configtest": OpSpec(
            op_name="configtest",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="config",
                    type=str,
                    required=False,
                    description="Path to a specific nginx.conf to test (default: nginx default config).",
                    default="",
                ),
            ],
            description="Test the nginx configuration file for syntax errors (nginx -t).",
        ),
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current status of the nginx.service systemd unit.",
        ),
        "start": OpSpec(
            op_name="start",
            permission_class=OpClass.WRITE,
            args=[],
            description="Start the nginx.service unit.",
        ),
        "stop": OpSpec(
            op_name="stop",
            permission_class=OpClass.WRITE,
            args=[],
            description="Stop the nginx.service unit.",
        ),
        "restart": OpSpec(
            op_name="restart",
            permission_class=OpClass.WRITE,
            args=[],
            description="Restart the nginx.service unit (stop then start).",
        ),
        "reload": OpSpec(
            op_name="reload",
            permission_class=OpClass.WRITE,
            args=[],
            description="Reload the nginx configuration without dropping active connections.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(NGINX_SPEC)
