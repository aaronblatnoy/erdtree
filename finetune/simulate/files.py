"""finetune/simulate/files.py — Rocky Linux 9 output simulator for the 'files' tool.

Public API
----------
simulate_files(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 11 real operations declared in core/tools/files.py
           (list, read, stat, find, copy, move, mkdir, chmod, chown, write, remove)
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context — snapshot_text str from make_context(), or a profile
           dict with keys like 'hostname', 'working_directory', etc.

Realism model
-------------
* Outputs mirror actual Rocky Linux 9 ls/stat/cat/find/cp/mv/mkdir/chmod/chown/
  tee/rm shell output, including SELinux-style error messages where appropriate.
* Exit codes mirror real shell behaviour:
    0  — success
    1  — general error (permission denied, target exists, etc.)
    2  — misuse of shell built-in (e.g. bad option)
* Failure triggers are deterministic, keyed on argument values so generate.py
  can produce both success and failure traces without out-of-band config:
    path containing "NOPERM"  → permission denied (exit 1)
    path containing "NOFILE" or "MISSING" (case-insensitive) → no such file (exit 1)
    path containing "BROKEN"  → I/O or other error (exit 1)
    src == "NOSRC" (copy/move) → no such source file (exit 1)
    owner == "NOUSER" (chown) → invalid user (exit 1)
    mode == "BADMODE" (chmod) → invalid mode (exit 1)
* When args is empty ({}) the simulator uses safe defaults and returns a
  SUCCESS result — the validation gate (`simulate_files(op, {}, ctx)`) always
  passes with the four required keys and an I2-clean summary.

I2 compliance
-------------
All `summary` strings are I2-clean (no AI, LLM, model, agent, ollama, inference,
neural, etc.).  The assert_no_ai_language guard is NOT called inline (to keep
this module fast and dependency-light for tests — the test_i2.py suite asserts
every returned summary).

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (to avoid circular deps when
__init__.py imports simulate modules before coreimports is fully settled).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _working_dir(ctx: Any) -> str:
    """Extract current working directory from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("working_directory", "/home/admin")
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("working directory:") or line.lower().startswith("cwd:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return "/home/admin"


def _is_perm_denied(path: str) -> bool:
    """Return True if the path should trigger a permission-denied error."""
    upper = path.upper()
    return "NOPERM" in upper


def _is_not_found(path: str) -> bool:
    """Return True if the path should trigger a not-found error."""
    upper = path.upper()
    return "NOFILE" in upper or "MISSING" in upper


def _is_broken(path: str) -> bool:
    """Return True if the path should trigger a broken/I-O error."""
    return "BROKEN" in path.upper()


def _path_basename(path: str) -> str:
    """Return the last component of a path."""
    return path.rstrip("/").split("/")[-1] or path


def _hash_scatter(key: str, buckets: int) -> int:
    """Return a deterministic integer in [0, buckets) based on key."""
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return h % buckets


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `tree -L 2 <path>` (or `ls -lah` fallback) output."""
    path: str = args.get("path", ".")

    if _is_not_found(path):
        stderr = f"tree: '{path}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Path '{path}' does not exist; listing failed.",
        )

    if _is_perm_denied(path):
        stderr = f"tree: '{path}': Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied when listing '{path}'.",
        )

    # Build a plausible tree output for the path
    base = _path_basename(path)
    stdout = (
        f"{path}\n"
        f"├── bin\n"
        f"│   ├── start.sh\n"
        f"│   └── health_check.sh\n"
        f"├── conf\n"
        f"│   └── {base}.conf\n"
        f"├── data\n"
        f"│   ├── cache\n"
        f"│   └── db\n"
        f"├── logs\n"
        f"│   ├── access.log\n"
        f"│   └── error.log\n"
        f"└── README.txt\n"
        f"\n"
        f"5 directories, 5 files\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Listed '{path}': 5 directories and 5 files found.",
    )


def _sim_read(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `cat <path>` with line cap."""
    path: str = args.get("path", "/etc/hostname")
    lines: int = int(args.get("lines", 200))
    lines = max(1, min(lines, 1000))

    if _is_not_found(path):
        stderr = f"cat: {path}: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"File '{path}' does not exist; read failed.",
        )

    if _is_perm_denied(path):
        stderr = f"cat: {path}: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied reading '{path}'.",
        )

    # Synthesise realistic file content based on extension/name
    base = _path_basename(path)
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""

    if ext in ("conf", "cfg", "ini"):
        content = (
            f"# {base} — configuration file\n"
            f"# Generated on Rocky Linux 9\n"
            f"\n"
            f"[main]\n"
            f"enabled = true\n"
            f"log_level = info\n"
            f"bind_address = 0.0.0.0\n"
            f"port = 8080\n"
            f"\n"
            f"[security]\n"
            f"tls_enabled = true\n"
            f"cert_file = /etc/pki/tls/certs/server.crt\n"
            f"key_file = /etc/pki/tls/private/server.key\n"
        )
    elif ext in ("log",):
        host = _hostname(ctx)
        content = (
            f"Jul 03 00:01:04 {host} systemd[1]: Service started.\n"
            f"Jul 03 00:15:30 {host} sshd[1234]: Accepted publickey for admin\n"
            f"Jul 03 01:00:01 {host} CROND[5678]: (root) CMD (/usr/sbin/logrotate /etc/logrotate.conf)\n"
            f"Jul 03 02:30:15 {host} kernel: EXT4-fs (sda1): mounted filesystem\n"
            f"Jul 03 04:00:01 {host} systemd[1]: Starting daily cleanup.\n"
        )
    elif ext in ("sh", "bash"):
        content = (
            f"#!/bin/bash\n"
            f"# {base}\n"
            f"set -euo pipefail\n"
            f"\n"
            f"echo 'Starting service checks...'\n"
            f"systemctl is-active --quiet nginx.service && echo 'nginx: ok' || echo 'nginx: down'\n"
            f"systemctl is-active --quiet postgresql.service && echo 'postgres: ok' || echo 'postgres: down'\n"
        )
    else:
        host = _hostname(ctx)
        content = (
            f"# {base}\n"
            f"# Host: {host}\n"
            f"# Rocky Linux 9.4\n"
            f"\n"
            f"Contents of {path}.\n"
        )

    content_lines = content.splitlines(keepends=True)
    truncated = len(content_lines) > lines
    if truncated:
        content_lines = content_lines[:lines]
    displayed = len(content_lines)
    suffix = f" (truncated to {lines} lines)" if truncated else ""

    return _make_result(
        exit_code=0,
        stdout="".join(content_lines),
        stderr="",
        summary=f"Read {displayed} lines from '{path}'{suffix}.",
    )


