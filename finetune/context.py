"""
finetune/context.py

Seeded Rocky Linux 9 system snapshot factory for the fine-tune data pipeline.

Public API
----------
make_context(tier: str, seed: int) -> str
    Returns a snapshot_text string compatible with PromptConfig.snapshot_text.
    Builds a real SystemSnapshot (core/context/snapshot.py) and calls its
    to_prompt_text() — the authoritative serialiser — then appends the fields
    that core's snapshot dataclass captures but to_prompt_text() does not emit
    (uptime, load average, firewall zone summary, package sample, recent
    journal lines).  tier nudges depth: radagon gets journal lines and the
    full package sample; marika gets a compact subset.

Design invariants
-----------------
INV-I2          Every produced string passes assert_no_ai_language before
                return.  Snapshots are injected into the system prompt which
                is user-facing, so no forbidden terms may appear.
INV-read-only-core  This module imports SystemSnapshot directly from
                core.context.snapshot (allowed — it is a read-only consumer of
                core/).  It does NOT modify anything in core/.
Drift safety    By calling SystemSnapshot.to_prompt_text() rather than
                reimplementing the serialiser, the context block stays in sync
                with what assemble_messages() will inject — drift is impossible.

Seed / profile selection
------------------------
seed % len(_PROFILES) selects deterministically from the 14 host profiles.
Callers cycling seed 0..N-1 will visit all profiles and wrap around after 14.
"""

from __future__ import annotations

from typing import Any

# SystemSnapshot + typed sub-entries — read-only consumer of core/
# (INV-read-only-core: finetune/ imports FROM core/, never the reverse)
from core.context.snapshot import DiskEntry, PortEntry, SystemSnapshot

# I2 checker — always via coreimports, never reimplemented (INV-I2)
from finetune.coreimports import assert_no_ai_language


# ---------------------------------------------------------------------------
# Byte conversion helper
# ---------------------------------------------------------------------------

_GB = 1024 ** 3  # bytes per GiB


def _gb(n: float) -> int:
    """Convert GiB (float) to bytes (int)."""
    return int(n * _GB)


# ---------------------------------------------------------------------------
# Host profiles
# ---------------------------------------------------------------------------
# Each profile is a plain dict.  Keys are documented by _build_snapshot() and
# _build_extra().  14 profiles cover the required >=12 and the full range of
# host roles: web, database (pg + mysql), container, firewall, fresh install,
# workstation, load balancer, monitoring, storage, mail, CI, DNS, and Java app.
#
# Kernel version map for reference (real Rocky Linux 9 point-release kernels):
#   9.0 -> 5.14.0-70.el9.x86_64
#   9.1 -> 5.14.0-162.el9_1.x86_64
#   9.2 -> 5.14.0-284.11.1.el9_2.x86_64
#   9.3 -> 5.14.0-362.8.1.el9_3.x86_64
#   9.4 -> 5.14.0-427.13.1.el9_4.x86_64
#   9.5 -> 5.14.0-503.14.1.el9_5.x86_64
#
# I2 compliance: every string value here is free of forbidden terms
# (ai, llm, model, agent, neural, machine learning, gpt, ollama, inference).
# make_context() asserts this at return time; this comment is the static
# documentation of the invariant.

