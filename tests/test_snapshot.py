"""
tests/test_snapshot.py

Unit tests for core/context/{collector,snapshot,cache}.py.
All Linux-specific syscalls are exercised via FIXTURE runners —
no live /proc, no live systemctl, no live rpm required.

DEV-HOST HONESTY: we are on macOS. Live collection is
DEFERRED-TO-MOSSAD.  Tests that require a running Linux box
are marked with the DEFERRED_TO_MOSSAD marker and skipped here.

Run:
    python -m pytest tests/test_snapshot.py -v
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from core.context.cache import SnapshotCache
from core.context.collector import Collector
from core.context.snapshot import DiskEntry, PortEntry, SystemSnapshot

# ---------------------------------------------------------------------------
# Marker for tests that need a real Linux host + Ollama
# ---------------------------------------------------------------------------
DEFERRED_TO_MOSSAD = pytest.mark.skip(
    reason="DEFERRED-TO-MOSSAD: requires real Linux / running services"
)

# ---------------------------------------------------------------------------
# Fixture runner factory
# ---------------------------------------------------------------------------

def _make_runner(responses: dict[str, tuple[int, str, str]]):
    """
    Build a fake ``run`` callable from a mapping of
      (cmd[0], *cmd[1:]) string key -> (rc, stdout, stderr).

    The key is the command joined by spaces, e.g. ``"cat /etc/os-release"``.
    The sentinel key ``"*"`` is returned for any unmatched command.
    """
    def _runner(cmd: list[str], **_kwargs: Any) -> tuple[int, str, str]:
        key = " ".join(cmd)
        if key in responses:
            return responses[key]
        # Try prefix match for commands with variable args (e.g. rpm)
        for k, v in responses.items():
            if key.startswith(k):
                return v
        return responses.get("*", (127, "", f"no fixture for: {key}"))
    return _runner


# ---------------------------------------------------------------------------
# Sample fixture data
# ---------------------------------------------------------------------------

_OS_RELEASE = """\
NAME="Rocky Linux"
VERSION="9.3 (Blue Onyx)"
ID=rocky
ID_LIKE="rhel centos fedora"
VERSION_ID=9.3
PRETTY_NAME="Rocky Linux 9.3 (Blue Onyx)"
PLATFORM_ID=platform:el9
"""

_CPUINFO = """\
processor\t: 0
vendor_id\t: GenuineIntel
model name\t: Intel(R) Xeon(R) Gold 6234 CPU @ 3.30GHz
cpu cores\t: 8

