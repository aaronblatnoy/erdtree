"""finetune/scenarios_v4 — corpus v4: MULTI-STEP scenarios.

Corpus v3 taught follow-ups (a new user turn after each answer) but every record
still had exactly ONE call per turn.  On the held-out multi-step pool both current
models therefore make one call, read the result, and answer instead of carrying on
(0 of 50 sequences completed).  A v4 record is one operator request that needs a
SEQUENCE of calls: call, result, call, result, ..., then one English answer that
reports the whole sequence.  No user turn sits between the calls.

Scenarios are generated from templates with variable fills so the surface forms
vary while every call stays schema-valid against the live registry.  An overlap
guard drops anything too close to finetune/scenarios/eval_pool_multistep.py.
"""
from __future__ import annotations

import itertools
import random
import re
from dataclasses import dataclass

from finetune import coreimports


@dataclass(frozen=True)
class Step:
    tool: str
    operation: str
    args: dict


@dataclass(frozen=True)
class V4:
    id: str
    kind: str
    user_input: str
    steps: tuple


def S(tool, operation, **kw):
    return Step(tool=tool, operation=operation, args={"operation": operation, **kw})


# --------------------------------------------------------------------------- fills
SERVICES = ["haproxy", "redis", "rabbitmq", "docker", "sshd", "firewalld", "cups", "smb", "nfs-server",
            "named", "keepalived", "grafana-server", "prometheus", "jenkins", "gitlab-runner", "php-fpm",
            "memcached", "vsftpd", "dovecot", "postfix", "auditd", "rsyslog", "NetworkManager", "libvirtd"]
PACKAGES = ["htop", "vim-enhanced", "git", "tmux", "wget", "curl", "bind-utils", "net-tools", "nmap", "iotop",
            "sysstat", "strace", "lsof", "jq", "rsync", "podman", "haproxy", "redis", "rabbitmq-server",
            "samba", "nfs-utils", "bind", "grafana", "prometheus", "fail2ban", "cockpit"]
PKG_TO_UNIT = {"haproxy": "haproxy", "redis": "redis", "rabbitmq-server": "rabbitmq-server", "samba": "smb",
               "nfs-utils": "nfs-server", "bind": "named", "grafana": "grafana-server", "prometheus": "prometheus",
               "fail2ban": "fail2ban", "cockpit": "cockpit.socket", "podman": "podman.socket"}
PORTS = ["8081/tcp", "8443/tcp", "5000/tcp", "6379/tcp", "9100/tcp", "3000/tcp", "2049/tcp", "514/udp",
         "1194/udp", "8888/tcp", "27017/tcp", "15672/tcp"]
FW_SERVICES = ["https", "ssh", "dns", "nfs", "samba", "mysql", "postgresql", "cockpit", "ntp", "ldap"]
USERS = ["mchen", "arivera", "dpatel", "lkim", "svc_backup", "svc_deploy", "tnguyen", "bwilson", "jokafor", "ci_runner"]
GROUPS = ["wheel", "docker", "developers", "ops", "audio", "sysadmin"]
DEVICES = ["/dev/sdb", "/dev/sdd", "/dev/nvme1n1", "/dev/vdb", "/dev/sde"]
PARTS = ["/dev/sdb1", "/dev/sdd1", "/dev/nvme1n1p1", "/dev/vdb1"]
MOUNTS = ["/mnt/backup", "/mnt/scratch", "/srv/media", "/data", "/mnt/archive"]
SYSCTLS = [("vm.swappiness", "10"), ("net.core.somaxconn", "4096"), ("fs.file-max", "2097152"),
           ("net.ipv4.tcp_syncookies", "1"), ("kernel.pid_max", "4194304"), ("net.ipv6.conf.all.disable_ipv6", "1"),
           ("vm.max_map_count", "262144"), ("net.ipv4.ip_local_port_range", "1024 65535")]
BOOLEANS = ["httpd_can_network_connect_db", "samba_enable_home_dirs", "nfs_export_all_rw", "ftpd_full_access",
            "httpd_enable_homedirs", "virt_use_nfs", "container_manage_cgroup"]