_PROFILES: list[dict[str, Any]] = [
    # ------------------------------------------------------------------
    # 0  Web server — nginx + php-fpm, certbot, production traffic
    # ------------------------------------------------------------------
    {
        "hostname": "web-prod-01.corp.example.com",
        "os_name": "Rocky Linux 9.4",
        "os_id": "rocky",
        "kernel": "5.14.0-427.13.1.el9_4.x86_64",
        "login_user": "sysadm",
        "cwd": "/etc/nginx",
        "home_dir": "/home/sysadm",
        "cpu_label": "Intel Xeon E5-2680 v4",
        "cpu_cores": 14,
        "mem_total_gb": 32.0,
        "mem_avail_gb": 22.4,
        "active_services": [
            "nginx.service", "php-fpm.service", "sshd.service",
            "firewalld.service", "crond.service", "rsyslog.service",
        ],
        "failed_services": [],
        "inactive_services": ["httpd.service"],
        "disks": [
            # (device, mount, total_gb, used_gb, avail_gb, use_pct)
            ("/dev/sda1", "/boot", 1.0, 0.3, 0.7, 28),
            ("/dev/sda2", "/", 50.0, 31.2, 18.8, 62),
            ("/dev/sdb1", "/var/www", 500.0, 187.4, 312.6, 37),
        ],
        "listen_ports": [
            # (proto, local_addr, port, state, pid, proc)
            ("tcp", "0.0.0.0", 80, "LISTEN", 1234, "nginx"),
            ("tcp", "0.0.0.0", 443, "LISTEN", 1234, "nginx"),
            ("tcp", "127.0.0.1", 9000, "LISTEN", 1567, "php-fpm"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 892, "sshd"),
        ],
        "pkg_count": 412,
        "pkg_sample": [
            "nginx", "php", "php-fpm", "certbot", "openssl",
            "curl", "tar", "gzip", "rsync", "logrotate",
        ],
        "uptime": "14 days, 6:47:12",
        "load_avg": "0.42 0.38 0.35",
        "firewall_zones": "public (active): enp3s0  services: ssh http https",
        "journal_lines": [
            'Jul 03 08:12:44 web-prod-01 nginx[1234]: 192.168.10.5 - - [03/Jul/2026] "GET /healthz HTTP/1.1" 200 2',
            "Jul 03 07:58:01 web-prod-01 systemd[1]: php-fpm.service: Reloading configuration",
            "Jul 03 07:30:00 web-prod-01 crond[998]: (root) CMD (/usr/bin/certbot renew --quiet)",
        ],
    },

    # ------------------------------------------------------------------
    # 1  PostgreSQL database server — primary, production
    # ------------------------------------------------------------------
    {
        "hostname": "db-pg-01.corp.example.com",
        "os_name": "Rocky Linux 9.3",
        "os_id": "rocky",
        "kernel": "5.14.0-362.8.1.el9_3.x86_64",
        "login_user": "postgres",
        "cwd": "/var/lib/pgsql/data",
        "home_dir": "/var/lib/pgsql",
        "cpu_label": "AMD EPYC 7532",
        "cpu_cores": 32,
        "mem_total_gb": 128.0,
        "mem_avail_gb": 44.6,
        "active_services": [
            "postgresql.service", "sshd.service", "firewalld.service",
            "rsyslog.service", "crond.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 1.0, 0.2, 0.8, 22),
            ("/dev/sda2", "/", 50.0, 18.7, 31.3, 37),
            ("/dev/nvme0n1p1", "/var/lib/pgsql", 2000.0, 1124.5, 875.5, 56),
            ("/dev/nvme1n1p1", "/var/lib/pgsql/wal", 500.0, 92.3, 407.7, 18),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 5432, "LISTEN", 2310, "postmaster"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 887, "sshd"),
        ],
        "pkg_count": 389,
        "pkg_sample": [
            "postgresql", "postgresql-server", "postgresql-contrib",
            "pgbackrest", "openssl", "python3", "tar", "gzip",
        ],
        "uptime": "42 days, 13:10:05",
        "load_avg": "2.14 2.08 1.97",
        "firewall_zones": "internal (active): enp1s0  services: ssh postgresql",
        "journal_lines": [
            "Jul 03 08:00:00 db-pg-01 postgres[2310]: LOG:  checkpoint starting: time",
            "Jul 03 07:30:00 db-pg-01 postgres[2310]: LOG:  checkpoint complete: wrote 4821 buffers (0.7%)",
            "Jul 03 06:00:01 db-pg-01 systemd[1]: Starting pgbackrest scheduled backup...",
        ],
    },

    # ------------------------------------------------------------------
    # 2  MySQL database server — high write load, one failed backup unit
    # ------------------------------------------------------------------
    {
        "hostname": "db-my-01.corp.example.com",
        "os_name": "Rocky Linux 9.4",
        "os_id": "rocky",
        "kernel": "5.14.0-427.13.1.el9_4.x86_64",
        "login_user": "root",
        "cwd": "/var/lib/mysql",
        "home_dir": "/root",
        "cpu_label": "Intel Xeon Silver 4214",
        "cpu_cores": 12,
        "mem_total_gb": 64.0,
        "mem_avail_gb": 18.3,
        "active_services": [
            "mysqld.service", "sshd.service", "firewalld.service",
            "crond.service", "rsyslog.service",
        ],
        "failed_services": ["mysql-backup.service"],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 1.0, 0.3, 0.7, 28),
            ("/dev/sda2", "/", 100.0, 47.2, 52.8, 47),
            ("/dev/sdb1", "/var/lib/mysql", 1000.0, 688.4, 311.6, 69),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 3306, "LISTEN", 3120, "mysqld"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 891, "sshd"),
        ],
        "pkg_count": 401,
        "pkg_sample": [
            "mysql-server", "mysql", "python3-PyMySQL",
            "openssl", "perl", "tar", "xtrabackup", "rsync",
        ],
        "uptime": "7 days, 2:15:44",
        "load_avg": "3.21 3.05 2.87",
        "firewall_zones": "internal (active): enp1s0  services: ssh mysql",
        "journal_lines": [
            "Jul 03 08:05:12 db-my-01 mysqld[3120]: InnoDB: page_cleaner: 1000ms intended loop took 2341ms",
            "Jul 03 04:00:01 db-my-01 systemd[1]: mysql-backup.service: Start request repeated too quickly",
            "Jul 03 04:00:01 db-my-01 systemd[1]: mysql-backup.service: Failed with result 'exit-code'",
        ],
    },

    # ------------------------------------------------------------------
    # 3  Container host — podman, systemd-managed container workloads
    # ------------------------------------------------------------------
    {
        "hostname": "ctr-01.corp.example.com",
        "os_name": "Rocky Linux 9.5",
        "os_id": "rocky",
        "kernel": "5.14.0-503.14.1.el9_5.x86_64",
        "login_user": "sysadm",
        "cwd": "/home/sysadm",
        "home_dir": "/home/sysadm",
        "cpu_label": "AMD EPYC 7302",
        "cpu_cores": 16,
        "mem_total_gb": 128.0,
        "mem_avail_gb": 62.1,
        "active_services": [
            "podman.service", "sshd.service", "firewalld.service",
            "rsyslog.service", "crond.service",
            "container-webapp.service", "container-redis.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 1.0, 0.2, 0.8, 22),
            ("/dev/sda2", "/", 100.0, 38.5, 61.5, 38),
            ("/dev/sdb1", "/var/lib/containers", 2000.0, 742.1, 1257.9, 37),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 8080, "LISTEN", 4521, "rootlesskit"),
            ("tcp", "0.0.0.0", 6379, "LISTEN", 4891, "redis-server"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 890, "sshd"),
        ],
        "pkg_count": 478,
        "pkg_sample": [
            "podman", "buildah", "skopeo", "containernetworking-plugins",
            "fuse-overlayfs", "slirp4netns", "python3", "openssl",
        ],
        "uptime": "5 days, 19:33:02",
        "load_avg": "1.87 1.74 1.62",
        "firewall_zones": "public (active): enp3s0  services: ssh",
        "journal_lines": [
            "Jul 03 08:10:21 ctr-01 systemd[1]: container-webapp.service: Scheduled restart job, restart counter is at 0",
            'Jul 03 07:58:44 ctr-01 podman[4521]: time="2026-07-03T07:58:44Z" level=info msg="Container started"',
            "Jul 03 06:30:00 ctr-01 crond[992]: (root) CMD (/usr/bin/podman system prune -f --filter until=24h)",
        ],
    },

    # ------------------------------------------------------------------
    # 4  Edge firewall / router — minimal, high-security perimeter
    # ------------------------------------------------------------------
    {
        "hostname": "fw-edge-01.corp.example.com",
        "os_name": "Rocky Linux 9.3",
        "os_id": "rocky",
        "kernel": "5.14.0-362.8.1.el9_3.x86_64",
        "login_user": "netops",
        "cwd": "/etc/firewalld",
        "home_dir": "/home/netops",
        "cpu_label": "Intel Atom C3758",
        "cpu_cores": 8,
        "mem_total_gb": 16.0,
        "mem_avail_gb": 13.2,
        "active_services": [
            "firewalld.service", "sshd.service", "keepalived.service",
            "rsyslog.service",
        ],
        "failed_services": [],
        "inactive_services": ["httpd.service", "crond.service"],
        "disks": [
            ("/dev/sda1", "/boot", 0.5, 0.1, 0.4, 22),
            ("/dev/sda2", "/", 20.0, 6.3, 13.7, 31),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 22, "LISTEN", 712, "sshd"),
        ],
        "pkg_count": 187,
        "pkg_sample": [
            "firewalld", "nftables", "iproute", "keepalived",
            "iptables", "tcpdump", "net-tools", "bind-utils",
        ],
        "uptime": "88 days, 4:55:31",
        "load_avg": "0.08 0.06 0.05",
        "firewall_zones": (
            "external (active): enp1s0  "
            "internal (active): enp2s0  "
            "services (internal): ssh"
        ),
        "journal_lines": [
            "Jul 03 08:13:00 fw-edge-01 firewalld[812]: INFO: Reloading firewall done",
            "Jul 03 08:00:01 fw-edge-01 keepalived[934]: Keepalived_vrrp: VRRP_Instance(VI_1) Entering MASTER STATE",
            "Jul 03 07:45:18 fw-edge-01 kernel: nft: table ip filter chain INPUT DROP src 198.51.100.0/24",
        ],
    },

    # ------------------------------------------------------------------
    # 5  Fresh install — minimal Rocky 9.5, just provisioned
    # ------------------------------------------------------------------
    {
        "hostname": "fresh-01.corp.example.com",
        "os_name": "Rocky Linux 9.5",
        "os_id": "rocky",
        "kernel": "5.14.0-503.14.1.el9_5.x86_64",
        "login_user": "root",
        "cwd": "/root",
        "home_dir": "/root",
        "cpu_label": "Intel Core i5-10400",
        "cpu_cores": 6,
        "mem_total_gb": 8.0,
        "mem_avail_gb": 7.1,
        "active_services": [
            "sshd.service", "firewalld.service", "rsyslog.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 1.0, 0.1, 0.9, 11),
            ("/dev/sda2", "/", 40.0, 4.1, 35.9, 10),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 22, "LISTEN", 791, "sshd"),
        ],
        "pkg_count": 142,
        "pkg_sample": [
            "basesystem", "bash", "coreutils", "dnf", "firewalld",
            "openssh-server", "rsyslog", "systemd",
        ],
        "uptime": "0 days, 0:12:44",
        "load_avg": "0.02 0.07 0.03",
        "firewall_zones": "public (active): enp3s0  services: ssh",
        "journal_lines": [
            "Jul 03 09:00:22 fresh-01 systemd[1]: Reached target Multi-User System",
            "Jul 03 09:00:21 fresh-01 sshd[791]: Server listening on 0.0.0.0 port 22",
            "Jul 03 09:00:20 fresh-01 firewalld[802]: INFO: Firewalld started successfully",
        ],
    },

    # ------------------------------------------------------------------
    # 6  Developer workstation — Rocky 9.4, local dev tools
    # ------------------------------------------------------------------
    {
        "hostname": "devws-01.corp.example.com",
        "os_name": "Rocky Linux 9.4",
        "os_id": "rocky",
        "kernel": "5.14.0-427.13.1.el9_4.x86_64",
        "login_user": "dev",
        "cwd": "/home/dev/projects/webapp",
        "home_dir": "/home/dev",
        "cpu_label": "Intel Core i7-12700K",
        "cpu_cores": 12,
        "mem_total_gb": 32.0,
        "mem_avail_gb": 14.8,
        "active_services": [
            "sshd.service", "firewalld.service", "rsyslog.service",
            "crond.service", "postgresql.service",
        ],
        "failed_services": [],
        "inactive_services": ["httpd.service"],
        "disks": [
            ("/dev/nvme0n1p1", "/boot", 1.0, 0.2, 0.8, 22),
            ("/dev/nvme0n1p2", "/", 200.0, 88.4, 111.6, 44),
            ("/dev/sdb1", "/data", 1000.0, 221.3, 778.7, 22),
        ],
        "listen_ports": [
            ("tcp", "127.0.0.1", 5432, "LISTEN", 3210, "postgres"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 881, "sshd"),
            ("tcp", "127.0.0.1", 8000, "LISTEN", 14523, "python3"),
        ],
        "pkg_count": 891,
        "pkg_sample": [
            "python3", "python3-pip", "git", "gcc", "make",
            "postgresql", "vim", "tmux", "curl", "jq",
        ],
        "uptime": "1 day, 8:22:15",
        "load_avg": "1.34 0.98 0.87",
        "firewall_zones": "public (active): enp3s0  services: ssh",
        "journal_lines": [
            "Jul 03 08:14:05 devws-01 systemd[1]: Started Session 12 of User dev",
            "Jul 03 08:01:00 devws-01 crond[990]: (dev) CMD (/home/dev/scripts/backup.sh)",
            "Jul 03 07:55:12 devws-01 sshd[881]: Accepted publickey for dev from 10.0.0.15 port 49821",
        ],
    },

    # ------------------------------------------------------------------
    # 7  HAProxy load balancer — high-throughput, dual-NIC bonded uplink
    # ------------------------------------------------------------------
    {
        "hostname": "lb-01.corp.example.com",
        "os_name": "Rocky Linux 9.3",
        "os_id": "rocky",
        "kernel": "5.14.0-362.8.1.el9_3.x86_64",
        "login_user": "sysadm",
        "cwd": "/etc/haproxy",
        "home_dir": "/home/sysadm",
        "cpu_label": "Intel Xeon E3-1270 v6",
        "cpu_cores": 4,
        "mem_total_gb": 8.0,
        "mem_avail_gb": 5.4,
        "active_services": [
            "haproxy.service", "sshd.service", "firewalld.service",
            "rsyslog.service", "keepalived.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 0.5, 0.1, 0.4, 22),
            ("/dev/sda2", "/", 30.0, 9.8, 20.2, 33),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 80, "LISTEN", 1812, "haproxy"),
            ("tcp", "0.0.0.0", 443, "LISTEN", 1812, "haproxy"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 893, "sshd"),
        ],
        "pkg_count": 198,
        "pkg_sample": [
            "haproxy", "keepalived", "openssl", "rsyslog",
            "iproute", "net-tools", "tcpdump", "socat",
        ],
        "uptime": "31 days, 11:44:08",
        "load_avg": "0.67 0.61 0.58",
        "firewall_zones": "public (active): bond0  services: ssh http https",
        "journal_lines": [
            "Jul 03 08:00:00 lb-01 haproxy[1812]: Proxy http-in started",
            "Jul 03 07:00:01 lb-01 keepalived[934]: VRRP_Instance(VI_1) Received advert with higher priority",
            "Jul 03 06:30:11 lb-01 haproxy[1812]: backend web-backend: web-prod-03:80 is DOWN, reason: Layer7 wrong status",
        ],
    },

    # ------------------------------------------------------------------
    # 8  Monitoring host — Prometheus, Grafana, Alertmanager
    # ------------------------------------------------------------------
    {
        "hostname": "monitoring-01.corp.example.com",
        "os_name": "Rocky Linux 9.4",
        "os_id": "rocky",
        "kernel": "5.14.0-427.13.1.el9_4.x86_64",
        "login_user": "sysadm",
        "cwd": "/etc/prometheus",
        "home_dir": "/home/sysadm",
        "cpu_label": "Intel Xeon E5-2650 v3",
        "cpu_cores": 10,
        "mem_total_gb": 32.0,
        "mem_avail_gb": 11.2,
        "active_services": [
            "prometheus.service", "grafana-server.service",
            "alertmanager.service", "sshd.service",
            "firewalld.service", "rsyslog.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 1.0, 0.2, 0.8, 22),
            ("/dev/sda2", "/", 100.0, 41.3, 58.7, 41),
            ("/dev/sdb1", "/var/lib/prometheus", 1000.0, 524.8, 475.2, 52),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 9090, "LISTEN", 2213, "prometheus"),
            ("tcp", "0.0.0.0", 3000, "LISTEN", 2418, "grafana"),
            ("tcp", "0.0.0.0", 9093, "LISTEN", 2601, "alertmanager"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 889, "sshd"),
        ],
        "pkg_count": 523,
        "pkg_sample": [
            "prometheus", "grafana", "alertmanager", "node-exporter",
            "openssl", "python3", "curl", "jq",
        ],
        "uptime": "21 days, 3:08:57",
        "load_avg": "1.12 0.98 0.91",
        "firewall_zones": (
            "internal (active): enp3s0  "
            "services: ssh prometheus grafana alertmanager"
        ),
        "journal_lines": [
            "Jul 03 08:15:00 monitoring-01 prometheus[2213]: ts=2026-07-03T08:15:00Z caller=compact.go msg=\"write block\" mint=1751515200 maxt=1751601600",
            "Jul 03 08:00:01 monitoring-01 alertmanager[2601]: level=info msg=\"Received POST\" path=/api/v2/alerts numAlerts=3",
            "Jul 03 07:30:00 monitoring-01 crond[994]: (root) CMD (/usr/local/bin/prometheus_cleanup.sh)",
        ],
    },

    # ------------------------------------------------------------------
    # 9  NFS storage server — large disks, quota enforcement
    # ------------------------------------------------------------------
    {
        "hostname": "storage-01.corp.example.com",
        "os_name": "Rocky Linux 9.3",
        "os_id": "rocky",
        "kernel": "5.14.0-362.8.1.el9_3.x86_64",
        "login_user": "root",
        "cwd": "/etc/exports.d",
        "home_dir": "/root",
        "cpu_label": "Intel Xeon Silver 4110",
        "cpu_cores": 8,
        "mem_total_gb": 32.0,
        "mem_avail_gb": 24.7,
        "active_services": [
            "nfs-server.service", "rpcbind.service", "nfs-mountd.service",
            "sshd.service", "firewalld.service", "rsyslog.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 1.0, 0.2, 0.8, 22),
            ("/dev/sda2", "/", 50.0, 14.8, 35.2, 30),
            ("/dev/sdb1", "/exports/data", 8000.0, 5124.3, 2875.7, 64),
            ("/dev/sdc1", "/exports/backup", 8000.0, 3871.2, 4128.8, 48),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 2049, "LISTEN", 1523, "nfs"),
            ("tcp", "0.0.0.0", 111, "LISTEN", 798, "rpcbind"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 882, "sshd"),
        ],
        "pkg_count": 312,
        "pkg_sample": [
            "nfs-utils", "rpcbind", "quota", "autofs",
            "rsync", "openssl", "tar", "lvm2",
        ],
        "uptime": "67 days, 9:21:18",
        "load_avg": "0.33 0.41 0.38",
        "firewall_zones": "internal (active): enp1s0  services: ssh nfs rpc-bind mountd",
        "journal_lines": [
            "Jul 03 08:10:30 storage-01 rpc.mountd[1524]: authenticated unmount request from 10.0.1.22:0 for /exports/data",
            "Jul 03 07:00:01 storage-01 systemd[1]: Starting NFS server and services...",
            "Jul 03 06:00:01 storage-01 crond[991]: (root) CMD (/usr/sbin/repquota -a > /var/log/quota.log)",
        ],
    },

    # ------------------------------------------------------------------
    # 10  Mail server — Postfix + Dovecot, TLS, spam filtering
    # ------------------------------------------------------------------
    {
        "hostname": "mail-01.corp.example.com",
        "os_name": "Rocky Linux 9.4",
        "os_id": "rocky",
        "kernel": "5.14.0-427.13.1.el9_4.x86_64",
        "login_user": "sysadm",
        "cwd": "/etc/postfix",
        "home_dir": "/home/sysadm",
        "cpu_label": "Intel Xeon E3-1230 v5",
        "cpu_cores": 4,
        "mem_total_gb": 16.0,
        "mem_avail_gb": 8.3,
        "active_services": [
            "postfix.service", "dovecot.service", "spamassassin.service",
            "clamd@scan.service", "sshd.service", "firewalld.service",
            "rsyslog.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 1.0, 0.2, 0.8, 22),
            ("/dev/sda2", "/", 50.0, 22.1, 27.9, 44),
            ("/dev/sdb1", "/var/spool/mail", 500.0, 124.7, 375.3, 25),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 25, "LISTEN", 1934, "postfix"),
            ("tcp", "0.0.0.0", 465, "LISTEN", 1934, "postfix"),
            ("tcp", "0.0.0.0", 587, "LISTEN", 1934, "postfix"),
            ("tcp", "0.0.0.0", 993, "LISTEN", 2103, "dovecot"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 886, "sshd"),
        ],
        "pkg_count": 487,
        "pkg_sample": [
            "postfix", "dovecot", "spamassassin", "clamav",
            "clamav-update", "openssl", "cyrus-sasl", "opendkim",
        ],
        "uptime": "9 days, 17:04:51",
        "load_avg": "0.88 0.74 0.66",
        "firewall_zones": (
            "public (active): enp3s0  "
            "services: ssh smtp smtps submission imaps"
        ),
        "journal_lines": [
            "Jul 03 08:11:12 mail-01 postfix/smtpd[1935]: connect from mail.sender.example.com[198.51.100.4]",
            "Jul 03 08:09:44 mail-01 postfix/smtp[1941]: to=<user@corp.example.com>, relay=10.0.1.5[10.0.1.5]:25, status=sent",
            "Jul 03 06:30:00 mail-01 crond[989]: (root) CMD (/usr/bin/freshclam --quiet)",
        ],
    },

    # ------------------------------------------------------------------
    # 11  CI / build server — Jenkins, Java builds, high CPU burst load
    # ------------------------------------------------------------------
    {
        "hostname": "ci-build-01.corp.example.com",
        "os_name": "Rocky Linux 9.4",
        "os_id": "rocky",
        "kernel": "5.14.0-427.13.1.el9_4.x86_64",
        "login_user": "jenkins",
        "cwd": "/var/lib/jenkins/workspace",
        "home_dir": "/var/lib/jenkins",
        "cpu_label": "AMD EPYC 7532",
        "cpu_cores": 32,
        "mem_total_gb": 64.0,
        "mem_avail_gb": 28.4,
        "active_services": [
            "jenkins.service", "sshd.service", "firewalld.service",
            "rsyslog.service", "crond.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 1.0, 0.2, 0.8, 22),
            ("/dev/sda2", "/", 100.0, 51.3, 48.7, 51),
            ("/dev/sdb1", "/var/lib/jenkins", 2000.0, 889.2, 1110.8, 44),
            ("/dev/sdc1", "/tmp/builds", 500.0, 213.4, 286.6, 43),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 8080, "LISTEN", 3412, "java"),
            ("tcp", "0.0.0.0", 50000, "LISTEN", 3412, "java"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 895, "sshd"),
        ],
        "pkg_count": 742,
        "pkg_sample": [
            "java-17-openjdk", "java-17-openjdk-devel", "git",
            "maven", "gcc", "make", "python3", "podman",
        ],
        "uptime": "3 days, 4:17:33",
        "load_avg": "8.42 6.31 5.14",
        "firewall_zones": "internal (active): enp1s0  services: ssh http",
        "journal_lines": [
            "Jul 03 08:14:55 ci-build-01 java[3412]: INFO: Build started: project webapp build #1247",
            "Jul 03 08:12:02 ci-build-01 java[3412]: INFO: Checking out from SCM: git@gitlab.corp.example.com:webapp.git",
            "Jul 03 08:10:01 ci-build-01 systemd[1]: jenkins.service: Reload signal sent",
        ],
    },

    # ------------------------------------------------------------------
    # 12  DNS / directory server — BIND9, SSSD, LDAP client
    # ------------------------------------------------------------------
    {
        "hostname": "dns-01.corp.example.com",
        "os_name": "Rocky Linux 9.3",
        "os_id": "rocky",
        "kernel": "5.14.0-362.8.1.el9_3.x86_64",
        "login_user": "root",
        "cwd": "/etc/named",
        "home_dir": "/root",
        "cpu_label": "Intel Xeon E3-1270 v6",
        "cpu_cores": 4,
        "mem_total_gb": 8.0,
        "mem_avail_gb": 5.9,
        "active_services": [
            "named.service", "sssd.service", "sshd.service",
            "firewalld.service", "rsyslog.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 0.5, 0.1, 0.4, 22),
            ("/dev/sda2", "/", 40.0, 11.2, 28.8, 28),
        ],
        "listen_ports": [
            ("udp", "0.0.0.0", 53, "LISTEN", 1312, "named"),
            ("tcp", "0.0.0.0", 53, "LISTEN", 1312, "named"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 884, "sshd"),
        ],
        "pkg_count": 278,
        "pkg_sample": [
            "bind", "bind-utils", "sssd", "openldap-clients",
            "krb5-workstation", "oddjob-mkhomedir", "openssl", "python3",
        ],
        "uptime": "55 days, 22:41:07",
        "load_avg": "0.11 0.09 0.08",
        "firewall_zones": "internal (active): enp1s0  services: ssh dns",
        "journal_lines": [
            "Jul 03 08:13:07 dns-01 named[1312]: zone corp.example.com/IN: sending notifies (serial 2026070301)",
            "Jul 03 07:00:01 dns-01 named[1312]: zone corp.example.com/IN: loaded serial 2026070301",
            "Jul 03 06:45:00 dns-01 sssd[1398]: Successfully refreshed SSSD cache for domain corp.example.com",
        ],
    },

    # ------------------------------------------------------------------
    # 13  Java application server — Tomcat, production webapp
    # ------------------------------------------------------------------
    {
        "hostname": "app-java-01.corp.example.com",
        "os_name": "Rocky Linux 9.4",
        "os_id": "rocky",
        "kernel": "5.14.0-427.13.1.el9_4.x86_64",
        "login_user": "tomcat",
        "cwd": "/opt/tomcat/webapps",
        "home_dir": "/home/tomcat",
        "cpu_label": "Intel Xeon Gold 5218",
        "cpu_cores": 16,
        "mem_total_gb": 64.0,
        "mem_avail_gb": 19.8,
        "active_services": [
            "tomcat.service", "sshd.service", "firewalld.service",
            "rsyslog.service", "crond.service",
        ],
        "failed_services": [],
        "inactive_services": [],
        "disks": [
            ("/dev/sda1", "/boot", 1.0, 0.2, 0.8, 22),
            ("/dev/sda2", "/", 100.0, 44.7, 55.3, 45),
            ("/dev/sdb1", "/opt/tomcat", 200.0, 87.3, 112.7, 44),
            ("/dev/sdb2", "/var/log/tomcat", 100.0, 31.2, 68.8, 31),
        ],
        "listen_ports": [
            ("tcp", "0.0.0.0", 8080, "LISTEN", 4123, "java"),
            ("tcp", "127.0.0.1", 8009, "LISTEN", 4123, "java"),
            ("tcp", "127.0.0.1", 8005, "LISTEN", 4123, "java"),
            ("tcp", "0.0.0.0", 22, "LISTEN", 896, "sshd"),
        ],
        "pkg_count": 534,
        "pkg_sample": [
            "java-17-openjdk", "java-17-openjdk-devel", "tomcat",
            "openssl", "curl", "tar", "logrotate", "python3",
        ],
        "uptime": "18 days, 7:53:29",
        "load_avg": "2.78 2.54 2.31",
        "firewall_zones": "internal (active): enp3s0  services: ssh http",
        "journal_lines": [
            "Jul 03 08:12:44 app-java-01 tomcat[4123]: INFO: Server startup in 4823 ms",
            "Jul 03 08:00:01 app-java-01 crond[993]: (tomcat) CMD (/opt/scripts/log_rotate_tomcat.sh)",
            "Jul 03 07:55:18 app-java-01 sshd[896]: Accepted publickey for tomcat from 10.0.2.14 port 52341",
        ],
    },
]

