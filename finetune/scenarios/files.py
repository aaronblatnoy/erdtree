"""finetune/scenarios/files.py — Scenario corpus for the 'files' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list    READ   — show directory contents as a tree
  read    READ   — show file contents (line-capped)
  stat    READ   — show file/directory metadata
  find    READ   — search for files via find
  copy    WRITE  — copy files/directories
  move    WRITE  — move or rename files/directories
  mkdir   WRITE  — create a directory
  chmod   WRITE  — change file permissions
  chown   WRITE  — change file ownership
  write   WRITE  — write content to a file
  remove  WRITE  — remove files/directories

Coverage targets
----------------
  >= 60 entries total across all 11 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE scenarios are honestly labeled (permission_class from registry)
  so downstream traces teach the confirm-before-write gate.

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
    """Return the live permission class for a files operation."""
    return registry.get("files").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="files-list-0001",
        tool="files",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me what's in /etc/nginx",
        notes="Basic directory listing of nginx config directory.",
    ),
    Scenario(
        id="files-list-0002",
        tool="files",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list the contents of /var/log",
        notes="List log directory contents.",
    ),
    Scenario(
        id="files-list-0003",
        tool="files",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what files are in the current directory?",
        notes="List current working directory using default path.",
    ),
    Scenario(
        id="files-list-0004",
        tool="files",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="show me the layout of /etc/systemd/system so I know which unit files are there",
        notes="Multi-step context: user wants to understand systemd unit file layout before editing.",
    ),
    Scenario(
        id="files-list-0005",
        tool="files",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="what's sitting in /tmp? I want to check for leftover junk",
        notes="Diagnostic: inspect /tmp for stale or unexpected files.",
    ),
    Scenario(
        id="files-list-0006",
        tool="files",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list /var/lib/postgresql",
        notes="Check PostgreSQL data directory structure.",
    ),
    Scenario(
        id="files-list-0007",
        tool="files",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="show me what's under /etc/pki/tls to audit certificate files",
        notes="Diagnostic: auditing TLS certificate layout for security review.",
    ),

    # =========================================================================
    # read  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="files-read-0001",
        tool="files",
        operation="read",
        permission_class=_pc("read"),
        complexity="single",
        user_input="show me the contents of /etc/nginx/nginx.conf",
        notes="Read nginx main config file.",
    ),
    Scenario(
        id="files-read-0002",
        tool="files",
        operation="read",
        permission_class=_pc("read"),
        complexity="single",
        user_input="read /etc/hosts",
        notes="Read /etc/hosts to inspect hostname mappings.",
    ),
    Scenario(
        id="files-read-0003",
        tool="files",
        operation="read",
        permission_class=_pc("read"),
        complexity="single",
        user_input="show me /etc/ssh/sshd_config",
        notes="Read SSH daemon configuration.",
    ),
    Scenario(
        id="files-read-0004",
        tool="files",
        operation="read",
        permission_class=_pc("read"),
        complexity="multi",
        user_input="read the sudoers file so I can see what permissions are set",
        notes="Multi-step context: user reviewing sudoers before making changes.",
    ),
    Scenario(
        id="files-read-0005",
        tool="files",
        operation="read",
        permission_class=_pc("read"),
        complexity="diagnostic",
        user_input="show me /var/log/messages, first 50 lines, something went wrong at boot",
        notes="Diagnostic: reading system log to investigate boot-time errors.",
    ),
    Scenario(
        id="files-read-0006",
        tool="files",
        operation="read",
        permission_class=_pc("read"),
        complexity="single",
        user_input="cat /proc/cpuinfo for me",
        notes="Read /proc/cpuinfo for hardware detail.",
    ),
    Scenario(
        id="files-read-0007",
        tool="files",
        operation="read",
        permission_class=_pc("read"),
        complexity="diagnostic",
        user_input="read /etc/fstab — I need to check if the data partition is set to mount at boot",
        notes="Diagnostic: verifying fstab entries for persistent mounts.",
    ),

    # =========================================================================
    # stat  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="files-stat-0001",
        tool="files",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="what are the permissions on /etc/shadow?",
        notes="Stat to check ownership and mode of the shadow password file.",
    ),
    Scenario(
        id="files-stat-0002",
        tool="files",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="check the metadata on /var/log/secure",
        notes="Stat security log to see size and timestamps.",
    ),
    Scenario(
        id="files-stat-0003",
        tool="files",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="diagnostic",
        user_input="when was /etc/passwd last modified? I suspect unauthorized changes",
        notes="Diagnostic: checking mtime on sensitive file as part of incident investigation.",
    ),
    Scenario(
        id="files-stat-0004",
        tool="files",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="single",
        user_input="show me the file info for /usr/bin/python3",
        notes="Stat to confirm binary exists and check its permissions.",
    ),
    Scenario(
        id="files-stat-0005",
        tool="files",
        operation="stat",
        permission_class=_pc("stat"),
        complexity="multi",
        user_input="give me the stat on /data/backups/latest.tar.gz so I can see how old it is",
        notes="Multi: user will decide whether to trigger a new backup based on mtime.",
    ),

    # =========================================================================
    # find  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="files-find-0001",
        tool="files",
        operation="find",
        permission_class=_pc("find"),
        complexity="single",
        user_input="find all .conf files under /etc",
        notes="Search for configuration files across /etc.",
    ),
    Scenario(
        id="files-find-0002",
        tool="files",
        operation="find",
        permission_class=_pc("find"),
        complexity="single",
        user_input="find all log files in /var/log",
        notes="Locate log files for inspection.",
    ),
    Scenario(
        id="files-find-0003",
        tool="files",
        operation="find",
        permission_class=_pc("find"),
        complexity="diagnostic",
        user_input="look for any core dump files on the system — check under /var/crash and /tmp",
        notes="Diagnostic: hunt for core dumps after a process crash.",
    ),
    Scenario(
        id="files-find-0004",
        tool="files",
        operation="find",
        permission_class=_pc("find"),
        complexity="single",
        user_input="find all directories under /home with maxdepth 2",
        notes="Enumerate user home subdirectories.",
    ),
    Scenario(
        id="files-find-0005",
        tool="files",
        operation="find",
        permission_class=_pc("find"),
        complexity="multi",
        user_input="find all .pem files under /etc/pki so I can see which certs are installed",
        notes="Multi: cert discovery step before a renewal workflow.",
    ),
    Scenario(
        id="files-find-0006",
        tool="files",
        operation="find",
        permission_class=_pc("find"),
        complexity="diagnostic",
        user_input="search for any world-writable files under /etc — security check",
        notes="Diagnostic: security audit for overly permissive files.",
    ),
    Scenario(
        id="files-find-0007",
        tool="files",
        operation="find",
        permission_class=_pc("find"),
        complexity="single",
        user_input="find files named 'authorized_keys' under /home",
        notes="Locate SSH authorized_keys files across all user home directories.",
    ),

    # =========================================================================
    # copy  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="files-copy-0001",
        tool="files",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="single",
        user_input="copy /etc/nginx/nginx.conf to /etc/nginx/nginx.conf.bak",
        notes="WRITE: backup nginx config before editing. Requires confirmation.",
    ),
    Scenario(
        id="files-copy-0002",
        tool="files",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="single",
        user_input="make a backup copy of /etc/hosts at /etc/hosts.orig",
        notes="WRITE: back up hosts file before modification.",
    ),
    Scenario(
        id="files-copy-0003",
        tool="files",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="multi",
        user_input="copy the entire /etc/nginx directory to /tmp/nginx-backup recursively",
        notes="WRITE: recursive copy of nginx config dir as multi-step pre-upgrade backup.",
    ),
    Scenario(
        id="files-copy-0004",
        tool="files",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="single",
        user_input="copy /var/lib/pgsql/data/postgresql.conf to /root/postgresql.conf.bak",
        notes="WRITE: backup PostgreSQL config before tuning.",
    ),
    Scenario(
        id="files-copy-0005",
        tool="files",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="diagnostic",
        user_input="copy /var/log/messages to /tmp/messages-snapshot for offline analysis",
        notes="WRITE: snapshot a live log file for safe offline review.",
    ),
    Scenario(
        id="files-copy-0006",
        tool="files",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="single",
        user_input="copy /etc/sysctl.conf to /etc/sysctl.conf.orig",
        notes="WRITE: preserve original sysctl settings before performance tuning.",
    ),

    # =========================================================================
    # move  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="files-move-0001",
        tool="files",
        operation="move",
        permission_class=_pc("move"),
        complexity="single",
        user_input="rename /etc/nginx/sites-available/default to /etc/nginx/sites-available/default.disabled",
        notes="WRITE: disable a virtual host by renaming its config file.",
    ),
    Scenario(
        id="files-move-0002",
        tool="files",
        operation="move",
        permission_class=_pc("move"),
        complexity="single",
        user_input="move /tmp/new-app.conf to /etc/app/app.conf",
        notes="WRITE: deploy a new config file into place.",
    ),
    Scenario(
        id="files-move-0003",
        tool="files",
        operation="move",
        permission_class=_pc("move"),
        complexity="multi",
        user_input="move the old log archive at /var/log/old-archive to /data/log-archive",
        notes="WRITE: relocate log archive as part of storage reorganization.",
    ),
    Scenario(
        id="files-move-0004",
        tool="files",
        operation="move",
        permission_class=_pc("move"),
        complexity="single",
        user_input="rename /root/setup.sh to /root/setup.sh.done to mark it as run",
        notes="WRITE: mark a one-shot script as completed by renaming it.",
    ),
    Scenario(
        id="files-move-0005",
        tool="files",
        operation="move",
        permission_class=_pc("move"),
        complexity="diagnostic",
        user_input="move /var/run/stale.pid out of the way — it's blocking the service from starting",
        notes="WRITE: remove a stale PID file (by moving it) during a diagnostic recovery.",
    ),

    # =========================================================================
    # mkdir  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="files-mkdir-0001",
        tool="files",
        operation="mkdir",
        permission_class=_pc("mkdir"),
        complexity="single",
        user_input="create the directory /var/data/uploads",
        notes="WRITE: create a new uploads directory.",
    ),
    Scenario(
        id="files-mkdir-0002",
        tool="files",
        operation="mkdir",
        permission_class=_pc("mkdir"),
        complexity="single",
        user_input="make /etc/app/conf.d and any missing parent directories",
        notes="WRITE: create a drop-in config directory with parent creation.",
    ),
    Scenario(
        id="files-mkdir-0003",
        tool="files",
        operation="mkdir",
        permission_class=_pc("mkdir"),
        complexity="multi",
        user_input="create /opt/myapp/logs so the app has somewhere to write",
        notes="WRITE: create app log directory as part of install workflow.",
    ),
    Scenario(
        id="files-mkdir-0004",
        tool="files",
        operation="mkdir",
        permission_class=_pc("mkdir"),
        complexity="single",
        user_input="set up the /data/backups directory",
        notes="WRITE: provision backup destination directory.",
    ),
    Scenario(
        id="files-mkdir-0005",
        tool="files",
        operation="mkdir",
        permission_class=_pc("mkdir"),
        complexity="diagnostic",
        user_input="the app is failing because /run/myapp doesn't exist — create it",
        notes="WRITE: create missing runtime directory to resolve a startup failure.",
    ),

    # =========================================================================
    # chmod  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="files-chmod-0001",
        tool="files",
        operation="chmod",
        permission_class=_pc("chmod"),
        complexity="single",
        user_input="make /usr/local/bin/myapp executable",
        notes="WRITE: set executable bit on a deployed binary.",
    ),
    Scenario(
        id="files-chmod-0002",
        tool="files",
        operation="chmod",
        permission_class=_pc("chmod"),
        complexity="single",
        user_input="set permissions on /etc/app/secret.key to 600",
        notes="WRITE: restrict a secret key file to owner-read-only.",
    ),
    Scenario(
        id="files-chmod-0003",
        tool="files",
        operation="chmod",
        permission_class=_pc("chmod"),
        complexity="multi",
        user_input="chmod 755 on /var/www/html so the web server can serve those files",
        notes="WRITE: part of web server setup — fix permissions so nginx can read content.",
    ),
    Scenario(
        id="files-chmod-0004",
        tool="files",
        operation="chmod",
        permission_class=_pc("chmod"),
        complexity="single",
        user_input="remove world-write from /tmp/shared — set it to 1775",
        notes="WRITE: harden /tmp/shared with sticky bit and remove world-write.",
    ),
    Scenario(
        id="files-chmod-0005",
        tool="files",
        operation="chmod",
        permission_class=_pc("chmod"),
        complexity="diagnostic",
        user_input="the cron script at /etc/cron.daily/cleanup isn't running — check and fix its permissions",
        notes="Diagnostic/WRITE: likely needs chmod +x to run as cron.",
    ),
    Scenario(
        id="files-chmod-0006",
        tool="files",
        operation="chmod",
        permission_class=_pc("chmod"),
        complexity="single",
        user_input="recursively set /var/www to 755",
        notes="WRITE: fix permissions across a web root directory tree.",
    ),

    # =========================================================================
    # chown  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="files-chown-0001",
        tool="files",
        operation="chown",
        permission_class=_pc("chown"),
        complexity="single",
        user_input="change the owner of /var/lib/myapp to myapp:myapp",
        notes="WRITE: set ownership for a service's data directory.",
    ),
    Scenario(
        id="files-chown-0002",
        tool="files",
        operation="chown",
        permission_class=_pc("chown"),
        complexity="single",
        user_input="give nginx ownership of /etc/nginx/ssl",
        notes="WRITE: hand SSL directory to the web server account.",
    ),
    Scenario(
        id="files-chown-0003",
        tool="files",
        operation="chown",
        permission_class=_pc("chown"),
        complexity="multi",
        user_input="recursively chown /opt/app to the app service account",
        notes="WRITE: mass ownership fix as part of app deployment.",
    ),
    Scenario(
        id="files-chown-0004",
        tool="files",
        operation="chown",
        permission_class=_pc("chown"),
        complexity="diagnostic",
        user_input="the postgres service can't read /data/pgdata — fix its ownership",
        notes="Diagnostic/WRITE: ownership mismatch preventing PostgreSQL from starting.",
    ),
    Scenario(
        id="files-chown-0005",
        tool="files",
        operation="chown",
        permission_class=_pc("chown"),
        complexity="single",
        user_input="set /home/alice/.ssh to be owned by alice",
        notes="WRITE: fix SSH directory ownership for user alice.",
    ),

    # =========================================================================
    # write  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="files-write-0001",
        tool="files",
        operation="write",
        permission_class=_pc("write"),
        complexity="single",
        user_input="write a basic /etc/motd that says 'Authorized users only'",
        notes="WRITE: set a login banner via motd file.",
    ),
    Scenario(
        id="files-write-0002",
        tool="files",
        operation="write",
        permission_class=_pc("write"),
        complexity="multi",
        user_input="create /etc/cron.d/cleanup with a nightly job to clear /tmp",
        notes="WRITE: drop a cron job file as part of maintenance setup.",
    ),
    Scenario(
        id="files-write-0003",
        tool="files",
        operation="write",
        permission_class=_pc("write"),
        complexity="single",
        user_input="write a simple /etc/resolv.conf pointing at 8.8.8.8 and 1.1.1.1",
        notes="WRITE: overwrite resolver config with public DNS servers.",
    ),
    Scenario(
        id="files-write-0004",
        tool="files",
        operation="write",
        permission_class=_pc("write"),
        complexity="diagnostic",
        user_input="the /etc/hosts is missing the db hostname — add it",
        notes="Diagnostic/WRITE: inserting a missing hosts entry to fix name resolution.",
    ),
    Scenario(
        id="files-write-0005",
        tool="files",
        operation="write",
        permission_class=_pc("write"),
        complexity="single",
        user_input="create /opt/app/config.ini with the standard defaults",
        notes="WRITE: initialize app config file from defaults.",
    ),
    Scenario(
        id="files-write-0006",
        tool="files",
        operation="write",
        permission_class=_pc("write"),
        complexity="multi",
        user_input="write the updated sysctl parameters to /etc/sysctl.d/99-perf.conf",
        notes="WRITE: persist performance tuning settings to a drop-in sysctl file.",
    ),

    # =========================================================================
    # remove  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="files-remove-0001",
        tool="files",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="delete the file /tmp/stale-lock",
        notes="WRITE: remove a stale lock file.",
    ),
    Scenario(
        id="files-remove-0002",
        tool="files",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="remove /etc/nginx/sites-enabled/old-site.conf",
        notes="WRITE: delete a decommissioned virtual host config.",
    ),
    Scenario(
        id="files-remove-0003",
        tool="files",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="multi",
        user_input="clean up /tmp/build-artifacts after the build finished",
        notes="WRITE: multi-step cleanup — remove build temp directory.",
    ),
    Scenario(
        id="files-remove-0004",
        tool="files",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="diagnostic",
        user_input="there's a leftover .pid file at /var/run/app.pid preventing the service from starting — remove it",
        notes="Diagnostic/WRITE: removing a stale PID file to unblock service start.",
    ),
    Scenario(
        id="files-remove-0005",
        tool="files",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="delete /root/tmp-keys.txt after we've finished rotating SSH keys",
        notes="WRITE: secure cleanup of a temporary key file.",
    ),
    Scenario(
        id="files-remove-0006",
        tool="files",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="remove the old backup file at /var/backups/db-2024-01-01.sql.gz",
        notes="WRITE: remove an aged database backup to free disk space.",
    ),

]
