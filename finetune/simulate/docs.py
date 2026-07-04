"""finetune/simulate/docs.py — Rocky Linux 9 output simulator for the 'docs' tool.

Public API
----------
simulate_docs(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the real operations declared in core/tools/docs.py
           (currently: "retrieve")
    args : dict of op arguments (may be {} for ops with all-optional args;
           "query" is required for retrieve but defaults to "" when absent
           so the validator smoke-path can call simulate_docs("retrieve", {}, ctx))
    ctx  : system context string produced by finetune.context.make_context(),
           OR a profile dict. Not used for retrieval outputs (corpus is local
           and independent of host state), but accepted for API consistency.

Realism model
-------------
* The docs tool reads a local sqlite-vec corpus index.  In simulation we
  substitute a curated bank of realistic passage snippets drawn from the
  topics a Linux sysadmin on Rocky 9 / RHEL 9 would actually look up:
  systemctl / systemd, dnf / rpm, journalctl, firewall-cmd, SELinux (semanage/
  restorecon/audit2allow), ip / nmcli, mount / fstab, useradd / passwd,
  df / lsblk / xfs, ss / netstat, cron, rsync, tar, chmod / ACL.

* Query-to-passages mapping is keyword-based (lowercase token matching) so
  that args["query"] drives the output content — satisfying INV-schema-sync
  without hardcoding a schema.

* Exit code is ALWAYS 0.  The real tool degrades gracefully (I9): on a
  missing index or backend it still returns exit_code=0 with empty stdout.
  Failure in the docs tool manifests as zero passages returned, not a
  non-zero exit.

* Passage count is capped at min(k, len(matched_passages)).  "k" defaults
  to 3 when not supplied (mirrors the real default _DEFAULT_K = 3).

* A query with no keyword match simulates an empty-result hit (empty stdout,
  summary "Retrieved 0 reference passages.") — teaching the caller to handle
  no-result gracefully.

I2 compliance
-------------
All `summary` strings use operator language only:
  "Retrieved N reference passages."
No AI/LLM/model/agent/ollama/inference language appears anywhere in this file.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (to avoid circular deps when
simulate/__init__.py imports tool modules before coreimports is fully settled).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Passage bank — curated realistic Linux reference snippets
# ---------------------------------------------------------------------------
# Each entry is (source_label, passage_text).
# Passages intentionally vary in length and style (man-page excerpt, wiki note,
# distro doc snippet) to produce varied stdout blocks.

_PASSAGE_BANK: list[tuple[str, str]] = [
    # -- systemd / systemctl ---------------------------------------------------
    (
        "man:systemctl(1)",
        "systemctl start UNIT...\n"
        "    Start (activate) one or more units specified on the command line.\n"
        "\n"
        "systemctl stop UNIT...\n"
        "    Stop (deactivate) one or more units specified on the command line.\n"
        "\n"
        "systemctl restart UNIT...\n"
        "    Restart one or more units specified on the command line. If the units\n"
        "    are not running yet, they will be started.\n"
        "\n"
        "systemctl status [PATTERN...|PID...]\n"
        "    Show terse runtime status information about one or more units,\n"
        "    followed by most recent journal log data from the unit. If no units\n"
        "    are specified, show system status.",
    ),
    (
        "man:systemctl(1)",
        "systemctl enable UNIT...\n"
        "    Enable one or more units or unit instances as specified on the\n"
        "    command line. This creates a set of symlinks in /etc/systemd/system/\n"
        "    encoding the suggested installation configuration of the unit(s).\n"
        "    Note that this does not start the unit(s).\n"
        "\n"
        "systemctl disable UNIT...\n"
        "    Disables one or more units. This removes all symlinks to the unit\n"
        "    files backing the specified units from the unit configuration\n"
        "    directory, and hence undoes the changes made by enable.",
    ),
    (
        "man:systemd.unit(5)",
        "[Unit]\n"
        "Description=    A human-readable description of the unit.\n"
        "After=          Defines ordering: this unit starts after the listed units.\n"
        "Requires=       Hard dependency — if the required unit fails, this fails too.\n"
        "Wants=          Soft dependency — if the wanted unit fails, this unit still starts.\n"
        "ConditionPathExists= Skip this unit unless the given path exists.\n"
        "\n"
        "[Service]\n"
        "Type=           simple | forking | oneshot | notify | dbus\n"
        "ExecStart=      Command to run when the service is started.\n"
        "Restart=        no | on-failure | on-abnormal | always\n"
        "RestartSec=     Time between restarts (seconds or time span).\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target    — most daemon units use this.",
    ),
    # -- dnf / rpm -------------------------------------------------------------
    (
        "man:dnf(8)",
        "dnf install PACKAGE...\n"
        "    Install the specified packages and all of their dependencies.\n"
        "\n"
        "dnf remove PACKAGE...\n"
        "    Remove the specified packages and any packages that depend on them.\n"
        "    Dependencies that were auto-installed and are no longer required are\n"
        "    also removed.\n"
        "\n"
        "dnf update [PACKAGE...]\n"
        "    Update one or all packages to the latest available version. With no\n"
        "    arguments, performs a full system update.\n"
        "\n"
        "dnf search KEYWORD\n"
        "    Search package names and summaries for the given keyword.",
    ),
    (
        "rhel9:package-management",
        "Transaction conflict resolution\n"
        "When dnf reports a conflict, it means two packages require incompatible\n"
        "versions of a dependency. Resolution options:\n"
        "  1. dnf update CONFLICTING_PKG  — update to a version that resolves the conflict.\n"
        "  2. dnf swap OLD_PKG NEW_PKG    — replace one package with another.\n"
        "  3. Use a module stream: dnf module switch-to MODULE:STREAM.\n"
        "\n"
        "To list all packages that provide a given file:\n"
        "  dnf provides /path/to/file\n"
        "\n"
        "To check which package owns a file already installed:\n"
        "  rpm -qf /path/to/file",
    ),
    (
        "man:rpm(8)",
        "rpm -q PACKAGE        Query whether PACKAGE is installed.\n"
        "rpm -qa               List all installed packages.\n"
        "rpm -qi PACKAGE       Display detailed information about PACKAGE.\n"
        "rpm -ql PACKAGE       List files owned by PACKAGE.\n"
        "rpm -qf FILE          Identify the package that owns FILE.\n"
        "rpm -V PACKAGE        Verify the integrity of an installed package.\n"
        "rpm --import KEY      Import a GPG public key for signature verification.",
    ),
    # -- journalctl / logs -----------------------------------------------------
    (
        "man:journalctl(1)",
        "journalctl [OPTIONS...] [MATCHES...]\n"
        "\n"
        "  -u, --unit=UNIT       Show messages from the specified systemd unit.\n"
        "  -f, --follow          Follow the journal in real time (like tail -f).\n"
        "  -n, --lines=N         Show the last N lines (default 10).\n"
        "  -p, --priority=LEVEL  Filter by priority: emerg,alert,crit,err,\n"
        "                        warning,notice,info,debug.\n"
        "  --since=DATE          Show entries since DATE (e.g. '2026-07-01 00:00:00').\n"
        "  --until=DATE          Show entries until DATE.\n"
        "  -b, --boot[=ID]       Show messages from this or a previous boot.\n"
        "  --disk-usage          Show the total disk space used by journal files.\n"
        "  --vacuum-size=BYTES   Reduce journal to at most BYTES on disk.",
    ),
    (
        "man:journalctl(1)",
        "Matching by field:\n"
        "  journalctl _SYSTEMD_UNIT=nginx.service\n"
        "  journalctl _PID=1234\n"
        "  journalctl _UID=0\n"
        "  journalctl SYSLOG_IDENTIFIER=sshd\n"
        "\n"
        "Combining matches: separate multiple matches with '+' (OR) or space (AND).\n"
        "\n"
        "Output formats:\n"
        "  -o short         (default) Human-readable, one line per entry.\n"
        "  -o json          Machine-parseable JSON, one entry per line.\n"
        "  -o cat           Message only, no metadata.\n"
        "  -o verbose       All fields, in key=value form.",
    ),
    # -- firewall-cmd ----------------------------------------------------------
    (
        "man:firewall-cmd(1)",
        "firewall-cmd --list-all\n"
        "    List all settings in the current active zone.\n"
        "\n"
        "firewall-cmd --add-service=SERVICE [--permanent]\n"
        "    Allow the named service. --permanent writes to the on-disk\n"
        "    configuration; omitting it applies only to the running configuration.\n"
        "\n"
        "firewall-cmd --add-port=PORT/PROTOCOL [--permanent]\n"
        "    Open a specific port (e.g. --add-port=8080/tcp).\n"
        "\n"
        "firewall-cmd --reload\n"
        "    Reload the firewall rules, applying any --permanent changes.\n"
        "\n"
        "firewall-cmd --remove-service=SERVICE [--permanent]\n"
        "    Revoke access for the named service.",
    ),
    (
        "rhel9:firewalld",
        "Zones in firewalld\n"
        "A zone defines the trust level for a network connection or interface.\n"
        "Common zones:\n"
        "  public   — do not trust other computers; only selected inbound allowed.\n"
        "  trusted  — all network connections accepted.\n"
        "  block    — any incoming connections are rejected.\n"
        "  drop     — any incoming connections are dropped (no response).\n"
        "\n"
        "Assign an interface to a zone:\n"
        "  firewall-cmd --zone=public --change-interface=eth0 --permanent\n"
        "\n"
        "List active zones:\n"
        "  firewall-cmd --get-active-zones",
    ),
    # -- SELinux ---------------------------------------------------------------
    (
        "rhel9:selinux",
        "SELinux status and mode\n"
        "  getenforce        Print the current enforcing mode.\n"
        "  setenforce 1      Switch to Enforcing (temporary, lost on reboot).\n"
        "  setenforce 0      Switch to Permissive (temporary).\n"
        "\n"
        "Check AVC denials:\n"
        "  ausearch -m avc -ts recent | audit2why\n"
        "  audit2allow -a            — generate a policy module from all denials.\n"
        "  audit2allow -a -M mypol   — write to mypol.pp / mypol.te.\n"
        "\n"
        "Restore default file context:\n"
        "  restorecon -Rv /path/to/dir\n"
        "\n"
        "Set a context explicitly:\n"
        "  semanage fcontext -a -t httpd_sys_content_t '/var/www(/.*)?'\n"
        "  restorecon -Rv /var/www",
    ),
    (
        "man:chcon(1)",
        "chcon — change SELinux security context of file(s).\n"
        "\n"
        "  chcon -t TYPE FILE          Change only the type component.\n"
        "  chcon -u USER FILE          Change the user component.\n"
        "  chcon -r ROLE FILE          Change the role component.\n"
        "  chcon -R TYPE DIR           Recursively change TYPE for all files under DIR.\n"
        "  chcon --reference=REF FILE  Copy context from REF to FILE.\n"
        "\n"
        "Note: chcon changes are NOT persistent across relabelling. Use semanage\n"
        "fcontext + restorecon for permanent context assignments.",
    ),
    # -- ip / network ----------------------------------------------------------
    (
        "man:ip(8)",
        "ip address show [DEV]\n"
        "    List all addresses or addresses on a specific interface.\n"
        "\n"
        "ip link show [DEV]\n"
        "    Show link-layer information for all or one interface.\n"
        "\n"
        "ip route show\n"
        "    Print the routing table.\n"
        "\n"
        "ip route add NETWORK via GATEWAY dev DEV\n"
        "    Add a static route.\n"
        "\n"
        "ip -br a\n"
        "    Brief one-line summary of all addresses. Columns: IFNAME STATE ADDR...\n"
        "\n"
        "ip -s link show DEV\n"
        "    Show per-interface RX/TX statistics.",
    ),
    (
        "man:nmcli(1)",
        "nmcli device status\n"
        "    Show the status of all network devices.\n"
        "\n"
        "nmcli connection show\n"
        "    List all connection profiles.\n"
        "\n"
        "nmcli connection up NAME\n"
        "    Activate a connection profile.\n"
        "\n"
        "nmcli connection modify NAME ipv4.addresses ADDR/PREFIX\n"
        "    Change the IPv4 address for a connection profile (takes effect on\n"
        "    next activation).\n"
        "\n"
        "nmcli connection add type ethernet con-name NAME ifname DEV\n"
        "    Create a new ethernet connection profile.",
    ),
    # -- mount / fstab ---------------------------------------------------------
    (
        "man:mount(8)",
        "mount -t TYPE DEVICE MOUNTPOINT\n"
        "    Mount DEVICE of filesystem TYPE at MOUNTPOINT.\n"
        "\n"
        "Common options:\n"
        "  -o ro             Mount read-only.\n"
        "  -o noexec         Disallow execution of binaries on this filesystem.\n"
        "  -o nosuid         Do not honour setuid/setgid bits.\n"
        "  -o nodev          Do not interpret character or block special devices.\n"
        "  -o remount,rw     Remount an already-mounted filesystem read-write.\n"
        "\n"
        "mount -a\n"
        "    Mount all filesystems listed in /etc/fstab that are not yet mounted.\n"
        "\n"
        "umount MOUNTPOINT\n"
        "    Unmount the filesystem. Use -l (lazy) if the device is busy.",
    ),
    (
        "rhel9:storage",
        "/etc/fstab format:\n"
        "  DEVICE  MOUNTPOINT  TYPE  OPTIONS  DUMP  PASS\n"
        "\n"
        "DEVICE: UUID=... preferred over /dev/sdXN for stability.\n"
        "OPTIONS: defaults,nofail  — nofail prevents boot hang if device absent.\n"
        "\n"
        "XFS-specific:\n"
        "  xfs_repair -n /dev/sdb1   — check without modifying (dry run).\n"
        "  xfs_repair /dev/sdb1      — repair (device must be unmounted).\n"
        "  xfs_info MOUNTPOINT       — display XFS filesystem geometry.\n"
        "  xfs_growfs MOUNTPOINT     — expand XFS to fill the underlying block device.",
    ),
    # -- useradd / passwd / users ----------------------------------------------
    (
        "man:useradd(8)",
        "useradd [OPTIONS] LOGIN\n"
        "    Create a new user account.\n"
        "\n"
        "  -m, --create-home     Create the user's home directory.\n"
        "  -s, --shell SHELL     Set the login shell (e.g. /bin/bash).\n"
        "  -G, --groups GROUP... Add the user to supplementary groups.\n"
        "  -u, --uid UID         Assign a specific numeric UID.\n"
        "  -e, --expiredate DATE Set the account expiry date (YYYY-MM-DD).\n"
        "  -r, --system          Create a system account (no home, lower UID range).\n"
        "\n"
        "passwd LOGIN\n"
        "    Set or change the password for LOGIN.\n"
        "\n"
        "usermod -aG GROUP USER\n"
        "    Append USER to GROUP without removing them from other groups.\n"
        "    Note: -a is required with -G; omitting -a replaces the group list.",
    ),
    (
        "man:id(1)",
        "id [USER]\n"
        "    Print the numeric UID, GID, and supplementary groups for USER\n"
        "    (or the current user if USER is omitted).\n"
        "\n"
        "Example output:\n"
        "  uid=1001(alice) gid=1001(alice) groups=1001(alice),10(wheel),992(docker)\n"
        "\n"
        "groups USER\n"
        "    Print the groups USER belongs to (names only).\n"
        "\n"
        "getent passwd USER\n"
        "    Look up USER in /etc/passwd (or LDAP/SSSD if configured).\n"
        "\n"
        "chage -l USER\n"
        "    Show the password expiry information for USER.",
    ),
    # -- disk / df / lsblk -----------------------------------------------------
    (
        "man:df(1)",
        "df [OPTIONS] [FILE...]\n"
        "    Report disk space usage of filesystems.\n"
        "\n"
        "  -h, --human-readable   Print sizes in human-readable form (K, M, G).\n"
        "  -T, --print-type       Include filesystem type in output.\n"
        "  -i, --inodes           Report inode usage rather than block usage.\n"
        "  --total                Produce a grand total line.\n"
        "\n"
        "lsblk\n"
        "    List block devices and their partition structure in a tree.\n"
        "    -f  Include filesystem type and UUID.\n"
        "    -o NAME,SIZE,FSTYPE,MOUNTPOINT  Select specific columns.",
    ),
    # -- processes / ps --------------------------------------------------------
    (
        "man:ps(1)",
        "ps aux\n"
        "    Show all processes (a), including those of other users (u) and\n"
        "    processes not attached to a terminal (x).\n"
        "\n"
        "ps -ef\n"
        "    Full-format listing with PPID. Similar coverage to ps aux.\n"
        "\n"
        "ps -p PID\n"
        "    Show only the process with PID.\n"
        "\n"
        "ps --sort=-%cpu | head -11\n"
        "    Top 10 CPU consumers.\n"
        "\n"
        "kill -SIGNAL PID\n"
        "    Send SIGNAL to PID. Common signals: SIGTERM (15), SIGKILL (9),\n"
        "    SIGHUP (1) for config reload, SIGUSR1/SIGUSR2 for app-specific use.",
    ),
    # -- cron ------------------------------------------------------------------
    (
        "man:crontab(5)",
        "Crontab field order (five time fields, then command):\n"
        "  MINUTE  HOUR  DAY_OF_MONTH  MONTH  DAY_OF_WEEK  COMMAND\n"
        "\n"
        "Ranges and wildcards:\n"
        "  *      any value\n"
        "  */5    every 5 units\n"
        "  1-5    range 1 through 5\n"
        "  1,3,5  list of values\n"
        "\n"
        "Examples:\n"
        "  0 2 * * *   /usr/local/bin/backup.sh    — daily at 02:00\n"
        "  */15 * * * * /usr/local/bin/healthcheck  — every 15 minutes\n"
        "\n"
        "System crontab (/etc/cron.d/) adds a USER field after the time fields.\n"
        "  0 3 * * * root /usr/sbin/logrotate /etc/logrotate.conf",
    ),
    # -- tar / rsync -----------------------------------------------------------
    (
        "man:tar(1)",
        "tar [OPTIONS] [FILE...]\n"
        "\n"
        "Common operation flags (use exactly one):\n"
        "  -c, --create        Create a new archive.\n"
        "  -x, --extract       Extract files from an archive.\n"
        "  -t, --list          List archive contents without extracting.\n"
        "\n"
        "Common modifier flags:\n"
        "  -v, --verbose       List files as they are processed.\n"
        "  -f FILE             Specify the archive file (required).\n"
        "  -z                  Filter through gzip (.tar.gz).\n"
        "  -j                  Filter through bzip2 (.tar.bz2).\n"
        "  -J                  Filter through xz (.tar.xz).\n"
        "  --exclude=PATTERN   Exclude files matching PATTERN.\n"
        "\n"
        "Examples:\n"
        "  tar -czf archive.tar.gz /data    — create compressed archive\n"
        "  tar -xzf archive.tar.gz -C /dst  — extract to /dst",
    ),
    # -- chmod / ACL -----------------------------------------------------------
    (
        "man:chmod(1)",
        "chmod MODE FILE...\n"
        "    Change file permissions.\n"
        "\n"
        "Symbolic mode examples:\n"
        "  chmod u+x FILE      — add execute for owner\n"
        "  chmod go-w FILE     — remove write for group and others\n"
        "  chmod a=r FILE      — set all to read-only\n"
        "\n"
        "Octal mode examples:\n"
        "  chmod 755 FILE      — rwxr-xr-x\n"
        "  chmod 644 FILE      — rw-r--r--\n"
        "  chmod 600 FILE      — rw------- (private key permission)\n"
        "\n"
        "setuid / setgid / sticky:\n"
        "  chmod u+s FILE      — setuid (run as file owner)\n"
        "  chmod g+s DIR       — setgid (new files inherit group)\n"
        "  chmod +t DIR        — sticky bit (only owner can delete files in DIR)",
    ),
    (
        "man:getfacl(1)",
        "POSIX Access Control Lists (ACLs)\n"
        "\n"
        "getfacl FILE        — show ACL entries for FILE.\n"
        "setfacl -m u:USER:rwx FILE   — grant USER rwx access.\n"
        "setfacl -m g:GROUP:rx FILE   — grant GROUP rx access.\n"
        "setfacl -x u:USER FILE       — remove ACL entry for USER.\n"
        "setfacl -b FILE              — remove all ACL entries.\n"
        "setfacl -R -m u:USER:rX DIR  — recursively grant USER read+execute on DIR.\n"
        "\n"
        "Default ACLs (applied to new files created inside a directory):\n"
        "  setfacl -d -m u:USER:rw DIR\n"
        "\n"
        "Filesystem must be mounted with 'acl' option, or use 'acl' in fstab.",
    ),
    # -- ss / socket -----------------------------------------------------------
    (
        "man:ss(8)",
        "ss — socket statistics (modern replacement for netstat).\n"
        "\n"
        "  ss -tuln           — listening TCP and UDP sockets, numeric addresses.\n"
        "  ss -tlnp           — listening TCP with process information.\n"
        "  ss -an             — all sockets, numeric.\n"
        "  ss -s              — summary statistics.\n"
        "  ss -o state established '( dport = :22 or sport = :22 )'\n"
        "                     — established SSH connections.\n"
        "\n"
        "State filters: established, syn-sent, syn-recv, fin-wait-{1,2},\n"
        "               time-wait, close, close-wait, last-ack, listen, closing.\n"
        "\n"
        "Filter by port:   dst :443   src :80   dport = :8080",
    ),
    # -- noexec / mount flags --------------------------------------------------
    (
        "rhel9:storage",
        "noexec mount option\n"
        "The noexec option prevents execution of any binaries on the mounted\n"
        "filesystem. It does NOT prevent interpreted scripts if the interpreter\n"
        "itself is on an executable filesystem (e.g. 'python3 /data/script.py'\n"
        "still works even if /data is noexec).\n"
        "\n"
        "Typical hardening use: mount /tmp, /var/tmp, /dev/shm noexec to limit\n"
        "impact of a file-drop attack.\n"
        "\n"
        "nosuid option: silently ignores setuid/setgid bits on the filesystem.\n"
        "Combined hardening:\n"
        "  /tmp  tmpfs  defaults,nodev,nosuid,noexec  0 0",
    ),
    # -- kernel / sysctl -------------------------------------------------------
    (
        "man:sysctl(8)",
        "sysctl [OPTIONS] [VARIABLE[=VALUE]...]\n"
        "\n"
        "  sysctl -a                   — list all kernel parameters.\n"
        "  sysctl net.ipv4.ip_forward  — read a single parameter.\n"
        "  sysctl -w net.ipv4.ip_forward=1  — set a parameter at runtime.\n"
        "\n"
        "Persistent settings: add to /etc/sysctl.d/99-custom.conf\n"
        "  net.ipv4.ip_forward = 1\n"
        "Apply: sysctl --system\n"
        "\n"
        "Common tuning parameters:\n"
        "  vm.swappiness              — preference for using swap (default 60).\n"
        "  net.core.somaxconn         — maximum listen backlog.\n"
        "  fs.file-max                — system-wide open file descriptor limit.",
    ),
    # -- generic Linux reference -----------------------------------------------
    (
        "arch-wiki:general",
        "Process signal reference:\n"
        "  SIGHUP  (1)  — Hangup / reload configuration.\n"
        "  SIGINT  (2)  — Interrupt from keyboard (Ctrl-C).\n"
        "  SIGQUIT (3)  — Quit from keyboard (Ctrl-\\).\n"
        "  SIGKILL (9)  — Kill (cannot be caught or ignored).\n"
        "  SIGTERM (15) — Termination signal (graceful shutdown, default for kill).\n"
        "  SIGUSR1 (10) — Application-defined.\n"
        "  SIGUSR2 (12) — Application-defined.\n"
        "\n"
        "Use 'kill -l' to list all available signals.\n"
        "Use 'kill -SIGNAL PID' or 'kill -s SIGNAL PID' to send a signal.",
    ),
]

# ---------------------------------------------------------------------------
# Keyword index: map lowercase tokens -> list of passage indices
# ---------------------------------------------------------------------------

_KEYWORD_INDEX: dict[str, list[int]] = {}

_TOPIC_KEYWORDS: list[tuple[list[str], list[int]]] = [
    # systemd / systemctl
    (
        ["systemd", "systemctl", "unit", "service", "start", "stop", "restart",
         "enable", "disable", "mask", "daemon", "boot", "active", "failed",
         "inactive", "loaded", "cgroup"],
        [0, 1, 2],
    ),
    # dnf / rpm / packages
    (
        ["dnf", "rpm", "package", "install", "remove", "update", "upgrade",
         "conflict", "dependency", "repo", "yum", "module", "stream"],
        [3, 4, 5],
    ),
    # journalctl / logs / journal
    (
        ["journalctl", "journal", "log", "logs", "syslog", "boot", "priority",
         "follow", "since", "until", "avc", "audit"],
        [6, 7],
    ),
    # firewall / firewalld / firewall-cmd
    (
        ["firewall", "firewall-cmd", "firewalld", "zone", "port", "service",
         "rule", "rich", "allow", "deny", "reject", "drop", "reload", "permanent"],
        [8, 9],
    ),
    # SELinux
    (
        ["selinux", "semanage", "restorecon", "chcon", "getenforce", "setenforce",
         "permissive", "enforcing", "context", "fcontext", "audit2allow", "avc",
         "denial", "label"],
        [10, 11],
    ),
    # ip / network / nmcli
    (
        ["ip", "network", "interface", "address", "route", "nmcli", "ethernet",
         "connection", "link", "inet", "ipv4", "ipv6", "subnet", "gateway"],
        [12, 13],
    ),
    # mount / fstab / filesystem
    (
        ["mount", "fstab", "umount", "filesystem", "xfs", "ext4", "btrfs",
         "noexec", "nosuid", "nodev", "ro", "rw", "tmpfs", "uuid", "repair",
         "growfs", "storage"],
        [14, 15, 26],
    ),
    # useradd / users / passwd
    (
        ["useradd", "user", "passwd", "password", "usermod", "group", "wheel",
         "uid", "gid", "home", "shell", "expire", "system", "id", "chage"],
        [16, 17],
    ),
    # disk / df / lsblk
    (
        ["disk", "df", "lsblk", "block", "partition", "inode", "space",
         "usage", "free", "size", "filesystem"],
        [18],
    ),
    # processes / ps / kill / signal
    (
        ["process", "ps", "kill", "signal", "pid", "cpu", "memory", "top",
         "htop", "nice", "renice", "sigterm", "sigkill", "sighup"],
        [19, 25],
    ),
    # cron / crontab
    (
        ["cron", "crontab", "schedule", "scheduled", "periodic", "timer",
         "minute", "hour", "daily", "weekly"],
        [20],
    ),
    # tar / rsync / backup / archive
    (
        ["tar", "rsync", "backup", "archive", "compress", "extract", "gzip",
         "bzip2", "xz", "bundle"],
        [21],
    ),
    # chmod / acl / permissions
    (
        ["chmod", "acl", "permission", "setuid", "setgid", "sticky", "rwx",
         "octal", "getfacl", "setfacl", "mode", "executable"],
        [22, 23],
    ),
    # ss / socket / netstat / port
    (
        ["ss", "socket", "netstat", "listen", "established", "tcp", "udp",
         "port", "connection", "state"],
        [24],
    ),
    # sysctl / kernel
    (
        ["sysctl", "kernel", "parameter", "tuning", "swappiness", "ip_forward",
         "somaxconn", "file-max", "proc"],
        [27],
    ),
]

# Build index
for _keywords, _indices in _TOPIC_KEYWORDS:
    for _kw in _keywords:
        if _kw not in _KEYWORD_INDEX:
            _KEYWORD_INDEX[_kw] = []
        for _idx in _indices:
            if _idx not in _KEYWORD_INDEX[_kw]:
                _KEYWORD_INDEX[_kw].append(_idx)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


def _match_passages(query: str, k: int) -> list[tuple[str, str]]:
    """Return up to k passage (source, text) pairs that match the query.

    Matching is keyword-based: tokenise query to lowercase words, score each
    passage index by how many keywords hit it, then return the top-k by score.
    Passages with no keyword hit are excluded (simulates a true no-result).
    """
    tokens = query.lower().split()
    scores: dict[int, int] = {}
    for token in tokens:
        # Also try partial match for common compound words
        for kw, indices in _KEYWORD_INDEX.items():
            if kw in token or token in kw:
                for idx in indices:
                    scores[idx] = scores.get(idx, 0) + 1

    if not scores:
        return []

    # Sort by score descending, then by index ascending for determinism
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    selected = ranked[:k]
    return [_PASSAGE_BANK[idx] for idx, _ in selected]


def _format_passages(passages: list[tuple[str, str]]) -> str:
    """Format a list of (source, text) passages into realistic stdout."""
    parts: list[str] = []
    for source, text in passages:
        header = f"[{source}]"
        parts.append(f"{header}\n{text}".strip())
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_retrieve(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a retrieve operation against the local corpus."""
    query: str = args.get("query", "")
    raw_k = args.get("k")
    k: int = int(raw_k) if raw_k is not None else 3
    k = max(1, k)

    # Empty query: return nothing (the real tool would also return nothing useful)
    if not query.strip():
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Retrieved 0 reference passages.",
        )

    passages = _match_passages(query, k)

    if not passages:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Retrieved 0 reference passages.",
        )

    stdout = _format_passages(passages)
    n = len(passages)
    summary = f"Retrieved {n} reference passage{'s' if n != 1 else ''}."

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "retrieve": _sim_retrieve,
}


def simulate_docs(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'docs' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the real ops declared in the docs
           ToolSpec (currently: "retrieve").
    args : argument dict (may be sparse; "query" defaults to "" when absent
           so the offline smoke-path can call simulate_docs("retrieve", {}, ctx)
           without raising KeyError).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict.  Not used for passage lookup but accepted for
           API consistency with the other simulate_<tool> functions.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_docs: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