# Sanity check: at least 12 profiles are defined (plan requirement: >=12).
assert len(_PROFILES) >= 12, (
    f"Expected at least 12 host profiles, got {len(_PROFILES)}.  "
    "Add more profiles to satisfy the corpus variety requirement."
)


# ---------------------------------------------------------------------------
# Snapshot builder
# ---------------------------------------------------------------------------

def _build_snapshot(p: dict) -> SystemSnapshot:
    """
    Convert a profile dict into a populated SystemSnapshot.

    Uses SystemSnapshot's typed fields directly so to_prompt_text() will
    serialise the data through the same code path that the live context
    collector uses — guaranteeing format parity with production.
    """
    disks = [
        DiskEntry(
            device=d[0],
            mount=d[1],
            total_bytes=_gb(d[2]),
            used_bytes=_gb(d[3]),
            avail_bytes=_gb(d[4]),
            use_pct=d[5],
        )
        for d in p["disks"]
    ]
    ports = [
        PortEntry(
            protocol=prt[0],
            local_addr=prt[1],
            local_port=prt[2],
            state=prt[3],
            pid=prt[4],
            process=prt[5],
        )
        for prt in p["listen_ports"]
    ]
    return SystemSnapshot(
        hostname=p["hostname"],
        os_name=p["os_name"],
        os_id=p["os_id"],
        kernel=p["kernel"],
        cwd=p["cwd"],
        home_dir=p["home_dir"],
        login_user=p["login_user"],
        cpu_model=p["cpu_label"],
        cpu_cores=p["cpu_cores"],
        mem_total_bytes=_gb(p["mem_total_gb"]),
        mem_avail_bytes=_gb(p["mem_avail_gb"]),
        installed_package_count=p["pkg_count"],
        installed_packages_sample=list(p["pkg_sample"]),
        failed_services=list(p["failed_services"]),
        active_services=list(p["active_services"]),
        inactive_services=list(p.get("inactive_services", [])),
        disks=disks,
        listen_ports=ports,
        collected_at="2026-07-03T08:00:00Z",
    )


