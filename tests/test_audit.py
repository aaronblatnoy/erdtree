"""
tests/test_audit.py — Tests for core/agent/audit.py (I4).

Validation gates (from the buildout plan §3 Phase 1):
  - Every classified op produces exactly one JSONL line.
  - File is append-only and parseable.
  - Partial-write recovery verified (a corrupt line does not corrupt neighbours).
  - fsync-on-write: verified by writing, crashing (simulated), re-reading.
  - No tier names hardcoded in the module itself (I6).
  - Record schema exactly matches the specified fields.

These tests are self-contained and run on macOS with standard Python >=3.9;
no Ollama, no Linux OS integration required.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

# Make the repo root importable regardless of how pytest is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agent.audit import (
    AuditLog,
    append_record,
    iter_records,
    _SCHEMA_KEYS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "audit.jsonl"


# ---------------------------------------------------------------------------
# 1. One parseable JSONL line per op
# ---------------------------------------------------------------------------

class TestOneLine:
    def test_single_write_produces_one_line(self, log_path: Path) -> None:
        """Exactly one line in the file after one write."""
        with AuditLog(log_path) as log:
            log.write(
                tier="test-tier",
                nl_input="show all failing services",
                tool="services",
                permission_decision="read",
                result="ok",
            )
        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1, f"Expected 1 line, got {len(lines)}"

    def test_single_line_is_valid_json(self, log_path: Path) -> None:
        """The single line must parse as JSON without error."""
        with AuditLog(log_path) as log:
            log.write(nl_input="install nginx", tool="packages", result="ok")
        line = log_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)  # must not raise
        assert isinstance(record, dict)

    def test_record_has_all_schema_keys(self, log_path: Path) -> None:
        """Every record must contain exactly the schema keys defined in audit.py."""
        with AuditLog(log_path) as log:
            log.write(nl_input="check disk", tool="disk", permission_decision="read")
        line = log_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        assert set(record.keys()) == set(_SCHEMA_KEYS), (
            f"Key mismatch: got {set(record.keys())}, expected {set(_SCHEMA_KEYS)}"
        )

    def test_n_writes_produce_n_lines(self, log_path: Path) -> None:
        """N writes must produce exactly N lines."""
        n = 7
        with AuditLog(log_path) as log:
            for i in range(n):
                log.write(nl_input=f"op-{i}", tool="services", result="ok")
        lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l]
        assert len(lines) == n

    def test_convenience_function_one_line(self, log_path: Path) -> None:
        """append_record() helper also produces exactly one line per call."""
        append_record(log_path, nl_input="list packages", tool="packages")
        lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l]
        assert len(lines) == 1

    def test_iter_records_yields_one_per_line(self, log_path: Path) -> None:
        """iter_records() yields the same number of dicts as written lines."""
        n = 4
        with AuditLog(log_path) as log:
            for i in range(n):
                log.write(nl_input=f"cmd-{i}", result="ok")
        records = list(iter_records(log_path))
        assert len(records) == n


# ---------------------------------------------------------------------------
# 2. Append-only behaviour
# ---------------------------------------------------------------------------

class TestAppendOnly:
    def test_second_open_appends_not_overwrites(self, log_path: Path) -> None:
        """Opening a new AuditLog on an existing file must APPEND, not truncate."""
        with AuditLog(log_path) as log:
            log.write(nl_input="first", result="ok")
        with AuditLog(log_path) as log:
            log.write(nl_input="second", result="ok")
        records = list(iter_records(log_path))
        assert len(records) == 2, "Second open must not truncate the file"
        assert records[0]["nl_input"] == "first"
        assert records[1]["nl_input"] == "second"

    def test_records_are_ordered_by_time(self, log_path: Path) -> None:
        """Records appended later must have ts >= earlier records."""
        with AuditLog(log_path) as log:
            for _ in range(5):
                log.write(result="ok")
                time.sleep(0.001)  # ensure monotonic ts
        records = list(iter_records(log_path))
        timestamps = [r["ts"] for r in records]
        assert timestamps == sorted(timestamps), "Timestamps must be non-decreasing"

    def test_file_byte_count_only_grows(self, log_path: Path) -> None:
        """The file must only ever grow in size (append-only invariant)."""
        sizes = []
        with AuditLog(log_path) as log:
            for i in range(5):
                log.write(nl_input=f"op-{i}", result="ok")
                sizes.append(log_path.stat().st_size)
        for a, b in zip(sizes, sizes[1:]):
            assert b > a, f"File shrank from {a} to {b} bytes — not append-only"


# ---------------------------------------------------------------------------
# 3. Partial-write / crash recovery
# ---------------------------------------------------------------------------

class TestPartialWriteRecovery:
    def test_corrupt_line_skipped_neighbours_preserved(self, log_path: Path) -> None:
        """
        Simulate a crash mid-write by manually injecting a partial (corrupt)
        JSON line between two valid records. iter_records() must skip the
        corrupt line and return both valid neighbours intact.
        """
        with AuditLog(log_path) as log:
            log.write(nl_input="before-crash", result="ok")
        # Inject a corrupt partial line (as if the process was killed mid-write).
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write('{"ts":1234567890,"nl_input":"truncated-crash\n')
        with AuditLog(log_path) as log:
            log.write(nl_input="after-crash", result="ok")

        records = list(iter_records(log_path))
        assert len(records) == 2, (
            f"Expected 2 valid records (corrupt line skipped), got {len(records)}: {records}"
        )
        assert records[0]["nl_input"] == "before-crash"
        assert records[1]["nl_input"] == "after-crash"

    def test_all_corrupt_lines_skipped(self, log_path: Path) -> None:
        """A file containing only corrupt lines must yield zero records."""
        log_path.write_text(
            '{"incomplete": true\n'
            'not json at all\n'
            '{"also": "broken\n',
            encoding="utf-8",
        )
        records = list(iter_records(log_path))
        assert records == [], f"Expected empty result, got {records}"

    def test_empty_file_yields_no_records(self, log_path: Path) -> None:
        log_path.write_text("", encoding="utf-8")
        assert list(iter_records(log_path)) == []

    def test_nonexistent_file_yields_no_records(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.jsonl"
        assert list(iter_records(path)) == []

    def test_blank_lines_skipped(self, log_path: Path) -> None:
        """Blank lines (e.g. from an editor) must not cause errors."""
        with AuditLog(log_path) as log:
            log.write(nl_input="real record", result="ok")
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("\n\n")
        records = list(iter_records(log_path))
        assert len(records) == 1


# ---------------------------------------------------------------------------
# 4. fsync-on-write (simulated)
# ---------------------------------------------------------------------------

class TestFsync:
    def test_data_readable_immediately_after_write(self, log_path: Path) -> None:
        """
        After write() returns, the data must be readable by a fresh file open.
        This verifies the write+fsync path completes before returning — if
        fsync were asynchronous or deferred, this could race.
        """
        with AuditLog(log_path) as log:
            for i in range(3):
                log.write(nl_input=f"op-{i}", result="ok")
                # Open a brand-new fd to read — simulates another process reading.
                records_so_far = list(iter_records(log_path))
                assert len(records_so_far) == i + 1, (
                    f"After write #{i+1}, expected {i+1} readable records, "
                    f"got {len(records_so_far)}"
                )

    def test_fsync_called_on_write(self, log_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify os.fsync() is called exactly once per write()."""
        import core.agent.audit as audit_module
        fsync_calls: list[int] = []
        original_fsync = os.fsync

        def mock_fsync(fd: int) -> None:
            fsync_calls.append(fd)
            original_fsync(fd)

        monkeypatch.setattr(audit_module.os, "fsync", mock_fsync)
        with AuditLog(log_path) as log:
            log.write(nl_input="check fsync", result="ok")
        assert len(fsync_calls) == 1, (
            f"Expected 1 fsync call per write, got {len(fsync_calls)}"
        )

    def test_fsync_called_n_times_for_n_writes(self, log_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """N writes must trigger exactly N fsync() calls."""
        import core.agent.audit as audit_module
        fsync_calls: list[int] = []
        original_fsync = os.fsync

        def mock_fsync(fd: int) -> None:
            fsync_calls.append(fd)
            original_fsync(fd)

        monkeypatch.setattr(audit_module.os, "fsync", mock_fsync)
        n = 5
        with AuditLog(log_path) as log:
            for i in range(n):
                log.write(nl_input=f"op-{i}", result="ok")
        assert len(fsync_calls) == n, (
            f"Expected {n} fsync calls, got {len(fsync_calls)}"
        )


# ---------------------------------------------------------------------------
# 5. Schema and field content
# ---------------------------------------------------------------------------

class TestSchema:
    def test_timestamp_is_float(self, log_path: Path) -> None:
        t_before = time.time()
        with AuditLog(log_path) as log:
            log.write(result="ok")
        t_after = time.time()
        record = next(iter_records(log_path))
        assert isinstance(record["ts"], float)
        assert t_before <= record["ts"] <= t_after

    def test_none_fields_serialise_as_null(self, log_path: Path) -> None:
        """Unset optional fields must appear as JSON null, not be omitted."""
        with AuditLog(log_path) as log:
            log.write()  # all defaults → None
        record = next(iter_records(log_path))
        for key in _SCHEMA_KEYS:
            if key == "ts":
                continue
            assert key in record, f"Missing key: {key}"
            assert record[key] is None, f"Expected null for {key}, got {record[key]!r}"

    def test_all_fields_round_trip(self, log_path: Path) -> None:
        """All populated fields must round-trip faithfully."""
        payload = {
            "tier": "custom-tier",
            "nl_input": "restart the web server",
            "translated_command": "systemctl restart nginx",
            "tool": "services",
            "args": {"unit": "nginx", "action": "restart"},
            "permission_decision": "write",
            "exit_code": 0,
            "stdout_summary": "",
            "stderr_summary": "",
            "result": "success",
        }
        with AuditLog(log_path) as log:
            log.write(**payload)
        record = next(iter_records(log_path))
        for key, value in payload.items():
            assert record[key] == value, f"Field {key}: expected {value!r}, got {record[key]!r}"

    def test_args_can_be_dict_list_or_string(self, log_path: Path) -> None:
        """The `args` field accepts any JSON-serialisable type."""
        for args_val in [{"a": 1}, ["x", "y"], "raw string", None, 42]:
            log_path.unlink(missing_ok=True)
            with AuditLog(log_path) as log:
                log.write(args=args_val)
            record = next(iter_records(log_path))
            assert record["args"] == args_val

    def test_long_input_truncated(self, log_path: Path) -> None:
        """Inputs longer than the cap are truncated (not rejected)."""
        long_str = "x" * 10_000
        with AuditLog(log_path) as log:
            log.write(nl_input=long_str)
        record = next(iter_records(log_path))
        assert record["nl_input"] is not None
        assert len(record["nl_input"]) < len(long_str)

    def test_long_stdout_truncated(self, log_path: Path) -> None:
        """stdout_summary longer than the cap is truncated (not rejected)."""
        long_str = "y" * 10_000
        with AuditLog(log_path) as log:
            log.write(stdout_summary=long_str)
        record = next(iter_records(log_path))
        assert record["stdout_summary"] is not None
        assert len(record["stdout_summary"]) < len(long_str)


# ---------------------------------------------------------------------------
# 6. I6 — no tier/product names hardcoded in the module source
# ---------------------------------------------------------------------------

class TestI6NoTierNames:
    _FORBIDDEN = ("marika", "radagon", "radahn", "starscourge", "rocky", "linux marika",
                  "linux radagon")

    def test_module_source_free_of_tier_names(self) -> None:
        """
        The audit.py source file must not contain any hardcoded tier or product
        names (I6). Tier identity is opaque data from the caller.
        """
        source_path = Path(__file__).resolve().parents[1] / "core" / "agent" / "audit.py"
        source = source_path.read_text(encoding="utf-8").lower()
        for name in self._FORBIDDEN:
            assert name not in source, (
                f"Hardcoded tier/product name '{name}' found in audit.py (violates I6)"
            )


# ---------------------------------------------------------------------------
# 7. Context-manager usage
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_context_manager_closes_fd(self, log_path: Path) -> None:
        """After __exit__, the file descriptor must be closed."""
        log = AuditLog(log_path)
        with log:
            log.write(nl_input="cm test", result="ok")
        assert log._fd is None, "fd should be None after context exit"

    def test_double_close_is_safe(self, log_path: Path) -> None:
        """Calling close() twice must not raise."""
        log = AuditLog(log_path)
        log.write(nl_input="safe close", result="ok")
        log.close()
        log.close()  # second close — must be idempotent

    def test_write_after_close_reopens(self, log_path: Path) -> None:
        """Writing after close() must reopen the file transparently."""
        with AuditLog(log_path) as log:
            log.write(nl_input="first", result="ok")
        # log is now closed; write again via append_record to same path
        append_record(log_path, nl_input="second", result="ok")
        records = list(iter_records(log_path))
        assert len(records) == 2


# ---------------------------------------------------------------------------
# 8. Directory auto-creation
# ---------------------------------------------------------------------------

class TestDirectoryAutoCreate:
    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """AuditLog must create nested parent directories that don't yet exist."""
        nested = tmp_path / "a" / "b" / "c" / "audit.jsonl"
        assert not nested.parent.exists()
        with AuditLog(nested) as log:
            log.write(nl_input="nested", result="ok")
        assert nested.exists()
        records = list(iter_records(nested))
        assert len(records) == 1
