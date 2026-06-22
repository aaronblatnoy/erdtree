"""
core/context/snapshot.py

Typed snapshot of the live system state. Cheap to serialize into the prompt.
No tier names (I6). No AI/LLM language (I2).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional


def current_identity() -> tuple[str, str, str]:
    """Return the live ``(cwd, home, login_user)`` of the running process.

    Never raises: a deleted/unreadable cwd degrades to "" so a turn never
    crashes on identity collection.  This is the anchor the operator's
    relative requests ("this folder", a bare name) resolve against — without
    it the command interface has no idea *where* the operator is.
    """
    try:
        cwd = os.getcwd()
    except OSError:
        cwd = ""
    try:
        home = os.path.expanduser("~")
    except (OSError, KeyError):
        home = ""
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    return cwd, home, user


@dataclass
class DiskEntry:
    device: str
    mount: str
    total_bytes: int
    used_bytes: int
    avail_bytes: int
    use_pct: int


@dataclass
class PortEntry:
    protocol: str  # tcp | udp
    local_addr: str
    local_port: int
    state: str      # LISTEN | ESTABLISHED | etc.
    pid: Optional[int]
    process: Optional[str]


@dataclass
class SystemSnapshot:
    """
    Live model of the OS environment, injected into every query (I5).
    All fields have typed defaults so partial collection never raises.
    Serialize with .to_prompt_text() for inclusion in a prompt, or
    .to_dict() / json.dumps(.to_dict()) for audit / serialization.
    """

    # --- identification ---
    hostname: str = ""
    os_name: str = ""          # e.g. "Rocky Linux 9.3"
    os_id: str = ""            # /etc/os-release ID field
    kernel: str = ""           # uname -r

    # --- session location / identity ---
    # The operator's current shell location and identity.  These anchor every
    # relative request ("this folder", a bare path) so the command interface
    # never has to guess where the operator is or invent an absolute path.
    cwd: str = ""              # current working directory
    home_dir: str = ""         # operator's home directory ($HOME)
    login_user: str = ""       # login user ($USER)

    # --- hardware ---
    cpu_model: str = ""
    cpu_cores: int = 0
    mem_total_bytes: int = 0
    mem_avail_bytes: int = 0

    # --- packages ---
    installed_package_count: int = 0
    # sample: first N names so the prompt isn't swamped
    installed_packages_sample: list[str] = field(default_factory=list)

    # --- services ---
    failed_services: list[str] = field(default_factory=list)
    active_services: list[str] = field(default_factory=list)
    inactive_services: list[str] = field(default_factory=list)

    # --- storage ---
    disks: list[DiskEntry] = field(default_factory=list)

    # --- network ---
    listen_ports: list[PortEntry] = field(default_factory=list)

    # --- recent changes ---
    # last N lines of the audit log if it exists, for context
    recent_audit_lines: list[str] = field(default_factory=list)

    # --- collection metadata ---
    collected_at: str = ""      # ISO-8601 UTC
    collection_errors: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_prompt_text(self, max_pkgs: int = 20, max_ports: int = 20) -> str:
        """
        Compact human-readable representation for prompt injection.
        Deliberately brief — the model doesn't need megabytes of context.
        """
        lines: list[str] = []

        lines.append(f"Host: {self.hostname}")
        # Location/identity first: the operator's "here" must be unmistakable.
        if self.login_user or self.home_dir:
            lines.append(
                f"User: {self.login_user}".rstrip()
                + (f"  Home: {self.home_dir}" if self.home_dir else "")
            )
        if self.cwd:
            lines.append(f"Working directory: {self.cwd}")
        if self.os_name:
            lines.append(f"OS: {self.os_name}  kernel: {self.kernel}")
        if self.cpu_model:
            lines.append(f"CPU: {self.cpu_model}  cores: {self.cpu_cores}")
        if self.mem_total_bytes:
            total_gb = self.mem_total_bytes / (1024 ** 3)
            avail_gb = self.mem_avail_bytes / (1024 ** 3)
            lines.append(
                f"Memory: {total_gb:.1f} GB total  {avail_gb:.1f} GB available"
            )

        # services
        if self.failed_services:
            lines.append(f"Failed services ({len(self.failed_services)}): "
                         + ", ".join(self.failed_services[:10]))
        if self.active_services:
            lines.append(f"Active services ({len(self.active_services)}): "
                         + ", ".join(self.active_services[:10]))

        # storage
        if self.disks:
            disk_strs = [
                f"{d.mount} ({d.use_pct}% used)" for d in self.disks[:8]
            ]
            lines.append("Disks: " + ", ".join(disk_strs))

        # packages
        if self.installed_package_count:
            lines.append(
                f"Packages installed: {self.installed_package_count}"
            )

        # ports
        listen = self.listen_ports[:max_ports]
        if listen:
            port_strs = [
                f"{p.local_port}/{p.protocol}" for p in listen
            ]
            lines.append("Listening ports: " + ", ".join(port_strs))

        # errors during collection — surfaced as a note, not hidden
        if self.collection_errors:
            lines.append(
                "Collection notes: " + "; ".join(self.collection_errors)
            )

        return "\n".join(lines)