def _sim_stat(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `stat <path>` output."""
    path: str = args.get("path", "/etc/hostname")

    if _is_not_found(path):
        stderr = f"stat: cannot stat '{path}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Path '{path}' does not exist; stat failed.",
        )

    if _is_perm_denied(path):
        stderr = f"stat: cannot stat '{path}': Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied when running stat on '{path}'.",
        )

    # Deterministic inode / size from path hash
    h = _hash_scatter(path, 100000)
    inode = 131072 + h
    size = 512 + _hash_scatter(path + "size", 65536)
    base = _path_basename(path)
    is_dir = "." not in base or path.endswith("/")

    if is_dir:
        file_type = "directory"
        mode_str = "0755/drwxr-xr-x"
        size = 4096
    else:
        file_type = "regular file"
        mode_str = "0644/-rw-r--r--"

    stdout = (
        f"  File: {path}\n"
        f"  Size: {size}\t\tBlocks: {(size // 512 + 1) * 8}\t"
        f"IO Block: 4096   {file_type}\n"
        f"Device: fd01h/{64769}d\tInode: {inode}\t Links: 1\n"
        f"Access: ({mode_str})  Uid: (    0/    root)   Gid: (    0/    root)\n"
        f"Context: system_u:object_r:etc_t:s0\n"
        f"Access: 2026-07-03 08:12:40.000000000 +0000\n"
        f"Modify: 2026-07-01 14:35:22.000000000 +0000\n"
        f"Change: 2026-07-01 14:35:22.000000000 +0000\n"
        f" Birth: 2026-06-15 09:00:00.000000000 +0000\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Stat for '{path}' retrieved ({file_type}, {size} bytes).",
    )


def _sim_find(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `find <path> [-name <pat>] [-type <t>] [-maxdepth <d>]` output."""
    path: str = args.get("path", ".")
    name: str | None = args.get("name")
    file_type: str | None = args.get("type")
    maxdepth = args.get("maxdepth")

    if _is_not_found(path):
        stderr = f"find: '{path}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Search root '{path}' does not exist; find failed.",
        )

    if _is_perm_denied(path):
        stderr = f"find: '{path}': Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied searching under '{path}'.",
        )

    # Build a deterministic but plausible list of matches
    pattern = name or "*"
    ext = pattern.lstrip("*.").lower() if "*" in pattern else pattern

    if file_type == "d":
        entries = [
            f"{path}/conf",
            f"{path}/data",
            f"{path}/logs",
            f"{path}/run",
        ]
    elif ext in ("log",):
        entries = [
            f"{path}/logs/access.log",
            f"{path}/logs/error.log",
            f"{path}/logs/audit.log",
        ]
    elif ext in ("conf", "cfg"):
        entries = [
            f"{path}/conf/main.conf",
            f"{path}/conf/tls.conf",
        ]
    else:
        entries = [
            f"{path}/bin/start.sh",
            f"{path}/conf/main.conf",
            f"{path}/data/cache",
            f"{path}/logs/access.log",
            f"{path}/logs/error.log",
            f"{path}/README.txt",
        ]

    # Apply maxdepth limit (simulate fewer results at shallow depths)
    if maxdepth is not None and int(maxdepth) <= 1:
        entries = entries[:2]

    stdout = "\n".join(entries) + "\n" if entries else ""
    count = len(entries)
    name_desc = f" matching '{name}'" if name else ""

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found {count} entries under '{path}'{name_desc}.",
    )


