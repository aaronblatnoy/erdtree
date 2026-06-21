"""core/tools/logs.py — journalctl + dmesg query/filter/tail/since.

Provides the 'logs' tool for the Erdtree agent loop.  Every operation runs
through the permission seam (core.agent.permissions) and produces a
structured ToolResult that the audit layer (core.agent.audit) can transcribe
directly.

Platform notes
--------------
These are Linux tools (journalctl, dmesg).  On a macOS dev host the
subprocess calls are expected to fail (command not found); the module is
designed so that the unit tests mock subprocess execution entirely and mark
any test that requires a live Linux binary as DEFERRED-TO-MOSSAD.

SELinux awareness
-----------------
On the target Linux host, SELinux denials often surface as cryptic
"Permission denied" or silent failures rather than an explicit AVC.  This
module surfaces audit2allow-style hints when:

  * The journalctl output contains AVC lines (kernel AVC denied).
  * The dmesg output contains AVC denied messages.

The hint is included verbatim in ToolResult.stderr / summary so the model
can surface a concrete remediation path to the user.

Invariants (see CLAUDE.md)
--------------------------
  I2  No AI/LLM/model/agent/agentic language in any user-facing string.
  I3  Every execute() has already been cleared by the permission seam (caller
      responsibility); this module just enforces the declared OpClass and
      never bypasses the gate.
  I4  execute() produces one ToolResult suitable for AuditLog.write().
  I6  Zero tier/product/model names anywhere in this file.
"""

from __future__ import annotations

import re
import shlex
from typing import Any, Optional

from core.agent.permissions import OpClass, classify, ExecContext
from core.agent.audit import AuditLog
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)

# ---------------------------------------------------------------------------
# SELinux hint extraction
# ---------------------------------------------------------------------------

# AVC denial pattern emitted by the kernel audit subsystem.
_AVC_RE = re.compile(
    r"avc:\s+denied\s+\{([^}]+)\}\s+for\s+pid=\d+.*?scontext=(\S+)\s+tcontext=(\S+)\s+tclass=(\S+)",
    re.IGNORECASE,
)

# Broader AVC line marker (for simple line-level detection).
_AVC_LINE_RE = re.compile(r"\bavc:\s+denied\b", re.IGNORECASE)


def _extract_selinux_hints(text: str) -> list[str]:
    """Return audit2allow-style hint lines for any AVC denials in *text*.

    Each hint describes what was denied and suggests the audit2allow command
    the sysadmin would run to generate a policy module — no model language,
    just a concrete next step.

    Returns an empty list when no AVC denials are found.
    """
    hints: list[str] = []
    for match in _AVC_RE.finditer(text):
        perms = match.group(1).strip()
        scontext = match.group(2)
        tcontext = match.group(3)
        tclass = match.group(4)
        hints.append(
            f"SELinux denied {{{perms}}} access: scontext={scontext} "
            f"tcontext={tcontext} tclass={tclass}. "
            f"To generate a policy module run: "
            f"audit2allow -a -M my_policy && semodule -i my_policy.pp"
        )
    return hints


# ---------------------------------------------------------------------------
# Internal subprocess helpers
# ---------------------------------------------------------------------------

_MAX_LINES = 500  # hard cap on lines returned to keep results model-friendly


def _head_lines(text: str, n: int = _MAX_LINES) -> str:
    """Return the first *n* lines of *text* (or the full text if shorter)."""
    lines = text.splitlines(keepends=True)
    if len(lines) <= n:
        return text
    truncated = "".join(lines[:n])
    return truncated + f"\n[... output truncated to {n} lines ...]"


def _tail_lines(text: str, n: int) -> str:
    """Return the last *n* lines of *text*."""
    lines = text.splitlines(keepends=True)
    if len(lines) <= n:
        return text
    return "".join(lines[-n:])


# ---------------------------------------------------------------------------
# journalctl operations
# ---------------------------------------------------------------------------