MODULES = ["br_netfilter", "overlay", "nf_conntrack", "ip_vs", "bonding", "8021q", "dm_crypt", "wireguard"]
HOSTS = ["db-replica", "cache-01", "auth.internal", "mail-relay", "ldap-primary", "nas-01"]
VMS = ["ci-agent-2", "win-test", "db-shadow", "web-canary", "k8s-node-3"]
CONTAINERS = ["api-blue", "worker-old", "cache-tmp", "web-v1", "batch-runner"]
IMAGES = ["redis:7", "postgres:16", "httpd:2.4", "alpine:3.20", "python:3.12-slim", "traefik:v3"]
HOSTNAMES = ["app-07", "db-02", "edge-01", "build-04", "lab-12"]
PROFILES = ["virtual-guest", "latency-performance", "network-throughput", "balanced", "powersave"]
CONNS = ["eth2", "bond0", "br0", "wlan0", "eno2"]
DBS = ["billing", "metrics", "staging_copy", "archive_2024", "sessions", "warehouse"]
DBUSERS = ["billing_app", "metrics_ro", "report_user", "etl_svc"]
VGS = [("vg_fast", "/dev/nvme1n1", "lv_db", "120G"), ("vg_bulk", "/dev/sdd", "lv_media", "800G"),
       ("vg_ci", "/dev/vdb", "lv_ci", "40G"), ("vg_home", "/dev/sde", "lv_home", "200G")]
TIMERS = [("snapshot", "hourly"), ("report", "weekly"), ("prune", "daily"), ("healthcheck", "*:0/15")]
ARCHIVES = [("/backup/home.tar.gz", "/home"), ("/backup/var-log.tar.gz", "/var/log"),
            ("/backup/srv.tar.gz", "/srv"), ("/backup/opt-apps.tar.gz", "/opt/apps")]
SYNCS = [("/var/www/", "mirror-01:/var/www/"), ("/opt/data/", "nas-01:/exports/data/"),
         ("/home/", "backup-host:/backups/home/"), ("/etc/", "cfg-store:/hosts/web/etc/")]
DIRS = [("/srv/reports", "reports", "770"), ("/var/app/cache", "app", "750"), ("/opt/tools", "ops", "755"),
        ("/srv/ftp/incoming", "ftp", "730")]
KEYS = ["/root/.ssh/ci_key", "/root/.ssh/backup_key", "/home/svc_deploy/.ssh/id_ed25519"]
MODSTREAMS = ["postgresql:16", "php:8.2", "ruby:3.3", "nginx:1.24", "maven:3.8"]
ZONES = ["dmz", "public", "trusted", "work"]
QUOTA_FS = ["/home", "/srv", "/data"]
FIND_ROOTS = ["/var", "/home", "/srv", "/opt"]

# ------------------------------------------------------------------ templates
# Each template: kind, list of phrasings (with {slots}), fill iterator, and a
# function fill -> steps.  Phrasings are chosen round-robin so the same sequence
# appears under several wordings.

def _t(kind, phrasings, fills, steps):
    return {"kind": kind, "phrasings": phrasings, "fills": fills, "steps": steps}