def _sim_copy(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `cp [-r] <src> <dst>` output."""
    src: str = args.get("src", "/tmp/source.txt")
    dst: str = args.get("dst", "/tmp/dest.txt")
    recursive: bool = bool(args.get("recursive", False))

    if src.upper() == "NOSRC" or _is_not_found(src):
        stderr = f"cp: cannot stat '{src}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Source '{src}' does not exist; copy failed.",
        )

    if _is_perm_denied(dst) or _is_perm_denied(src):
        denied = dst if _is_perm_denied(dst) else src
        stderr = f"cp: cannot create regular file '{dst}': Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied; copy to '{dst}' failed.",
        )

    # Recursive copy of a directory without -r flag
    if not recursive and _hash_scatter(src + dst, 8) == 0:
        stderr = f"cp: -r not specified; omitting directory '{src}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Copy failed: '{src}' is a directory and -r was not set.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Copied '{src}' to '{dst}'.",
    )


def _sim_move(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `mv <src> <dst>` output."""
    src: str = args.get("src", "/tmp/source.txt")
    dst: str = args.get("dst", "/tmp/dest.txt")

    if src.upper() == "NOSRC" or _is_not_found(src):
        stderr = f"mv: cannot stat '{src}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Source '{src}' does not exist; move failed.",
        )

    if _is_perm_denied(dst) or _is_perm_denied(src):
        stderr = f"mv: cannot move '{src}' to '{dst}': Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied; move to '{dst}' failed.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Moved '{src}' to '{dst}'.",
    )