def _journalctl_query(args: dict[str, Any]) -> ToolResult:
    """journalctl query — show log entries, optionally filtered.

    args:
      unit      (str, optional)  — filter to a specific systemd unit name.
      since     (str, optional)  — journalctl --since value, e.g. "1 hour ago",
                                   "2026-01-01 00:00:00".
      until     (str, optional)  — journalctl --until value.
      priority  (str, optional)  — 0-7 or name (err, warning, ...).
      lines     (int, optional)  — number of most-recent lines (--lines N).
      grep      (str, optional)  — filter output to lines matching this pattern
                                   (passed to journalctl --grep).
      identifier (str, optional) — syslog identifier (-t IDENTIFIER).
      boot      (str, optional)  — boot offset or ID (--boot).
    """
    cmd: list[str] = ["journalctl", "--no-pager", "--output=short-iso"]

    unit = args.get("unit")
    if unit:
        cmd += ["-u", str(unit)]

    since = args.get("since")
    if since:
        cmd += ["--since", str(since)]

    until = args.get("until")
    if until:
        cmd += ["--until", str(until)]

    priority = args.get("priority")
    if priority is not None:
        cmd += ["-p", str(priority)]

    identifier = args.get("identifier")
    if identifier:
        cmd += ["-t", str(identifier)]

    boot = args.get("boot")
    if boot is not None:
        cmd += ["--boot", str(boot)]

    grep_pat = args.get("grep")
    if grep_pat:
        cmd += ["--grep", str(grep_pat)]

    lines = args.get("lines")
    if lines is not None:
        cmd += ["-n", str(int(lines))]
    else:
        # Default: last 100 lines to avoid flooding the model context.
        cmd += ["-n", "100"]

    result = run_subprocess(cmd, timeout=30)
    stdout = _head_lines(result.stdout)

    hints = _extract_selinux_hints(stdout)
    hint_text = "\n".join(hints) if hints else ""

    summary_parts = [result.summary]
    if hints:
        summary_parts.append(f"{len(hints)} SELinux denial(s) detected.")
    summary = " ".join(summary_parts)

    stderr_out = "\n".join(filter(None, [result.stderr, hint_text]))

    return ToolResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr_out,
        summary=summary,
    )


def _journalctl_tail(args: dict[str, Any]) -> ToolResult:
    """journalctl --follow — stream recent log entries.

    This is a READ op that returns the last N lines (no live follow; live
    follow is not meaningful inside a single tool-call round-trip).  The
    'lines' arg controls how many to show (default 50).

    args:
      unit   (str, optional) — filter to a specific unit.
      lines  (int, optional) — number of recent lines to return (default 50).
    """
    n = int(args.get("lines") or 50)
    cmd: list[str] = ["journalctl", "--no-pager", "--output=short-iso", "-n", str(n)]

    unit = args.get("unit")
    if unit:
        cmd += ["-u", str(unit)]

    result = run_subprocess(cmd, timeout=15)
    stdout = _head_lines(result.stdout)
    hints = _extract_selinux_hints(stdout)
    hint_text = "\n".join(hints) if hints else ""
    stderr_out = "\n".join(filter(None, [result.stderr, hint_text]))

    summary_parts = [result.summary]
    if hints:
        summary_parts.append(f"{len(hints)} SELinux denial(s) detected.")

    return ToolResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr_out,
        summary=" ".join(summary_parts),
    )


def _journalctl_since(args: dict[str, Any]) -> ToolResult:
    """journalctl --since — show entries since a specific time.

    args:
      since  (str, required) — time expression e.g. "1 hour ago", "yesterday",
                                "2026-01-01 12:00:00".
      unit   (str, optional) — filter to a specific unit.
      lines  (int, optional) — cap on number of lines returned (default 200).
    """
    since = args.get("since", "1 hour ago")
    n = int(args.get("lines") or 200)

    cmd: list[str] = [
        "journalctl", "--no-pager", "--output=short-iso",
        "--since", str(since),
        "-n", str(n),
    ]

    unit = args.get("unit")
    if unit:
        cmd += ["-u", str(unit)]

    result = run_subprocess(cmd, timeout=30)
    stdout = _head_lines(result.stdout)
    hints = _extract_selinux_hints(stdout)
    hint_text = "\n".join(hints) if hints else ""
    stderr_out = "\n".join(filter(None, [result.stderr, hint_text]))

    summary_parts = [result.summary]
    if hints:
        summary_parts.append(f"{len(hints)} SELinux denial(s) detected.")

    return ToolResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr_out,
        summary=" ".join(summary_parts),
    )