TEMPLATES = [
    # ------------------------------------------------------------ diagnose
    _t("diagnose",
       ["{svc} isn't responding, work out why", "why is {svc} down?", "figure out what's wrong with {svc}",
        "{svc} looks broken, check it and pull its log"],
       [dict(svc=s) for s in SERVICES],
       lambda f: (S("services", "status", unit=f"{f['svc']}.service"),
                  S("services", "logs", unit=f"{f['svc']}.service"))),
    _t("diagnose",
       ["{svc} is down, find out why and bring it back", "get {svc} running again and tell me what happened",
        "{svc} died overnight, diagnose it and restore service"],
       [dict(svc=s) for s in SERVICES],
       lambda f: (S("services", "status", unit=f"{f['svc']}.service"),
                  S("services", "logs", unit=f"{f['svc']}.service"),
                  S("services", "start", unit=f"{f['svc']}.service"),
                  S("services", "status", unit=f"{f['svc']}.service"))),
    _t("diagnose",
       ["load is high, find out what's using the CPU", "the server is sluggish, tell me what's hogging it",
        "something is pegging the box, identify it"],
       [dict()],
       lambda f: (S("performance", "load"), S("processes", "top"))),
    _t("diagnose",
       ["disk is nearly full under {root}, find the big files", "where did the space under {root} go?",
        "{root} is filling up, locate what's large"],
       [dict(root=r) for r in FIND_ROOTS],
       lambda f: (S("disk", "usage"), S("files", "find", path=f["root"], type="f"))),
    _t("diagnose",
       ["clients can't reach port {port}, check whether it's listening and whether the firewall passes it",
        "is anything on {port} and does the firewall allow it?"],
       [dict(port=p.split("/")[0]) for p in PORTS],
       lambda f: (S("network", "listening"), S("firewall", "list"))),
    _t("diagnose",
       ["check whether the clock is in sync and where it's syncing from", "is time drifting here? check tracking and sources"],
       [dict()],
       lambda f: (S("chrony", "tracking"), S("chrony", "sources"))),
    _t("diagnose",
       ["httpd won't start after my edit, find the problem", "apache is failing to come up, check state and test the config"],
       [dict()],
       lambda f: (S("services", "status", unit="httpd.service"), S("httpd", "configtest"))),
    _t("diagnose",
       ["nginx refuses to start, find out why", "nginx is failing, check status, logs and the config"],
       [dict()],
       lambda f: (S("services", "status", unit="nginx.service"), S("services", "logs", unit="nginx.service"),
                  S("nginx", "configtest"))),
    _t("diagnose",
       ["{host} won't resolve, check the resolver config then try it", "dns for {host} is failing, look at resolv.conf and dig it"],
       [dict(host=h) for h in HOSTS],
       lambda f: (S("dns", "resolv_view"), S("dns", "dig", name=f["host"]))),
    _t("diagnose",
       ["the {mod} module isn't coming up, see if it's loaded and what the kernel says",
        "check whether {mod} is loaded and grep dmesg for it"],
       [dict(mod=m) for m in MODULES],
       lambda f: (S("kernel_modules", "lsmod"), S("logs", "dmesg_query", grep=f["mod"]))),
    _t("diagnose",
       ["is {dev} dying? check its health and the kernel messages", "run a health check on {dev} and see if dmesg complains"],
       [dict(dev=d) for d in DEVICES],
       lambda f: (S("disk", "smart", device=f["dev"]), S("logs", "dmesg_query", grep=f["dev"].split("/")[-1]))),
    _t("diagnose",
       ["selinux seems to be blocking {comm}, confirm the mode and show the denials",
        "check enforcing mode and pull audit denials for {comm}"],
       [dict(comm=c) for c in ["nginx", "sshd", "smbd", "named", "postgres", "mysqld"]],
       lambda f: (S("selinux", "getenforce"), S("audit", "search-by-comm", comm=f["comm"]))),
    _t("diagnose",
       ["the machine rebooted on its own, show boot errors and kernel errors", "we crashed last night, pull boot and kernel error lines"],
       [dict()],
       lambda f: (S("logs", "boot_errors"), S("logs", "dmesg_errors"))),
    _t("diagnose",
       ["the VM {vm} is unreachable, check it and start it if it's off", "is {vm} running? start it if not"],
       [dict(vm=v) for v in VMS],
       lambda f: (S("virsh", "dominfo", domain=f["vm"]), S("virsh", "start", domain=f["vm"]))),
    _t("diagnose",
       ["postgres is refusing connections, check it and read its service log", "check postgresql status then its journal"],
       [dict()],
       lambda f: (S("postgresql", "status"), S("services", "logs", unit="postgresql.service"))),
    _t("diagnose",
       ["container {ctr} keeps dying, check the running list and its logs", "why does {ctr} exit? list containers and show its log"],
       [dict(ctr=c) for c in CONTAINERS],
       lambda f: (S("podman", "ps"), S("podman", "logs", container=f["ctr"]))),
    _t("diagnose",
       ["io feels slow, show disk stats and the memory picture", "check iostat and vmstat, something is thrashing"],
       [dict()],
       lambda f: (S("performance", "iostat"), S("performance", "vmstat"))),
    # ------------------------------------------------------- change_verify
    _t("change_verify",
       ["restart {svc} and confirm it came back", "bounce {svc} then verify it's active", "restart {svc}, make sure it's up afterwards"],
       [dict(svc=s) for s in SERVICES],
       lambda f: (S("services", "restart", unit=f"{f['svc']}.service"), S("services", "status", unit=f"{f['svc']}.service"))),
    _t("change_verify",
       ["enable and start {svc}, then check it", "get {svc} enabled at boot and running now, verify it"],
       [dict(svc=s) for s in SERVICES],
       lambda f: (S("services", "enable", unit=f"{f['svc']}.service"), S("services", "start", unit=f"{f['svc']}.service"),
                  S("services", "status", unit=f"{f['svc']}.service"))),
    _t("change_verify",
       ["stop and disable {svc}, confirm it's inactive", "shut {svc} down for good and verify"],
       [dict(svc=s) for s in SERVICES],
       lambda f: (S("services", "stop", unit=f"{f['svc']}.service"), S("services", "disable", unit=f"{f['svc']}.service"),
                  S("services", "status", unit=f"{f['svc']}.service"))),
    _t("change_verify",
       ["open {port} permanently and show me it's in the rules", "allow {port} through the firewall, reload, and list the rules"],
       [dict(port=p) for p in PORTS],
       lambda f: (S("firewall", "add_port", port=f["port"]), S("firewall", "reload"), S("firewall", "list"))),
    _t("change_verify",
       ["allow the {fsvc} service in the firewall and confirm", "add {fsvc} to the firewall, reload, check it's there"],
       [dict(fsvc=s) for s in FW_SERVICES],
       lambda f: (S("firewall", "add_service", service=f["fsvc"]), S("firewall", "reload"), S("firewall", "query", service=f["fsvc"]))),
    _t("change_verify",
       ["set {key} to {val}, persist it, and read it back", "change {key} to {val} now and permanently, then verify"],
       [dict(key=k, val=v) for k, v in SYSCTLS],
       lambda f: (S("sysctl", "set", key=f["key"], value=f["val"]), S("sysctl", "persist", key=f["key"], value=f["val"]),
                  S("sysctl", "get", key=f["key"]))),
    _t("change_verify",
       ["set selinux to {mode} and confirm", "switch selinux to {mode} mode then check it"],
       [dict(mode=m) for m in ["permissive", "enforcing"]],
       lambda f: (S("selinux", "setenforce", mode=f["mode"]), S("selinux", "getenforce"))),
    _t("change_verify",
       ["turn {boolean} on and read it back", "enable the {boolean} boolean and verify"],
       [dict(boolean=b) for b in BOOLEANS],
       lambda f: (S("selinux", "setsebool", boolean=f["boolean"], value="on"), S("selinux", "getsebool", boolean=f["boolean"]))),
    _t("change_verify",
       ["add user {user}, put them in {group}, show me the account", "create {user} in group {group} and confirm"],
       [dict(user=u, group=g) for u, g in zip(USERS, itertools.cycle(GROUPS))],
       lambda f: (S("users", "add", user=f["user"]), S("users", "add_to_group", user=f["user"], group=f["group"]),
                  S("users", "info", user=f["user"]))),
    _t("change_verify",
       ["lock {user} and show the account state", "disable login for {user} then confirm"],
       [dict(user=u) for u in USERS],
       lambda f: (S("users", "lock", user=f["user"]), S("users", "info", user=f["user"]))),
    _t("change_verify",
       ["test the nginx config and reload it", "reload nginx, config test first"],
       [dict()],
       lambda f: (S("nginx", "configtest"), S("nginx", "reload"))),
    _t("change_verify",
       ["test the httpd config and restart it", "restart apache after checking the config parses"],
       [dict()],
       lambda f: (S("httpd", "configtest"), S("httpd", "restart"))),
    _t("change_verify",
       ["mount {part} on {mnt} and verify", "attach {part} at {mnt} then list block devices"],
       [dict(part=p, mnt=m) for p, m in zip(PARTS, MOUNTS)],
       lambda f: (S("disk", "mount", device=f["part"], mount_point=f["mnt"]), S("disk", "list"))),
    _t("change_verify",
       ["switch tuned to {prof} and confirm", "apply the {prof} tuned profile then check the active one"],
       [dict(prof=p) for p in PROFILES],
       lambda f: (S("tuned", "profile", profile=f["prof"]), S("tuned", "active"))),
    _t("change_verify",
       ["rename this host to {hn} and show the status", "set hostname {hn} and verify"],
       [dict(hn=h) for h in HOSTNAMES],
       lambda f: (S("hostname", "set-hostname", name=f["hn"]), S("hostname", "status"))),
    _t("change_verify",
       ["bring {conn} up and show the devices", "activate connection {conn} then check device status"],
       [dict(conn=c) for c in CONNS],
       lambda f: (S("nmcli", "connection_up", name=f["conn"]), S("nmcli", "device_status"))),
    _t("change_verify",
       ["load {mod} and confirm it's loaded", "modprobe {mod} then check lsmod"],
       [dict(mod=m) for m in MODULES],
       lambda f: (S("kernel_modules", "modprobe", module=f["mod"]), S("kernel_modules", "lsmod"))),
    _t("change_verify",
       ["make {zone} the default firewall zone and show the zones", "set default zone {zone}, then list zones"],
       [dict(zone=z) for z in ZONES],
       lambda f: (S("firewall", "set_default_zone", zone=f["zone"]), S("firewall", "get_zones"))),
    _t("change_verify",
       ["turn quotas on for {fs} and pull the report", "enable quota enforcement on {fs} then show repquota"],
       [dict(fs=q) for q in QUOTA_FS],
       lambda f: (S("quota", "quotaon", filesystem=f["fs"]), S("quota", "repquota"))),
    _t("change_verify",
       ["step the clock now and show tracking", "force a time sync and confirm the offset"],
       [dict()],
       lambda f: (S("chrony", "makestep"), S("chrony", "tracking"))),
    # ---------------------------------------------------- install_configure
    _t("install_configure",
       ["install {pkg}, enable it, start it, and confirm it's running", "set up {pkg} as a running service"],
       [dict(pkg=p, unit=u) for p, u in PKG_TO_UNIT.items()],
       lambda f: (S("packages", "install", packages=[f["pkg"]]),
                  S("services", "enable", unit=f["unit"] if f["unit"].endswith(".socket") else f"{f['unit']}.service"),
                  S("services", "start", unit=f["unit"] if f["unit"].endswith(".socket") else f"{f['unit']}.service"),
                  S("services", "status", unit=f["unit"] if f["unit"].endswith(".socket") else f"{f['unit']}.service"))),
    _t("install_configure",
       ["install {pkg} then show its info", "get {pkg} installed and tell me about it"],
       [dict(pkg=p) for p in PACKAGES],
       lambda f: (S("packages", "install", packages=[f["pkg"]]), S("packages", "info", package=f["pkg"]))),
    _t("install_configure",
       ["install postgresql-server, start it, and create a database {db}", "set up postgres with a {db} database"],
       [dict(db=d) for d in DBS],
       lambda f: (S("packages", "install", packages=["postgresql-server"]), S("services", "start", unit="postgresql.service"),
                  S("postgresql", "createdb", dbname=f["db"]))),
    _t("install_configure",
       ["create a postgres role {role} and a database {db}, then confirm the server is up",
        "add role {role} and db {db} in postgres and check status"],
       [dict(role=r, db=d) for r, d in zip(DBUSERS, DBS)],
       lambda f: (S("postgresql", "createuser", rolename=f["role"]), S("postgresql", "createdb", dbname=f["db"]),
                  S("postgresql", "status"))),
    _t("install_configure",
       ["install mariadb-server, start it, create database {db} and grant {user} on it",
        "stand up mariadb with a {db} database for {user}"],
       [dict(db=d, user=u) for d, u in zip(DBS, DBUSERS)],
       lambda f: (S("packages", "install", packages=["mariadb-server"]), S("services", "start", unit="mariadb.service"),
                  S("mariadb", "query", sql=f"CREATE DATABASE {f['db']};"), S("mariadb", "grant", user=f["user"], database=f["db"]))),
    _t("install_configure",
       ["install httpd, allow {fsvc} in the firewall, start it, confirm", "put up apache with {fsvc} opened and verify"],
       [dict(fsvc=s) for s in ["http", "https"]],
       lambda f: (S("packages", "install", packages=["httpd"]), S("firewall", "add_service", service=f["fsvc"]),
                  S("services", "start", unit="httpd.service"), S("services", "status", unit="httpd.service"))),
    _t("install_configure",
       ["pull {img} and run it", "fetch the {img} image and start a container from it"],
       [dict(img=i) for i in IMAGES],
       lambda f: (S("podman", "pull", image=f["img"]), S("podman", "run", image=f["img"]))),
    _t("install_configure",
       ["pull {img}, run it, and show me the running containers", "start a {img} container and list what's running"],
       [dict(img=i) for i in IMAGES],
       lambda f: (S("podman", "pull", image=f["img"]), S("podman", "run", image=f["img"]), S("podman", "ps"))),
    _t("install_configure",
       ["create volume group {vg} on {pv} and a {size} volume {lv}", "set up lvm: pv {pv}, vg {vg}, lv {lv} of {size}"],
       [dict(vg=vg, pv=pv, lv=lv, size=sz) for vg, pv, lv, sz in VGS],
       lambda f: (S("lvm", "pvcreate", pv=f["pv"]), S("lvm", "vgcreate", vg=f["vg"], pv=f["pv"]),
                  S("lvm", "lvcreate", lv_name=f["lv"], vg=f["vg"], size=f["size"]))),
    _t("install_configure",
       ["enable the {stream} module stream and install it", "switch on {stream} and install the module"],
       [dict(stream=s) for s in MODSTREAMS],
       lambda f: (S("dnf_modules", "enable", module=f["stream"]), S("dnf_modules", "install", module=f["stream"]))),
    _t("install_configure",
       ["create {name}.timer running {name}.service {cal}, enable it, list timers",
        "add a {cal} timer for {name}.service and confirm it's listed"],
       [dict(name=n, cal=c) for n, c in TIMERS],
       lambda f: (S("systemd_timers", "create", timer=f"{f['name']}.timer",
                    content=f"[Timer]\nOnCalendar={f['cal']}\n[Install]\nWantedBy=timers.target"),
                  S("systemd_timers", "enable", timer=f"{f['name']}.timer"), S("systemd_timers", "list-timers"))),
    _t("install_configure",
       ["install {pkg} and open {port} for it", "get {pkg} in and allow {port} through the firewall"],
       [dict(pkg=p, port=q) for p, q in zip(PACKAGES[:12], PORTS)],
       lambda f: (S("packages", "install", packages=[f["pkg"]]), S("firewall", "add_port", port=f["port"]), S("firewall", "reload"))),
    # ---------------------------------------------------------- inspect_act
    _t("inspect_act",
       ["see what's on port {port} and kill it", "find the process bound to {port} and stop it"],
       [dict(port=p.split("/")[0], pid=pid) for p, pid in zip(PORTS, [3101, 4870, 2219, 5533, 1907, 6644, 2780, 3390, 4412, 5150, 2011, 3777])],
       lambda f: (S("network", "listening"), S("processes", "signal", pid=f["pid"]))),
    _t("inspect_act",
       ["list timers and disable {name}.timer", "check the timers, then turn off {name}.timer"],
       [dict(name=n) for n, _ in TIMERS],
       lambda f: (S("systemd_timers", "list-timers"), S("systemd_timers", "disable", timer=f"{f['name']}.timer"))),
    _t("inspect_act",
       ["list containers and stop {ctr}", "show running containers, then stop the one called {ctr}"],
       [dict(ctr=c) for c in CONTAINERS],
       lambda f: (S("podman", "ps"), S("podman", "stop", container=f["ctr"]))),
    _t("inspect_act",
       ["list containers, stop {ctr}, and remove it", "clean up {ctr}: list, stop, rm"],
       [dict(ctr=c) for c in CONTAINERS],
       lambda f: (S("podman", "ps"), S("podman", "stop", container=f["ctr"]), S("podman", "rm", container=f["ctr"]))),
    _t("inspect_act",
       ["show the VMs and shut {vm} down cleanly", "list domains, then a clean shutdown of {vm}"],
       [dict(vm=v) for v in VMS],
       lambda f: (S("virsh", "list"), S("virsh", "shutdown", domain=f["vm"]))),
    _t("inspect_act",
       ["show the firewall rules and remove {port}", "check the rules, then close {port}"],
       [dict(port=p) for p in PORTS],
       lambda f: (S("firewall", "list"), S("firewall", "remove_port", port=f["port"]), S("firewall", "reload"))),
    _t("inspect_act",
       ["list users and delete {user}", "check the account list, then remove {user}"],
       [dict(user=u) for u in USERS],
       lambda f: (S("users", "list"), S("users", "delete", user=f["user"]))),
    _t("inspect_act",
       ["show loaded modules and unload {mod}", "check lsmod, then rmmod {mod}"],
       [dict(mod=m) for m in MODULES],
       lambda f: (S("kernel_modules", "lsmod"), S("kernel_modules", "rmmod", module=f["mod"]))),
    _t("inspect_act",
       ["show the queued at jobs and remove job {job}", "list atq then delete job {job}"],
       [dict(job=j) for j in ["3", "7", "12", "21"]],
       lambda f: (S("at", "atq"), S("at", "atrm", job_id=f["job"]))),
    # ----------------------------------------------------------------- chain
    _t("chain",
       ["archive {src} to {arc} and verify the archive", "back up {src} into {arc}, then check it"],
       [dict(arc=a, src=s) for a, s in ARCHIVES],
       lambda f: (S("tar", "create_gz", archive=f["arc"], sources=[f["src"]]), S("tar", "verify", archive=f["arc"]))),
    _t("chain",
       ["dry-run a sync of {src} to {dst}, then do it for real", "rsync {src} to {dst}: dry run first, then sync"],
       [dict(src=s, dst=d) for s, d in SYNCS],
       lambda f: (S("rsync", "dry-run", src=f["src"], dest=f["dst"]), S("rsync", "sync", src=f["src"], dest=f["dst"]))),
    _t("chain",
       ["dump {db} to {out} then drop it", "back up the {db} database to {out} and remove it"],
       [dict(db=d, out=f"/backup/{d}.sql") for d in DBS],
       lambda f: (S("postgresql", "pg_dump", dbname=f["db"], output_file=f["out"]), S("postgresql", "dropdb", dbname=f["db"]))),
    _t("chain",
       ["make {path}, give it to {owner} with mode {mode}, show me the result", "create {path} owned by {owner}, mode {mode}, and stat it"],
       [dict(path=p, owner=o, mode=m) for p, o, m in DIRS],
       lambda f: (S("files", "mkdir", path=f["path"]), S("files", "chown", owner=f["owner"], path=f["path"]),
                  S("files", "chmod", mode=f["mode"], path=f["path"]), S("files", "stat", path=f["path"]))),
    _t("chain",
       ["generate a key at {key} and add its public half to authorized_keys", "make an ssh key {key} and authorize it"],
       [dict(key=k) for k in KEYS],
       lambda f: (S("ssh_keys", "keygen", path=f["key"]), S("ssh_keys", "authorized_keys_add", key=f"{f['key']}.pub"))),
    _t("chain",
       ["extend {lv} by {size} and show the logical volumes", "grow {lv} {size} then display lvs"],
       [dict(lv=f"/dev/{vg}/{lv}", size="20G") for vg, _, lv, _ in VGS],
       lambda f: (S("lvm", "lvextend", lv=f["lv"], size=f["size"]), S("lvm", "lvdisplay"))),
    _t("chain",
       ["copy {src} to {dst} and confirm the copy exists", "duplicate {src} as {dst}, then stat it"],
       [dict(src=s, dst=d) for s, d in [("/etc/nginx/nginx.conf", "/root/nginx.conf.bak"), ("/etc/fstab", "/root/fstab.bak"),
                                         ("/etc/ssh/sshd_config", "/root/sshd_config.bak"), ("/etc/hosts", "/root/hosts.bak")]],
       lambda f: (S("files", "copy", src=f["src"], dst=f["dst"]), S("files", "stat", path=f["dst"]))),
    _t("chain",
       ["schedule {cmd} at {when} and show the queue", "queue a one-off job at {when} that runs {cmd}, then list it"],
       [dict(cmd=c, when=w) for c, w in [("/opt/scripts/reindex.sh", "23:00"), ("/usr/bin/updatedb", "3:30 tomorrow"),
                                          ("/opt/scripts/rotate-keys.sh", "now + 2 hours"), ("/usr/sbin/fstrim -av", "1:00 tomorrow")]],
       lambda f: (S("at", "schedule", time=f["when"], command=f["cmd"]), S("at", "atq"))),
    _t("chain",
       ["add an audit rule watching {path} and list the rules", "watch {path} with auditd, then show the rule list"],
       [dict(path=p, key=k) for p, k in [("/etc/sudoers", "sudoers_changes"), ("/etc/passwd", "passwd_changes"),
                                          ("/etc/ssh/sshd_config", "sshd_config_changes"), ("/var/log/audit", "audit_log_access")]],
       lambda f: (S("audit", "add-rule", rule=f"-w {f['path']} -p wa -k {f['key']}"), S("audit", "list"))),
]


