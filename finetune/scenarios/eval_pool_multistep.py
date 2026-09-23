"""finetune/scenarios/eval_pool_multistep.py -- HELD-OUT multi-step eval pool. Never train on this.

One operator request that needs a SEQUENCE of operations.  The reference sequence is the
order a careful operator would take; each step's simulated result is fed back before the
next call, exactly as the runtime does.  After the last step the correct move is to answer
in English, not to call again.

Written 2026-09-22, before any multi-step training data existed (corpus v3 has at most
one call per turn), so it stays held out for corpus v4 and later.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    tool: str
    operation: str
    args: dict            # includes "operation"


@dataclass(frozen=True)
class MultiStep:
    id: str
    kind: str             # diagnose | change_verify | install_configure | inspect_act | chain
    user_input: str
    steps: tuple          # 2 to 5 Step


def S(tool, operation, **kw):
    return Step(tool=tool, operation=operation, args={"operation": operation, **kw})


EVAL_MULTISTEP = [
    # ---------------------------------------------------------------- diagnose
    MultiStep("ms-eval-0001", "diagnose", "why is nginx not starting?", (
        S("services", "status", unit="nginx.service"),
        S("services", "logs", unit="nginx.service"),
        S("nginx", "configtest"),
    )),
    MultiStep("ms-eval-0002", "diagnose", "postgresql is down, figure out why and get it back up", (
        S("services", "status", unit="postgresql.service"),
        S("services", "logs", unit="postgresql.service"),
        S("services", "start", unit="postgresql.service"),
        S("services", "status", unit="postgresql.service"),
    )),
    MultiStep("ms-eval-0003", "diagnose", "the box feels slow, find out what is eating the CPU", (
        S("performance", "load"),
        S("processes", "top"),
    )),
    MultiStep("ms-eval-0004", "diagnose", "we're out of disk on the root filesystem, find where the space went", (
        S("disk", "usage"),
        S("files", "find", path="/", type="f"),
    )),
    MultiStep("ms-eval-0005", "diagnose", "sshd keeps rejecting logins, check its state and recent log lines", (
        S("services", "status", unit="sshd.service"),
        S("services", "logs", unit="sshd.service"),
    )),
    MultiStep("ms-eval-0006", "diagnose", "the app can't reach the database on port 5432, check whether anything is listening there and whether the firewall allows it", (
        S("network", "listening"),
        S("firewall", "list"),
    )),
    MultiStep("ms-eval-0007", "diagnose", "is the time on this server drifting? check sync status and the sources", (
        S("chrony", "tracking"),
        S("chrony", "sources"),
    )),
    MultiStep("ms-eval-0008", "diagnose", "httpd won't come up after the config change, tell me what's wrong", (
        S("services", "status", unit="httpd.service"),
        S("httpd", "configtest"),
    )),
    MultiStep("ms-eval-0009", "diagnose", "name resolution is failing for internal hosts, look at the resolver config and try resolving db-primary", (
        S("dns", "resolv_view"),
        S("dns", "dig", name="db-primary"),
    )),
    MultiStep("ms-eval-0010", "diagnose", "the nvidia module isn't loading, check whether it's present and what the kernel says", (
        S("kernel_modules", "lsmod"),
        S("logs", "dmesg_query", grep="nvidia"),
    )),
    MultiStep("ms-eval-0011", "diagnose", "mariadb is refusing connections, check service state then its logs", (
        S("mariadb", "status"),
        S("services", "logs", unit="mariadb.service"),
    )),
    MultiStep("ms-eval-0012", "diagnose", "the VM build-runner is unreachable, check whether it is running and start it if not", (
        S("virsh", "dominfo", domain="build-runner"),
        S("virsh", "start", domain="build-runner"),
    )),
    MultiStep("ms-eval-0013", "diagnose", "something is being blocked by selinux for httpd, confirm enforcing mode and pull the recent denials", (
        S("selinux", "getenforce"),
        S("audit", "search-by-comm", comm="httpd"),
    )),
    MultiStep("ms-eval-0014", "diagnose", "we had a kernel panic overnight, show boot errors and the kernel error lines", (
        S("logs", "boot_errors"),
        S("logs", "dmesg_errors"),
    )),
    MultiStep("ms-eval-0015", "diagnose", "is /dev/sda failing? check its health and the kernel messages about it", (
        S("disk", "smart", device="/dev/sda"),
        S("logs", "dmesg_query", grep="sda"),
    )),
    # ---------------------------------------------------------- change_verify
    MultiStep("ms-eval-0016", "change_verify", "restart crond and make sure it actually came back", (
        S("services", "restart", unit="crond.service"),
        S("services", "status", unit="crond.service"),
    )),
    MultiStep("ms-eval-0017", "change_verify", "open 9090/tcp permanently and confirm it shows in the active rules", (
        S("firewall", "add_port", port="9090/tcp"),
        S("firewall", "reload"),
        S("firewall", "list"),
    )),
    MultiStep("ms-eval-0018", "change_verify", "set net.ipv4.ip_forward to 1 now, make it stick across reboots, and read it back", (
        S("sysctl", "set", key="net.ipv4.ip_forward", value="1"),
        S("sysctl", "persist", key="net.ipv4.ip_forward", value="1"),
        S("sysctl", "get", key="net.ipv4.ip_forward"),
    )),
    MultiStep("ms-eval-0019", "change_verify", "enable and start the chronyd service, then check it is active", (
        S("services", "enable", unit="chronyd.service"),
        S("services", "start", unit="chronyd.service"),
        S("services", "status", unit="chronyd.service"),
    )),
    MultiStep("ms-eval-0020", "change_verify", "put selinux in permissive mode for now and confirm the change took", (
        S("selinux", "setenforce", mode="permissive"),
        S("selinux", "getenforce"),
    )),
    MultiStep("ms-eval-0021", "change_verify", "add user jsmith, put them in the wheel group, and show me the result", (
        S("users", "add", user="jsmith"),
        S("users", "add_to_group", user="jsmith", group="wheel"),
        S("users", "info", user="jsmith"),
    )),
    MultiStep("ms-eval-0022", "change_verify", "reload nginx after the config edit, but test the config first", (
        S("nginx", "configtest"),
        S("nginx", "reload"),
    )),
    MultiStep("ms-eval-0023", "change_verify", "mount /dev/sdb1 at /mnt/data and verify it shows up", (
        S("disk", "mount", device="/dev/sdb1", mount_point="/mnt/data"),
        S("disk", "list"),
    )),
    MultiStep("ms-eval-0024", "change_verify", "switch the tuned profile to throughput-performance and confirm it is active", (
        S("tuned", "profile", profile="throughput-performance"),
        S("tuned", "active"),
    )),
    MultiStep("ms-eval-0025", "change_verify", "set the hostname to web-03 and show me the new status", (
        S("hostname", "set-hostname", name="web-03"),
        S("hostname", "status"),
    )),
    MultiStep("ms-eval-0026", "change_verify", "bring connection eth1 up and check the device list", (
        S("nmcli", "connection_up", name="eth1"),
        S("nmcli", "device_status"),
    )),
    MultiStep("ms-eval-0027", "change_verify", "lock the account for user tmp_contractor and show its state", (
        S("users", "lock", user="tmp_contractor"),
        S("users", "info", user="tmp_contractor"),
    )),
    MultiStep("ms-eval-0028", "change_verify", "load the vfio module and confirm it is loaded", (
        S("kernel_modules", "modprobe", module="vfio"),
        S("kernel_modules", "lsmod"),
    )),
    MultiStep("ms-eval-0029", "change_verify", "turn on the httpd_can_network_connect boolean and read it back", (
        S("selinux", "setsebool", boolean="httpd_can_network_connect", value="on"),
        S("selinux", "getsebool", boolean="httpd_can_network_connect"),
    )),
    MultiStep("ms-eval-0030", "change_verify", "stop the ntpd service, disable it, and confirm it is inactive", (
        S("services", "stop", unit="ntpd.service"),
        S("services", "disable", unit="ntpd.service"),
        S("services", "status", unit="ntpd.service"),
    )),
    # ------------------------------------------------------- install_configure
    MultiStep("ms-eval-0031", "install_configure", "install nginx, enable it, start it, and check it is running", (
        S("packages", "install", packages=["nginx"]),
        S("services", "enable", unit="nginx.service"),
        S("services", "start", unit="nginx.service"),
        S("services", "status", unit="nginx.service"),
    )),
    MultiStep("ms-eval-0032", "install_configure", "install postgresql-server, start it, and create a database called inventory", (
        S("packages", "install", packages=["postgresql-server"]),
        S("services", "start", unit="postgresql.service"),
        S("postgresql", "createdb", dbname="inventory"),
    )),
    MultiStep("ms-eval-0033", "install_configure", "install chrony and get it running, then check whether it is tracking a source", (
        S("packages", "install", packages=["chrony"]),
        S("services", "start", unit="chronyd.service"),
        S("chrony", "tracking"),
    )),
    MultiStep("ms-eval-0034", "install_configure", "install httpd, open http in the firewall, start it, and confirm it is up", (
        S("packages", "install", packages=["httpd"]),
        S("firewall", "add_service", service="http"),
        S("services", "start", unit="httpd.service"),
        S("services", "status", unit="httpd.service"),
    )),
    MultiStep("ms-eval-0035", "install_configure", "pull the nginx:latest image and run a container from it", (
        S("podman", "pull", image="nginx:latest"),
        S("podman", "run", image="nginx:latest"),
    )),
    MultiStep("ms-eval-0036", "install_configure", "install mariadb-server, start it, and create a database named shop with a user shop_app granted on it", (
        S("packages", "install", packages=["mariadb-server"]),
        S("services", "start", unit="mariadb.service"),
        S("mariadb", "query", sql="CREATE DATABASE shop;"),
        S("mariadb", "grant", user="shop_app", database="shop"),
    )),
    MultiStep("ms-eval-0037", "install_configure", "set up a new volume group vg_data on /dev/sdc and carve a 50G logical volume lv_app from it", (
        S("lvm", "pvcreate", pv="/dev/sdc"),
        S("lvm", "vgcreate", vg="vg_data", pv="/dev/sdc"),
        S("lvm", "lvcreate", lv_name="lv_app", vg="vg_data", size="50G"),
    )),
    MultiStep("ms-eval-0038", "install_configure", "install the tree package and then show me its info", (
        S("packages", "install", packages=["tree"]),
        S("packages", "info", package="tree"),
    )),
    MultiStep("ms-eval-0039", "install_configure", "enable the nodejs:20 module stream and install it", (
        S("dnf_modules", "enable", module="nodejs:20"),
        S("dnf_modules", "install", module="nodejs:20"),
    )),
    MultiStep("ms-eval-0040", "install_configure", "create a timer backup.timer that runs backup.service daily, enable it, and list timers to confirm", (
        S("systemd_timers", "create", timer="backup.timer", content="[Timer]\nOnCalendar=daily\n[Install]\nWantedBy=timers.target"),
        S("systemd_timers", "enable", timer="backup.timer"),
        S("systemd_timers", "list-timers"),
    )),
    # ------------------------------------------------------------ inspect_act
    MultiStep("ms-eval-0041", "inspect_act", "find out what process is holding port 8080 and kill it", (
        S("network", "listening"),
        S("processes", "signal", pid=4242),
    )),
    MultiStep("ms-eval-0042", "inspect_act", "check which timers are enabled and disable the one named cleanup.timer", (
        S("systemd_timers", "list-timers"),
        S("systemd_timers", "disable", timer="cleanup.timer"),
    )),
    MultiStep("ms-eval-0043", "inspect_act", "list the running containers and stop the one called web-old", (
        S("podman", "ps"),
        S("podman", "stop", container="web-old"),
    )),
    MultiStep("ms-eval-0044", "inspect_act", "show the current default zone and then make internal the default", (
        S("firewall", "get_zones"),
        S("firewall", "set_default_zone", zone="internal"),
    )),
    MultiStep("ms-eval-0045", "inspect_act", "check the VMs that are defined and shut down staging-db cleanly", (
        S("virsh", "list"),
        S("virsh", "shutdown", domain="staging-db"),
    )),
    # -------------------------------------------------------------------- chain
    MultiStep("ms-eval-0046", "chain", "back up /etc into /backup/etc.tar.gz and then verify the archive", (
        S("tar", "create_gz", archive="/backup/etc.tar.gz", sources=["/etc"]),
        S("tar", "verify", archive="/backup/etc.tar.gz"),
    )),
    MultiStep("ms-eval-0047", "chain", "do a dry run of syncing /srv/www/ to backup-host:/srv/www/ and if it looks fine run the real sync", (
        S("rsync", "dry-run", src="/srv/www/", dest="backup-host:/srv/www/"),
        S("rsync", "sync", src="/srv/www/", dest="backup-host:/srv/www/"),
    )),
    MultiStep("ms-eval-0048", "chain", "dump the analytics database to /backup/analytics.sql then drop it", (
        S("postgresql", "pg_dump", dbname="analytics", output_file="/backup/analytics.sql"),
        S("postgresql", "dropdb", dbname="analytics"),
    )),
    MultiStep("ms-eval-0049", "chain", "make /srv/uploads, hand it to user www with mode 750, and show me its details", (
        S("files", "mkdir", path="/srv/uploads"),
        S("files", "chown", owner="www", path="/srv/uploads"),
        S("files", "chmod", mode="750", path="/srv/uploads"),
        S("files", "stat", path="/srv/uploads"),
    )),
    MultiStep("ms-eval-0050", "chain", "generate an ssh key at /root/.ssh/deploy_key and add its public key to authorized_keys", (
        S("ssh_keys", "keygen", path="/root/.ssh/deploy_key"),
        S("ssh_keys", "authorized_keys_add", key="/root/.ssh/deploy_key.pub"),
    )),
]


def check_pool() -> None:
    from finetune import coreimports
    ids = [s.id for s in EVAL_MULTISTEP]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for s in EVAL_MULTISTEP:
        assert 2 <= len(s.steps) <= 5, f"{s.id}: 2-5 steps"
        for st in s.steps:
            spec = coreimports.registry.get(st.tool)
            assert spec is not None, f"{s.id}: unknown tool {st.tool}"
            assert st.operation in spec.ops, f"{s.id}: unknown op {st.tool}.{st.operation}"
            coreimports.validate_arguments(spec, dict(st.args))


check_pool()
