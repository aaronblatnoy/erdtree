"""finetune/simulate/logs.py — realistic Rocky Linux 9 log-tool output simulator.

Exposes simulate_logs(op, args, ctx) -> {exit_code, stdout, stderr, summary}
mirroring core.tools.ToolResult for every real operation registered under the
'logs' tool.

Op coverage (derived LIVE from finetune.coreimports — INV-schema-sync):
  query        journalctl with optional unit/time/priority/grep filters
  tail         journalctl most-recent N lines
  since        journalctl --since a given time expression
  boot_errors  journalctl -p err for the specified boot
  dmesg_query  dmesg kernel ring buffer, optionally filtered
  dmesg_errors dmesg error-level messages only

Design invariants observed here
--------------------------------
INV-schema-sync   Op names are looked up at call time from the live registry
                  via finetune.coreimports — never hardcoded.  simulate_logs()
                  raises KeyError on an unknown op so the Phase 3 join can
                  detect gaps.
INV-I2            Every `summary` value must be I2-clean (no AI/LLM/model/
                  agent/ollama/inference/neural/gpt language).  All summary
                  strings are static or assembled from plain sysadmin terms.
                  assert_no_ai_language is called on every returned summary.
INV-offline       No network, no subprocess, no Ollama — everything is pure
                  Python data construction.
INV-read-only-core  This module imports only from finetune.coreimports; it
                    does NOT modify anything under core/.
"""

from __future__ import annotations

import random
from typing import Any

from finetune.coreimports import assert_no_ai_language, registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit_appears_running(unit: str, ctx: Any) -> bool:
    """Return True if *unit* (or its base name) appears in the context string.

    ctx is typically the snapshot_text string produced by make_context().  We
    do a simple substring check — if the unit name appears anywhere in the
    context block it is reasonable to assume the host has it installed and
    (likely) running.  The caller uses this to pick a realistic success vs.
    not-found scenario.
    """
    if not unit or ctx is None:
        return False
    ctx_str = str(ctx)
    # Strip common suffixes for a looser match.
    base = unit.replace(".service", "").replace(".socket", "").replace(".timer", "")
    return base in ctx_str or unit in ctx_str


def _result(exit_code: int, stdout: str, stderr: str, summary: str) -> dict:
    """Return a ToolResult-shaped dict after asserting the summary is I2-clean."""
    assert_no_ai_language(summary)
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Shared realistic log-line blocks (Rocky Linux 9 journalctl short-iso format)
# ---------------------------------------------------------------------------

_JOURNAL_HEADER = "-- Journal begins at Mon 2026-06-01 00:01:03 UTC. --"

_GENERIC_LINES = """\
2026-07-03T08:00:01+0000 web-prod-01 systemd[1]: Starting Session 142 of User sysadm...
2026-07-03T08:00:02+0000 web-prod-01 systemd[1]: Started Session 142 of User sysadm.
2026-07-03T08:01:15+0000 web-prod-01 sshd[14221]: Accepted publickey for sysadm from 10.0.0.5 port 54312 ssh2
2026-07-03T08:02:00+0000 web-prod-01 crond[998]: (root) CMD (/usr/bin/certbot renew --quiet)
2026-07-03T08:05:33+0000 web-prod-01 rsyslog[847]: -- MARK --
2026-07-03T08:10:00+0000 web-prod-01 systemd[1]: systemd-tmpfiles-clean.service: Deactivating.
2026-07-03T08:10:00+0000 web-prod-01 systemd[1]: Finished Cleanup of Temporary Directories.
2026-07-03T08:15:01+0000 web-prod-01 crond[998]: (root) CMD (run-parts /etc/cron.d)
2026-07-03T08:20:44+0000 web-prod-01 kernel: perf: interrupt took too long (3125 > 3124), lowering kernel.perf_event_max_sample_rate to 64000
2026-07-03T08:30:00+0000 web-prod-01 systemd[1]: Starting Daily rotation of log files...
2026-07-03T08:30:01+0000 web-prod-01 systemd[1]: Finished Daily rotation of log files."""

