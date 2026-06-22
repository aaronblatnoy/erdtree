"""core/tools/files.py — Filesystem operations tool.

Supported operations
--------------------
  list    (READ)       — list directory contents via ls.
  read    (READ)       — show file contents via cat (line-capped).
  stat    (READ)       — show file/directory metadata via stat.
  find    (READ)       — search for files via find.
  copy    (WRITE)      — copy files/dirs via cp.
  move    (WRITE)      — move/rename files via mv.
  mkdir   (WRITE)      — create a directory via mkdir.
  chmod   (WRITE)      — change file permissions via chmod.
  chown   (WRITE)      — change file ownership via chown.
  write   (WRITE)      — write content to a file via tee.
  remove  (WRITE/DESTR)— remove files/dirs via rm.  Recursive or forced removal
                         of a system path is DESTRUCTIVE; the classifier decides
                         based on the synthesized command line (rm -rf <path>).

Permission mapping
------------------
  READ       : list, read, stat, find
  WRITE      : copy, move, mkdir, chmod, chown, write, remove (plain)
  DESTRUCTIVE: remove when synthesize_command emits 'rm -rf <path>'
               or when the target is a system/critical path — the EXISTING
               classifier in permissions.py fires on the synthesized string;
               this tool does NOT self-classify (I3 / A3).

Design rules
------------
  I1  No external network calls; all ops shell out only via run_subprocess.
  I2  No AI/LLM/model/agent/agentic language in any user-facing string.
  I3  The caller (router / REPL) MUST resolve the permission gate BEFORE
      calling execute().  This module does NOT call permissions.classify().
  I4  Audit is the caller's responsibility; no audit code here.
  I6  Zero tier/product/model names.
  I9  No exception escapes: every failure path returns a ToolResult.

SELinux note
------------
  File operations on SELinux-enforcing systems frequently trip AVC denials
  (context mismatches on copied/moved files, label changes on chmod/chown).
  The _maybe_selinux_hint helper surfaces a hint in those cases.

Subprocess mocking
------------------
  On the build host, binaries such as ls/stat/cat/find/cp/mv/rm/mkdir/
  chmod/chown/tee may exist but tests must NOT rely on them. Every test
  patches ``core.tools.files.run_subprocess`` so no real process runs.
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
# SELinux hint detection (copied from services.py — see CLAUDE.md template)
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
# Read line cap
# ---------------------------------------------------------------------------

_READ_LINE_DEFAULT = 200
_READ_LINE_MAX = 1000


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list(args: dict[str, Any]) -> ToolResult:
    """ls -lah <path>"""
    path: str = args.get("path", ".")
    result = run_subprocess(["ls", "-lah", path])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = result.stdout.count("\n")
        summary = f"Listed {line_count} entries in '{path}'."
    else:
        summary = f"Listing '{path}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_read(args: dict[str, Any]) -> ToolResult:
    """cat <path> — output is capped at _READ_LINE_MAX lines."""
    path: str = args["path"]
    raw_lines = args.get("lines")
    lines: int = int(raw_lines) if raw_lines is not None else _READ_LINE_DEFAULT
    lines = max(1, min(lines, _READ_LINE_MAX))

    result = run_subprocess(["cat", path])
    selinux = _maybe_selinux_hint(result.stderr)

    if result.ok:
        # Clamp output to the requested line count.
        raw_lines_list = result.stdout.splitlines(keepends=True)
        truncated = False
        if len(raw_lines_list) > lines:
            raw_lines_list = raw_lines_list[:lines]
            truncated = True
        stdout = "".join(raw_lines_list)
        suffix = f" (truncated to {lines} lines)" if truncated else ""
        summary = f"Read {len(raw_lines_list)} lines from '{path}'{suffix}."
    else:
        stdout = result.stdout
        summary = f"Reading '{path}' failed (exit {result.exit_code})."

    return ToolResult(
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_stat(args: dict[str, Any]) -> ToolResult:
    """stat <path>"""
    path: str = args["path"]
    result = run_subprocess(["stat", path])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Stat for '{path}' retrieved."
    else:
        summary = f"Stat for '{path}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_find(args: dict[str, Any]) -> ToolResult:
    """find <path> [-name <pattern>] [-type <type>] [-maxdepth <depth>]"""
    path: str = args.get("path", ".")
    cmd = ["find", path]

    name: str | None = args.get("name")
    if name:
        cmd += ["-name", name]

    file_type: str | None = args.get("type")
    if file_type:
        cmd += ["-type", file_type]

    maxdepth = args.get("maxdepth")
    if maxdepth is not None:
        cmd += ["-maxdepth", str(int(maxdepth))]

    result = run_subprocess(cmd)
    if result.ok:
        match_count = len([l for l in result.stdout.splitlines() if l.strip()])
        summary = f"Found {match_count} entries under '{path}'."
    else:
        summary = f"Search under '{path}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary,
    )


def _op_copy(args: dict[str, Any]) -> ToolResult:
    """cp [-r] <src> <dst>"""
    src: str = args["src"]
    dst: str = args["dst"]
    recursive: bool = bool(args.get("recursive", False))
    cmd = ["cp"]
    if recursive:
        cmd.append("-r")
    cmd += [src, dst]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Copied '{src}' to '{dst}'."
    else:
        summary = f"Copy from '{src}' to '{dst}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_move(args: dict[str, Any]) -> ToolResult:
    """mv <src> <dst>"""
    src: str = args["src"]
    dst: str = args["dst"]
    result = run_subprocess(["mv", src, dst])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Moved '{src}' to '{dst}'."
    else:
        summary = f"Move from '{src}' to '{dst}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_mkdir(args: dict[str, Any]) -> ToolResult:
    """mkdir [-p] <path>"""
    path: str = args["path"]
    parents: bool = bool(args.get("parents", True))
    cmd = ["mkdir"]
    if parents:
        cmd.append("-p")
    cmd.append(path)
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Directory '{path}' created."
    else:
        summary = f"Creating directory '{path}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_chmod(args: dict[str, Any]) -> ToolResult:
    """chmod [-R] <mode> <path>"""
    mode: str = args["mode"]
    path: str = args["path"]
    recursive: bool = bool(args.get("recursive", False))
    cmd = ["chmod"]
    if recursive:
        cmd.append("-R")
    cmd += [mode, path]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Permissions on '{path}' changed to {mode}."
    else:
        summary = f"chmod on '{path}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_chown(args: dict[str, Any]) -> ToolResult:
    """chown [-R] <owner> <path>"""
    owner: str = args["owner"]
    path: str = args["path"]
    recursive: bool = bool(args.get("recursive", False))
    cmd = ["chown"]
    if recursive:
        cmd.append("-R")
    cmd += [owner, path]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Ownership of '{path}' changed to {owner}."
    else:
        summary = f"chown on '{path}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_write(args: dict[str, Any]) -> ToolResult:
    """Write content to a file via tee (overwrite mode: tee <path>)."""
    path: str = args["path"]
    content: str = args["content"]
    result = run_subprocess(["tee", path], input=content)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        byte_count = len(content.encode())
        summary = f"Wrote {byte_count} bytes to '{path}'."
    else:
        summary = f"Writing to '{path}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_remove(args: dict[str, Any]) -> ToolResult:
    """rm [-r] [-f] <path>

    The synthesized command line (built by synthesize_command in repl.py) drives
    the classifier gate — NOT this function. This function simply builds and
    executes the command that synthesize_command already declared safe to run.
    Plain remove: 'rm <path>' -> WRITE.
    Recursive/forced: 'rm -rf <path>' -> DESTRUCTIVE (classifier handles it).
    """
    path: str = args["path"]
    recursive: bool = bool(args.get("recursive", False))
    force: bool = bool(args.get("force", False))
    cmd = ["rm"]
    if recursive:
        cmd.append("-r")
    if force:
        cmd.append("-f")
    cmd.append(path)
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Removed '{path}'."
    else:
        summary = f"Removal of '{path}' failed (exit {result.exit_code})."
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
    "list": _op_list,
    "read": _op_read,
    "stat": _op_stat,
    "find": _op_find,
    "copy": _op_copy,
    "move": _op_move,
    "mkdir": _op_mkdir,
    "chmod": _op_chmod,
    "chown": _op_chown,
    "write": _op_write,
    "remove": _op_remove,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a files operation and return a structured ToolResult.

    The caller (Phase 4 router) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never writes to the audit log itself (I4 is the caller's responsibility).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for files tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_PATH_ARG = ArgSpec(
    name="path",
    type=str,
    required=True,
    description="The filesystem path to operate on.",
)

_PATH_OPT_ARG = ArgSpec(
    name="path",
    type=str,
    required=False,
    description="The filesystem path to operate on (default: current directory).",
    default=".",
)

FILES_SPEC = ToolSpec(
    name="files",
    description="Inspect and manipulate files and directories on the local filesystem.",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[_PATH_OPT_ARG],
            description="List directory contents.",
        ),
        "read": OpSpec(
            op_name="read",
            permission_class=OpClass.READ,
            args=[
                _PATH_ARG,
                ArgSpec(
                    name="lines",
                    type=int,
                    required=False,
                    description=(
                        f"Maximum lines to return (default {_READ_LINE_DEFAULT}, "
                        f"max {_READ_LINE_MAX})."
                    ),
                    default=_READ_LINE_DEFAULT,
                ),
            ],
            description="Show the contents of a file (output is line-capped).",
        ),
        "stat": OpSpec(
            op_name="stat",
            permission_class=OpClass.READ,
            args=[_PATH_ARG],
            description="Show metadata (size, permissions, timestamps) for a path.",
        ),
        "find": OpSpec(
            op_name="find",
            permission_class=OpClass.READ,
            args=[
                _PATH_OPT_ARG,
                ArgSpec(
                    name="name",
                    type=str,
                    required=False,
                    description="Filename pattern to match (passed to find -name).",
                ),
                ArgSpec(
                    name="type",
                    type=str,
                    required=False,
                    description="Entry type filter: 'f' for files, 'd' for directories.",
                ),
                ArgSpec(
                    name="maxdepth",
                    type=int,
                    required=False,
                    description="Maximum directory depth to descend.",
                ),
            ],
            description="Search for files and directories under a path.",
        ),
        "copy": OpSpec(
            op_name="copy",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(name="src", type=str, required=True,
                        description="Source path."),
                ArgSpec(name="dst", type=str, required=True,
                        description="Destination path."),
                ArgSpec(name="recursive", type=bool, required=False,
                        description="Copy directories recursively.", default=False),
            ],
            description="Copy a file or directory to a new location.",
        ),
        "move": OpSpec(
            op_name="move",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(name="src", type=str, required=True,
                        description="Source path."),
                ArgSpec(name="dst", type=str, required=True,
                        description="Destination path."),
            ],
            description="Move or rename a file or directory.",
        ),
        "mkdir": OpSpec(
            op_name="mkdir",
            permission_class=OpClass.WRITE,
            args=[
                _PATH_ARG,
                ArgSpec(name="parents", type=bool, required=False,
                        description="Create parent directories as needed.", default=True),
            ],
            description="Create a directory (and parent directories by default).",
        ),
        "chmod": OpSpec(
            op_name="chmod",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(name="mode", type=str, required=True,
                        description="Permission mode (e.g. '755', 'u+x')."),
                _PATH_ARG,
                ArgSpec(name="recursive", type=bool, required=False,
                        description="Apply permissions recursively.", default=False),
            ],
            description="Change the permissions of a file or directory.",
        ),
        "chown": OpSpec(
            op_name="chown",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(name="owner", type=str, required=True,
                        description="New owner (user or user:group)."),
                _PATH_ARG,
                ArgSpec(name="recursive", type=bool, required=False,
                        description="Apply ownership change recursively.", default=False),
            ],
            description="Change the ownership of a file or directory.",
        ),
        "write": OpSpec(
            op_name="write",
            permission_class=OpClass.WRITE,
            args=[
                _PATH_ARG,
                ArgSpec(name="content", type=str, required=True,
                        description="Text content to write to the file."),
            ],
            description="Write text content to a file, replacing existing contents.",
        ),
        "remove": OpSpec(
            op_name="remove",
            permission_class=OpClass.WRITE,
            args=[
                _PATH_ARG,
                ArgSpec(name="recursive", type=bool, required=False,
                        description="Remove directories recursively.", default=False),
                ArgSpec(name="force", type=bool, required=False,
                        description="Force removal without prompting.", default=False),
            ],
            description=(
                "Remove a file or directory. Recursive or forced removal of system "
                "paths requires typed confirmation."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(FILES_SPEC)