# ---------------------------------------------------------------------------
# Extra-field builder
# ---------------------------------------------------------------------------

def _build_extra(p: dict, tier: str) -> str:
    """
    Build the supplemental context lines not emitted by to_prompt_text().

    to_prompt_text() does not render: uptime, load average, firewall zone
    summary, installed_packages_sample names, or recent journal lines.
    This function produces those lines so the snapshot_text is complete.

    Verbosity is tier-sensitive (but NOT structure-sensitive — INV-I6):
      - marika : uptime, load, firewall, first 5 package names
      - radagon: same + full package list + all journal lines
    """
    lines: list[str] = []

    lines.append(f"Uptime: {p['uptime']}")
    lines.append(f"Load average (1m/5m/15m): {p['load_avg']}")
    lines.append(f"Firewall: {p['firewall_zones']}")

    # Package sample — name count nudged by tier
    pkg_sample: list[str] = p.get("pkg_sample", [])
    if pkg_sample:
        depth = len(pkg_sample) if tier == "radagon" else min(5, len(pkg_sample))
        lines.append("Packages (sample): " + ", ".join(pkg_sample[:depth]))

    # Journal lines — radagon gets full context; marika skips for brevity
    if tier == "radagon":
        journal: list[str] = p.get("journal_lines", [])
        if journal:
            lines.append("Recent journal:")
            for jl in journal:
                lines.append(f"  {jl}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def make_context(tier: str, seed: int) -> str:
    """
    Return a seeded Rocky Linux 9 snapshot_text for the given tier.

    The returned string is ready for direct assignment to
    PromptConfig.snapshot_text and subsequent injection by assemble_messages().

    Parameters
    ----------
    tier : str
        "marika" or "radagon".  Nudges context depth — radagon gets more
        journal lines and the full package sample.  Does NOT change structure.
    seed : int
        Selects a host profile deterministically via (seed % len(_PROFILES)).
        Callers cycling seed 0..N-1 will visit all 14 profiles.

    Returns
    -------
    str
        I2-clean snapshot_text string.  assert_no_ai_language is called
        before return; any forbidden term in a profile raises ValueError
        immediately so corpus generation cannot silently emit tainted context.

    Raises
    ------
    ValueError
        If the produced text contains any I2-forbidden term.
    """
    profile = _PROFILES[seed % len(_PROFILES)]
    snap = _build_snapshot(profile)
    base_text = snap.to_prompt_text()
    extra = _build_extra(profile, tier)
    text = f"{base_text}\n{extra}" if extra else base_text
    # INV-I2: snapshots are injected into the user-facing system prompt.
    assert_no_ai_language(text, label=f"context(tier={tier!r}, seed={seed})")
    return text
