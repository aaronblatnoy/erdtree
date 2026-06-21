"""
core/context/collector.py

Collects live system state from /proc, /sys, systemctl, rpm, ss, etc.
Designed for Rocky Linux 9 / RHEL-derivative targets.

On macOS (dev host): all Linux-specific syscalls are MOCKED by passing a
``_provider`` callable at construction. The real Linux paths are written
here; only their invocation is swapped out in test. The live collection
path is DEFERRED-TO-MOSSAD (requires a running Linux box).

No tier names (I6). No AI/LLM language (I2).
"""

from __future__ import annotations

import datetime
import os
import re
import shlex
import socket
import subprocess
from pathlib import Path
from typing import Callable, Optional

from core.context.snapshot import DiskEntry, PortEntry, SystemSnapshot

# ---------------------------------------------------------------------------
# Default subprocess runner — can be replaced in tests with a fixture runner
# ---------------------------------------------------------------------------

def _default_run(
    cmd: list[str], *, timeout: int = 10, check: bool = False
) -> tuple[int, str, str]:
    """
    Run *cmd* with subprocess, return (returncode, stdout, stderr).
    Never raises on non-zero exit unless check=True.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s: {shlex.join(cmd)}"
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class Collector:
    """
    Gathers a SystemSnapshot from the live OS.

    Parameters
    ----------
    run:
        Callable(cmd: list[str]) -> (returncode, stdout, stderr).
        Defaults to subprocess. Replace in tests with a fixture runner.
    pkg_sample_n:
        How many package names to include in the sample (prompt size guard).
    svc_sample_n:
        How many service names per state bucket to include.
    audit_lines_n:
        How many recent audit lines to surface (0 = skip).
    audit_log_path:
        Path to the append-only audit JSONL. Read from env ERDTREE_AUDIT_LOG
        if set, else None (silently skipped if absent — the log may not exist
        on a freshly installed box).
    """

    def __init__(
        self,
        run: Optional[Callable[[list[str]], tuple[int, str, str]]] = None,
        pkg_sample_n: int = 50,
        svc_sample_n: int = 30,
        audit_lines_n: int = 5,
        audit_log_path: Optional[str] = None,
    ) -> None:
        self._run = run if run is not None else _default_run
        self._pkg_sample_n = pkg_sample_n
        self._svc_sample_n = svc_sample_n
        self._audit_lines_n = audit_lines_n
        # resolve audit log path: explicit arg > env > None
        self._audit_log_path: Optional[Path] = None
        raw = audit_log_path or os.environ.get("ERDTREE_AUDIT_LOG")
        if raw:
            self._audit_log_path = Path(raw)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def collect(self) -> SystemSnapshot:
        """
        Return a fresh SystemSnapshot. Tolerates missing subsystems:
        each domain returns empty/zero on failure and appends a note to
        ``collection_errors`` so the caller (and prompt) can see what
        was skipped without crashing.
        """
        errors: list[str] = []
        snap = SystemSnapshot(
            collected_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

        snap.hostname = self._collect_hostname(errors)
        self._collect_os(snap, errors)
        self._collect_hardware(snap, errors)
        self._collect_packages(snap, errors)
        self._collect_services(snap, errors)
        self._collect_disks(snap, errors)
        self._collect_ports(snap, errors)
        self._collect_audit_tail(snap, errors)

        snap.collection_errors = errors
        return snap

    # ------------------------------------------------------------------
    # Domain collectors
    # ------------------------------------------------------------------

    def _collect_hostname(self, errors: list[str]) -> str:
        try:
            return socket.gethostname()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"hostname: {exc}")
            return ""

    def _collect_os(self, snap: SystemSnapshot, errors: list[str]) -> None:
        # /etc/os-release — standard on systemd distros
        rc, out, _ = self._run(["cat", "/etc/os-release"])
        if rc == 0:
            kv: dict[str, str] = {}
            for line in out.splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    kv[k.strip()] = v.strip().strip('"')
            snap.os_id = kv.get("ID", "")
            # Prefer PRETTY_NAME, fall back to NAME + VERSION_ID
            snap.os_name = kv.get("PRETTY_NAME") or (
                kv.get("NAME", "") + " " + kv.get("VERSION_ID", "")
            ).strip()
        else:
            errors.append("os-release: not readable")

        # kernel version from uname
        rc, out, _ = self._run(["uname", "-r"])
        if rc == 0:
            snap.kernel = out.strip()
        else:
            errors.append("uname: not available")

    def _collect_hardware(
        self, snap: SystemSnapshot, errors: list[str]
    ) -> None:
        # CPU info from /proc/cpuinfo
        rc, out, _ = self._run(["cat", "/proc/cpuinfo"])
        if rc == 0:
            model_names = re.findall(r"^model name\s*:\s*(.+)$", out, re.M)
            if model_names:
                snap.cpu_model = model_names[0].strip()
            snap.cpu_cores = len(
                re.findall(r"^processor\s*:", out, re.M)
            )
        else:
            errors.append("cpuinfo: /proc/cpuinfo not readable")

        # Memory from /proc/meminfo
        rc, out, _ = self._run(["cat", "/proc/meminfo"])
        if rc == 0:
            def _kib(pattern: str) -> int:
                m = re.search(rf"^{pattern}\s*:\s*(\d+)\s*kB$", out, re.M)
                return int(m.group(1)) * 1024 if m else 0

            snap.mem_total_bytes = _kib("MemTotal")
            snap.mem_avail_bytes = _kib("MemAvailable")
        else:
            errors.append("meminfo: /proc/meminfo not readable")

    def _collect_packages(
        self, snap: SystemSnapshot, errors: list[str]
    ) -> None:
        # rpm -qa — works on Rocky/RHEL/Fedora/CentOS; sorted for stability
        rc, out, _ = self._run(
            ["rpm", "-qa", "--qf", "%{NAME}\\n"], timeout=30
        )
        if rc == 0:
            names = [l.strip() for l in out.splitlines() if l.strip()]
            snap.installed_package_count = len(names)
            snap.installed_packages_sample = sorted(names)[: self._pkg_sample_n]
        else:
            errors.append("rpm: not available — package list skipped")

    def _collect_services(
        self, snap: SystemSnapshot, errors: list[str]
    ) -> None:
        # systemctl list-units -- machine-parseable output
        rc, out, _ = self._run([
            "systemctl", "list-units",
            "--type=service",
            "--no-legend",
            "--no-pager",
            "--plain",
            "--all",
        ])
        if rc != 0:
            errors.append("systemctl: not available — service list skipped")
            return

        failed: list[str] = []
        active: list[str] = []
        inactive: list[str] = []

        for line in out.splitlines():
            # Format: UNIT  LOAD  ACTIVE  SUB  DESCRIPTION
            parts = line.split(None, 4)
            if len(parts) < 3:
                continue
            unit_name = parts[0]
            # strip trailing ● or similar glyphs that systemd may emit
            unit_name = re.sub(r"[^\w@:\-.]+$", "", unit_name)
            active_state = parts[2] if len(parts) > 2 else ""

            if active_state == "failed":
                failed.append(unit_name)
            elif active_state == "active":
                active.append(unit_name)
            else:
                inactive.append(unit_name)

        snap.failed_services = failed[: self._svc_sample_n]
        snap.active_services = active[: self._svc_sample_n]
        snap.inactive_services = inactive[: self._svc_sample_n]

    def _collect_disks(
        self, snap: SystemSnapshot, errors: list[str]
    ) -> None:
        # df --block-size=1 (bytes) for all real filesystems
        rc, out, _ = self._run([
            "df", "--block-size=1",
            "--output=source,target,size,used,avail,pcent",
            "-x", "tmpfs", "-x", "devtmpfs", "-x", "squashfs",
        ])
        if rc != 0:
            errors.append("df: not available — disk info skipped")
            return

        entries: list[DiskEntry] = []
        for line in out.splitlines()[1:]:  # skip header
            parts = line.split(None, 5)
            if len(parts) < 6:
                continue
            try:
                device = parts[0]
                total = int(parts[2])
                used = int(parts[3])
                avail = int(parts[4])
                pct_str = parts[5].strip().rstrip("%")
                pct = int(pct_str) if pct_str.isdigit() else 0
                mount = parts[1]
                entries.append(
                    DiskEntry(
                        device=device,
                        mount=mount,
                        total_bytes=total,
                        used_bytes=used,
                        avail_bytes=avail,
                        use_pct=pct,
                    )
                )
            except (ValueError, IndexError):
                continue

        snap.disks = entries

    def _collect_ports(
        self, snap: SystemSnapshot, errors: list[str]
    ) -> None:
        # ss -tlnpH — TCP listen ports, numeric, no headers
        # ss -ulnpH — UDP listen ports
        ports: list[PortEntry] = []
        for proto, flags in [("tcp", "-tlnpH"), ("udp", "-ulnpH")]:
            rc, out, _ = self._run(["ss", flags])
            if rc != 0:
                errors.append(f"ss: {proto} listen failed — port list skipped")
                continue
            for line in out.splitlines():
                entry = self._parse_ss_line(proto, line)
                if entry:
                    ports.append(entry)
        snap.listen_ports = ports

    def _parse_ss_line(self, proto: str, line: str) -> Optional[PortEntry]:
        """
        Parse one line of ``ss -t/-u lnpH`` output.
        Sample:
          tcp   LISTEN  0  128  0.0.0.0:22  0.0.0.0:*  users:(("sshd",pid=1234,fd=3))
        """
        parts = line.split()
        if len(parts) < 5:
            return None
        state = parts[1] if proto == "tcp" else "LISTEN"
        local = parts[4] if len(parts) > 4 else parts[3]

        # extract addr:port — handle IPv6 brackets
        if local.startswith("["):
            # [::]:port
            m = re.match(r"\[(.+)\]:(\d+)", local)
            if not m:
                return None
            addr, port_s = m.group(1), m.group(2)
        elif ":" in local:
            addr, _, port_s = local.rpartition(":")
        else:
            return None

        try:
            port = int(port_s)
        except ValueError:
            return None

        # process info from users:(("name",pid=N,...))
        pid: Optional[int] = None
        proc: Optional[str] = None
        proc_m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
        if proc_m:
            proc = proc_m.group(1)
            pid = int(proc_m.group(2))

        return PortEntry(
            protocol=proto,
            local_addr=addr,
            local_port=port,
            state=state,
            pid=pid,
            process=proc,
        )

    def _collect_audit_tail(
        self, snap: SystemSnapshot, errors: list[str]
    ) -> None:
        if self._audit_lines_n <= 0 or self._audit_log_path is None:
            return
        try:
            if not self._audit_log_path.exists():
                return
            lines = self._audit_log_path.read_text().splitlines()
            snap.recent_audit_lines = lines[-self._audit_lines_n :]
        except Exception as exc:  # noqa: BLE001
            errors.append(f"audit-tail: {exc}")