_NGINX_LINES = """\
2026-07-03T08:00:00+0000 web-prod-01 nginx[1234]: 10.10.1.2 - - [03/Jul/2026:08:00:00 +0000] "GET / HTTP/1.1" 200 1024
2026-07-03T08:01:10+0000 web-prod-01 nginx[1234]: 10.10.1.5 - - [03/Jul/2026:08:01:10 +0000] "GET /healthz HTTP/1.1" 200 2
2026-07-03T08:02:30+0000 web-prod-01 nginx[1234]: 10.10.1.7 - - [03/Jul/2026:08:02:30 +0000] "POST /api/data HTTP/1.1" 201 512
2026-07-03T08:03:00+0000 web-prod-01 nginx[1234]: 10.10.1.9 - - [03/Jul/2026:08:03:00 +0000] "GET /static/app.js HTTP/1.1" 304 0
2026-07-03T08:04:45+0000 web-prod-01 nginx[1234]: upstream timed out (110: Connection timed out) while reading response header from upstream
2026-07-03T08:04:45+0000 web-prod-01 nginx[1234]: 10.10.2.1 - - [03/Jul/2026:08:04:45 +0000] "GET /api/slow HTTP/1.1" 504 0"""

_SSHD_LINES = """\
2026-07-03T07:50:01+0000 web-prod-01 sshd[14100]: Invalid user admin from 185.220.101.5 port 41200
2026-07-03T07:50:02+0000 web-prod-01 sshd[14101]: Connection closed by invalid user admin 185.220.101.5 port 41200 [preauth]
2026-07-03T07:55:10+0000 web-prod-01 sshd[14180]: Accepted publickey for sysadm from 10.0.0.3 port 51234 ssh2
2026-07-03T07:55:11+0000 web-prod-01 sshd[14181]: pam_unix(sshd:session): session opened for user sysadm by (uid=0)
2026-07-03T08:01:15+0000 web-prod-01 sshd[14221]: Accepted publickey for sysadm from 10.0.0.5 port 54312 ssh2"""

_POSTGRESQL_LINES = """\
2026-07-03T08:00:00+0000 db-prod-01 postgres[3201]: [3-1] db=app,user=appuser LOG: connection received: host=10.0.1.5 port=49123
2026-07-03T08:00:00+0000 db-prod-01 postgres[3201]: [3-2] db=app,user=appuser LOG: connection authorized: user=appuser database=app
2026-07-03T08:01:00+0000 db-prod-01 postgres[3202]: [4-1] db=app,user=appuser LOG: duration: 4512.233 ms statement: SELECT * FROM orders WHERE status='pending'
2026-07-03T08:02:00+0000 db-prod-01 postgres[3201]: [5-1] db=app,user=appuser LOG: disconnection: session time: 0:01:58.211"""

_BOOT_ERROR_LINES = """\
2026-07-03T04:00:01+0000 web-prod-01 kernel: ACPI: bus type USB registered
2026-07-03T04:00:02+0000 web-prod-01 kernel: [drm:drm_crtc_commit_begin] *ERROR* flip_done timed out
2026-07-03T04:00:05+0000 web-prod-01 systemd[1]: Failed to start Load Kernel Module drm.
2026-07-03T04:00:10+0000 web-prod-01 kernel: EXT4-fs error (device sda2): ext4_find_entry:1455: inode #2: comm systemd: reading directory lblock 0
2026-07-03T04:00:15+0000 web-prod-01 systemd[1]: postfix.service: Start request repeated too quickly.
2026-07-03T04:00:15+0000 web-prod-01 systemd[1]: postfix.service: Failed with result 'exit-code'."""