def _journalctl_boot_errors(args: dict[str, Any]) -> ToolResult:
    """journalctl — show error-and-above messages from the current boot.

    args:
      boot  (str, optional) — boot ID or offset (default: current boot "0").
    """
    boot = args.get("boot", "0")
    cmd: list[str] = [
        "journalctl", "--no-pager", "--output=short-iso",
        "--boot", str(boot),
        "-p", "err",
    ]

    result = run_subprocess(cmd, timeout=30)
    stdout = _head_lines(result.stdout)
    hints = _extract_selinux_hints(stdout)
    hint_text = "\n".join(hints) if hints else ""
    stderr_out = "\n".join(filter(None, [result.stderr, hint_text]))

    summary_parts = [result.summary]
    if hints:
        summary_parts.append(f"{len(hints)} SELinux denial(s) detected.")

    return ToolResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr_out,
        summary=" ".join(summary_parts),
    )


# ---------------------------------------------------------------------------
# dmesg operations
# ---------------------------------------------------------------------------

def _dmesg_query(args: dict[str, Any]) -> ToolResult:
    """dmesg — show kernel ring buffer, optionally filtered.

    args:
      level   (str, optional) — kernel log level filter: err, warn, info, debug.
      grep    (str, optional) — regex pattern to filter lines (applied in Python
                                after capture, not via a shell pipe).
      lines   (int, optional) — number of most-recent lines to return (default
                                200).
      since   (str, optional) — not native to dmesg; if provided, we attempt
                                dmesg --since (kernel 5.14+; silently ignored on
                                older kernels when dmesg returns an error).
    """
    cmd: list[str] = ["dmesg", "--color=never", "-T"]

    level = args.get("level")
    if level:
        # Map friendly names to dmesg level numbers.
        _level_map = {
            "emerg": "0", "alert": "1", "crit": "2", "err": "3",
            "error": "3", "warn": "4", "warning": "4",
            "notice": "5", "info": "6", "debug": "7",
        }
        lvl = _level_map.get(str(level).lower(), str(level))
        cmd += ["-l", lvl]

    since = args.get("since")
    if since:
        # --since is available on util-linux >= 2.37 (the target distro ships 2.37).
        cmd += ["--since", str(since)]

    result = run_subprocess(cmd, timeout=15)

    stdout = result.stdout
    grep_pat = args.get("grep")
    if grep_pat and stdout:
        try:
            pat = re.compile(grep_pat)
            filtered = "\n".join(
                line for line in stdout.splitlines() if pat.search(line)
            )
            stdout = filtered
        except re.error as exc:
            # Bad regex — return an error result without running the command.
            return ToolResult(
                exit_code=1,
                stdout="",
                stderr=f"Invalid grep pattern: {exc}",
                summary=f"invalid grep pattern: {exc}",
            )

    # Cap output.
    lines_n = args.get("lines")
    if lines_n is not None:
        stdout = _tail_lines(stdout, int(lines_n))
    else:
        stdout = _tail_lines(stdout, 200)

    hints = _extract_selinux_hints(stdout)
    hint_text = "\n".join(hints) if hints else ""

    stderr_out = "\n".join(filter(None, [result.stderr, hint_text]))
    summary_parts = [result.summary]
    if hints:
        summary_parts.append(f"{len(hints)} SELinux denial(s) detected.")

    return ToolResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr_out,
        summary=" ".join(summary_parts),
    )


def _dmesg_errors(args: dict[str, Any]) -> ToolResult:
    """dmesg — show only error-level messages (err + above).

    args:
      lines (int, optional) — number of recent lines (default 100).
    """
    cmd: list[str] = ["dmesg", "--color=never", "-T", "-l", "err,crit,alert,emerg"]
    result = run_subprocess(cmd, timeout=15)

    stdout = result.stdout
    n = int(args.get("lines") or 100)
    stdout = _tail_lines(stdout, n)

    hints = _extract_selinux_hints(stdout)
    hint_text = "\n".join(hints) if hints else ""
    stderr_out = "\n".join(filter(None, [result.stderr, hint_text]))
    summary_parts = [result.summary]
    if hints:
        summary_parts.append(f"{len(hints)} SELinux denial(s) detected.")

    return ToolResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr_out,
        summary=" ".join(summary_parts),
    )


