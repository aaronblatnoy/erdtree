"""core/tools/sosreport.py — sosreport/sos system diagnostics collection tool.

Supported operations
--------------------
  generate  (WRITE) — run 'sos report' to collect a system diagnostics archive.
  info      (READ)  — run 'sos info' to list available plugins and their status.

Permission mapping (per Phase 9 H plan table):
  READ  : info
  WRITE : generate  (writes a large archive under /var/tmp or --output-dir)

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.

Notes
-----
  'sos report' can take several minutes on heavily-loaded systems. A timeout of
  300 seconds is passed to run_subprocess, which is patched in tests and so is
  not exercised live during unit tests.
  'sos info' is a fast inspection-only command (READ).
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
# SELinux hint detection (VERBATIM from services.py)
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
# Operation implementations
# ---------------------------------------------------------------------------

def _op_generate(args: dict[str, Any]) -> ToolResult:
    """sos report [--batch] [--label <label>] [--output-dir <dir>]

    Runs sos report to gather a system diagnostics archive.  'sos report'
    can be slow; pass a 300-second timeout.  Tests patch run_subprocess so
    the timeout is never exercised live.
    """
    cmd = ["sos", "report", "--batch"]

    label: str | None = args.get("label")
    if label:
        cmd += ["--label", label]

    output_dir: str | None = args.get("output_dir")
    if output_dir:
        cmd += ["--output-dir", output_dir]

    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)

    if result.ok:
        # Parse the archive path from stdout if present; fall back to a generic message.
        archive_path = ""
        for line in result.stdout.splitlines():
            if "sosreport-" in line and line.strip().endswith(".tar.xz"):
                archive_path = line.strip()
                break
        if archive_path:
            summary = f"Diagnostics archive generated: {archive_path}."
        else:
            lbl_note = f" (label: {label})" if label else ""
            summary = f"Diagnostics archive collected successfully{lbl_note}."
    else:
        summary = f"sos report failed (exit {result.exit_code})."

    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_info(args: dict[str, Any]) -> ToolResult:
    """sos info [<plugin>]

    Lists available sos plugins and their enabled/disabled status.
    If a plugin name is provided, shows details for that plugin only.
    """
    plugin: str | None = args.get("plugin")

    if plugin:
        cmd = ["sos", "info", plugin]
    else:
        cmd = ["sos", "info"]

    result = run_subprocess(cmd, timeout=30)
    selinux = _maybe_selinux_hint(result.stderr)

    if result.ok:
        if plugin:
            summary = f"Plugin information for '{plugin}' retrieved."
        else:
            line_count = result.stdout.count("\n")
            summary = f"sos plugin listing retrieved ({line_count} lines)."
    else:
        if plugin:
            summary = f"Failed to retrieve info for plugin '{plugin}' (exit {result.exit_code})."
        else:
            summary = f"sos info failed (exit {result.exit_code})."

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
    "generate": _op_generate,
    "info": _op_info,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a sosreport operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    audit records.  This function never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for sosreport tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

SOSREPORT_SPEC = ToolSpec(
    name="sosreport",
    description="Collect system diagnostics archives and inspect sos plugins via the sos utility.",
    ops={
        "generate": OpSpec(
            op_name="generate",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="label",
                    type=str,
                    required=False,
                    description="Optional label appended to the archive filename.",
                    default=None,
                ),
                ArgSpec(
                    name="output_dir",
                    type=str,
                    required=False,
                    description="Directory to write the archive into (default: /var/tmp).",
                    default=None,
                ),
            ],
            description="Run 'sos report --batch' to collect a system diagnostics archive.",
        ),
        "info": OpSpec(
            op_name="info",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="plugin",
                    type=str,
                    required=False,
                    description="Name of a specific sos plugin to inspect (omit for full listing).",
                    default=None,
                ),
            ],
            description="List available sos plugins and their status via 'sos info'.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(SOSREPORT_SPEC)
