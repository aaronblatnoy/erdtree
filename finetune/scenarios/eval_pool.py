"""finetune/scenarios/eval_pool.py — HELD-OUT evaluation pool.

This module is a held-out EVALUATION corpus, disjoint from the training
scenario corpus aggregated in finetune/scenarios/__init__.py.  It exists to
measure the fine-tuned Erdtree agent on user requests it was never trained
on, spanning every registered tool.

Coverage
--------
  Exactly 2 scenarios per tool, for all 55 tools registered in
  finetune.coreimports.TOOL_NAMES = 110 entries total.
  All three permission classes represented (read / write / destructive).
  All three complexities represented (single / multi / diagnostic).

INV-schema-sync:  permission_class is derived LIVE from the registry via
  the local _pc(tool, op) helper — never hardcoded.
INV-read-only-core:  imports only from finetune.coreimports and (one-way,
  for the novelty check) finetune.scenarios — never directly from core/.
  finetune/scenarios/__init__.py must NOT import this module back.
INV-offline:  imports cleanly with no network, no Ollama, no API key.

This module is NOT part of finetune/scenarios/__init__.py's ALL_SCENARIOS
aggregation and is never used for training data generation — it is
consumed only by evaluation tooling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, TOOL_NAMES, registry

# ---------------------------------------------------------------------------
# Frozen local Scenario dataclass — field-compatible with
# finetune.scenarios.Scenario (see finetune/scenarios/aide.py for the same
# pattern used by the training corpus).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    id: str
    tool: str
    operation: str
    permission_class: OpClass
    complexity: Literal["single", "multi", "diagnostic"]
    user_input: str
    notes: str


# ---------------------------------------------------------------------------
# Live permission-class lookup — INV-schema-sync.
# Takes the tool name explicitly since this pool spans all 55 tools.
# ---------------------------------------------------------------------------


def _pc(tool: str, op: str) -> OpClass:
    """Return the live permission class for *op* on *tool*."""
    return registry.get(tool).permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries — exactly 2 per tool, 55 tools, 110 total.
# ---------------------------------------------------------------------------

EVAL_SCENARIOS: list[Scenario] = [
    Scenario(
        id="aide-check-eval-0001",
        tool="aide",
        operation="check",
        permission_class=_pc("aide", "check"),
        complexity="single",
        user_input="Before I touch anything on this box, run an aide integrity scan so I have a clean report to point to later.",
        notes="Pre-change baseline capture.",
    ),
    Scenario(
        id="aide-init-eval-0002",
        tool="aide",
        operation="init",
        permission_class=_pc("aide", "init"),
        complexity="diagnostic",
        user_input="The new replica host db02 never had an aide database created and check keeps erroring out — get it stood up.",
        notes="Missing-DB diagnostic resolved by init.",
    ),
    Scenario(
        id="at-atq-eval-0001",
        tool="at",
        operation="atq",
        permission_class=_pc("at", "atq"),
        complexity="single",
        user_input="List whatever one-off jobs are still sitting in the at queue on this box.",
        notes="Queue inspection.",
    ),
    Scenario(
        id="at-schedule-eval-0002",
        tool="at",
        operation="schedule",
        permission_class=_pc("at", "schedule"),
        complexity="multi",
        user_input="Queue up a one-time job for 2am tomorrow that rotates the app logs, and confirm it landed in the queue.",
        notes="Schedule then verify via atq.",
    ),
    Scenario(
        id="audit-search-by-key-eval-0001",
        tool="audit",
        operation="search-by-key",
        permission_class=_pc("audit", "search-by-key"),
        complexity="single",
        user_input="Pull every audit log entry tagged with the key privilege-escalation from today.",
        notes="Keyed audit search.",
    ),
    Scenario(
        id="audit-add-rule-eval-0002",
        tool="audit",
        operation="add-rule",
        permission_class=_pc("audit", "add-rule"),
        complexity="multi",
        user_input="Add an audit rule watching writes to /etc/shadow and then show me the current rule list to confirm it took.",
        notes="Add rule then list rules.",
    ),
    Scenario(
        id="bond-show-eval-0001",
        tool="bond",
        operation="show",
        permission_class=_pc("bond", "show"),
        complexity="single",
        user_input="What's the current state of the bond0 interface?",
        notes="Bond status check.",
    ),
    Scenario(
        id="bond-add-eval-0002",
        tool="bond",
        operation="add",
        permission_class=_pc("bond", "add"),
        complexity="multi",
        user_input="Create an active-backup bond called bond1 out of eth2 and eth3, then show me its status.",
        notes="Bond creation then verification.",
    ),
    Scenario(
        id="buildah-images-eval-0001",
        tool="buildah",
        operation="images",
        permission_class=_pc("buildah", "images"),
        complexity="single",
        user_input="List the local container images buildah knows about.",
        notes="Image inventory.",
    ),
    Scenario(
        id="buildah-build-eval-0002",
        tool="buildah",
        operation="build",
        permission_class=_pc("buildah", "build"),
        complexity="multi",
        user_input="Build an image from the Containerfile in /srv/app-build and tag it app:release, then list images to confirm it's there.",
        notes="Build then verify presence.",
    ),
    Scenario(
        id="chrony-tracking-eval-0001",
        tool="chrony",
        operation="tracking",
        permission_class=_pc("chrony", "tracking"),
        complexity="single",
        user_input="How far off is our clock from the NTP source right now?",
        notes="Tracking/offset check.",
    ),
    Scenario(
        id="chrony-makestep-eval-0002",
        tool="chrony",
        operation="makestep",
        permission_class=_pc("chrony", "makestep"),
        complexity="diagnostic",
        user_input="The clock has drifted almost a full second and services are complaining about cert validity — force a step correction.",
        notes="Large-drift diagnostic resolved by makestep.",
    ),
    Scenario(
        id="cron-list-eval-0001",
        tool="cron",
        operation="list",
        permission_class=_pc("cron", "list"),
        complexity="single",
        user_input="What cron jobs does the deploy user have scheduled?",
        notes="Per-user crontab listing.",
    ),
    Scenario(
        id="cron-edit-eval-0002",
        tool="cron",
        operation="edit",
        permission_class=_pc("cron", "edit"),
        complexity="multi",
        user_input="Add a nightly 3am cron entry for the backup user that runs /opt/scripts/nightly-sync.sh, then show me the crontab so I can eyeball it.",
        notes="Edit crontab then list to confirm.",
    ),
    Scenario(
        id="crypto_policies-get-eval-0001",
        tool="crypto_policies",
        operation="get",
        permission_class=_pc("crypto_policies", "get"),
        complexity="single",
        user_input="What system-wide crypto policy is currently active?",
        notes="Active policy read.",
    ),
    Scenario(
        id="crypto_policies-set-eval-0002",
        tool="crypto_policies",
        operation="set",
        permission_class=_pc("crypto_policies", "set"),
        complexity="multi",
        user_input="Switch the system to the FUTURE crypto policy and then show me the active policy to confirm it applied.",
        notes="Set policy then re-read to confirm.",
    ),
    Scenario(
        id="disk-usage-eval-0001",
        tool="disk",
        operation="usage",
        permission_class=_pc("disk", "usage"),
        complexity="single",
        user_input="How much free space is left on /var right now?",
        notes="Filesystem usage check.",
    ),
    Scenario(
        id="disk-format-eval-0002",
        tool="disk",
        operation="format",
        permission_class=_pc("disk", "format"),
        complexity="diagnostic",
        user_input="The replacement drive at /dev/sdc is brand new and unpartitioned — we need it wiped and formatted ext4 before it goes into the array.",
        notes="New-disk prep, destructive format after confirming target.",
    ),
    Scenario(
        id="dnf_modules-list-eval-0001",
        tool="dnf_modules",
        operation="list",
        permission_class=_pc("dnf_modules", "list"),
        complexity="single",
        user_input="Which dnf module streams are currently enabled on this host?",
        notes="Module stream inventory.",
    ),
    Scenario(
        id="dnf_modules-enable-eval-0002",
        tool="dnf_modules",
        operation="enable",
        permission_class=_pc("dnf_modules", "enable"),
        complexity="multi",
        user_input="Enable the postgresql:15 module stream and then list modules so I can confirm 15 is what's active.",
        notes="Enable then re-list to confirm.",
    ),
    Scenario(
        id="dns-dig-eval-0001",
        tool="dns",
        operation="dig",
        permission_class=_pc("dns", "dig"),
        complexity="single",
        user_input="Look up the A record for billing.internal.corp.",
        notes="DNS record lookup.",
    ),
    Scenario(
        id="dns-flush_caches-eval-0002",
        tool="dns",
        operation="flush_caches",
        permission_class=_pc("dns", "flush_caches"),
        complexity="diagnostic",
        user_input="Clients are still resolving the old IP for a host we repointed an hour ago — flush the local DNS cache.",
        notes="Stale-record diagnostic resolved by cache flush.",
    ),
    Scenario(
        id="docs-retrieve-eval-0001",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("docs", "retrieve"),
        complexity="single",
        user_input="What flags does firewall-cmd take for adding a rich rule?",
        notes="Reference-corpus lookup for a specific flag.",
    ),
    Scenario(
        id="docs-retrieve-eval-0002",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("docs", "retrieve"),
        complexity="diagnostic",
        user_input="I'm not sure whether setenforce or semanage is the right tool for a permanent SELinux context change — look it up before I do anything.",
        notes="Corpus lookup used to disambiguate before acting; docs has only one operation.",
    ),
    Scenario(
        id="fapolicyd-status-eval-0001",
        tool="fapolicyd",
        operation="status",
        permission_class=_pc("fapolicyd", "status"),
        complexity="single",
        user_input="Is fapolicyd currently enforcing on this host?",
        notes="Enforcement status check.",
    ),
    Scenario(
        id="fapolicyd-deny-eval-0002",
        tool="fapolicyd",
        operation="deny",
        permission_class=_pc("fapolicyd", "deny"),
        complexity="multi",
        user_input="Add a deny rule blocking execution from /tmp and then show me the current rule list.",
        notes="Add deny rule then list to confirm.",
    ),
    Scenario(
        id="files-find-eval-0001",
        tool="files",
        operation="find",
        permission_class=_pc("files", "find"),
        complexity="single",
        user_input="Find every file under /var/log larger than 500MB.",
        notes="Size-based file search.",
    ),
    Scenario(
        id="files-remove-eval-0002",
        tool="files",
        operation="remove",
        permission_class=_pc("files", "remove"),
        complexity="diagnostic",
        user_input="The build server is out of space and there's a stale 40GB core dump at /var/crash/core.12044 — get rid of it.",
        notes="Disk-pressure diagnostic resolved by removing a specific file.",
    ),
    Scenario(
        id="firewall-list-eval-0001",
        tool="firewall",
        operation="list",
        permission_class=_pc("firewall", "list"),
        complexity="single",
        user_input="Show me everything currently allowed through the firewall on the public zone.",
        notes="Zone rule listing.",
    ),
    Scenario(
        id="firewall-panic_on-eval-0002",
        tool="firewall",
        operation="panic_on",
        permission_class=_pc("firewall", "panic_on"),
        complexity="diagnostic",
        user_input="We think this host is actively being exfiltrated from right now — cut all network traffic immediately.",
        notes="Active-incident diagnostic resolved by panic mode.",
    ),
    Scenario(
        id="grub-default-kernel-eval-0001",
        tool="grub",
        operation="default-kernel",
        permission_class=_pc("grub", "default-kernel"),
        complexity="single",
        user_input="Which kernel is set as the GRUB default right now?",
        notes="Default kernel read.",
    ),
    Scenario(
        id="grub-remove-kernel-eval-0002",
        tool="grub",
        operation="remove-kernel",
        permission_class=_pc("grub", "remove-kernel"),
        complexity="diagnostic",
        user_input="/boot is nearly full because of old kernel entries piling up — clear out the oldest installed kernel.",
        notes="/boot space diagnostic resolved by removing a kernel entry.",
    ),
    Scenario(
        id="hardware-pci-eval-0001",
        tool="hardware",
        operation="pci",
        permission_class=_pc("hardware", "pci"),
        complexity="single",
        user_input="List the PCI devices attached to this machine.",
        notes="PCI device inventory.",
    ),
    Scenario(
        id="hardware-summary-eval-0002",
        tool="hardware",
        operation="summary",
        permission_class=_pc("hardware", "summary"),
        complexity="multi",
        user_input="Give me a full hardware rundown for this box — CPU, memory, and disks — I'm filling out an asset form.",
        notes="Broad hardware summary spanning multiple subsystems.",
    ),
    Scenario(
        id="hostname-status-eval-0001",
        tool="hostname",
        operation="status",
        permission_class=_pc("hostname", "status"),
        complexity="single",
        user_input="What's this machine's current hostname and chassis type?",
        notes="Hostname/status read.",
    ),
    Scenario(
        id="hostname-set-hostname-eval-0002",
        tool="hostname",
        operation="set-hostname",
        permission_class=_pc("hostname", "set-hostname"),
        complexity="multi",
        user_input="Rename this host to db-replica-03 and then read the status back to make sure it stuck.",
        notes="Set hostname then re-check status.",
    ),
    Scenario(
        id="httpd-status-eval-0001",
        tool="httpd",
        operation="status",
        permission_class=_pc("httpd", "status"),
        complexity="single",
        user_input="Is the Apache service currently running?",
        notes="Service status check.",
    ),
    Scenario(
        id="httpd-restart-eval-0002",
        tool="httpd",
        operation="restart",
        permission_class=_pc("httpd", "restart"),
        complexity="diagnostic",
        user_input="Apache is serving stale content even though the vhost config was updated twenty minutes ago — restart it.",
        notes="Stale-config diagnostic resolved by restart.",
    ),
    Scenario(
        id="kernel_modules-lsmod-eval-0001",
        tool="kernel_modules",
        operation="lsmod",
        permission_class=_pc("kernel_modules", "lsmod"),
        complexity="single",
        user_input="Give me a rundown of every kernel module loaded on the mail server right now.",
        notes="Loaded-module listing.",
    ),
    Scenario(
        id="kernel_modules-rmmod-eval-0002",
        tool="kernel_modules",
        operation="rmmod",
        permission_class=_pc("kernel_modules", "rmmod"),
        complexity="diagnostic",
        user_input="The nouveau driver is conflicting with the proprietary NVIDIA one we just installed — unload nouveau.",
        notes="Driver-conflict diagnostic resolved by unloading a module.",
    ),
    Scenario(
        id="locale-localectl-status-eval-0001",
        tool="locale",
        operation="localectl-status",
        permission_class=_pc("locale", "localectl-status"),
        complexity="single",
        user_input="What locale and keyboard layout is this system set to?",
        notes="Locale status read.",
    ),
    Scenario(
        id="locale-set-timezone-eval-0002",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("locale", "set-timezone"),
        complexity="multi",
        user_input="Set this server's timezone to America/Chicago and then show me the status to confirm the change landed.",
        notes="Set timezone then re-check status.",
    ),
    Scenario(
        id="logs-tail-eval-0001",
        tool="logs",
        operation="tail",
        permission_class=_pc("logs", "tail"),
        complexity="single",
        user_input="Tail the last 50 lines of the system journal.",
        notes="Live-ish journal tail.",
    ),
    Scenario(
        id="logs-boot_errors-eval-0002",
        tool="logs",
        operation="boot_errors",
        permission_class=_pc("logs", "boot_errors"),
        complexity="diagnostic",
        user_input="The box came back up slower than usual after last night's reboot — check for any errors during that boot.",
        notes="Slow-boot diagnostic via boot-scoped error query.",
    ),
    Scenario(
        id="lvm-lvdisplay-eval-0001",
        tool="lvm",
        operation="lvdisplay",
        permission_class=_pc("lvm", "lvdisplay"),
        complexity="single",
        user_input="Show me the logical volumes on vg_data.",
        notes="LV inventory.",
    ),
    Scenario(
        id="lvm-lvremove-eval-0002",
        tool="lvm",
        operation="lvremove",
        permission_class=_pc("lvm", "lvremove"),
        complexity="diagnostic",
        user_input="The old staging snapshot lv_stage_snap is no longer needed and it's eating space on vg_data — remove it.",
        notes="Stale-snapshot diagnostic resolved by removing the LV.",
    ),
    Scenario(
        id="mariadb-status-eval-0001",
        tool="mariadb",
        operation="status",
        permission_class=_pc("mariadb", "status"),
        complexity="single",
        user_input="Is the MariaDB service up and accepting connections?",
        notes="DB service status check.",
    ),
    Scenario(
        id="mariadb-drop_database-eval-0002",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("mariadb", "drop_database"),
        complexity="diagnostic",
        user_input="The QA team confirmed the scratch_test database from last sprint is no longer needed anywhere — drop it.",
        notes="Confirmed-unused-DB diagnostic resolved by dropping it.",
    ),
    Scenario(
        id="network-show-eval-0001",
        tool="network",
        operation="show",
        permission_class=_pc("network", "show"),
        complexity="single",
        user_input="Show me the IP configuration on eth0.",
        notes="Interface config read.",
    ),
    Scenario(
        id="network-bring_down-eval-0002",
        tool="network",
        operation="bring_down",
        permission_class=_pc("network", "bring_down"),
        complexity="diagnostic",
        user_input="eth1 is flapping and taking down the whole bond — bring that interface down manually while we investigate.",
        notes="Flapping-link diagnostic resolved by bringing the interface down.",
    ),
    Scenario(
        id="nfs-showmount-eval-0001",
        tool="nfs",
        operation="showmount",
        permission_class=_pc("nfs", "showmount"),
        complexity="single",
        user_input="What clients currently have this host's NFS exports mounted?",
        notes="Mounted-client listing.",
    ),
    Scenario(
        id="nfs-exportfs_unexport-eval-0002",
        tool="nfs",
        operation="exportfs_unexport",
        permission_class=_pc("nfs", "exportfs_unexport"),
        complexity="multi",
        user_input="Unexport /srv/nfs/archive since we're decommissioning it, then show me showmount to confirm no one's still attached.",
        notes="Unexport then re-check active mounts.",
    ),
    Scenario(
        id="nftables-list_ruleset-eval-0001",
        tool="nftables",
        operation="list_ruleset",
        permission_class=_pc("nftables", "list_ruleset"),
        complexity="single",
        user_input="Dump the current nftables ruleset.",
        notes="Ruleset listing.",
    ),
    Scenario(
        id="nftables-flush_ruleset-eval-0002",
        tool="nftables",
        operation="flush_ruleset",
        permission_class=_pc("nftables", "flush_ruleset"),
        complexity="multi",
        user_input="Flush the entire nftables ruleset on this test box and then list it back to confirm it's empty.",
        notes="Flush then re-list to confirm empty state.",
    ),
    Scenario(
        id="nginx-configtest-eval-0001",
        tool="nginx",
        operation="configtest",
        permission_class=_pc("nginx", "configtest"),
        complexity="single",
        user_input="Check whether the nginx config I just edited is syntactically valid.",
        notes="Config syntax validation.",
    ),
    Scenario(
        id="nginx-reload-eval-0002",
        tool="nginx",
        operation="reload",
        permission_class=_pc("nginx", "reload"),
        complexity="multi",
        user_input="Reload nginx to pick up the new server block and then check its status to make sure it's still running.",
        notes="Reload then re-check service status.",
    ),
    Scenario(
        id="nmcli-device_status-eval-0001",
        tool="nmcli",
        operation="device_status",
        permission_class=_pc("nmcli", "device_status"),
        complexity="single",
        user_input="What's the connection state of each network device via NetworkManager?",
        notes="Device-level status read.",
    ),
    Scenario(
        id="nmcli-connection_delete-eval-0002",
        tool="nmcli",
        operation="connection_delete",
        permission_class=_pc("nmcli", "connection_delete"),
        complexity="diagnostic",
        user_input="There's a leftover stale-office-wifi connection profile causing nmcli to try and fail to auto-connect on boot — delete it.",
        notes="Boot-delay diagnostic resolved by deleting the stale profile.",
    ),
    Scenario(
        id="packages-search-eval-0001",
        tool="packages",
        operation="search",
        permission_class=_pc("packages", "search"),
        complexity="single",
        user_input="Search for available packages matching postgresql-server.",
        notes="Package search.",
    ),
    Scenario(
        id="packages-remove-eval-0002",
        tool="packages",
        operation="remove",
        permission_class=_pc("packages", "remove"),
        complexity="multi",
        user_input="Uninstall the old telnet-server package since it failed the security scan, then search for it again to confirm it's gone.",
        notes="Remove then re-search to confirm removal.",
    ),
    Scenario(
        id="pam-pamd_audit-eval-0001",
        tool="pam",
        operation="pamd_audit",
        permission_class=_pc("pam", "pamd_audit"),
        complexity="single",
        user_input="Audit the PAM stack for the sshd service and flag anything unusual.",
        notes="PAM config audit.",
    ),
    Scenario(
        id="pam-faillock_reset-eval-0002",
        tool="pam",
        operation="faillock_reset",
        permission_class=_pc("pam", "faillock_reset"),
        complexity="multi",
        user_input="Reset the failed-login counter for user jsmith and then check the faillock status to confirm it's cleared.",
        notes="Reset lockout counter then re-check status.",
    ),
    Scenario(
        id="perf-stat-eval-0001",
        tool="perf",
        operation="stat",
        permission_class=_pc("perf", "stat"),
        complexity="single",
        user_input="Grab CPU performance counters for the postgres process for 10 seconds.",
        notes="Short perf counter sample.",
    ),
    Scenario(
        id="perf-record-eval-0002",
        tool="perf",
        operation="record",
        permission_class=_pc("perf", "record"),
        complexity="multi",
        user_input="Record perf data on PID 4821 for 30 seconds so we can profile the CPU spike, then let me know when the recording is done.",
        notes="Record profiling data then report completion.",
    ),
    Scenario(
        id="performance-vmstat-eval-0001",
        tool="performance",
        operation="vmstat",
        permission_class=_pc("performance", "vmstat"),
        complexity="single",
        user_input="Show me current vmstat output.",
        notes="Memory/CPU snapshot.",
    ),
    Scenario(
        id="performance-iostat-eval-0002",
        tool="performance",
        operation="iostat",
        permission_class=_pc("performance", "iostat"),
        complexity="diagnostic",
        user_input="Disk-bound workloads have been crawling since this morning — check iostat to see if a device is saturated.",
        notes="IO-bottleneck diagnostic via iostat.",
    ),
    Scenario(
        id="podman-ps-eval-0001",
        tool="podman",
        operation="ps",
        permission_class=_pc("podman", "ps"),
        complexity="single",
        user_input="List the running podman containers.",
        notes="Container listing.",
    ),
    Scenario(
        id="podman-rm-eval-0002",
        tool="podman",
        operation="rm",
        permission_class=_pc("podman", "rm"),
        complexity="diagnostic",
        user_input="There's a crashed container named worker-old sitting around from a failed deploy — remove it so the name is free again.",
        notes="Failed-deploy cleanup diagnostic resolved by removing the container.",
    ),
    Scenario(
        id="postgresql-status-eval-0001",
        tool="postgresql",
        operation="status",
        permission_class=_pc("postgresql", "status"),
        complexity="single",
        user_input="Is the postgresql service currently running?",
        notes="DB service status check.",
    ),
    Scenario(
        id="postgresql-dropdb-eval-0002",
        tool="postgresql",
        operation="dropdb",
        permission_class=_pc("postgresql", "dropdb"),
        complexity="diagnostic",
        user_input="The analytics team says the reporting_sandbox database was a one-off experiment and can be dropped now.",
        notes="Confirmed-experiment diagnostic resolved by dropping the DB.",
    ),
    Scenario(
        id="processes-list-eval-0001",
        tool="processes",
        operation="list",
        permission_class=_pc("processes", "list"),
        complexity="single",
        user_input="Show me every process owned by the deploy user.",
        notes="Per-user process listing.",
    ),
    Scenario(
        id="processes-signal-eval-0002",
        tool="processes",
        operation="signal",
        permission_class=_pc("processes", "signal"),
        complexity="diagnostic",
        user_input="PID 9931 has been pegged at 100% CPU and unresponsive for ten minutes — kill it.",
        notes="Hung-process diagnostic resolved by sending a kill signal.",
    ),
    Scenario(
        id="quota-repquota-eval-0001",
        tool="quota",
        operation="repquota",
        permission_class=_pc("quota", "repquota"),
        complexity="single",
        user_input="Show disk quota usage for all users on /home.",
        notes="Quota report.",
    ),
    Scenario(
        id="quota-quotaon-eval-0002",
        tool="quota",
        operation="quotaon",
        permission_class=_pc("quota", "quotaon"),
        complexity="multi",
        user_input="Turn on quota enforcement for /home and then pull a quota report to confirm it's active.",
        notes="Enable quotas then re-check via report.",
    ),
    Scenario(
        id="restic-snapshots-eval-0001",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("restic", "snapshots"),
        complexity="single",
        user_input="List the restic snapshots in the offsite backup repo.",
        notes="Snapshot listing.",
    ),
    Scenario(
        id="restic-forget_prune-eval-0002",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("restic", "forget_prune"),
        complexity="diagnostic",
        user_input="The backup repo has ballooned past its disk budget — apply our 7-daily/4-weekly retention policy and actually reclaim the space.",
        notes="Repo-size diagnostic resolved by forget+prune.",
    ),
    Scenario(
        id="routing-route_show-eval-0001",
        tool="routing",
        operation="route_show",
        permission_class=_pc("routing", "route_show"),
        complexity="single",
        user_input="Show me the current IP routing table.",
        notes="Routing table read.",
    ),
    Scenario(
        id="routing-route_flush-eval-0002",
        tool="routing",
        operation="route_flush",
        permission_class=_pc("routing", "route_flush"),
        complexity="diagnostic",
        user_input="There are a bunch of stale routes left over from a VPN test that are now breaking outbound traffic — clear the routing table.",
        notes="Broken-routing diagnostic resolved by flushing routes.",
    ),
    Scenario(
        id="rpm-query_info-eval-0001",
        tool="rpm",
        operation="query_info",
        permission_class=_pc("rpm", "query_info"),
        complexity="single",
        user_input="What version of openssl is installed according to rpm?",
        notes="Package metadata query.",
    ),
    Scenario(
        id="rpm-install-eval-0002",
        tool="rpm",
        operation="install",
        permission_class=_pc("rpm", "install"),
        complexity="multi",
        user_input="Install the RPM at /tmp/vendor-agent-2.3.rpm and then query it back to confirm the version that landed.",
        notes="Install then verify via query.",
    ),
    Scenario(
        id="rsync-dry-run-eval-0001",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("rsync", "dry-run"),
        complexity="single",
        user_input="Do a dry run of syncing /data/exports to backup-host:/data/exports so I can see what would change.",
        notes="Preview sync without transferring.",
    ),
    Scenario(
        id="rsync-sync-delete-eval-0002",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("rsync", "sync-delete"),
        complexity="diagnostic",
        user_input="The mirror at backup-host has accumulated files that were deleted from the source weeks ago — sync it with delete so it matches exactly.",
        notes="Drift diagnostic resolved by a delete-sync.",
    ),
    Scenario(
        id="samba-smbd_status-eval-0001",
        tool="samba",
        operation="smbd_status",
        permission_class=_pc("samba", "smbd_status"),
        complexity="single",
        user_input="Is the smbd service healthy right now?",
        notes="Samba daemon status check.",
    ),
    Scenario(
        id="samba-smbpasswd_delete-eval-0002",
        tool="samba",
        operation="smbpasswd_delete",
        permission_class=_pc("samba", "smbpasswd_delete"),
        complexity="diagnostic",
        user_input="The contractor account cbrooks left the company yesterday — remove their Samba password entry.",
        notes="Offboarding diagnostic resolved by deleting the smbpasswd entry.",
    ),
    Scenario(
        id="selinux-getenforce-eval-0001",
        tool="selinux",
        operation="getenforce",
        permission_class=_pc("selinux", "getenforce"),
        complexity="single",
        user_input="What SELinux mode is this host running in?",
        notes="Enforcement mode read.",
    ),
    Scenario(
        id="selinux-setenforce-eval-0002",
        tool="selinux",
        operation="setenforce",
        permission_class=_pc("selinux", "setenforce"),
        complexity="multi",
        user_input="Switch this host to permissive mode temporarily and then confirm the mode actually changed.",
        notes="Set mode then re-check via getenforce.",
    ),
    Scenario(
        id="services-status-eval-0001",
        tool="services",
        operation="status",
        permission_class=_pc("services", "status"),
        complexity="single",
        user_input="Is the sshd.service active right now?",
        notes="Service status check.",
    ),
    Scenario(
        id="services-restart-eval-0002",
        tool="services",
        operation="restart",
        permission_class=_pc("services", "restart"),
        complexity="multi",
        user_input="Restart the redis service and then check its status to make sure it came back up clean.",
        notes="Restart then re-verify status.",
    ),
    Scenario(
        id="sosreport-info-eval-0001",
        tool="sosreport",
        operation="info",
        permission_class=_pc("sosreport", "info"),
        complexity="single",
        user_input="What sos plugins are available for collecting diagnostics on this host?",
        notes="Plugin inventory read.",
    ),
    Scenario(
        id="sosreport-generate-eval-0002",
        tool="sosreport",
        operation="generate",
        permission_class=_pc("sosreport", "generate"),
        complexity="multi",
        user_input="Generate an sos report scoped to the networking and selinux plugins, and tell me where the archive lands.",
        notes="Generate report then report output location.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_list-eval-0001",
        tool="ssh_keys",
        operation="authorized_keys_list",
        permission_class=_pc("ssh_keys", "authorized_keys_list"),
        complexity="single",
        user_input="What keys are in root's authorized_keys file?",
        notes="authorized_keys inventory.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_remove-eval-0002",
        tool="ssh_keys",
        operation="authorized_keys_remove",
        permission_class=_pc("ssh_keys", "authorized_keys_remove"),
        complexity="diagnostic",
        user_input="A former contractor's SSH key is still in the deploy user's authorized_keys — pull it out.",
        notes="Offboarding diagnostic resolved by removing a specific key.",
    ),
    Scenario(
        id="sssd-status-eval-0001",
        tool="sssd",
        operation="status",
        permission_class=_pc("sssd", "status"),
        complexity="single",
        user_input="Is the sssd service running and healthy?",
        notes="SSSD service status check.",
    ),
    Scenario(
        id="sssd-realm_leave-eval-0002",
        tool="sssd",
        operation="realm_leave",
        permission_class=_pc("sssd", "realm_leave"),
        complexity="diagnostic",
        user_input="This host is being decommissioned from the domain — take it out of the AD realm before we shut it down.",
        notes="Decommission diagnostic resolved by leaving the realm.",
    ),
    Scenario(
        id="stratis-pool-list-eval-0001",
        tool="stratis",
        operation="pool-list",
        permission_class=_pc("stratis", "pool-list"),
        complexity="single",
        user_input="List the Stratis storage pools on this host.",
        notes="Pool inventory.",
    ),
    Scenario(
        id="stratis-pool-destroy-eval-0002",
        tool="stratis",
        operation="pool-destroy",
        permission_class=_pc("stratis", "pool-destroy"),
        complexity="diagnostic",
        user_input="The scratch Stratis pool from last quarter's load test is confirmed unused — tear it down.",
        notes="Confirmed-unused diagnostic resolved by destroying the pool.",
    ),
    Scenario(
        id="subscription-status-eval-0001",
        tool="subscription",
        operation="status",
        permission_class=_pc("subscription", "status"),
        complexity="single",
        user_input="Is this host currently registered with Red Hat subscription management?",
        notes="Registration status check.",
    ),
    Scenario(
        id="subscription-unregister-eval-0002",
        tool="subscription",
        operation="unregister",
        permission_class=_pc("subscription", "unregister"),
        complexity="diagnostic",
        user_input="We're retiring this VM and it needs to be unregistered from RHSM before the license seat is reclaimed.",
        notes="Decommission diagnostic resolved by unregistering.",
    ),
    Scenario(
        id="sysctl-get-eval-0001",
        tool="sysctl",
        operation="get",
        permission_class=_pc("sysctl", "get"),
        complexity="single",
        user_input="What's the current value of net.ipv4.ip_forward?",
        notes="Single-parameter read.",
    ),
    Scenario(
        id="sysctl-set-eval-0002",
        tool="sysctl",
        operation="set",
        permission_class=_pc("sysctl", "set"),
        complexity="multi",
        user_input="Bump vm.swappiness down to 10 and persist it so it survives a reboot.",
        notes="Set and persist a kernel parameter.",
    ),
    Scenario(
        id="systemd_timers-list-timers-eval-0001",
        tool="systemd_timers",
        operation="list-timers",
        permission_class=_pc("systemd_timers", "list-timers"),
        complexity="single",
        user_input="What systemd timers are currently scheduled on this host?",
        notes="Timer inventory.",
    ),
    Scenario(
        id="systemd_timers-create-eval-0002",
        tool="systemd_timers",
        operation="create",
        permission_class=_pc("systemd_timers", "create"),
        complexity="multi",
        user_input="Create a timer that runs the log-rotation unit every night at 1am and then enable it so it survives reboot.",
        notes="Create timer then enable it.",
    ),
    Scenario(
        id="tar-list-eval-0001",
        tool="tar",
        operation="list",
        permission_class=_pc("tar", "list"),
        complexity="single",
        user_input="What files are inside /backups/app-2026-09-01.tar.gz without extracting it?",
        notes="Archive contents listing.",
    ),
    Scenario(
        id="tar-extract-eval-0002",
        tool="tar",
        operation="extract",
        permission_class=_pc("tar", "extract"),
        complexity="diagnostic",
        user_input="We need to recover a config file that only exists in last week's tar backup — extract that archive somewhere safe so we can pull it out.",
        notes="Recovery diagnostic resolved by extracting an archive.",
    ),
    Scenario(
        id="tuned-active-eval-0001",
        tool="tuned",
        operation="active",
        permission_class=_pc("tuned", "active"),
        complexity="single",
        user_input="Which tuned profile is currently active?",
        notes="Active profile read.",
    ),
    Scenario(
        id="tuned-profile-eval-0002",
        tool="tuned",
        operation="profile",
        permission_class=_pc("tuned", "profile"),
        complexity="multi",
        user_input="Switch this database host over to the throughput-performance tuned profile and confirm it's active afterward.",
        notes="Switch profile then re-check active profile.",
    ),
    Scenario(
        id="users-list-eval-0001",
        tool="users",
        operation="list",
        permission_class=_pc("users", "list"),
        complexity="single",
        user_input="List every local user account on this system.",
        notes="Local account inventory.",
    ),
    Scenario(
        id="users-lock-eval-0002",
        tool="users",
        operation="lock",
        permission_class=_pc("users", "lock"),
        complexity="diagnostic",
        user_input="We suspect the account tsmith was compromised in last night's phishing attempt — lock it immediately.",
        notes="Suspected-compromise diagnostic resolved by locking the account.",
    ),
    Scenario(
        id="virsh-list-eval-0001",
        tool="virsh",
        operation="list",
        permission_class=_pc("virsh", "list"),
        complexity="single",
        user_input="What VMs are currently running under libvirt?",
        notes="VM inventory.",
    ),
    Scenario(
        id="virsh-destroy-eval-0002",
        tool="virsh",
        operation="destroy",
        permission_class=_pc("virsh", "destroy"),
        complexity="diagnostic",
        user_input="The vm named legacy-test01 is stuck and not responding to a graceful shutdown request — force it off.",
        notes="Unresponsive-VM diagnostic resolved by force-destroying it.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity / acceptance assertions at import time.
# ---------------------------------------------------------------------------

assert len(EVAL_SCENARIOS) == 110, (
    f"EVAL_SCENARIOS must contain exactly 110 entries; got {len(EVAL_SCENARIOS)}."
)

_ids = [_s.id for _s in EVAL_SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected in EVAL_SCENARIOS"

_tool_counts: dict[str, int] = {}
for _s in EVAL_SCENARIOS:
    _tool_counts[_s.tool] = _tool_counts.get(_s.tool, 0) + 1

for _t in TOOL_NAMES:
    assert _tool_counts.get(_t, 0) == 2, (
        f"Tool {_t!r} must appear exactly twice in EVAL_SCENARIOS; "
        f"got {_tool_counts.get(_t, 0)}."
    )
assert set(_tool_counts.keys()) == set(TOOL_NAMES), (
    "EVAL_SCENARIOS references tools outside the live TOOL_NAMES registry: "
    f"{set(_tool_counts.keys()) - set(TOOL_NAMES)}"
)

for _s in EVAL_SCENARIOS:
    assert registry.get(_s.tool).permission_class_for(_s.operation) is not None, (
        f"{_s.id}: operation {_s.operation!r} is not a valid operation of "
        f"tool {_s.tool!r} in the live registry."
    )
    assert _s.permission_class == registry.get(_s.tool).permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

# Held-out novelty check: no eval user_input may appear verbatim (case-insensitive,
# stripped) among the TRAINING corpus's user_inputs.  This is a one-way import
# (finetune.scenarios -> here); finetune/scenarios/__init__.py must never import
# this module back.
from finetune.scenarios import ALL_SCENARIOS  # noqa: E402

_train_inputs_norm: frozenset[str] = frozenset(
    s.user_input.strip().lower() for s in ALL_SCENARIOS
)
for _s in EVAL_SCENARIOS:
    assert _s.user_input.strip().lower() not in _train_inputs_norm, (
        f"{_s.id}: user_input duplicates a TRAINING scenario verbatim — "
        "the eval pool must be held out. Rephrase it."
    )