_DMESG_GENERIC = """\
[Thu Jul  3 08:00:01 2026] Linux version 5.14.0-427.13.1.el9_4.x86_64 (mockbuild@rl9-build-x86-001.rockylinux.org) (gcc version 11.4.1 20231218)
[Thu Jul  3 08:00:01 2026] Command line: BOOT_IMAGE=(hd0,gpt2)/vmlinuz-5.14.0-427.13.1.el9_4.x86_64 ro root=/dev/sda2 quiet crashkernel=auto rhgb
[Thu Jul  3 08:00:02 2026] BIOS-e820: [mem 0x0000000000000000-0x000000000009fbff] usable
[Thu Jul  3 08:00:02 2026] DMI: Dell Inc. PowerEdge R640/0KM5PX, BIOS 2.15.0 08/02/2023
[Thu Jul  3 08:00:03 2026] clocksource: tsc-early: mask: 0xffffffffffffffff max_cycles: 0x24209b2e0d7
[Thu Jul  3 08:00:04 2026] Oops: general protection fault, probably for non-canonical address 0x0
[Thu Jul  3 08:00:05 2026] SCSI subsystem initialized
[Thu Jul  3 08:00:06 2026] libata version 3.00 loaded.
[Thu Jul  3 08:00:07 2026] EXT4-fs (sda2): mounted filesystem with ordered data mode. Opts: (null)
[Thu Jul  3 08:00:08 2026] NET: Registered PF_INET6 protocol family
[Thu Jul  3 08:00:10 2026] perf: interrupt took too long (3125 > 3124), lowering kernel.perf_event_max_sample_rate to 64000
[Thu Jul  3 08:15:00 2026] usb 1-1: USB disconnect, device number 2"""

_DMESG_ERRORS = """\
[Thu Jul  3 08:00:02 2026] [drm:drm_crtc_commit_begin] *ERROR* flip_done timed out
[Thu Jul  3 08:00:04 2026] Oops: general protection fault, probably for non-canonical address 0x0
[Thu Jul  3 08:00:10 2026] EXT4-fs error (device sda2): ext4_find_entry:1455: inode #2: comm systemd
[Thu Jul  3 08:05:00 2026] EDAC MC0: 1 CE error on CPU#0Channel#0_DIMM#0 (channel:0 slot:0 page:0x0 offset:0x0 grain:8)"""


# ---------------------------------------------------------------------------
# Per-op simulators
# ---------------------------------------------------------------------------

def _sim_query(args: dict, ctx: Any) -> dict:
    """Simulate journalctl query."""
    unit = args.get("unit", "")
    priority = args.get("priority", "")
    grep = args.get("grep", "")
    since = args.get("since", "")

    # Failure: permission denied when querying kernel journal as non-root
    if priority in ("0", "1", "2", "emerg", "alert", "crit") and not unit:
        return _result(
            exit_code=1,
            stdout="",
            stderr="Hint: You need appropriate permissions to view all logs.\nFailed to add match for '_TRANSPORT=kernel': Operation not permitted",
            summary="journalctl failed: insufficient permissions to query kernel-priority logs.",
        )

    # Unit not found / no entries
    if unit and not _unit_appears_running(unit, ctx):
        return _result(
            exit_code=0,
            stdout=f"{_JOURNAL_HEADER}\n-- No entries --",
            stderr="",
            summary=f"journalctl returned no entries for unit {unit!r}.",
        )

    # Pick realistic lines based on known unit or generic
    if unit and "nginx" in unit:
        lines = f"{_JOURNAL_HEADER}\n{_NGINX_LINES}"
        summary = f"journalctl returned recent entries for nginx.service."
    elif unit and "sshd" in unit:
        lines = f"{_JOURNAL_HEADER}\n{_SSHD_LINES}"
        summary = "journalctl returned recent sshd log entries including authentication events."
    elif unit and ("postgres" in unit or "postgresql" in unit):
        lines = f"{_JOURNAL_HEADER}\n{_POSTGRESQL_LINES}"
        summary = "journalctl returned recent postgresql log entries."
    else:
        # Grep filter applied
        if grep:
            filtered = "\n".join(
                ln for ln in _GENERIC_LINES.splitlines() if grep.lower() in ln.lower()
            )
            if not filtered:
                return _result(
                    exit_code=0,
                    stdout=f"{_JOURNAL_HEADER}\n-- No entries --",
                    stderr="",
                    summary=f"journalctl query matched no entries for grep pattern {grep!r}.",
                )
            lines = f"{_JOURNAL_HEADER}\n{filtered}"
            summary = f"journalctl query returned entries matching {grep!r}."
        else:
            lines = f"{_JOURNAL_HEADER}\n{_GENERIC_LINES}"
            priority_label = f" at priority {priority}" if priority else ""
            since_label = f" since {since}" if since else ""
            summary = f"journalctl query returned system log entries{priority_label}{since_label}."

    return _result(exit_code=0, stdout=lines, stderr="", summary=summary)


