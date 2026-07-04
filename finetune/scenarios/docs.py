"""finetune/scenarios/docs.py — Scenario corpus for the 'docs' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  retrieve  READ  — look up relevant reference passages from the local corpus

Coverage targets
----------------
  >= 60 entries total across the single 'retrieve' operation.
  All three complexities represented: single | multi | diagnostic.
  Query topics span the full sysadmin domain:
    service management, package management, log analysis, network diagnostics,
    firewall rules, user administration, disk health, process management,
    hardware inventory, file operations, security hardening.

INV-schema-sync:  permission_class for each entry is derived from the LIVE
  registry via finetune.coreimports, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass
# Compatible field names are EXACT so the P1 JOIN can unify without renames.
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
# Live permission-class lookup — INV-schema-sync
# ---------------------------------------------------------------------------

def _pc(op: str) -> OpClass:
    """Return the live permission class for a docs operation."""
    return registry.get("docs").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenarios
# All 60+ entries use operation='retrieve' (the only op on the docs tool).
# Complexities:
#   single     — look up one concept, return answer directly
#   multi      — look up docs as a prerequisite step before acting
#   diagnostic — look up docs to understand a symptom or failure
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [
    # ------------------------------------------------------------------
    # SINGLE complexity — direct reference look-ups
    # ------------------------------------------------------------------
    Scenario(
        id="docs-retrieve-0001",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what does the noexec mount option do",
        notes="Filesystem mount flag lookup; READ op, no gate.",
    ),
    Scenario(
        id="docs-retrieve-0002",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do I make a systemd unit restart automatically on failure",
        notes="systemd unit Restart= directive lookup.",
    ),
    Scenario(
        id="docs-retrieve-0003",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what is the syntax for firewall-cmd to add a rich rule",
        notes="firewall-cmd rich rule syntax reference.",
    ),
    Scenario(
        id="docs-retrieve-0004",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do I set file permissions with chmod recursively",
        notes="chmod -R flag documentation.",
    ),
    Scenario(
        id="docs-retrieve-0005",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what journalctl flags show logs since last boot",
        notes="journalctl -b flag lookup.",
    ),
    Scenario(
        id="docs-retrieve-0006",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how does dnf history undo work",
        notes="dnf history undo command reference.",
    ),
    Scenario(
        id="docs-retrieve-0007",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what is the difference between hard and soft ulimits",
        notes="ulimit hard vs soft limit explanation.",
    ),
    Scenario(
        id="docs-retrieve-0008",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what does tcp_keepalive_time control in the kernel",
        notes="kernel sysctl TCP keepalive parameter lookup.",
    ),
    Scenario(
        id="docs-retrieve-0009",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do I check if SELinux is enforcing or permissive",
        notes="SELinux status check command reference.",
    ),
    Scenario(
        id="docs-retrieve-0010",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what does the sticky bit do on a directory",
        notes="Sticky bit filesystem permission explanation.",
    ),
    Scenario(
        id="docs-retrieve-0011",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do I list all open ports on the system",
        notes="ss or netstat command reference for open ports.",
    ),
    Scenario(
        id="docs-retrieve-0012",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what are the fields in /proc/meminfo",
        notes="procfs meminfo field descriptions.",
    ),
    Scenario(
        id="docs-retrieve-0013",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how does lvm thin provisioning work",
        notes="LVM thin provisioning concept reference.",
    ),
    Scenario(
        id="docs-retrieve-0014",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do I create a new user with a specific UID",
        notes="useradd -u flag documentation.",
    ),
    Scenario(
        id="docs-retrieve-0015",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what does the o option do in the ip route add command",
        notes="ip route command options reference.",
    ),
    Scenario(
        id="docs-retrieve-0016",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do tuned profiles affect system performance",
        notes="tuned profile documentation for Rocky Linux.",
    ),
    Scenario(
        id="docs-retrieve-0017",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what sysctl parameter limits the number of open files system-wide",
        notes="fs.file-max sysctl parameter reference.",
    ),
    Scenario(
        id="docs-retrieve-0018",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how does the cgroup v2 memory.high limit work",
        notes="cgroup v2 memory controller documentation.",
    ),
    Scenario(
        id="docs-retrieve-0019",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what is the difference between ExecStart and ExecStartPre in a unit file",
        notes="systemd unit file directive comparison.",
    ),
    Scenario(
        id="docs-retrieve-0020",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do I change the default target in systemd",
        notes="systemd default target / runlevel equivalent reference.",
    ),
    Scenario(
        id="docs-retrieve-0021",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what does the nofail mount option do in fstab",
        notes="fstab nofail option documentation.",
    ),
    Scenario(
        id="docs-retrieve-0022",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do I generate an SSH key pair for a service account",
        notes="ssh-keygen command reference for non-interactive use.",
    ),
    Scenario(
        id="docs-retrieve-0023",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what columns does ps aux show",
        notes="ps aux output column descriptions.",
    ),
    Scenario(
        id="docs-retrieve-0024",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how does the Linux OOM killer choose which process to kill",
        notes="OOM killer selection algorithm documentation.",
    ),
    Scenario(
        id="docs-retrieve-0025",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what is the syntax for adding a sudoers rule",
        notes="sudoers file syntax reference.",
    ),
    Scenario(
        id="docs-retrieve-0026",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do I see which kernel modules are loaded",
        notes="lsmod command reference.",
    ),
    Scenario(
        id="docs-retrieve-0027",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what does the -Z flag do in ls output",
        notes="ls -Z SELinux context display flag reference.",
    ),
    Scenario(
        id="docs-retrieve-0028",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how does dnf module stream switching work",
        notes="dnf module command reference.",
    ),
    Scenario(
        id="docs-retrieve-0029",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="what is the purpose of the /run directory in Linux",
        notes="tmpfs /run filesystem purpose documentation.",
    ),
    Scenario(
        id="docs-retrieve-0030",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="single",
        user_input="how do I view SMART data for a disk",
        notes="smartctl command reference.",
    ),

    # ------------------------------------------------------------------
    # MULTI complexity — look-up as prerequisite step before acting
    # ------------------------------------------------------------------
    Scenario(
        id="docs-retrieve-0031",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="before I change the postgresql port, look up how postgresql handles port configuration in its config file",
        notes="Pre-action doc look-up for postgresql.conf port setting.",
    ),
    Scenario(
        id="docs-retrieve-0032",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="look up the correct dnf command to lock a package to its current version before I update everything else",
        notes="dnf versionlock plugin reference, precedes a package update.",
    ),
    Scenario(
        id="docs-retrieve-0033",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="what firewall-cmd options do I need before I open port 5432 only to a specific subnet",
        notes="firewall-cmd --add-rich-rule source lookup before applying.",
    ),
    Scenario(
        id="docs-retrieve-0034",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="look up what PAM account module controls password expiry before I disable it for service accounts",
        notes="PAM pam_unix account module docs, precedes user policy change.",
    ),
    Scenario(
        id="docs-retrieve-0035",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="find the journalctl flags to export logs as JSON before I pipe them into a script",
        notes="journalctl --output=json flag lookup, precedes log processing.",
    ),
    Scenario(
        id="docs-retrieve-0036",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="look up how to mount a tmpfs with a size limit before I add it to fstab",
        notes="tmpfs size= mount option reference, precedes fstab edit.",
    ),
    Scenario(
        id="docs-retrieve-0037",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="what ss filter syntax should I use to list only established TCP connections before I check for suspicious activity",
        notes="ss state filter syntax lookup, precedes network investigation.",
    ),
    Scenario(
        id="docs-retrieve-0038",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="look up the rsync flags for preserving permissions and doing a dry run before I sync the backup",
        notes="rsync -n --archive flag lookup, precedes backup operation.",
    ),
    Scenario(
        id="docs-retrieve-0039",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="find the correct chcon or restorecon command before I fix SELinux context on the nginx docroot",
        notes="SELinux context restore command lookup, precedes fix.",
    ),
    Scenario(
        id="docs-retrieve-0040",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="what lvcreate flags do I need to snapshot an existing logical volume before I resize it",
        notes="lvcreate -s snapshot flag reference, precedes LV resize.",
    ),
    Scenario(
        id="docs-retrieve-0041",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="look up how systemd drop-in files work before I override a vendor unit without editing it directly",
        notes="systemd .d override directory pattern, precedes unit customization.",
    ),
    Scenario(
        id="docs-retrieve-0042",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="find the correct sysctl key to increase the maximum number of inotify watches before I bump it",
        notes="fs.inotify.max_user_watches lookup, precedes sysctl write.",
    ),
    Scenario(
        id="docs-retrieve-0043",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="look up the correct useradd flags for creating a system account with no login shell before I add the prometheus user",
        notes="useradd -r -s /sbin/nologin flags, precedes user creation.",
    ),
    Scenario(
        id="docs-retrieve-0044",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="what ip route flush syntax should I use before I re-apply a routing table from scratch",
        notes="ip route flush table lookup, precedes routing reconfiguration.",
    ),
    Scenario(
        id="docs-retrieve-0045",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="look up how rpm -V works before I verify the integrity of installed packages",
        notes="rpm --verify flag reference, precedes package integrity check.",
    ),
    Scenario(
        id="docs-retrieve-0046",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="find the correct audit.rules syntax for auditing writes to /etc/passwd before I add the rule",
        notes="auditctl -w file watch rule syntax, precedes audit rule addition.",
    ),
    Scenario(
        id="docs-retrieve-0047",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="look up how to configure logrotate to compress and keep 14 days of nginx logs before I write the config",
        notes="logrotate directive reference, precedes config authoring.",
    ),
    Scenario(
        id="docs-retrieve-0048",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="find the correct lsblk columns to display filesystem type and mount point before I map out all disks",
        notes="lsblk -o column selector reference, precedes disk inventory.",
    ),
    Scenario(
        id="docs-retrieve-0049",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="look up what crontab fields represent before I schedule a weekly database backup",
        notes="cron field reference, precedes crontab entry.",
    ),
    Scenario(
        id="docs-retrieve-0050",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="multi",
        user_input="what is the correct nmcli command to set a static IP before I apply it to the primary interface",
        notes="nmcli connection modify reference, precedes network config change.",
    ),

    # ------------------------------------------------------------------
    # DIAGNOSTIC complexity — look-up to understand a symptom or failure
    # ------------------------------------------------------------------
    Scenario(
        id="docs-retrieve-0051",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="nginx won't start and SELinux is blocking it — look up what SELinux boolean controls httpd network connections",
        notes="SELinux httpd_can_network_connect boolean reference for diagnosis.",
    ),
    Scenario(
        id="docs-retrieve-0052",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="the system is running out of file descriptors — look up which /proc or sysctl entry shows the current open file count",
        notes="/proc/sys/fs/file-nr or fs.file-max diagnostic reference.",
    ),
    Scenario(
        id="docs-retrieve-0053",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="a service is failing with exit code 203 — what does that mean in systemd",
        notes="systemd exit code 203 (EXEC) documentation for failure diagnosis.",
    ),
    Scenario(
        id="docs-retrieve-0054",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="disk writes are very slow — look up what iostat columns indicate write saturation",
        notes="iostat %util and await column meanings for I/O diagnosis.",
    ),
    Scenario(
        id="docs-retrieve-0055",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="ssh connections are hanging at 'pledge' — look up what that means in sshd",
        notes="sshd pledge sandbox failure diagnostic reference.",
    ),
    Scenario(
        id="docs-retrieve-0056",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="the kernel log shows soft lockup on CPU 0 — look up what causes that",
        notes="soft lockup / RCU stall kernel message diagnostic reference.",
    ),
    Scenario(
        id="docs-retrieve-0057",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="dnf update is failing with a GPG check error — look up how to verify and re-import a repo key",
        notes="dnf GPG key import and verification reference for diagnosis.",
    ),
    Scenario(
        id="docs-retrieve-0058",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="a user cannot log in and /var/log/secure shows pam_unix authentication failure — look up which PAM module is responsible",
        notes="PAM pam_unix authentication failure log reference.",
    ),
    Scenario(
        id="docs-retrieve-0059",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="the system rebooted unexpectedly — look up how to check the last kernel crash reason in journalctl",
        notes="journalctl -k previous boot crash log diagnostic reference.",
    ),
    Scenario(
        id="docs-retrieve-0060",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="a container cannot reach the host network — look up which bridge netfilter sysctl controls that",
        notes="net.bridge.bridge-nf-call-iptables sysctl diagnostic reference.",
    ),
    Scenario(
        id="docs-retrieve-0061",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="df shows the filesystem is full but du shows only half the space used — look up what deleted-but-open files do to disk usage",
        notes="deleted files held open by processes causing phantom disk usage reference.",
    ),
    Scenario(
        id="docs-retrieve-0062",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="firewall-cmd --list-all shows the rule is there but traffic is still blocked — look up how runtime vs permanent zones differ",
        notes="firewall-cmd runtime vs permanent config discrepancy diagnostic.",
    ),
    Scenario(
        id="docs-retrieve-0063",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="a process is stuck in D state — look up what uninterruptible sleep means and how to investigate it",
        notes="D-state (TASK_UNINTERRUPTIBLE) diagnosis reference.",
    ),
    Scenario(
        id="docs-retrieve-0064",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="sshd log shows 'too many authentication failures' — look up the MaxAuthTries sshd_config option",
        notes="sshd_config MaxAuthTries parameter diagnostic reference.",
    ),
    Scenario(
        id="docs-retrieve-0065",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="nfs mounts are hanging after a network blip — look up the hard vs soft nfs mount option behaviour",
        notes="NFS hard vs soft mount option documentation for hang diagnosis.",
    ),
    Scenario(
        id="docs-retrieve-0066",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="tcp connections to port 443 are being reset immediately — look up what nf_conntrack_max controls and how to check if it is full",
        notes="nf_conntrack_max and conntrack table overflow diagnostic reference.",
    ),
    Scenario(
        id="docs-retrieve-0067",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="a package install fails with 'scriptlet failed' — look up how to get the full scriptlet output from dnf",
        notes="dnf --verbose scriptlet failure diagnostic reference.",
    ),
    Scenario(
        id="docs-retrieve-0068",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="the system is swapping heavily but free memory is not zero — look up what swappiness controls and what value suits a database host",
        notes="vm.swappiness sysctl reference for database server tuning diagnosis.",
    ),
    Scenario(
        id="docs-retrieve-0069",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="inotify watch limit is being hit by a file-sync service — look up how to verify the current limit and raise it",
        notes="fs.inotify.max_user_watches diagnostic and fix reference.",
    ),
    Scenario(
        id="docs-retrieve-0070",
        tool="docs",
        operation="retrieve",
        permission_class=_pc("retrieve"),
        complexity="diagnostic",
        user_input="audit logs show avc denied for httpd reading /var/www — look up what restorecon does and when to use it",
        notes="restorecon vs chcon for AVC denial fix diagnostic reference.",
    ),
]
