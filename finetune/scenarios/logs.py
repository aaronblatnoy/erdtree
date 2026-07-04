"""finetune/scenarios/logs.py — Scenario corpus for the 'logs' tool.

Operations and their declared permission classes are derived LIVE from the
registry via finetune.coreimports (INV-schema-sync).  Nothing here is
hardcoded; if core/tools/logs.py adds or renames an operation the
_PCLASS lookup will surface any mismatch at import time.

All logs operations are OpClass.READ (the tool only reads existing log data).

Complexity legend
-----------------
single     — one straightforward read, plausible in < 10 s of typing.
multi      — operator has multiple context clues or is doing a mini
             investigation spanning one tool call.
diagnostic — deep diagnostic or cross-cutting question that requires
             correlating several facets (time range + unit + priority,
             boot forensics, kernel + journal, security audit, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Core seam — derive all permission_class values LIVE (INV-schema-sync).
# ---------------------------------------------------------------------------
from finetune.coreimports import registry, OpClass

# Pull the live logs ToolSpec so permission classes are always in sync.
_LOGS = registry.get("logs")

# Convenience: permission_class keyed by real op name.
_PCLASS: dict[str, OpClass] = {
    op_name: op_spec.permission_class
    for op_name, op_spec in _LOGS.ops.items()
}

# Sanity-check every op we reference below is real.
_EXPECTED_OPS = {"query", "tail", "since", "boot_errors", "dmesg_query", "dmesg_errors"}
_ACTUAL_OPS = set(_PCLASS.keys())
assert _EXPECTED_OPS == _ACTUAL_OPS, (
    f"logs op set mismatch — expected {_EXPECTED_OPS}, got {_ACTUAL_OPS}. "
    "Update this module to match core/tools/logs.py."
)


# ---------------------------------------------------------------------------
# Scenario dataclass (field names are EXACT; the JOIN will unify these).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Scenario:
    """A single training scenario for the fine-tuning corpus.

    Fields
    ------
    id              Unique string, prefixed with the tool name.
    tool            Always 'logs' in this module.
    operation       A real op name as declared in registry.get('logs').ops.
    permission_class  The op's declared OpClass (always READ for logs).
    complexity      'single' | 'multi' | 'diagnostic'.
    user_input      Natural English an operator would type at the terminal.
    notes           Short rationale / coverage annotation.
    """

    id: str
    tool: str
    operation: str
    permission_class: OpClass
    complexity: Literal["single", "multi", "diagnostic"]
    user_input: str
    notes: str


# ---------------------------------------------------------------------------
# Corpus — >= 60 scenarios across all 6 operations and 3 complexities.
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # Operation: query  (12 entries)
    # =========================================================================

    Scenario(
        id="logs-query-0001",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="single",
        user_input="show me the last 50 lines from the nginx logs",
        notes="Simple unit-filtered query with an explicit line count.",
    ),
    Scenario(
        id="logs-query-0002",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="single",
        user_input="show journal entries for sshd",
        notes="Unit filter only, no time/priority constraints.",
    ),
    Scenario(
        id="logs-query-0003",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="single",
        user_input="get all error-level log entries",
        notes="Priority filter at 'err', no unit restriction.",
    ),
    Scenario(
        id="logs-query-0004",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="single",
        user_input="search the journal for 'connection refused'",
        notes="Grep filter on a common failure pattern.",
    ),
    Scenario(
        id="logs-query-0005",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="single",
        user_input="show me postgresql logs from the last 2 hours",
        notes="Unit + since time range, simple form.",
    ),
    Scenario(
        id="logs-query-0006",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="multi",
        user_input="show warning and higher messages for firewalld since yesterday",
        notes="Priority + since + unit combination covering firewall investigation.",
    ),
    Scenario(
        id="logs-query-0007",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="multi",
        user_input="find all authentication failures in the journal from the past 24 hours",
        notes="Grep for auth failure patterns with since filter — security scenario.",
    ),
    Scenario(
        id="logs-query-0008",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="multi",
        user_input="show me errors from the kernel between midnight and 6am today",
        notes="Time-bounded query with priority filter; diagnostic window investigation.",
    ),
    Scenario(
        id="logs-query-0009",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="diagnostic",
        user_input="pull all critical and above log entries for httpd, postgresql, and redis since the deployment at 03:00 this morning",
        notes="Multi-service investigation — ops would combine into sequential calls.",
    ),
    Scenario(
        id="logs-query-0010",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="diagnostic",
        user_input="the database keeps disconnecting around 2am — show me all errors from postgresql between 01:45 and 02:15 for the past week",
        notes="Recurring failure window investigation; time window + priority + unit.",
    ),
    Scenario(
        id="logs-query-0011",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="diagnostic",
        user_input="we had an outage at 14:30 yesterday. show me every error from all services between 14:00 and 15:00",
        notes="Post-incident time-window forensics, priority=err, broad scope.",
    ),
    Scenario(
        id="logs-query-0012",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="single",
        user_input="show me the last 200 entries from the cron syslog identifier",
        notes="Syslog identifier filter (-t) for cron job log inspection.",
    ),

    # =========================================================================
    # Operation: tail  (11 entries)
    # =========================================================================

    Scenario(
        id="logs-tail-0001",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="single",
        user_input="show the most recent log entries",
        notes="Plain tail with no filters — quick sanity check.",
    ),
    Scenario(
        id="logs-tail-0002",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="single",
        user_input="tail the last 100 lines of the system journal",
        notes="Explicit line count, no unit filter.",
    ),
    Scenario(
        id="logs-tail-0003",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="single",
        user_input="show me the latest nginx log entries",
        notes="Unit-filtered tail for a web server.",
    ),
    Scenario(
        id="logs-tail-0004",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="single",
        user_input="give me the last 25 lines from sshd",
        notes="Small tail to check recent SSH activity.",
    ),
    Scenario(
        id="logs-tail-0005",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="single",
        user_input="what are the most recent journal entries for the docker service?",
        notes="Conversational tail request for containerized workload.",
    ),
    Scenario(
        id="logs-tail-0006",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="multi",
        user_input="the web server just went down — show me the last 200 lines from httpd",
        notes="Reactive tail after an incident to see the final log entries before failure.",
    ),
    Scenario(
        id="logs-tail-0007",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="multi",
        user_input="a cron job ran 10 minutes ago. show me the last 50 log lines to see if it completed cleanly",
        notes="Post-job verification using tail as a recency probe.",
    ),
    Scenario(
        id="logs-tail-0008",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="multi",
        user_input="after that restart give me the latest 150 entries from systemd to see what came back up",
        notes="Post-restart sanity check — tail used as a brief timeline.",
    ),
    Scenario(
        id="logs-tail-0009",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="diagnostic",
        user_input="something is flooding the logs — show me the most recent 500 lines so I can see what's spamming",
        notes="High-volume log flood investigation; large line count.",
    ),
    Scenario(
        id="logs-tail-0010",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="diagnostic",
        user_input="the monitoring system triggered an alert. tail the last 300 lines from rsyslog to see what caused it",
        notes="Alert-driven tail; diagnostic starting point before targeted query.",
    ),
    Scenario(
        id="logs-tail-0011",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="single",
        user_input="show me the latest entries from auditd",
        notes="Tail of the Linux audit daemon — security-hardening context.",
    ),

    # =========================================================================
    # Operation: since  (12 entries)
    # =========================================================================

    Scenario(
        id="logs-since-0001",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="single",
        user_input="show me logs from the last hour",
        notes="Simple recency window, no unit or line cap.",
    ),
    Scenario(
        id="logs-since-0002",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="single",
        user_input="show all journal entries since yesterday",
        notes="'yesterday' time expression — covers rolling 24h window.",
    ),
    Scenario(
        id="logs-since-0003",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="single",
        user_input="pull journal logs since 2026-07-01 08:00:00",
        notes="Absolute timestamp — change-management window review.",
    ),
    Scenario(
        id="logs-since-0004",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="single",
        user_input="show me nginx logs since 2 hours ago",
        notes="Unit filter combined with relative time expression.",
    ),
    Scenario(
        id="logs-since-0005",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="single",
        user_input="get logs since the last reboot — 3 hours ago",
        notes="Operator provides relative hint; since='3 hours ago'.",
    ),
    Scenario(
        id="logs-since-0006",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="multi",
        user_input="the deploy went out at 09:30 this morning. show me all postgresql logs since then",
        notes="Post-deploy log review for a specific service.",
    ),
    Scenario(
        id="logs-since-0007",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="multi",
        user_input="show me sshd logs since midnight — I need to see who logged in overnight",
        notes="Security audit for overnight access; since='midnight' or '00:00:00'.",
    ),
    Scenario(
        id="logs-since-0008",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="multi",
        user_input="the application team says they started seeing 503s around 15:45 — give me all httpd logs since 15:30, limit 500 lines",
        notes="Targeted investigation with explicit line cap; multi-detail input.",
    ),
    Scenario(
        id="logs-since-0009",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="diagnostic",
        user_input="we had a security scan run last night at 22:00. pull all journal entries since 21:55 and look for anything suspicious",
        notes="Security posture review around a known event; broad since filter.",
    ),
    Scenario(
        id="logs-since-0010",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="diagnostic",
        user_input="the backup job should have finished at 04:00. show me all backup-related logs since 03:45 — I want to know if it succeeded or failed",
        notes="Backup verification; since + unit (or broad search) for outcome.",
    ),
    Scenario(
        id="logs-since-0011",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="diagnostic",
        user_input="we rolled back the config at 11:20 after a bad deploy. pull everything since 11:00 for httpd and postgresql so I can see the before-and-after",
        notes="Config rollback forensics; multi-service time window.",
    ),
    Scenario(
        id="logs-since-0012",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="single",
        user_input="give me journal entries since 30 minutes ago",
        notes="Short recency window, no unit filter — quick check.",
    ),

    # =========================================================================
    # Operation: boot_errors  (11 entries)
    # =========================================================================

    Scenario(
        id="logs-boot_errors-0001",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="single",
        user_input="show me all errors from the current boot",
        notes="Default boot_errors call — current boot, no args.",
    ),
    Scenario(
        id="logs-boot_errors-0002",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="single",
        user_input="did anything fail during the last reboot?",
        notes="Conversational form; maps to boot_errors with default current boot.",
    ),
    Scenario(
        id="logs-boot_errors-0003",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="single",
        user_input="show me boot errors from the previous boot",
        notes="boot='-1' to inspect the prior boot.",
    ),
    Scenario(
        id="logs-boot_errors-0004",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="single",
        user_input="check for any error messages that showed up during startup",
        notes="Startup error check using boot_errors; single, casual form.",
    ),
    Scenario(
        id="logs-boot_errors-0005",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="multi",
        user_input="the server was rebooted for patching last night. show me all errors from that boot",
        notes="Post-patch boot inspection; maps to boot='-1' (the previous boot).",
    ),
    Scenario(
        id="logs-boot_errors-0006",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="multi",
        user_input="we had an unexpected reboot two boots ago. what errors were logged during that boot?",
        notes="Incident investigation two boots back; boot='-2'.",
    ),
    Scenario(
        id="logs-boot_errors-0007",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="multi",
        user_input="the kernel panicked during the last boot cycle. pull all errors from that boot so I can see what triggered it",
        notes="Kernel panic root cause; boot='-1' with panic context.",
    ),
    Scenario(
        id="logs-boot_errors-0008",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="diagnostic",
        user_input="this server has been rebooting spontaneously twice a week. show me boot errors from the three most recent boots so I can look for a pattern",
        notes="Multi-boot pattern analysis; repeated calls for boot=0, -1, -2.",
    ),
    Scenario(
        id="logs-boot_errors-0009",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="diagnostic",
        user_input="after applying the kernel update there were complaints about slow startup. show me all errors from the current boot and the one before the update",
        notes="Kernel update regression; compare current vs pre-update boot errors.",
    ),
    Scenario(
        id="logs-boot_errors-0010",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="diagnostic",
        user_input="SELinux is denying something on boot. can you pull all errors from the current boot so we can find the AVC?",
        notes="SELinux boot denial investigation — ties into the tool's AVC hint feature.",
    ),
    Scenario(
        id="logs-boot_errors-0011",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="single",
        user_input="show boot-time errors so I can verify the server came up clean after the hardware swap",
        notes="Hardware swap validation; current boot errors.",
    ),

    # =========================================================================
    # Operation: dmesg_query  (12 entries)
    # =========================================================================

    Scenario(
        id="logs-dmesg_query-0001",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="single",
        user_input="show me the kernel ring buffer",
        notes="Plain dmesg_query, no filters — full recent kernel output.",
    ),
    Scenario(
        id="logs-dmesg_query-0002",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="single",
        user_input="check dmesg for disk errors",
        notes="Grep for disk error patterns in the kernel ring buffer.",
    ),
    Scenario(
        id="logs-dmesg_query-0003",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="single",
        user_input="show kernel warning messages",
        notes="level='warn' to surface kernel warnings.",
    ),
    Scenario(
        id="logs-dmesg_query-0004",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="single",
        user_input="look at dmesg for USB device detection messages",
        notes="grep='usb' to see USB-related kernel messages.",
    ),
    Scenario(
        id="logs-dmesg_query-0005",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="single",
        user_input="show me the last 100 lines from dmesg",
        notes="Line count cap on kernel ring buffer.",
    ),
    Scenario(
        id="logs-dmesg_query-0006",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="multi",
        user_input="the NIC keeps dropping — search dmesg for network-related errors",
        notes="Network hardware failure investigation; grep for NIC/eth patterns.",
    ),
    Scenario(
        id="logs-dmesg_query-0007",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="multi",
        user_input="check dmesg for memory errors or ECC corrections since the hardware was last replaced",
        notes="Memory health check; grep='ECC|memory error|EDAC' with optional since.",
    ),
    Scenario(
        id="logs-dmesg_query-0008",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="multi",
        user_input="look for any SCSI or SATA errors in the kernel log",
        notes="Storage layer investigation; grep='scsi|ata' error patterns.",
    ),
    Scenario(
        id="logs-dmesg_query-0009",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="diagnostic",
        user_input="the server was producing kernel oops messages last night. pull dmesg filtered for oops and panic so I can assess the damage",
        notes="Kernel oops/panic forensics; grep='Oops|panic|BUG'.",
    ),
    Scenario(
        id="logs-dmesg_query-0010",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="diagnostic",
        user_input="we suspect a hardware failure on this node. show me kernel errors from dmesg and look for anything about hardware, memory, or disk",
        notes="Broad hardware failure triage; level='err' or multiple greps.",
    ),
    Scenario(
        id="logs-dmesg_query-0011",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="diagnostic",
        user_input="after adding the new GPU the system is unstable. pull all kernel error and warn messages from dmesg to see if there are driver conflicts",
        notes="Hardware driver conflict investigation; level filter + GPU-related grep.",
    ),
    Scenario(
        id="logs-dmesg_query-0012",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="single",
        user_input="look for any SELinux denials in dmesg",
        notes="SELinux AVC check via dmesg; grep='avc:.*denied'.",
    ),

    # =========================================================================
    # Operation: dmesg_errors  (10 entries)
    # =========================================================================

    Scenario(
        id="logs-dmesg_errors-0001",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="single",
        user_input="show me kernel errors from dmesg",
        notes="Plain dmesg_errors call — err/crit/alert/emerg level messages.",
    ),
    Scenario(
        id="logs-dmesg_errors-0002",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="single",
        user_input="are there any critical kernel messages?",
        notes="Conversational form; maps to dmesg_errors for crit/above.",
    ),
    Scenario(
        id="logs-dmesg_errors-0003",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="single",
        user_input="show the last 50 kernel error messages",
        notes="dmesg_errors with an explicit lines cap.",
    ),
    Scenario(
        id="logs-dmesg_errors-0004",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="single",
        user_input="check dmesg for any serious hardware alerts",
        notes="Hardware health check using error-level kernel messages.",
    ),
    Scenario(
        id="logs-dmesg_errors-0005",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="multi",
        user_input="the storage array threw an alert. show me kernel errors to see if it made it into dmesg",
        notes="Alert-driven storage investigation; dmesg_errors as confirmation step.",
    ),
    Scenario(
        id="logs-dmesg_errors-0006",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="multi",
        user_input="the server was sluggish this morning. show me the last 200 kernel error and critical messages to see if the hardware complained",
        notes="Performance triage via kernel error review.",
    ),
    Scenario(
        id="logs-dmesg_errors-0007",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="multi",
        user_input="before we escalate to the hardware vendor, pull all kernel errors and criticals from dmesg so I have the evidence ready",
        notes="Pre-escalation evidence gathering; dmesg_errors as documentation step.",
    ),
    Scenario(
        id="logs-dmesg_errors-0008",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="diagnostic",
        user_input="this node has been dropping out of the cluster every few days. pull all kernel error and critical messages so I can look for a recurring pattern",
        notes="Cluster instability root cause; large lines cap for pattern analysis.",
    ),
    Scenario(
        id="logs-dmesg_errors-0009",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="diagnostic",
        user_input="the system RAID is reporting faults. show me all kernel errors — I need to see if this is a disk failure, a controller failure, or a cable issue",
        notes="RAID fault triage; dmesg_errors as first step in hardware failure tree.",
    ),
    Scenario(
        id="logs-dmesg_errors-0010",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="diagnostic",
        user_input="we're hitting kernel panics under load. dump all kernel error-level and above messages so we can start identifying the call stack",
        notes="Kernel panic investigation; dmesg_errors as evidence collection.",
    ),

    # =========================================================================
    # Bonus entries (security hardening & log audit scenarios — all READ ops)
    # =========================================================================

    Scenario(
        id="logs-query-0013",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="diagnostic",
        user_input="audit all sudo invocations in the past 7 days — show me the full journal entries for sudo",
        notes="Security hardening: privilege escalation audit via sudo syslog id.",
    ),
    Scenario(
        id="logs-query-0014",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="diagnostic",
        user_input="show me all failed login attempts to this server in the past 48 hours",
        notes="Security hardening: brute-force detection via sshd logs with grep.",
    ),
    Scenario(
        id="logs-since-0013",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="diagnostic",
        user_input="we ran a CIS benchmark scan at 10:00. pull all journal entries since 09:55 so I can correlate what it touched",
        notes="Security audit correlation; since + broad scope for compliance scan.",
    ),
    Scenario(
        id="logs-boot_errors-0012",
        tool="logs",
        operation="boot_errors",
        permission_class=_PCLASS["boot_errors"],
        complexity="multi",
        user_input="SELinux was put into enforcing mode last reboot. did it block anything on boot?",
        notes="SELinux enforcing mode verification; boot_errors to surface AVCs.",
    ),
    Scenario(
        id="logs-dmesg_query-0013",
        tool="logs",
        operation="dmesg_query",
        permission_class=_PCLASS["dmesg_query"],
        complexity="multi",
        user_input="check dmesg for any firewall or netfilter messages — I want to see if any packets are being dropped at the kernel level",
        notes="Kernel-level packet filtering investigation; grep for netfilter/iptables.",
    ),
    Scenario(
        id="logs-tail-0012",
        tool="logs",
        operation="tail",
        permission_class=_PCLASS["tail"],
        complexity="multi",
        user_input="a port scan was just run against this host. tail the recent logs so I can see if anything was triggered",
        notes="Reactive security check; tail after a network event.",
    ),
    Scenario(
        id="logs-query-0015",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="single",
        user_input="show me logs from the chronyd time synchronization service",
        notes="NTP/time sync diagnostic; unit=chronyd.",
    ),
    Scenario(
        id="logs-query-0016",
        tool="logs",
        operation="query",
        permission_class=_PCLASS["query"],
        complexity="single",
        user_input="pull the last 100 lines from the NetworkManager service journal",
        notes="Network configuration logs; unit=NetworkManager.",
    ),
    Scenario(
        id="logs-since-0014",
        tool="logs",
        operation="since",
        permission_class=_PCLASS["since"],
        complexity="single",
        user_input="show me everything that happened in the last 15 minutes",
        notes="Very short recency window; rapid triage after an event.",
    ),
    Scenario(
        id="logs-dmesg_errors-0011",
        tool="logs",
        operation="dmesg_errors",
        permission_class=_PCLASS["dmesg_errors"],
        complexity="single",
        user_input="are there any kernel-level errors I should know about?",
        notes="Casual health check; dmesg_errors with default line count.",
    ),
]


# ---------------------------------------------------------------------------
# Validation at import time — catches authoring mistakes immediately.
# ---------------------------------------------------------------------------

_ids = [s.id for s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected in logs.py"

for _s in SCENARIOS:
    assert _s.tool == "logs", f"Scenario {_s.id} has wrong tool: {_s.tool!r}"
    assert _s.operation in _ACTUAL_OPS, (
        f"Scenario {_s.id} references unknown operation {_s.operation!r}. "
        f"Real ops: {_ACTUAL_OPS}"
    )
    assert _s.permission_class == _PCLASS[_s.operation], (
        f"Scenario {_s.id} has wrong permission_class {_s.permission_class!r}; "
        f"registry says {_PCLASS[_s.operation]!r} for op {_s.operation!r}"
    )

assert len(SCENARIOS) >= 60, (
    f"Expected >= 60 scenarios for 'logs', got {len(SCENARIOS)}."
)