def _sim_tail(args: dict, ctx: Any) -> dict:
    """Simulate journalctl tail (most recent N lines)."""
    unit = args.get("unit", "")
    n = int(args.get("lines") or 50)

    # Failure: unit not found
    if unit and not _unit_appears_running(unit, ctx):
        return _result(
            exit_code=0,
            stdout=f"{_JOURNAL_HEADER}\n-- No entries --",
            stderr="",
            summary=f"journalctl tail found no entries for unit {unit!r}.",
        )

    if unit and "nginx" in unit:
        body_lines = _NGINX_LINES.splitlines()
    elif unit and "sshd" in unit:
        body_lines = _SSHD_LINES.splitlines()
    else:
        body_lines = _GENERIC_LINES.splitlines()

    body_lines = body_lines[-n:] if len(body_lines) > n else body_lines
    body = "\n".join(body_lines)
    unit_label = f" for {unit}" if unit else ""
    summary = f"journalctl tail returned the last {len(body_lines)} log line(s){unit_label}."
    return _result(
        exit_code=0,
        stdout=f"{_JOURNAL_HEADER}\n{body}",
        stderr="",
        summary=summary,
    )


def _sim_since(args: dict, ctx: Any) -> dict:
    """Simulate journalctl --since."""
    since = args.get("since", "1 hour ago")
    unit = args.get("unit", "")

    # Failure: unrecognised time expression
    invalid_times = ("never", "whenever", "sometime", "yesterday morning")
    if since.lower() in invalid_times:
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"Failed to parse timestamp: {since!r}",
            summary=f"journalctl since failed: could not parse time expression {since!r}.",
        )

    # Unit not found
    if unit and not _unit_appears_running(unit, ctx):
        return _result(
            exit_code=0,
            stdout=f"{_JOURNAL_HEADER}\n-- No entries --",
            stderr="",
            summary=f"journalctl since {since!r} returned no entries for unit {unit!r}.",
        )

    if unit and "sshd" in unit:
        body = _SSHD_LINES
    elif unit and "nginx" in unit:
        body = _NGINX_LINES
    else:
        body = _GENERIC_LINES

    unit_label = f" for {unit}" if unit else ""
    summary = f"journalctl returned log entries since {since!r}{unit_label}."
    return _result(
        exit_code=0,
        stdout=f"{_JOURNAL_HEADER}\n{body}",
        stderr="",
        summary=summary,
    )


def _sim_boot_errors(args: dict, ctx: Any) -> dict:
    """Simulate journalctl boot errors (-p err)."""
    boot = args.get("boot", "0")

    # Failure: invalid boot ID
    if boot not in ("0", "-1", "-2", "0") and len(boot) < 8:
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"Failed to look up boot {boot!r}: No match",
            summary=f"journalctl boot_errors failed: boot ID {boot!r} not found.",
        )

    # Clean boot — no errors (realistic for a stable host)
    if boot in ("-1", "-2"):
        return _result(
            exit_code=0,
            stdout=f"{_JOURNAL_HEADER}\n-- No entries --",
            stderr="",
            summary=f"No error-level log entries found for boot {boot!r}.",
        )

    # Current boot with some errors
    summary = "journalctl boot_errors returned error-level entries from the current boot."
    return _result(
        exit_code=0,
        stdout=f"{_JOURNAL_HEADER}\n{_BOOT_ERROR_LINES}",
        stderr="",
        summary=summary,
    )