# ---------------------------------------------------------------------------
# Unified execute() dispatcher
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Dispatch an operation to the correct implementation."""
    dispatch = {
        "query": _journalctl_query,
        "tail": _journalctl_tail,
        "since": _journalctl_since,
        "boot_errors": _journalctl_boot_errors,
        "dmesg_query": _dmesg_query,
        "dmesg_errors": _dmesg_errors,
    }
    fn = dispatch.get(op)
    if fn is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr=f"Unknown log operation: {op!r}",
            summary=f"unknown log operation: {op!r}",
        )
    return fn(args)


# ---------------------------------------------------------------------------
# ToolSpec registration
# ---------------------------------------------------------------------------

TOOL_SPEC = ToolSpec(
    name="logs",
    description="Query system logs via journalctl and dmesg; surfaces SELinux hints.",
    ops={
        # -- journalctl operations (all READ — we only display existing log data)
        "query": OpSpec(
            op_name="query",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(name="unit",       type=str, required=False,
                        description="Filter to a systemd unit name"),
                ArgSpec(name="since",      type=str, required=False,
                        description="Start time, e.g. '1 hour ago'"),
                ArgSpec(name="until",      type=str, required=False,
                        description="End time, e.g. '2026-01-01 12:00:00'"),
                ArgSpec(name="priority",   type=str, required=False,
                        description="Log priority 0-7 or name (err, warning, ...)"),
                ArgSpec(name="lines",      type=int, required=False,
                        description="Number of most-recent lines (default 100)"),
                ArgSpec(name="grep",       type=str, required=False,
                        description="Filter output to lines matching this pattern"),
                ArgSpec(name="identifier", type=str, required=False,
                        description="Syslog identifier (-t)"),
                ArgSpec(name="boot",       type=str, required=False,
                        description="Boot ID or offset (--boot)"),
            ],
            description="Query journalctl with optional unit/time/priority/grep filters",
        ),
        "tail": OpSpec(
            op_name="tail",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(name="unit",  type=str, required=False,
                        description="Filter to a systemd unit name"),
                ArgSpec(name="lines", type=int, required=False,
                        description="Number of recent lines to return (default 50)"),
            ],
            description="Show the most recent log entries",
        ),
        "since": OpSpec(
            op_name="since",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(name="since", type=str, required=True,
                        description="Time expression, e.g. '1 hour ago'"),
                ArgSpec(name="unit",  type=str, required=False,
                        description="Filter to a systemd unit name"),
                ArgSpec(name="lines", type=int, required=False,
                        description="Cap on lines returned (default 200)"),
            ],
            description="Show log entries since a given time",
        ),
        "boot_errors": OpSpec(
            op_name="boot_errors",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(name="boot", type=str, required=False,
                        description="Boot ID or offset (default '0' = current boot)"),
            ],
            description="Show error-level and above messages from the specified boot",
        ),
        "dmesg_query": OpSpec(
            op_name="dmesg_query",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(name="level", type=str, required=False,
                        description="Kernel log level: err, warn, info, debug"),
                ArgSpec(name="grep",  type=str, required=False,
                        description="Regex to filter kernel ring buffer lines"),
                ArgSpec(name="lines", type=int, required=False,
                        description="Number of most-recent lines (default 200)"),
                ArgSpec(name="since", type=str, required=False,
                        description="Only show messages since this timestamp (kernel 5.14+)"),
            ],
            description="Query the kernel ring buffer (dmesg), optionally filtered",
        ),
        "dmesg_errors": OpSpec(
            op_name="dmesg_errors",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(name="lines", type=int, required=False,
                        description="Number of recent lines (default 100)"),
            ],
            description="Show error-level kernel messages (err/crit/alert/emerg)",
        ),
    },
    execute=_execute,
)

# Self-register into the module-level singleton when imported.
registry.register(TOOL_SPEC)