processor\t: 1
vendor_id\t: GenuineIntel
model name\t: Intel(R) Xeon(R) Gold 6234 CPU @ 3.30GHz
cpu cores\t: 8
"""

_MEMINFO = """\
MemTotal:       32768000 kB
MemFree:         8192000 kB
MemAvailable:   16384000 kB
Buffers:          204800 kB
Cached:          8192000 kB
"""

_RPM_QA = """\
bash
coreutils
glibc
kernel
openssh-server
python3
rpm
systemd
"""

_SYSTEMCTL_UNITS = """\
nginx.service              loaded active   running  A high performance web server
sshd.service               loaded active   running  OpenSSH server daemon
firewalld.service          loaded inactive dead     firewalld - dynamic firewall daemon
httpd.service              loaded failed   failed   The Apache HTTP Server
crond.service              loaded active   running  Command Scheduler
"""

_DF_OUT = """\
Filesystem     Mounted on  1B-blocks        Used  Available Use%
/dev/sda1      /          107374182400 32212254720 75161927680  30%
/dev/sda2      /boot        1073741824   536870912   536870912  50%
"""

_SS_TCP = """\
tcp   LISTEN  0  128    0.0.0.0:22     0.0.0.0:*  users:(("sshd",pid=1234,fd=3))
tcp   LISTEN  0  511    0.0.0.0:80     0.0.0.0:*  users:(("nginx",pid=5678,fd=6))
tcp   LISTEN  0  128         [::]:22        [::]:*  users:(("sshd",pid=1234,fd=4))
"""

_SS_UDP = """\
udp   UNCONN  0   0    0.0.0.0:123    0.0.0.0:*
"""

_FIXTURE_RUNNER = _make_runner({
    "cat /etc/os-release": (0, _OS_RELEASE, ""),
    "uname -r": (0, "5.14.0-362.8.1.el9_3.x86_64\n", ""),
    "cat /proc/cpuinfo": (0, _CPUINFO, ""),
    "cat /proc/meminfo": (0, _MEMINFO, ""),
    "rpm -qa --qf %{NAME}\\n": (0, _RPM_QA, ""),
    "systemctl list-units --type=service --no-legend --no-pager --plain --all": (
        0, _SYSTEMCTL_UNITS, ""
    ),
    # df variant — match by prefix
    "df --block-size=1 --output=source,target,size,used,avail,pcent -x tmpfs -x devtmpfs -x squashfs": (
        0, _DF_OUT, ""
    ),
    "ss -tlnpH": (0, _SS_TCP, ""),
    "ss -ulnpH": (0, _SS_UDP, ""),
})


def _make_collector(**kwargs) -> Collector:
    return Collector(run=_FIXTURE_RUNNER, **kwargs)


# ===========================================================================
# SnapshotCollector tests (fixture-based — all run on macOS)
# ===========================================================================

class TestCollectorOS:
    def test_os_name_parsed(self):
        snap = _make_collector().collect()
        assert "Rocky Linux" in snap.os_name

    def test_os_id_parsed(self):
        snap = _make_collector().collect()
        assert snap.os_id == "rocky"

    def test_kernel_present(self):
        snap = _make_collector().collect()
        assert snap.kernel.startswith("5.")

    def test_hostname_is_string(self):
        snap = _make_collector().collect()
        assert isinstance(snap.hostname, str)
        # hostname should be non-empty on any dev box
        assert len(snap.hostname) > 0


class TestCollectorIdentity:
    """cwd/home/user are the anchor for relative requests ('this folder')."""

    def test_cwd_populated(self):
        import os
        snap = _make_collector().collect()
        assert snap.cwd == os.getcwd()

    def test_home_populated(self):
        import os
        snap = _make_collector().collect()
        assert snap.home_dir == os.path.expanduser("~")

    def test_identity_in_prompt_text(self):
        import os
        text = _make_collector().collect().to_prompt_text()
        assert os.getcwd() in text
        assert "Working directory:" in text


class TestCollectorHardware:
    def test_cpu_model_parsed(self):
        snap = _make_collector().collect()
        assert "Xeon" in snap.cpu_model

    def test_cpu_cores_counted(self):
        snap = _make_collector().collect()
        assert snap.cpu_cores == 2  # fixture has 2 processor blocks

    def test_mem_total_bytes(self):
        snap = _make_collector().collect()
        expected = 32768000 * 1024
        assert snap.mem_total_bytes == expected

    def test_mem_avail_bytes(self):
        snap = _make_collector().collect()
        expected = 16384000 * 1024
        assert snap.mem_avail_bytes == expected


class TestCollectorPackages:
    def test_package_count(self):
        snap = _make_collector().collect()
        assert snap.installed_package_count == 8

    def test_package_sample_contents(self):
        snap = _make_collector().collect()
        assert "bash" in snap.installed_packages_sample
        assert "python3" in snap.installed_packages_sample

    def test_package_sample_sorted(self):
        snap = _make_collector().collect()
        assert snap.installed_packages_sample == sorted(snap.installed_packages_sample)

    def test_package_sample_capped(self):
        snap = _make_collector(pkg_sample_n=3).collect()
        assert len(snap.installed_packages_sample) <= 3


class TestCollectorServices:
    def test_failed_services_populated(self):
        snap = _make_collector().collect()
        assert "httpd.service" in snap.failed_services

    def test_active_services_populated(self):
        snap = _make_collector().collect()
        assert "nginx.service" in snap.active_services
        assert "sshd.service" in snap.active_services

    def test_inactive_services_populated(self):
        snap = _make_collector().collect()
        assert "firewalld.service" in snap.inactive_services

    def test_service_sample_capped(self):
        snap = _make_collector(svc_sample_n=1).collect()
        assert len(snap.active_services) <= 1


class TestCollectorDisks:
    def test_root_disk_present(self):
        snap = _make_collector().collect()
        mounts = {d.mount for d in snap.disks}
        assert "/" in mounts

    def test_boot_disk_present(self):
        snap = _make_collector().collect()
        mounts = {d.mount for d in snap.disks}
        assert "/boot" in mounts

    def test_tmpfs_excluded(self):
        snap = _make_collector().collect()
        # df fixture passes -x tmpfs so our fixture omits it already;
        # verify it's not in the parsed output
        mounts = {d.mount for d in snap.disks}
        assert "/dev/shm" not in mounts

    def test_disk_fields(self):
        snap = _make_collector().collect()
        root = next(d for d in snap.disks if d.mount == "/")
        assert root.total_bytes == 107374182400
        assert root.use_pct == 30
        assert root.device == "/dev/sda1"


class TestCollectorPorts:
    def test_ssh_port_present(self):
        snap = _make_collector().collect()
        ports = {p.local_port for p in snap.listen_ports}
        assert 22 in ports

    def test_http_port_present(self):
        snap = _make_collector().collect()
        ports = {p.local_port for p in snap.listen_ports}
        assert 80 in ports

    def test_ntp_udp_port_present(self):
        snap = _make_collector().collect()
        udp_ports = {p.local_port for p in snap.listen_ports if p.protocol == "udp"}
        assert 123 in udp_ports

    def test_port_process_parsed(self):
        snap = _make_collector().collect()
        sshd = next(
            (p for p in snap.listen_ports if p.local_port == 22 and p.local_addr == "0.0.0.0"),
            None,
        )
        assert sshd is not None
        assert sshd.process == "sshd"
        assert sshd.pid == 1234

    def test_ipv6_port_parsed(self):
        snap = _make_collector().collect()
        ipv6_ports = [p for p in snap.listen_ports if p.local_addr == "::"]
        assert any(p.local_port == 22 for p in ipv6_ports)


class TestCollectorErrors:
    def test_no_errors_with_good_fixture(self):
        snap = _make_collector().collect()
        assert snap.collection_errors == []

    def test_graceful_on_missing_command(self):
        # Runner that returns not-found for rpm — should degrade gracefully
        bad_runner = _make_runner({
            "cat /etc/os-release": (0, _OS_RELEASE, ""),
            "uname -r": (0, "5.14.0-362.el9.x86_64\n", ""),
            "cat /proc/cpuinfo": (0, _CPUINFO, ""),
            "cat /proc/meminfo": (0, _MEMINFO, ""),
            "rpm -qa --qf %{NAME}\\n": (127, "", "rpm: command not found"),
            "systemctl list-units --type=service --no-legend --no-pager --plain --all": (
                0, _SYSTEMCTL_UNITS, ""
            ),
            "df --block-size=1 --output=source,target,size,used,avail,pcent -x tmpfs -x devtmpfs -x squashfs": (
                0, _DF_OUT, ""
            ),
            "ss -tlnpH": (0, _SS_TCP, ""),
            "ss -ulnpH": (0, _SS_UDP, ""),
        })
        snap = Collector(run=bad_runner).collect()
        # packages degrade gracefully
        assert snap.installed_package_count == 0
        assert snap.installed_packages_sample == []
        # at least one error note present
        assert any("rpm" in e for e in snap.collection_errors)
        # everything ELSE is still populated
        assert "Rocky Linux" in snap.os_name
        assert snap.failed_services  # httpd still parsed

    def test_collected_at_is_iso8601(self):
        import datetime
        snap = _make_collector().collect()
        # should parse without error
        dt = datetime.datetime.fromisoformat(snap.collected_at)
        assert dt.tzinfo is not None  # UTC-aware


# ===========================================================================
# SystemSnapshot serialization tests
# ===========================================================================

class TestSnapshotSerialization:
    def _snap(self) -> SystemSnapshot:
        return _make_collector().collect()

    def test_to_dict_is_dict(self):
        assert isinstance(self._snap().to_dict(), dict)

    def test_to_json_parses(self):
        d = json.loads(self._snap().to_json())
        assert "hostname" in d
        assert "os_name" in d
        assert "installed_package_count" in d

    def test_to_prompt_text_contains_os(self):
        text = self._snap().to_prompt_text()
        assert "Rocky Linux" in text

    def test_to_prompt_text_contains_failed_service(self):
        text = self._snap().to_prompt_text()
        assert "httpd.service" in text

    def test_to_prompt_text_contains_memory(self):
        text = self._snap().to_prompt_text()
        assert "Memory" in text

    def test_to_prompt_text_contains_port(self):
        text = self._snap().to_prompt_text()
        assert "22" in text

    def test_no_tier_name_in_prompt_text(self):
        """I6: no Erdtree tier/product names hardcoded in framework output.
        'Rocky Linux' in the OS field is factual system data (user's own env),
        not an Erdtree framework tier name — it is explicitly ALLOWED.
        """
        text = self._snap().to_prompt_text()
        # Only Erdtree's own tier/product names are forbidden in core/ output
        for forbidden in ("marika", "radagon", "starscourge"):
            assert forbidden not in text.lower(), (
                f"Erdtree tier/product name hardcoded in framework output: {forbidden!r}"
            )

    def test_no_ai_language_in_prompt_text(self):
        """I2: no AI/LLM/model/agent language in user-facing strings.
        Checked as whole-word matches to avoid false positives from substrings
        like 'ai' inside 'available' or 'agent' inside 'pageant'.
        """
        import re
        text = self._snap().to_prompt_text()
        # whole-word forbidden terms (case-insensitive)
        for forbidden in ("llm", "model", "agent", "agentic", "neural",
                          r"\bai\b"):
            pattern = forbidden if forbidden.startswith(r"\b") else rf"\b{forbidden}\b"
            assert not re.search(pattern, text, re.IGNORECASE), (
                f"Forbidden AI-language term found in prompt text: {forbidden!r}"
            )


# ===========================================================================
# SnapshotCache tests
# ===========================================================================

class TestSnapshotCache:
    def _cache(self, ttl: float = 60.0) -> SnapshotCache:
        col = Collector(run=_FIXTURE_RUNNER)
        return SnapshotCache(collector=col, ttl=ttl)

    def test_first_get_returns_snapshot(self):
        snap = self._cache().get()
        assert isinstance(snap, SystemSnapshot)
        assert "Rocky Linux" in snap.os_name

    def test_second_get_returns_same_object(self):
        cache = self._cache()
        s1 = cache.get()
        s2 = cache.get()
        assert s1 is s2  # same object — cache hit

    def test_force_returns_fresh_object(self):
        cache = self._cache()
        s1 = cache.get()
        s2 = cache.get(force=True)
        assert s1 is not s2  # re-collected

    def test_invalidate_triggers_recollect(self):
        cache = self._cache()
        s1 = cache.get()
        cache.invalidate()
        s2 = cache.get()
        assert s1 is not s2  # fresh collect after invalidate

    def test_ttl_zero_always_recollects(self):
        cache = self._cache(ttl=0.0)
        s1 = cache.get()
        s2 = cache.get()
        assert s1 is not s2

    def test_is_warm_after_get(self):
        cache = self._cache(ttl=60.0)
        assert not cache.is_warm()
        cache.get()
        assert cache.is_warm()

    def test_is_warm_false_after_invalidate(self):
        cache = self._cache(ttl=60.0)
        cache.get()
        cache.invalidate()
        assert not cache.is_warm()

    def test_ttl_expiry(self, monkeypatch):
        # Use a very short TTL and advance the monotonic clock via monkeypatch
        import time as time_mod
        _base = time_mod.monotonic()
        _offset = 0.0

        def _fake_monotonic():
            return _base + _offset

        monkeypatch.setattr("core.context.cache.time.monotonic", _fake_monotonic)

        cache = self._cache(ttl=1.0)
        s1 = cache.get()
        assert cache.is_warm()

        # Advance time past TTL
        _offset = 2.0
        assert not cache.is_warm()
        s2 = cache.get()
        assert s1 is not s2  # re-collected after expiry

    def test_ttl_setter_validates(self):
        cache = self._cache()
        with pytest.raises(ValueError):
            cache.ttl = -1.0

    def test_cache_is_thread_safe(self):
        """Smoke-test: concurrent .get() calls don't crash."""
        import threading
        cache = self._cache(ttl=0.01)
        results = []
        errors = []

        def _worker():
            try:
                results.append(cache.get())
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert len(results) == 20


# ===========================================================================
# Audit-log tail tests
# ===========================================================================

class TestAuditTail:
    def test_audit_tail_read(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        log.write_text(
            '{"ts":"2026-06-21T00:00:00Z","nl_input":"show services"}\n'
            '{"ts":"2026-06-21T00:01:00Z","nl_input":"check disk"}\n'
            '{"ts":"2026-06-21T00:02:00Z","nl_input":"show logs"}\n'
        )
        col = Collector(run=_FIXTURE_RUNNER, audit_lines_n=2, audit_log_path=str(log))
        snap = col.collect()
        assert len(snap.recent_audit_lines) == 2
        assert "show logs" in snap.recent_audit_lines[-1]
        assert "check disk" in snap.recent_audit_lines[0]

    def test_audit_tail_missing_file_is_silent(self, tmp_path):
        col = Collector(
            run=_FIXTURE_RUNNER,
            audit_lines_n=5,
            audit_log_path=str(tmp_path / "nonexistent.jsonl"),
        )
        snap = col.collect()
        assert snap.recent_audit_lines == []
        assert snap.collection_errors == []


# ===========================================================================
# DEFERRED-TO-MOSSAD: live collection on a real Linux box
# ===========================================================================

@DEFERRED_TO_MOSSAD
def test_live_collection_rocky_linux():
    """
    DEFERRED-TO-MOSSAD
    Run on the mossad server (Rocky Linux 9 with Ollama).
    Verifies the default Collector() with the real subprocess runner populates
    all fields from /proc, systemctl, rpm -qa, ss, df.

    Expected: no collection_errors; os_id == "rocky"; failed_services is a list;
    installed_package_count > 100; listen_ports includes port 22.
    """
    snap = Collector().collect()
    assert snap.os_id == "rocky"
    assert snap.installed_package_count > 100
    assert snap.cpu_cores > 0
    assert snap.mem_total_bytes > 0
    ports = {p.local_port for p in snap.listen_ports}
    assert 22 in ports
    assert snap.collection_errors == []


@DEFERRED_TO_MOSSAD
def test_live_cache_invalidation():
    """
    DEFERRED-TO-MOSSAD
    Verifies that SnapshotCache with default TTL 5s:
    - returns a warm cached snapshot on second call (same object)
    - re-collects after TTL expires (different object, fresh data)
    """
    import time
    cache = SnapshotCache(ttl=1.0)
    s1 = cache.get()
    s2 = cache.get()
    assert s1 is s2, "expected cache hit"
    time.sleep(1.1)
    s3 = cache.get()
    assert s3 is not s1, "expected fresh collect after TTL"