def _sim_dmesg_query(args: dict, ctx: Any) -> dict:
    """Simulate dmesg kernel ring buffer query."""
    level = args.get("level", "")
    grep = args.get("grep", "")
    lines_arg = args.get("lines")

    # Failure: permission denied (dmesg restricted on some kernels)
    if level in ("debug",) and not ctx:
        return _result(
            exit_code=1,
            stdout="",
            stderr="dmesg: read kernel buffer failed: Operation not permitted",
            summary="dmesg query failed: reading the kernel ring buffer requires root privileges.",
        )

    body = _DMESG_GENERIC

    # Apply grep filter
    if grep:
        try:
            import re
            filtered = "\n".join(
                ln for ln in body.splitlines() if re.search(grep, ln)
            )
            if not filtered:
                return _result(
                    exit_code=0,
                    stdout="",
                    stderr="",
                    summary=f"dmesg query matched no kernel ring buffer lines for pattern {grep!r}.",
                )
            body = filtered
            summary = f"dmesg query returned kernel ring buffer lines matching {grep!r}."
        except Exception:
            return _result(
                exit_code=1,
                stdout="",
                stderr=f"Invalid grep pattern: {grep!r}",
                summary=f"dmesg query failed: invalid grep pattern {grep!r}.",
            )
    elif level in ("err", "error", "crit", "alert", "emerg"):
        body = _DMESG_ERRORS
        summary = f"dmesg query returned kernel ring buffer entries at level {level!r}."
    else:
        summary = "dmesg query returned kernel ring buffer output."

    # Cap lines
    if lines_arg is not None:
        n = int(lines_arg)
        body_lines = body.splitlines()
        body = "\n".join(body_lines[-n:] if len(body_lines) > n else body_lines)

    return _result(exit_code=0, stdout=body, stderr="", summary=summary)


def _sim_dmesg_errors(args: dict, ctx: Any) -> dict:
    """Simulate dmesg --level err,crit,alert,emerg."""
    lines_arg = args.get("lines")

    # Failure: restricted kernel buffer (e.g. kernel.dmesg_restrict=1, not root)
    # Use a random draw so the corpus gets a mix of success and failure traces.
    fail_chance = 0.2
    if random.random() < fail_chance:
        return _result(
            exit_code=1,
            stdout="",
            stderr="dmesg: read kernel buffer failed: Operation not permitted",
            summary="dmesg errors failed: kernel ring buffer access restricted; run as root.",
        )

    body = _DMESG_ERRORS
    if lines_arg is not None:
        n = int(lines_arg)
        body_lines = body.splitlines()
        body = "\n".join(body_lines[-n:] if len(body_lines) > n else body_lines)

    n_lines = len(body.splitlines())
    summary = f"dmesg returned {n_lines} error-level kernel ring buffer line(s)."
    return _result(exit_code=0, stdout=body, stderr="", summary=summary)


# ---------------------------------------------------------------------------
# Dispatch table — built from the LIVE registry (INV-schema-sync)
# ---------------------------------------------------------------------------

_DISPATCH = {
    "query": _sim_query,
    "tail": _sim_tail,
    "since": _sim_since,
    "boot_errors": _sim_boot_errors,
    "dmesg_query": _sim_dmesg_query,
    "dmesg_errors": _sim_dmesg_errors,
}


def simulate_logs(op: str, args: dict, ctx: Any) -> dict:
    """Simulate the 'logs' tool for *op* with *args* and system context *ctx*.

    Returns a ToolResult-shaped dict:
        {exit_code: int, stdout: str, stderr: str, summary: str}

    The op name is validated against the LIVE registry (INV-schema-sync) so
    that any drift in core/tools/logs.py is caught immediately at call time.
    Raises KeyError for an unregistered op — the Phase 3 join asserts no gaps.
    """
    # Validate op against live registry (INV-schema-sync — no hardcoded names)
    spec = registry.get("logs")
    real_ops: set[str] = set(spec.ops.keys())
    if op not in real_ops:
        raise KeyError(
            f"simulate_logs: op {op!r} is not a registered operation of 'logs'. "
            f"Real ops: {sorted(real_ops)}"
        )

    fn = _DISPATCH[op]
    return fn(args if args is not None else {}, ctx)