_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_TOKEN.findall(text.lower()))


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / max(1, len(a | b))


def generate(per_template: int = 14, seed: int = 4) -> list:
    """Deterministic scenario list with the held-out multi-step pool excluded."""
    from finetune.scenarios.eval_pool_multistep import EVAL_MULTISTEP
    held = [(_tokens(s.user_input), tuple((st.tool, st.operation, tuple(sorted(st.args.items()))) for st in s.steps))
            for s in EVAL_MULTISTEP]
    rng = random.Random(seed)
    out, n = [], 0
    for ti, tpl in enumerate(TEMPLATES):
        fills = list(tpl["fills"])
        rng.shuffle(fills)
        for fi, fill in enumerate(fills[:per_template]):
            phrasing = tpl["phrasings"][fi % len(tpl["phrasings"])]
            text = phrasing.format(**fill)
            steps = tuple(tpl["steps"](fill))
            sig = tuple((st.tool, st.operation, tuple(sorted(st.args.items()))) for st in steps)
            toks = _tokens(text)
            if any(sig == hsig or _jaccard(toks, htok) > 0.7 for htok, hsig in held):
                continue
            n += 1
            out.append(V4(id=f"ms-v4-{n:04d}", kind=tpl["kind"], user_input=text, steps=steps))
    return out


def check_all(scenarios: list) -> None:
    ids = [s.id for s in scenarios]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for s in scenarios:
        assert 2 <= len(s.steps) <= 5, f"{s.id}: 2-5 steps"
        for st in s.steps:
            spec = coreimports.registry.get(st.tool)
            assert spec is not None, f"{s.id}: unknown tool {st.tool}"
            assert st.operation in spec.ops, f"{s.id}: unknown op {st.tool}.{st.operation}"
            coreimports.validate_arguments(spec, dict(st.args))


def load_all() -> list:
    scenarios = generate()
    check_all(scenarios)
    return scenarios
