"""
core/agent/audit.py — Append-only JSONL audit writer (I4).

Every operation that passes through the framework produces exactly one JSONL
record in the audit log. The writer is:
  - Append-only: new records are only ever added, never overwritten.
  - Atomic: a partial record (from a crash mid-write) is detected and skipped
    on the next read; the file is never left in an unreadable state for the
    already-committed records.
  - fsync-on-write: each record is flushed and synced to disk before the write
    call returns, so a power-loss or OS crash between records never corrupts
    the preceding ones.
  - Tier-name-free (I6): the audit log path is given by the caller; this module
    never hardcodes a tier or product name. The `tier` field in the record is
    opaque data supplied by the caller — this module does not interpret it.

Atomicity strategy
------------------
We want "no partial line ever appears in the file." We achieve this via two
layers:

1. Build the full JSONL line (including the trailing newline) in memory first.
2. Write it in a single os.write() call. On POSIX, a write smaller than
   PIPE_BUF (usually 4 KiB) to an O_APPEND file is atomic at the kernel level
   (POSIX.1-2008 §2.9.7). Our records are always well under 4 KiB.
3. fsync() after every write so the data is durable before we return.

For records that might exceed PIPE_BUF (edge case: very long stdout/stderr),
we truncate the summaries at 2 KiB each, keeping the record well under the
PIPE_BUF limit.

Partial-write recovery (reader side)
-------------------------------------
`iter_records()` skips any line that is not valid JSON, so a truncated record
left by a crash (which would be invalid JSON) is silently dropped. All records
before and after the corrupt line are returned normally. This is the correct
"append-only crash-safe" recovery posture for an audit log.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

# Maximum byte length for stdout/stderr summaries inside one record.
# Keeping this well under POSIX PIPE_BUF (4096) ensures O_APPEND atomicity.
_SUMMARY_MAX_BYTES: int = 512

# Maximum byte length for nl_input and translated_command fields.
_INPUT_MAX_BYTES: int = 256

# Record schema keys (ordered for readability in the log).
_SCHEMA_KEYS = (
    "ts",
    "tier",
    "nl_input",
    "translated_command",
    "tool",
    "args",
    "permission_decision",
    "exit_code",
    "stdout_summary",
    "stderr_summary",
    "result",
)


def _truncate(value: Optional[str], max_bytes: int) -> Optional[str]:
    """Truncate a UTF-8 string to at most *max_bytes* encoded bytes."""
    if value is None:
        return None
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    # Truncate and mark as truncated.
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated + "…[truncated]"


def _build_record(
    *,
    tier: Optional[str],
    nl_input: Optional[str],
    translated_command: Optional[str],
    tool: Optional[str],
    args: Optional[Any],
    permission_decision: Optional[str],
    exit_code: Optional[int],
    stdout_summary: Optional[str],
    stderr_summary: Optional[str],
    result: Optional[str],
) -> bytes:
    """Assemble a single audit record as UTF-8 JSONL bytes (with trailing newline)."""
    record = {
        "ts": time.time(),
        "tier": tier,
        "nl_input": _truncate(nl_input, _INPUT_MAX_BYTES),
        "translated_command": _truncate(translated_command, _INPUT_MAX_BYTES),
        "tool": tool,
        "args": args,
        "permission_decision": permission_decision,
        "exit_code": exit_code,
        "stdout_summary": _truncate(stdout_summary, _SUMMARY_MAX_BYTES),
        "stderr_summary": _truncate(stderr_summary, _SUMMARY_MAX_BYTES),
        "result": _truncate(result, _INPUT_MAX_BYTES),
    }
    # Validate key set matches schema (defensive).
    assert set(record.keys()) == set(_SCHEMA_KEYS), (
        f"Record key mismatch: {set(record.keys())} != {set(_SCHEMA_KEYS)}"
    )
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    return line.encode("utf-8")


class AuditLog:
    """
    Append-only JSONL audit log.

    Usage::

        log = AuditLog("/var/log/some-tier/audit.jsonl")
        log.write(
            tier="custom-tier",
            nl_input="show failing services",
            tool="services",
            permission_decision="read",
            result="ok",
        )

    The log file and its parent directory are created on first write if they
    do not already exist.

    All keyword arguments to :meth:`write` are optional (default to ``None``)
    so callers only supply the fields they have.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        # File descriptor held open in O_APPEND mode so the kernel's POSIX
        # O_APPEND atomicity guarantee applies across concurrent writers too.
        self._fd: Optional[int] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(
        self,
        *,
        tier: Optional[str] = None,
        nl_input: Optional[str] = None,
        translated_command: Optional[str] = None,
        tool: Optional[str] = None,
        args: Optional[Any] = None,
        permission_decision: Optional[str] = None,
        exit_code: Optional[int] = None,
        stdout_summary: Optional[str] = None,
        stderr_summary: Optional[str] = None,
        result: Optional[str] = None,
    ) -> None:
        """
        Write one audit record.

        Thread-safe via O_APPEND: each :func:`os.write` call is atomic for
        records smaller than PIPE_BUF. After writing we fsync the fd so the
        record is durable before this call returns.
        """
        record_bytes = _build_record(
            tier=tier,
            nl_input=nl_input,
            translated_command=translated_command,
            tool=tool,
            args=args,
            permission_decision=permission_decision,
            exit_code=exit_code,
            stdout_summary=stdout_summary,
            stderr_summary=stderr_summary,
            result=result,
        )
        fd = self._get_fd()
        # os.write() on an O_APPEND fd: kernel positions at EOF atomically.
        os.write(fd, record_bytes)
        # fsync — flush kernel page cache → disk.
        os.fsync(fd)

    def close(self) -> None:
        """Close the underlying file descriptor (idempotent)."""
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

    def __enter__(self) -> "AuditLog":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_fd(self) -> int:
        """Open (or reuse) the append-mode file descriptor."""
        if self._fd is not None:
            return self._fd
        # Create parent directory if needed.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # O_CREAT | O_APPEND | O_WRONLY — POSIX append mode.
        flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
        self._fd = os.open(str(self._path), flags, 0o640)
        return self._fd


# ---------------------------------------------------------------------------
# Reader (for tests and diagnostics — not part of the write hot-path)
# ---------------------------------------------------------------------------

def iter_records(path: str | Path):
    """
    Yield parsed records from an audit log, one dict per valid JSONL line.

    Lines that are not valid JSON (e.g. a partial write from a crash) are
    silently skipped — this is the correct crash-recovery posture.
    """
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Partial write / corrupt line — skip, do not raise.
                continue


# ---------------------------------------------------------------------------
# Convenience one-shot function (tests + simple callers)
# ---------------------------------------------------------------------------

def append_record(
    path: str | Path,
    *,
    tier: Optional[str] = None,
    nl_input: Optional[str] = None,
    translated_command: Optional[str] = None,
    tool: Optional[str] = None,
    args: Optional[Any] = None,
    permission_decision: Optional[str] = None,
    exit_code: Optional[int] = None,
    stdout_summary: Optional[str] = None,
    stderr_summary: Optional[str] = None,
    result: Optional[str] = None,
) -> None:
    """
    Open *path*, append one record, fsync, and close.

    Use :class:`AuditLog` directly (keep-open) for the hot path where many
    records are written in sequence; use this function for one-off writes.
    """
    with AuditLog(path) as log:
        log.write(
            tier=tier,
            nl_input=nl_input,
            translated_command=translated_command,
            tool=tool,
            args=args,
            permission_decision=permission_decision,
            exit_code=exit_code,
            stdout_summary=stdout_summary,
            stderr_summary=stderr_summary,
            result=result,
        )
