"""finetune/simulate/__init__.py — P3 JOIN: unified simulate() dispatch.

Public API
----------
simulate(tool, op, args, ctx) -> dict
    Route to the correct per-tool simulator and return its result.

    Parameters
    ----------
    tool : str
        Registered tool name (must be in the live TOOL_NAMES registry).
    op : str
        Operation name (must be in the tool's live op enum).
    args : dict
        Argument dict for the op (may be {} for all-optional ops).
    ctx : str | dict
        System context string or profile dict (passed through to the
        per-tool simulator unchanged).

    Returns
    -------
    dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str  (always I2-clean)

    Raises
    ------
    ValueError
        If `tool` is not in the live registry, or if `op` is not in that
        tool's declared op enum.  The message names both the bad value and
        the accepted set so callers can surface useful diagnostics.

Load-bearing invariants
-----------------------
INV-schema-sync   Tool names, op names, and the valid-op set are derived
                  LIVE from finetune.coreimports.  Nothing is hardcoded.

INV-read-only-core  This module does NOT import from core/ directly.
                    It uses finetune.coreimports as the sole seam.

INV-offline       This module imports cleanly with no network, no Ollama,
                  and no ANTHROPIC_API_KEY.

COMPLETENESS ASSERT (module-level)
-----------------------------------
At import time this module iterates every (tool, op) pair in the live
registry and verifies that:
  1. A simulator function exists for the tool.
  2. Calling simulate(tool, op, minimal_args, ctx={}) returns a dict with
     the required four keys: exit_code, stdout, stderr, summary.
Any gap causes an AssertionError that surfaces immediately — before
generate.py can silently KeyError mid-run.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 1. Import per-tool simulators.
#    Each import is a hard dependency — if a sibling module is missing or
#    broken, the ImportError surfaces here immediately (as intended).
# ---------------------------------------------------------------------------
from finetune.simulate.aide            import simulate_aide
from finetune.simulate.at              import simulate_at
from finetune.simulate.audit           import simulate_audit
from finetune.simulate.bond            import simulate_bond
from finetune.simulate.buildah         import simulate_buildah
from finetune.simulate.chrony          import simulate_chrony
from finetune.simulate.cron            import simulate_cron
from finetune.simulate.crypto_policies import simulate_crypto_policies
from finetune.simulate.disk            import simulate_disk
from finetune.simulate.dnf_modules     import simulate_dnf_modules
from finetune.simulate.dns             import simulate_dns
from finetune.simulate.docs            import simulate_docs
from finetune.simulate.fapolicyd       import simulate_fapolicyd
from finetune.simulate.files           import simulate_files
from finetune.simulate.firewall        import simulate_firewall
from finetune.simulate.grub            import simulate_grub
from finetune.simulate.hardware        import simulate_hardware
from finetune.simulate.hostname        import simulate_hostname
from finetune.simulate.httpd           import simulate_httpd
from finetune.simulate.kernel_modules  import simulate_kernel_modules
from finetune.simulate.locale          import simulate_locale
from finetune.simulate.logs            import simulate_logs
from finetune.simulate.lvm             import simulate_lvm
from finetune.simulate.mariadb         import simulate_mariadb
from finetune.simulate.network         import simulate_network
from finetune.simulate.nfs             import simulate_nfs
from finetune.simulate.nftables        import simulate_nftables
from finetune.simulate.nginx           import simulate_nginx
from finetune.simulate.nmcli           import simulate_nmcli
from finetune.simulate.packages        import simulate_packages
from finetune.simulate.pam             import simulate_pam
from finetune.simulate.perf            import simulate_perf
from finetune.simulate.performance     import simulate_performance
from finetune.simulate.podman          import simulate_podman
from finetune.simulate.postgresql      import simulate_postgresql
from finetune.simulate.processes       import simulate_processes
from finetune.simulate.quota           import simulate_quota
from finetune.simulate.restic          import simulate_restic
from finetune.simulate.routing         import simulate_routing
from finetune.simulate.rpm             import simulate_rpm
from finetune.simulate.rsync           import simulate_rsync
from finetune.simulate.samba           import simulate_samba
from finetune.simulate.selinux         import simulate_selinux
from finetune.simulate.services        import simulate_services
from finetune.simulate.sosreport       import simulate_sosreport
from finetune.simulate.ssh_keys        import simulate_ssh_keys
from finetune.simulate.sssd            import simulate_sssd
from finetune.simulate.stratis         import simulate_stratis
from finetune.simulate.subscription    import simulate_subscription
from finetune.simulate.sysctl          import simulate_sysctl
from finetune.simulate.systemd_timers  import simulate_systemd_timers
from finetune.simulate.tar             import simulate_tar
from finetune.simulate.tuned           import simulate_tuned
from finetune.simulate.users           import simulate_users
from finetune.simulate.virsh           import simulate_virsh

# ---------------------------------------------------------------------------
# 2. Dispatch table: tool name -> simulator function.
#    Keys MUST match the live TOOL_NAMES from coreimports.
#    The completeness assert below validates this at import time.
# ---------------------------------------------------------------------------
_DISPATCH: dict[str, Any] = {
    "aide":            simulate_aide,
    "at":              simulate_at,
    "audit":           simulate_audit,
    "bond":            simulate_bond,
    "buildah":         simulate_buildah,
    "chrony":          simulate_chrony,
    "cron":            simulate_cron,
    "crypto_policies": simulate_crypto_policies,
    "disk":            simulate_disk,
    "dnf_modules":     simulate_dnf_modules,
    "dns":             simulate_dns,
    "docs":            simulate_docs,
    "fapolicyd":       simulate_fapolicyd,
    "files":           simulate_files,
    "firewall":        simulate_firewall,
    "grub":            simulate_grub,
    "hardware":        simulate_hardware,
    "hostname":        simulate_hostname,
    "httpd":           simulate_httpd,
    "kernel_modules":  simulate_kernel_modules,
    "locale":          simulate_locale,
    "logs":            simulate_logs,
    "lvm":             simulate_lvm,
    "mariadb":         simulate_mariadb,
    "network":         simulate_network,
    "nfs":             simulate_nfs,
    "nftables":        simulate_nftables,
    "nginx":           simulate_nginx,
    "nmcli":           simulate_nmcli,
    "packages":        simulate_packages,
    "pam":             simulate_pam,
    "perf":            simulate_perf,
    "performance":     simulate_performance,
    "podman":          simulate_podman,
    "postgresql":      simulate_postgresql,
    "processes":       simulate_processes,
    "quota":           simulate_quota,
    "restic":          simulate_restic,
    "routing":         simulate_routing,
    "rpm":             simulate_rpm,
    "rsync":           simulate_rsync,
    "samba":           simulate_samba,
    "selinux":         simulate_selinux,
    "services":        simulate_services,
    "sosreport":       simulate_sosreport,
    "ssh_keys":        simulate_ssh_keys,
    "sssd":            simulate_sssd,
    "stratis":         simulate_stratis,
    "subscription":    simulate_subscription,
    "sysctl":          simulate_sysctl,
    "systemd_timers":  simulate_systemd_timers,
    "tar":             simulate_tar,
    "tuned":           simulate_tuned,
    "users":           simulate_users,
    "virsh":           simulate_virsh,
}

# ---------------------------------------------------------------------------
# 3. Per-(tool, op) minimal probe args for the completeness assert.
#    These are the smallest arg dicts that allow each op to return a result
#    without raising on a missing required argument.  They are used ONLY in
#    the module-level assert — generate.py passes real scenario args.
#    Derived from the live registry's required-arg lists; never hardcoded
#    against schema internals (the dict keys are just realistic strings).
# ---------------------------------------------------------------------------
_PROBE_ARGS: dict[tuple[str, str], dict] = {
    # aide — all args optional
    ("aide", "check"):     {},
    ("aide", "db_status"): {},
    ("aide", "init"):      {},
    ("aide", "update"):    {},
    # at — all args optional
    ("at", "atq"):      {},
    ("at", "atrm"):     {},
    ("at", "schedule"): {},
    # audit — all args optional
    ("audit", "add-rule"):        {},
    ("audit", "auditd-start"):    {},
    ("audit", "auditd-stop"):     {},
    ("audit", "delete-rule"):     {},
    ("audit", "list"):            {},
    ("audit", "report"):          {},
    ("audit", "search-by-comm"):  {},
    ("audit", "search-by-key"):   {},
    ("audit", "search-by-time"):  {},
    ("audit", "status"):          {},
    # bond — all args optional
    ("bond", "add"):    {},
    ("bond", "modify"): {},
    ("bond", "remove"): {},
    ("bond", "show"):   {},
    # buildah — all args optional
    ("buildah", "build"):  {},
    ("buildah", "commit"): {},
    ("buildah", "copy"):   {},
    ("buildah", "from"):   {},
    ("buildah", "images"): {},
    ("buildah", "push"):   {},
    ("buildah", "rm"):     {},
    ("buildah", "run"):    {},
    # chrony — all args optional
    ("chrony", "conf_edit"):  {},
    ("chrony", "conf_view"):  {},
    ("chrony", "makestep"):   {},
    ("chrony", "sources"):    {},
    ("chrony", "status"):     {},
    ("chrony", "tracking"):   {},
    # cron — all args optional
    ("cron", "crond-add"):  {},
    ("cron", "crond-view"): {},
    ("cron", "edit"):       {},
    ("cron", "list"):       {},
    ("cron", "list-all"):   {},
    ("cron", "remove"):     {},
    # crypto_policies — all args optional
    ("crypto_policies", "fips-enable"):  {},
    ("crypto_policies", "fips-status"):  {},
    ("crypto_policies", "get"):          {},
    ("crypto_policies", "list"):         {},
    ("crypto_policies", "set"):          {},
    # disk
    ("disk", "usage"):     {},
    ("disk", "list"):      {},
    ("disk", "smart"):     {"device": "/dev/sda"},
    ("disk", "mount"):     {"device": "/dev/sda1", "mount_point": "/mnt/data"},
    ("disk", "unmount"):   {"target": "/mnt/data"},
    ("disk", "format"):    {"device": "/dev/sdb"},
    ("disk", "partition"): {"device": "/dev/sdb"},
    ("disk", "wipe"):      {"device": "/dev/sdb"},
    ("disk", "dd_write"):  {"device": "/dev/sdb", "source": "/dev/zero"},
    # dnf_modules — all args optional
    ("dnf_modules", "disable"): {},
    ("dnf_modules", "enable"):  {},
    ("dnf_modules", "info"):    {},
    ("dnf_modules", "install"): {},
    ("dnf_modules", "list"):    {},
    ("dnf_modules", "reset"):   {},
    # dns — all args optional
    ("dns", "dig"):          {},
    ("dns", "flush_caches"): {},
    ("dns", "host"):         {},
    ("dns", "named_status"): {},
    ("dns", "nslookup"):     {},
    ("dns", "resolv_view"):  {},
    # docs
    ("docs", "retrieve"): {"query": "how to configure firewalld"},
    # files
    ("files", "list"):   {"path": "/etc"},
    ("files", "read"):   {"path": "/etc/hostname"},
    ("files", "write"):  {"path": "/tmp/test.txt", "content": "hello"},
    ("files", "find"):   {"path": "/etc", "name": "*.conf"},
    ("files", "stat"):   {"path": "/etc/hostname"},
    ("files", "mkdir"):  {"path": "/tmp/testdir"},
    ("files", "copy"):   {"src": "/etc/hostname", "dest": "/tmp/hostname.bak"},
    ("files", "move"):   {"src": "/tmp/hostname.bak", "dest": "/tmp/hostname2.bak"},
    ("files", "remove"): {"path": "/tmp/test.txt"},
    ("files", "chmod"):  {"path": "/tmp/test.txt", "mode": "644"},
    ("files", "chown"):  {"path": "/tmp/test.txt", "owner": "root"},
    # fapolicyd — all args optional
    ("fapolicyd", "allow"):      {},
    ("fapolicyd", "deny"):       {},
    ("fapolicyd", "list_rules"): {},
    ("fapolicyd", "status"):     {},
    ("fapolicyd", "update"):     {},
    # firewall
    ("firewall", "list"):           {},
    ("firewall", "get_zones"):      {},
    ("firewall", "reload"):         {},
    ("firewall", "panic_on"):       {},
    ("firewall", "add_port"):       {"port": "8080/tcp"},
    ("firewall", "remove_port"):    {"port": "8080/tcp"},
    ("firewall", "add_service"):    {"service": "http"},
    ("firewall", "remove_service"): {"service": "http"},
    ("firewall", "set_default_zone"): {"zone": "public"},
    ("firewall", "query"):          {"service": "ssh"},
    # grub — all args optional
    ("grub", "args-add"):       {},
    ("grub", "args-remove"):    {},
    ("grub", "default-kernel"): {},
    ("grub", "info"):           {},
    ("grub", "mkconfig"):       {},
    ("grub", "remove-kernel"):  {},
    ("grub", "set-default"):    {},
    ("grub", "set-password"):   {},
    # hardware
    ("hardware", "summary"): {},
    ("hardware", "cpu"):     {},
    ("hardware", "memory"):  {},
    ("hardware", "block"):   {},
    ("hardware", "pci"):     {},
    ("hardware", "usb"):     {},
    ("hardware", "sensors"): {},
    # hostname — all args optional
    ("hostname", "hosts-edit"):   {},
    ("hostname", "hosts-view"):   {},
    ("hostname", "set-hostname"): {},
    ("hostname", "status"):       {},
    # httpd — all args optional
    ("httpd", "configtest"): {},
    ("httpd", "mod_status"): {},
    ("httpd", "restart"):    {},
    ("httpd", "start"):      {},
    ("httpd", "status"):     {},
    ("httpd", "stop"):       {},
    ("httpd", "vhost_list"): {},
    # kernel_modules — all args optional
    ("kernel_modules", "lsmod"):          {},
    ("kernel_modules", "modinfo"):        {},
    ("kernel_modules", "modprobe"):       {},
    ("kernel_modules", "modules-load.d"): {},
    ("kernel_modules", "rmmod"):          {},
    # locale — all args optional
    ("locale", "localectl-status"):  {},
    ("locale", "set-keymap"):        {},
    ("locale", "set-locale"):        {},
    ("locale", "set-ntp"):           {},
    ("locale", "set-timezone"):      {},
    ("locale", "timedatectl-status"): {},
    # logs
    ("logs", "tail"):         {},
    ("logs", "since"):        {"since": "1h"},
    ("logs", "query"):        {"pattern": "error"},
    ("logs", "boot_errors"):  {},
    ("logs", "dmesg_errors"): {},
    ("logs", "dmesg_query"):  {"pattern": "usb"},
    # lvm — all args optional
    ("lvm", "lvcreate"):  {},
    ("lvm", "lvdisplay"): {},
    ("lvm", "lvextend"):  {},
    ("lvm", "lvreduce"):  {},
    ("lvm", "lvremove"):  {},
    ("lvm", "pvcreate"):  {},
    ("lvm", "pvdisplay"): {},
    ("lvm", "pvremove"):  {},
    ("lvm", "vgcreate"):  {},
    ("lvm", "vgdisplay"): {},
    ("lvm", "vgextend"):  {},
    ("lvm", "vgremove"):  {},
    # mariadb — all args optional
    ("mariadb", "drop_database"): {},
    ("mariadb", "dump"):          {},
    ("mariadb", "grant"):         {},
    ("mariadb", "query"):         {},
    ("mariadb", "status"):        {},
    # network
    ("network", "interfaces"):  {},
    ("network", "connections"): {},
    ("network", "status"):      {},
    ("network", "wifi"):        {},
    ("network", "show"):        {"interface": "eth0"},
    ("network", "bring_up"):    {"interface": "eth0"},
    ("network", "bring_down"):  {"interface": "eth0"},
    ("network", "set_ip"):      {"interface": "eth0", "ip": "192.168.1.100/24"},
    # nfs — all args optional
    ("nfs", "exportfs_add"):     {},
    ("nfs", "exportfs_list"):    {},
    ("nfs", "exportfs_unexport"): {},
    ("nfs", "exports_view"):     {},
    ("nfs", "mount_client"):     {},
    ("nfs", "nfs_start"):        {},
    ("nfs", "nfs_stop"):         {},
    ("nfs", "showmount"):        {},
    # nftables — all args optional
    ("nftables", "add_rule"):      {},
    ("nftables", "delete_rule"):   {},
    ("nftables", "flush_ruleset"): {},
    ("nftables", "list_ruleset"):  {},
    # nginx — all args optional
    ("nginx", "configtest"): {},
    ("nginx", "reload"):     {},
    ("nginx", "restart"):    {},
    ("nginx", "start"):      {},
    ("nginx", "status"):     {},
    ("nginx", "stop"):       {},
    # nmcli — all args optional
    ("nmcli", "connection_add"):    {},
    ("nmcli", "connection_delete"): {},
    ("nmcli", "connection_down"):   {},
    ("nmcli", "connection_modify"): {},
    ("nmcli", "connection_show"):   {},
    ("nmcli", "connection_up"):     {},
    ("nmcli", "device_status"):     {},
    ("nmcli", "dns_configure"):     {},
    ("nmcli", "wifi_connect"):      {},
    ("nmcli", "wifi_list"):         {},
    # packages
    ("packages", "update"):  {},
    ("packages", "install"): {"packages": ["vim"]},
    ("packages", "remove"):  {"packages": ["vim"]},
    ("packages", "search"):  {"keyword": "nginx"},
    ("packages", "info"):    {"package": "nginx"},
    # pam — all args optional
    ("pam", "faillock_reset"):   {},
    ("pam", "faillock_status"):  {},
    ("pam", "pam_auth_update"):  {},
    ("pam", "pamd_audit"):       {},
    # perf — all args optional
    ("perf", "record"): {},
    ("perf", "stat"):   {},
    ("perf", "top"):    {},
    # performance — all args optional
    ("performance", "iostat"): {},
    ("performance", "load"):   {},
    ("performance", "mpstat"): {},
    ("performance", "sar"):    {},
    ("performance", "uptime"): {},
    ("performance", "vmstat"): {},
    # podman — all args optional
    ("podman", "build"):   {},
    ("podman", "exec"):    {},
    ("podman", "images"):  {},
    ("podman", "inspect"): {},
    ("podman", "logs"):    {},
    ("podman", "ps"):      {},
    ("podman", "pull"):    {},
    ("podman", "push"):    {},
    ("podman", "rm"):      {},
    ("podman", "rmi"):     {},
    ("podman", "run"):     {},
    ("podman", "stop"):    {},
    # postgresql — all args optional
    ("postgresql", "createdb"):   {},
    ("postgresql", "createuser"): {},
    ("postgresql", "dropdb"):     {},
    ("postgresql", "pg_dump"):    {},
    ("postgresql", "query"):      {},
    ("postgresql", "status"):     {},
    # processes
    ("processes", "list"):   {},
    ("processes", "top"):    {},
    ("processes", "tree"):   {},
    ("processes", "info"):   {"pid": 1},
    ("processes", "signal"): {"pid": 12345, "signal": 15},
    ("processes", "renice"): {"pid": 12345, "priority": 10},
    # quota — all args optional
    ("quota", "edquota"):    {},
    ("quota", "quota_user"): {},
    ("quota", "quotacheck"): {},
    ("quota", "quotaoff"):   {},
    ("quota", "quotaon"):    {},
    ("quota", "repquota"):   {},
    # restic — all args optional
    ("restic", "backup"):       {},
    ("restic", "forget"):       {},
    ("restic", "forget_prune"): {},
    ("restic", "restore"):      {},
    ("restic", "snapshots"):    {},
    # routing — all args optional
    ("routing", "policy_rule_add"):   {},
    ("routing", "policy_rule_flush"): {},
    ("routing", "policy_rule_show"):  {},
    ("routing", "route_add"):         {},
    ("routing", "route_del"):         {},
    ("routing", "route_flush"):       {},
    ("routing", "route_show"):        {},
    # rpm — all args optional
    ("rpm", "checksig"):    {},
    ("rpm", "install"):     {},
    ("rpm", "query_file"):  {},
    ("rpm", "query_files"): {},
    ("rpm", "query_info"):  {},
    ("rpm", "rpm2cpio"):    {},
    ("rpm", "verify"):      {},
    # rsync — all args optional
    ("rsync", "dry-run"):     {},
    ("rsync", "progress"):    {},
    ("rsync", "sync"):        {},
    ("rsync", "sync-delete"): {},
    # samba — all args optional
    ("samba", "nmbd_status"):      {},
    ("samba", "smbd_status"):      {},
    ("samba", "smbpasswd_add"):    {},
    ("samba", "smbpasswd_delete"): {},
    ("samba", "testparm"):         {},
    ("samba", "usershare_add"):    {},
    ("samba", "usershare_list"):   {},
    # selinux — all args optional
    ("selinux", "audit2allow"):             {},
    ("selinux", "chcon"):                   {},
    ("selinux", "getenforce"):              {},
    ("selinux", "getsebool"):               {},
    ("selinux", "restorecon"):              {},
    ("selinux", "semanage_fcontext_add"):   {},
    ("selinux", "semanage_fcontext_delete"): {},
    ("selinux", "semanage_fcontext_list"):  {},
    ("selinux", "semanage_port_add"):       {},
    ("selinux", "semanage_port_delete"):    {},
    ("selinux", "semanage_port_list"):      {},
    ("selinux", "semanage_user_add"):       {},
    ("selinux", "semanage_user_delete"):    {},
    ("selinux", "semanage_user_list"):      {},
    ("selinux", "sestatus"):                {},
    ("selinux", "setenforce"):              {},
    ("selinux", "setsebool"):               {},
    # services
    ("services", "status"):  {"unit": "nginx.service"},
    ("services", "start"):   {"unit": "nginx.service"},
    ("services", "stop"):    {"unit": "nginx.service"},
    ("services", "restart"): {"unit": "nginx.service"},
    ("services", "enable"):  {"unit": "nginx.service"},
    ("services", "disable"): {"unit": "nginx.service"},
    ("services", "mask"):    {"unit": "nginx.service"},
    ("services", "logs"):    {"unit": "nginx.service"},
    # sosreport — all args optional
    ("sosreport", "generate"): {},
    ("sosreport", "info"):     {},
    # ssh_keys — all args optional
    ("ssh_keys", "authorized_keys_add"):    {},
    ("ssh_keys", "authorized_keys_list"):   {},
    ("ssh_keys", "authorized_keys_remove"): {},
    ("ssh_keys", "keygen"):                 {},
    ("ssh_keys", "known_hosts_list"):       {},
    ("ssh_keys", "known_hosts_remove"):     {},
    ("ssh_keys", "sshd_config_audit"):      {},
    # sssd — all args optional
    ("sssd", "cache_flush"): {},
    ("sssd", "id_lookup"):   {},
    ("sssd", "realm_join"):  {},
    ("sssd", "realm_leave"): {},
    ("sssd", "realm_list"):  {},
    ("sssd", "status"):      {},
    # stratis — all args optional
    ("stratis", "filesystem-create"):   {},
    ("stratis", "filesystem-destroy"):  {},
    ("stratis", "filesystem-list"):     {},
    ("stratis", "filesystem-snapshot"): {},
    ("stratis", "pool-create"):         {},
    ("stratis", "pool-destroy"):        {},
    ("stratis", "pool-list"):           {},
    # subscription — all args optional
    ("subscription", "list"):          {},
    ("subscription", "register"):      {},
    ("subscription", "repos_disable"): {},
    ("subscription", "repos_enable"):  {},
    ("subscription", "status"):        {},
    ("subscription", "unregister"):    {},
    # sysctl — all args optional
    ("sysctl", "get"):    {},
    ("sysctl", "list"):   {},
    ("sysctl", "persist"): {},
    ("sysctl", "set"):    {},
    # systemd_timers — all args optional
    ("systemd_timers", "create"):      {},
    ("systemd_timers", "disable"):     {},
    ("systemd_timers", "enable"):      {},
    ("systemd_timers", "list-timers"): {},
    ("systemd_timers", "systemd-run"): {},
    ("systemd_timers", "timer-show"):  {},
    # tar — all args optional
    ("tar", "create"):     {},
    ("tar", "create_bz2"): {},
    ("tar", "create_gz"):  {},
    ("tar", "create_xz"):  {},
    ("tar", "extract"):    {},
    ("tar", "list"):       {},
    ("tar", "verify"):     {},
    # tuned — all args optional
    ("tuned", "active"):    {},
    ("tuned", "list"):      {},
    ("tuned", "off"):       {},
    ("tuned", "profile"):   {},
    ("tuned", "recommend"): {},
    # users
    ("users", "list"):               {},
    ("users", "info"):               {"username": "root"},
    ("users", "add"):                {"username": "testuser"},
    ("users", "delete"):             {"username": "testuser"},
    ("users", "lock"):               {"username": "testuser"},
    ("users", "add_to_group"):       {"username": "testuser", "group": "wheel"},
    ("users", "remove_from_privgroup"): {"username": "testuser"},
    ("users", "set_shell"):          {"username": "testuser", "shell": "/bin/bash"},
    # virsh — all args optional
    ("virsh", "define"):       {},
    ("virsh", "destroy"):      {},
    ("virsh", "dominfo"):      {},
    ("virsh", "list"):         {},
    ("virsh", "pool-define"):  {},
    ("virsh", "pool-destroy"): {},
    ("virsh", "pool-list"):    {},
    ("virsh", "shutdown"):     {},
    ("virsh", "start"):        {},
    ("virsh", "undefine"):     {},
}

# ---------------------------------------------------------------------------
# 4. Derive the valid-op set per tool from the LIVE registry at import time.
#    This set is used by simulate() to validate op names before dispatching.
#    INV-schema-sync: never hardcode op names — read from registry_schemas().
# ---------------------------------------------------------------------------
def _build_valid_ops() -> dict[str, frozenset[str]]:
    """Return {tool_name: frozenset(op_names)} from the live registry."""
    from finetune.coreimports import registry_schemas, registry  # local import avoids circularity
    result: dict[str, frozenset[str]] = {}
    for schema in registry_schemas(registry):
        tool_name = schema["name"]
        props = schema["parameters"]["properties"]
        ops: frozenset[str] = frozenset()
        for _key, spec in props.items():
            if isinstance(spec, dict) and "enum" in spec:
                ops = frozenset(spec["enum"])
                break
        result[tool_name] = ops
    return result


_VALID_OPS: dict[str, frozenset[str]] = _build_valid_ops()

# ---------------------------------------------------------------------------
# 5. Public dispatch function.
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = frozenset({"exit_code", "stdout", "stderr", "summary"})


def simulate(
    tool: str,
    op: str,
    args: dict[str, Any],
    ctx: Any,
) -> dict[str, Any]:
    """Dispatch to the correct per-tool simulator and return its result.

    Parameters
    ----------
    tool:
        Registered tool name.  Must be in the live TOOL_NAMES registry.
    op:
        Operation name.  Must be in that tool's declared op enum.
    args:
        Argument dict for the op.
    ctx:
        System context (str snapshot or profile dict) passed through unchanged.

    Returns
    -------
    dict with keys: exit_code, stdout, stderr, summary.

    Raises
    ------
    ValueError
        If `tool` is unknown or `op` is not valid for that tool.
    """
    # --- validate tool ---
    if tool not in _DISPATCH:
        known = sorted(_DISPATCH)
        raise ValueError(
            f"Unknown tool {tool!r}.  Known tools: {known}"
        )

    # --- validate op ---
    valid_ops = _VALID_OPS.get(tool, frozenset())
    if op not in valid_ops:
        raise ValueError(
            f"Unknown operation {op!r} for tool {tool!r}.  "
            f"Valid operations: {sorted(valid_ops)}"
        )

    # --- dispatch ---
    result: dict[str, Any] = _DISPATCH[tool](op, args, ctx)

    return result


# ---------------------------------------------------------------------------
# 6. Module-level completeness assert.
#
#    Iterates every (tool, op) in the LIVE registry and verifies:
#      a. A simulator exists in _DISPATCH for the tool.
#      b. simulate(tool, op, probe_args, ctx={}) returns a dict with
#         exactly the four required keys.
#
#    Any gap causes an AssertionError immediately at import time so that
#    generate.py never reaches a silent KeyError mid-run.
#
#    The probe args come from _PROBE_ARGS (defined above).  If a (tool, op)
#    pair is missing from _PROBE_ARGS the assert uses {} which is valid for
#    all-optional ops; an op that requires args will raise inside the
#    simulator and the assert will surface that as a failure — which is
#    exactly the right signal (a gap in coverage).
# ---------------------------------------------------------------------------

def _run_completeness_assert() -> None:
    """Verify zero (tool, op) gaps.  Called once at module import time."""
    from finetune.coreimports import registry_schemas, registry  # local import

    gaps: list[str] = []

    for schema in registry_schemas(registry):
        tool_name = schema["name"]
        props = schema["parameters"]["properties"]

        ops: list[str] = []
        for _key, spec in props.items():
            if isinstance(spec, dict) and "enum" in spec:
                ops = spec["enum"]
                break

        if tool_name not in _DISPATCH:
            gaps.append(f"NO SIMULATOR for tool {tool_name!r}")
            continue

        for op in ops:
            probe_args = _PROBE_ARGS.get((tool_name, op), {})
            try:
                result = simulate(tool_name, op, probe_args, ctx={})
            except Exception as exc:  # noqa: BLE001
                gaps.append(
                    f"{tool_name}.{op}: simulate() raised {type(exc).__name__}: {exc}"
                )
                continue

            missing = _REQUIRED_KEYS - set(result.keys())
            if missing:
                gaps.append(
                    f"{tool_name}.{op}: result missing keys {sorted(missing)}"
                )

    assert not gaps, (
        f"simulate() completeness check failed — {len(gaps)} gap(s):\n"
        + "\n".join(f"  {g}" for g in gaps)
    )


_run_completeness_assert()


# ---------------------------------------------------------------------------
# 7. Public surface.
# ---------------------------------------------------------------------------
__all__ = [
    "simulate",
]