def _sim_mkdir(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `mkdir [-p] <path>` output."""
    path: str = args.get("path", "/tmp/newdir")
    parents: bool = bool(args.get("parents", True))

    if _is_perm_denied(path):
        stderr = f"mkdir: cannot create directory '{path}': Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied; directory '{path}' could not be created.",
        )

    # Simulate "already exists" error when parents=False and hash triggers it
    if not parents and _hash_scatter(path, 5) == 0:
        stderr = f"mkdir: cannot create directory '{path}': File exists\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Directory '{path}' already exists; mkdir without -p failed.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Directory '{path}' created.",
    )


def _sim_chmod(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `chmod [-R] <mode> <path>` output."""
    mode: str = args.get("mode", "644")
    path: str = args.get("path", "/tmp/file.txt")
    recursive: bool = bool(args.get("recursive", False))

    if mode.upper() == "BADMODE":
        stderr = f"chmod: invalid mode: '{mode}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Invalid permission mode '{mode}'; chmod failed.",
        )

    if _is_not_found(path):
        stderr = f"chmod: cannot access '{path}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Path '{path}' does not exist; chmod failed.",
        )

    if _is_perm_denied(path):
        stderr = f"chmod: changing permissions of '{path}': Operation not permitted\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied; chmod on '{path}' failed.",
        )

    scope = "recursively " if recursive else ""
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Permissions on '{path}' {scope}changed to {mode}.",
    )


def _sim_chown(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `chown [-R] <owner> <path>` output."""
    owner: str = args.get("owner", "root:root")
    path: str = args.get("path", "/tmp/file.txt")
    recursive: bool = bool(args.get("recursive", False))

    if owner.upper() == "NOUSER" or "NOUSER" in owner.upper():
        user_part = owner.split(":")[0]
        stderr = f"chown: invalid user: '{user_part}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"User '{user_part}' does not exist; chown failed.",
        )

    if _is_not_found(path):
        stderr = f"chown: cannot access '{path}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Path '{path}' does not exist; chown failed.",
        )

    if _is_perm_denied(path):
        stderr = f"chown: changing ownership of '{path}': Operation not permitted\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied; chown on '{path}' failed.",
        )

    scope = "recursively " if recursive else ""
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Ownership of '{path}' {scope}changed to {owner}.",
    )


def _sim_write(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `tee <path>` with content piped in."""
    path: str = args.get("path", "/tmp/output.txt")
    content: str = args.get("content", "")

    if _is_perm_denied(path):
        stderr = f"tee: {path}: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied; write to '{path}' failed.",
        )

    if _is_broken(path):
        stderr = f"tee: {path}: Input/output error\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"I/O error writing to '{path}'; the path may be on a failing device.",
        )

    # tee echoes the content to stdout as well as writing it to the file
    byte_count = len(content.encode())
    return _make_result(
        exit_code=0,
        stdout=content,
        stderr="",
        summary=f"Wrote {byte_count} bytes to '{path}'.",
    )


def _sim_remove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate `rm [-r] [-f] <path>` output."""
    path: str = args.get("path", "/tmp/file.txt")
    recursive: bool = bool(args.get("recursive", False))
    force: bool = bool(args.get("force", False))

    # Without force, a missing file is an error
    if _is_not_found(path) and not force:
        stderr = f"rm: cannot remove '{path}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Path '{path}' does not exist; removal failed.",
        )

    # force + missing = silent success (rm -f on absent file exits 0)
    if _is_not_found(path) and force:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary=f"'{path}' did not exist; removal completed without error (force mode).",
        )

    if _is_perm_denied(path):
        stderr = f"rm: cannot remove '{path}': Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Permission denied; removal of '{path}' failed.",
        )

    # Attempting to remove a directory without -r
    if not recursive and _hash_scatter(path + "isdir", 4) == 0:
        stderr = f"rm: cannot remove '{path}': Is a directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"'{path}' is a directory; use recursive removal to remove it.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Removed '{path}'.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "list":   _sim_list,
    "read":   _sim_read,
    "stat":   _sim_stat,
    "find":   _sim_find,
    "copy":   _sim_copy,
    "move":   _sim_move,
    "mkdir":  _sim_mkdir,
    "chmod":  _sim_chmod,
    "chown":  _sim_chown,
    "write":  _sim_write,
    "remove": _sim_remove,
}


def simulate_files(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'files' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 11 real ops declared in
           core/tools/files.py (list, read, stat, find, copy, move, mkdir,
           chmod, chown, write, remove).
    args : argument dict (may be sparse; per-op defaults are applied).
    ctx  : system context — snapshot_text str from make_context(), or a profile
           dict with keys like 'hostname', 'working_directory'.

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
            f"simulate_files: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
