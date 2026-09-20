"""finetune/scenarios/eval_pool_multiturn.py -- HELD-OUT multi-turn eval pool. Never train on this."""
from __future__ import annotations

import re

from finetune.scenarios_v3 import V3, Turn, check_module
from finetune.scenarios_v3 import load_all as _load_all_v3

EVAL_MULTITURN = [
    # -- services --------------------------------------------------------- #
    V3(id="mt-eval-0001", tool="services", kind="followup", turns=(
        Turn(user_input="what's the current status on nginx.service", tool="services", operation="status",
             args={"operation": "status", "unit": "nginx.service"}),
        Turn(user_input="same check but for haproxy.service", tool="services", operation="status",
             args={"operation": "status", "unit": "haproxy.service"}),
    )),
    V3(id="mt-eval-0002", tool="services", kind="followup", turns=(
        Turn(user_input="stop the crond service", tool="services", operation="stop",
             args={"operation": "stop", "unit": "crond.service"}),
        Turn(user_input="ok, get it running again", tool="services", operation="start",
             args={"operation": "start", "unit": "crond.service"}),
    )),
    # -- packages ----------------------------------------------------------- #
    V3(id="mt-eval-0003", tool="packages", kind="followup", turns=(
        Turn(user_input="install the tree package", tool="packages", operation="install",
             args={"operation": "install", "packages": ["tree"]}),
        Turn(user_input="now show me its info", tool="packages", operation="info",
             args={"operation": "info", "package": "tree"}),
    )),
    V3(id="mt-eval-0004", tool="packages", kind="followup", turns=(
        Turn(user_input="remove the telnet package", tool="packages", operation="remove",
             args={"operation": "remove", "packages": ["telnet"], "gate_cleared": True}),
        Turn(user_input="actually undo that, reinstall it", tool="packages", operation="install",
             args={"operation": "install", "packages": ["telnet"]}),
    )),
    # -- firewall ------------------------------------------------------------ #
    V3(id="mt-eval-0005", tool="firewall", kind="followup", turns=(
        Turn(user_input="open port 8443/tcp in the firewall", tool="firewall", operation="add_port",
             args={"operation": "add_port", "port": "8443/tcp"}),
        Turn(user_input="yes, apply that to the internal zone too", tool="firewall", operation="add_port",
             args={"operation": "add_port", "port": "8443/tcp", "zone": "internal"}),
    )),
    V3(id="mt-eval-0006", tool="firewall", kind="followup", turns=(
        Turn(user_input="check whether the https service is allowed", tool="firewall", operation="query",
             args={"operation": "query", "service": "https"}),
        Turn(user_input="and the same check for the http service", tool="firewall", operation="query",
             args={"operation": "query", "service": "http"}),
    )),
    # -- nftables -------------------------------------------------------------- #
    V3(id="mt-eval-0007", tool="nftables", kind="followup", turns=(
        Turn(user_input="list the current nftables ruleset", tool="nftables", operation="list_ruleset",
             args={"operation": "list_ruleset"}),
        Turn(user_input="ok now flush it", tool="nftables", operation="flush_ruleset",
             args={"operation": "flush_ruleset"}),
    )),
    V3(id="mt-eval-0008", tool="nftables", kind="followup", turns=(
        Turn(user_input="add a drop rule to table inet filter chain input for tcp port 4444",
             tool="nftables", operation="add_rule",
             args={"operation": "add_rule", "family": "inet", "table": "filter", "chain": "input",
                   "rule": "tcp dport 4444 drop"}),
        Turn(user_input="now check its logs", tool="logs", operation="query",
             args={"operation": "query", "unit": "nftables.service"}),
    )),
    # -- users ------------------------------------------------------------------- #
    V3(id="mt-eval-0009", tool="users", kind="followup", turns=(
        Turn(user_input="put user jsmith into the wheel group", tool="users", operation="add_to_group",
             args={"operation": "add_to_group", "user": "jsmith", "group": "wheel"}),
        Turn(user_input="no, use the docker group instead", tool="users", operation="add_to_group",
             args={"operation": "add_to_group", "user": "jsmith", "group": "docker"}),
    )),
    V3(id="mt-eval-0010", tool="users", kind="followup", turns=(
        Turn(user_input="add a new user named amartinez", tool="users", operation="add",
             args={"operation": "add", "user": "amartinez"}),
        Turn(user_input="yes, set the shell to /bin/zsh for that one", tool="users", operation="set_shell",
             args={"operation": "set_shell", "user": "amartinez", "shell": "/bin/zsh"}),
    )),
    # -- disk ---------------------------------------------------------------------- #
    V3(id="mt-eval-0011", tool="disk", kind="followup", turns=(
        Turn(user_input="show disk usage for /var", tool="disk", operation="usage",
             args={"operation": "usage", "path": "/var"}),
        Turn(user_input="same deal, but this time for /home", tool="disk", operation="usage",
             args={"operation": "usage", "path": "/home"}),
    )),
    V3(id="mt-eval-0012", tool="disk", kind="followup", turns=(
        Turn(user_input="show me the partition layout for /dev/sdb", tool="disk", operation="list",
             args={"operation": "list", "device": "/dev/sdb"}),
        Turn(user_input="ok now mount it at /mnt/data", tool="disk", operation="mount",
             args={"operation": "mount", "device": "/dev/sdb", "mount_point": "/mnt/data"}),
    )),
    # -- lvm ---------------------------------------------------------------------- #
    V3(id="mt-eval-0013", tool="lvm", kind="followup", turns=(
        Turn(user_input="show the vgdisplay for vg_data", tool="lvm", operation="vgdisplay",
             args={"operation": "vgdisplay", "vg": "vg_data"}),
        Turn(user_input="now check its dmesg output for errors", tool="logs", operation="dmesg_query",
             args={"operation": "dmesg_query", "grep": "vg_data"}),
    )),
    V3(id="mt-eval-0014", tool="lvm", kind="followup", turns=(
        Turn(user_input="extend the lv_data logical volume by 10G", tool="lvm", operation="lvextend",
             args={"operation": "lvextend", "lv": "lv_data", "size": "+10G"}),
        Turn(user_input="actually undo that, shrink it back down 10G", tool="lvm", operation="lvreduce",
             args={"operation": "lvreduce", "lv": "lv_data", "size": "-10G"}),
    )),
    # -- network -------------------------------------------------------------------- #
    V3(id="mt-eval-0015", tool="network", kind="followup", turns=(
        Turn(user_input="bring down the eth0 interface", tool="network", operation="bring_down",
             args={"operation": "bring_down", "interface": "eth0"}),
        Turn(user_input="yes, do that for eth1 as well", tool="network", operation="bring_down",
             args={"operation": "bring_down", "interface": "eth1"}),
    )),
    V3(id="mt-eval-0016", tool="network", kind="followup", turns=(
        Turn(user_input="set the IP address on eth0 to 10.0.0.5/24", tool="network", operation="set_ip",
             args={"operation": "set_ip", "interface": "eth0", "address": "10.0.0.5/24"}),
        Turn(user_input="and the same for eth1, use 10.0.0.6/24", tool="network", operation="set_ip",
             args={"operation": "set_ip", "interface": "eth1", "address": "10.0.0.6/24"}),
    )),
    # -- nmcli --------------------------------------------------------------------- #
    V3(id="mt-eval-0017", tool="nmcli", kind="followup", turns=(
        Turn(user_input="show the connection details for office-vpn", tool="nmcli", operation="connection_show",
             args={"operation": "connection_show", "name": "office-vpn"}),
        Turn(user_input="ok, get that connection running", tool="nmcli", operation="connection_up",
             args={"operation": "connection_up", "name": "office-vpn"}),
    )),
    V3(id="mt-eval-0018", tool="nmcli", kind="followup", turns=(
        Turn(user_input="add a wifi connection named guest-net on wlan0 with ip4 192.168.50.10/24 and gateway 192.168.50.1",
             tool="nmcli", operation="connection_add",
             args={"operation": "connection_add", "type": "wifi", "con_name": "guest-net", "ifname": "wlan0",
                   "ip4": "192.168.50.10/24", "gw4": "192.168.50.1"}),
        Turn(user_input="now check its route table", tool="routing", operation="route_show",
             args={"operation": "route_show"}),
    )),
    # -- dns ------------------------------------------------------------------------ #
    V3(id="mt-eval-0019", tool="dns", kind="followup", turns=(
        Turn(user_input="look up the A record for api.example.com", tool="dns", operation="dig",
             args={"operation": "dig", "name": "api.example.com", "record_type": "A"}),
        Turn(user_input="no, use the MX record instead", tool="dns", operation="dig",
             args={"operation": "dig", "name": "api.example.com", "record_type": "MX"}),
    )),
    V3(id="mt-eval-0020", tool="dns", kind="followup", turns=(
        Turn(user_input="check whether named is running", tool="dns", operation="named_status",
             args={"operation": "named_status"}),
        Turn(user_input="yes, flush the caches while you're at it", tool="dns", operation="flush_caches",
             args={"operation": "flush_caches"}),
    )),
    # -- ssh_keys --------------------------------------------------------------------- #
    V3(id="mt-eval-0021", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="show me deploy's authorized_keys entries", tool="ssh_keys", operation="authorized_keys_list",
             args={"operation": "authorized_keys_list", "user": "deploy"}),
        Turn(user_input="and the same for user backup", tool="ssh_keys", operation="authorized_keys_list",
             args={"operation": "authorized_keys_list", "user": "backup"}),
    )),
    V3(id="mt-eval-0022", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="generate an ed25519 keypair at /home/deploy/.ssh/id_ed25519", tool="ssh_keys",
             operation="keygen",
             args={"operation": "keygen", "path": "/home/deploy/.ssh/id_ed25519", "key_type": "ed25519"}),
        Turn(user_input="ok now add it to deploy's authorized_keys", tool="ssh_keys",
             operation="authorized_keys_add",
             args={"operation": "authorized_keys_add",
                   "key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyDeploy deploy@server",
                   "user": "deploy"}),
    )),
    # -- cron -------------------------------------------------------------------------- #
    V3(id="mt-eval-0023", tool="cron", kind="followup", turns=(
        Turn(user_input="show the crontab for user backupuser", tool="cron", operation="list",
             args={"operation": "list", "user": "backupuser"}),
        Turn(user_input="now check its cron job logs", tool="logs", operation="query",
             args={"operation": "query", "unit": "crond.service"}),
    )),
    V3(id="mt-eval-0024", tool="cron", kind="followup", turns=(
        Turn(user_input="edit backupuser's crontab to add '0 2 * * * /usr/local/bin/backup.sh'", tool="cron",
             operation="edit",
             args={"operation": "edit", "content": "0 2 * * * /usr/local/bin/backup.sh", "user": "backupuser"}),
        Turn(user_input="actually, remove that crontab instead", tool="cron", operation="remove",
             args={"operation": "remove", "user": "backupuser"}),
    )),
    # -- at ---------------------------------------------------------------------------- #
    V3(id="mt-eval-0025", tool="at", kind="followup", turns=(
        Turn(user_input="schedule a job to run 'systemctl restart nginx' at 23:30", tool="at",
             operation="schedule",
             args={"operation": "schedule", "time": "23:30", "command": "systemctl restart nginx"}),
        Turn(user_input="yes, list the queue to confirm it's there", tool="at", operation="atq",
             args={"operation": "atq"}),
    )),
    V3(id="mt-eval-0026", tool="at", kind="followup", turns=(
        Turn(user_input="remove at job 7", tool="at", operation="atrm",
             args={"operation": "atrm", "job_id": "7"}),
        Turn(user_input="and the same for job 8", tool="at", operation="atrm",
             args={"operation": "atrm", "job_id": "8"}),
    )),
    # -- systemd_timers -------------------------------------------------------------------- #
    V3(id="mt-eval-0027", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="show the timer details for backup.timer", tool="systemd_timers", operation="timer-show",
             args={"operation": "timer-show", "timer": "backup.timer"}),
        Turn(user_input="yes, switch it on", tool="systemd_timers", operation="enable",
             args={"operation": "enable", "timer": "backup.timer"}),
    )),
    V3(id="mt-eval-0028", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="create a timer named cleanup.timer that runs cleanup.service daily", tool="systemd_timers",
             operation="create",
             args={"operation": "create", "timer": "cleanup.timer",
                   "content": "[Timer]\nOnCalendar=daily\n[Install]\nWantedBy=timers.target"}),
        Turn(user_input="now check its logs", tool="logs", operation="query",
             args={"operation": "query", "unit": "cleanup.timer"}),
    )),
    # -- logs ------------------------------------------------------------------------------- #
    V3(id="mt-eval-0029", tool="logs", kind="followup", turns=(
        Turn(user_input="show the last 50 log lines for sshd", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "sshd.service", "lines": 50}),
        Turn(user_input="no, give me the last 200 instead", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "sshd.service", "lines": 200}),
    )),
    V3(id="mt-eval-0030", tool="logs", kind="followup", turns=(
        Turn(user_input="query the boot errors from the current boot", tool="logs", operation="boot_errors",
             args={"operation": "boot_errors", "boot": "0"}),
        Turn(user_input="yes, check the previous boot too", tool="logs", operation="boot_errors",
             args={"operation": "boot_errors", "boot": "-1"}),
    )),
    # -- processes ---------------------------------------------------------------------------- #
    V3(id="mt-eval-0031", tool="processes", kind="followup", turns=(
        Turn(user_input="show info for pid 4021", tool="processes", operation="info",
             args={"operation": "info", "pid": 4021}),
        Turn(user_input="check that one too, pid 4088", tool="processes", operation="info",
             args={"operation": "info", "pid": 4088}),
    )),
    V3(id="mt-eval-0032", tool="processes", kind="followup", turns=(
        Turn(user_input="show the process tree", tool="processes", operation="tree",
             args={"operation": "tree"}),
        Turn(user_input="ok now renice pid 5120 to priority 10", tool="processes", operation="renice",
             args={"operation": "renice", "pid": 5120, "priority": 10}),
    )),
    # -- samba ---------------------------------------------------------------------------------- #
    V3(id="mt-eval-0033", tool="samba", kind="followup", turns=(
        Turn(user_input="can you tell if the smbd daemon is up", tool="samba", operation="smbd_status",
             args={"operation": "smbd_status"}),
        Turn(user_input="now check its firewall rule for the samba service", tool="firewall", operation="query",
             args={"operation": "query", "service": "samba"}),
    )),
    V3(id="mt-eval-0034", tool="samba", kind="followup", turns=(
        Turn(user_input="add a samba password for user amelia", tool="samba", operation="smbpasswd_add",
             args={"operation": "smbpasswd_add", "username": "amelia"}),
        Turn(user_input="no, delete that account instead", tool="samba", operation="smbpasswd_delete",
             args={"operation": "smbpasswd_delete", "username": "amelia"}),
    )),
    # -- nfs --------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0035", tool="nfs", kind="followup", turns=(
        Turn(user_input="check mounts exported by server nfs01", tool="nfs", operation="showmount",
             args={"operation": "showmount", "server": "nfs01"}),
        Turn(user_input="yes, mount that export at /mnt/nfs01 using path /export/data", tool="nfs",
             operation="mount_client",
             args={"operation": "mount_client", "server": "nfs01", "path": "/export/data",
                   "mountpoint": "/mnt/nfs01"}),
    )),
    V3(id="mt-eval-0036", tool="nfs", kind="followup", turns=(
        Turn(user_input="unexport /export/data", tool="nfs", operation="exportfs_unexport",
             args={"operation": "exportfs_unexport", "target": "/export/data"}),
        Turn(user_input="and the same for /export/backups", tool="nfs", operation="exportfs_unexport",
             args={"operation": "exportfs_unexport", "target": "/export/backups"}),
    )),
    # -- rsync ---------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0037", tool="rsync", kind="followup", turns=(
        Turn(user_input="do a dry run syncing /data to backup01:/data", tool="rsync", operation="dry-run",
             args={"operation": "dry-run", "src": "/data", "dest": "backup01:/data"}),
        Turn(user_input="ok looks good, now actually sync it", tool="rsync", operation="sync",
             args={"operation": "sync", "src": "/data", "dest": "backup01:/data"}),
    )),
    V3(id="mt-eval-0038", tool="rsync", kind="followup", turns=(
        Turn(user_input="sync /var/www to webbackup:/var/www with progress", tool="rsync", operation="progress",
             args={"operation": "progress", "src": "/var/www", "dest": "webbackup:/var/www"}),
        Turn(user_input="now check its disk usage there", tool="disk", operation="usage",
             args={"operation": "usage", "path": "/var/www"}),
    )),
    # -- tar -------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0039", tool="tar", kind="followup", turns=(
        Turn(user_input="create a gzip archive backup.tar.gz of /etc", tool="tar", operation="create_gz",
             args={"operation": "create_gz", "archive": "backup.tar.gz", "sources": ["/etc"]}),
        Turn(user_input="no wait, use xz compression instead", tool="tar", operation="create_xz",
             args={"operation": "create_xz", "archive": "backup.tar.xz", "sources": ["/etc"]}),
    )),
    V3(id="mt-eval-0040", tool="tar", kind="followup", turns=(
        Turn(user_input="list the contents of site-backup.tar", tool="tar", operation="list",
             args={"operation": "list", "archive": "site-backup.tar"}),
        Turn(user_input="yes, unpack it into /restore", tool="tar", operation="extract",
             args={"operation": "extract", "archive": "site-backup.tar", "dest": "/restore"}),
    )),
    # -- restic ------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0041", tool="restic", kind="followup", turns=(
        Turn(user_input="list snapshots tagged nightly", tool="restic", operation="snapshots",
             args={"operation": "snapshots", "tag": "nightly"}),
        Turn(user_input="and the same for snapshots tagged weekly", tool="restic", operation="snapshots",
             args={"operation": "snapshots", "tag": "weekly"}),
    )),
    V3(id="mt-eval-0042", tool="restic", kind="followup", turns=(
        Turn(user_input="back up /srv/data to the offsite repo", tool="restic", operation="backup",
             args={"operation": "backup", "path": "/srv/data", "repo": "offsite"}),
        Turn(user_input="ok now prune the old snapshots, keep the last 5", tool="restic", operation="forget_prune",
             args={"operation": "forget_prune", "keep_last": 5, "repo": "offsite"}),
    )),
    # -- mariadb --------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0043", tool="mariadb", kind="followup", turns=(
        Turn(user_input="check mariadb status", tool="mariadb", operation="status",
             args={"operation": "status"}),
        Turn(user_input="now check its service logs", tool="logs", operation="query",
             args={"operation": "query", "unit": "mariadb.service"}),
    )),
    V3(id="mt-eval-0044", tool="mariadb", kind="followup", turns=(
        Turn(user_input="drop the database named staging_old", tool="mariadb", operation="drop_database",
             args={"operation": "drop_database", "database": "staging_old"}),
        Turn(user_input="actually undo that, dump it first instead", tool="mariadb", operation="dump",
             args={"operation": "dump", "database": "staging_old"}),
    )),
    # -- postgresql -------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0045", tool="postgresql", kind="followup", turns=(
        Turn(user_input="is postgresql up and running", tool="postgresql", operation="status",
             args={"operation": "status"}),
        Turn(user_input="yes, create a database called reporting while you're at it", tool="postgresql",
             operation="createdb",
             args={"operation": "createdb", "dbname": "reporting"}),
    )),
    V3(id="mt-eval-0046", tool="postgresql", kind="followup", turns=(
        Turn(user_input="create a database user named analyst", tool="postgresql", operation="createuser",
             args={"operation": "createuser", "rolename": "analyst"}),
        Turn(user_input="and the same for a user named auditor", tool="postgresql", operation="createuser",
             args={"operation": "createuser", "rolename": "auditor"}),
    )),
    # -- nginx --------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0047", tool="nginx", kind="followup", turns=(
        Turn(user_input="test the nginx config", tool="nginx", operation="configtest",
             args={"operation": "configtest"}),
        Turn(user_input="ok now reload it", tool="nginx", operation="reload",
             args={"operation": "reload"}),
    )),
    V3(id="mt-eval-0048", tool="nginx", kind="followup", turns=(
        Turn(user_input="can you tell me if nginx is up right now", tool="nginx", operation="status",
             args={"operation": "status"}),
        Turn(user_input="now check its recent logs", tool="logs", operation="query",
             args={"operation": "query", "unit": "nginx.service"}),
    )),
    # -- httpd ---------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0049", tool="httpd", kind="followup", turns=(
        Turn(user_input="stop httpd", tool="httpd", operation="stop",
             args={"operation": "stop"}),
        Turn(user_input="no, restart it instead", tool="httpd", operation="restart",
             args={"operation": "restart"}),
    )),
    V3(id="mt-eval-0050", tool="httpd", kind="followup", turns=(
        Turn(user_input="run the httpd config test", tool="httpd", operation="configtest",
             args={"operation": "configtest"}),
        Turn(user_input="yes, show me the vhost list too", tool="httpd", operation="vhost_list",
             args={"operation": "vhost_list"}),
    )),
    # -- podman ---------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0051", tool="podman", kind="followup", turns=(
        Turn(user_input="show logs for the container web-api", tool="podman", operation="logs",
             args={"operation": "logs", "container": "web-api"}),
        Turn(user_input="and the same for the container worker-queue", tool="podman", operation="logs",
             args={"operation": "logs", "container": "worker-queue"}),
    )),
    V3(id="mt-eval-0052", tool="podman", kind="followup", turns=(
        Turn(user_input="pull the image redis:7", tool="podman", operation="pull",
             args={"operation": "pull", "image": "redis:7"}),
        Turn(user_input="ok now run it detached", tool="podman", operation="run",
             args={"operation": "run", "image": "redis:7", "detach": True}),
    )),
    # -- virsh ------------------------------------------------------------------------------------------------------ #
    V3(id="mt-eval-0053", tool="virsh", kind="followup", turns=(
        Turn(user_input="show dominfo for the VM named build-runner", tool="virsh", operation="dominfo",
             args={"operation": "dominfo", "domain": "build-runner"}),
        Turn(user_input="now check its logs", tool="logs", operation="query",
             args={"operation": "query", "unit": "libvirtd.service"}),
    )),
    V3(id="mt-eval-0054", tool="virsh", kind="followup", turns=(
        Turn(user_input="shut down the VM build-runner", tool="virsh", operation="shutdown",
             args={"operation": "shutdown", "domain": "build-runner"}),
        Turn(user_input="no, start it back up instead", tool="virsh", operation="start",
             args={"operation": "start", "domain": "build-runner"}),
    )),
    # -- sssd -------------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0055", tool="sssd", kind="followup", turns=(
        Turn(user_input="check sssd status", tool="sssd", operation="status",
             args={"operation": "status"}),
        Turn(user_input="yes, flush the cache while you're at it", tool="sssd", operation="cache_flush",
             args={"operation": "cache_flush"}),
    )),
    V3(id="mt-eval-0056", tool="sssd", kind="followup", turns=(
        Turn(user_input="look up the id for user mchen", tool="sssd", operation="id_lookup",
             args={"operation": "id_lookup", "user": "mchen"}),
        Turn(user_input="and the same for user twong", tool="sssd", operation="id_lookup",
             args={"operation": "id_lookup", "user": "twong"}),
    )),
    # -- selinux ----------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0057", tool="selinux", kind="followup", turns=(
        Turn(user_input="what's the current value of the httpd_can_network_connect selinux boolean", tool="selinux", operation="getsebool",
             args={"operation": "getsebool", "boolean": "httpd_can_network_connect"}),
        Turn(user_input="ok now turn it on persistently", tool="selinux", operation="setsebool",
             args={"operation": "setsebool", "boolean": "httpd_can_network_connect", "value": "on",
                   "persist": True}),
    )),
    V3(id="mt-eval-0058", tool="selinux", kind="followup", turns=(
        Turn(user_input="check the current selinux enforcement mode", tool="selinux", operation="getenforce",
             args={"operation": "getenforce"}),
        Turn(user_input="now check its recent denials in the audit log", tool="audit", operation="search-by-key",
             args={"operation": "search-by-key", "key": "selinux"}),
    )),
    # -- sysctl ------------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0059", tool="sysctl", kind="followup", turns=(
        Turn(user_input="turn on net.ipv4.ip_forward, set it to 1", tool="sysctl", operation="set",
             args={"operation": "set", "key": "net.ipv4.ip_forward", "value": "1"}),
        Turn(user_input="no, set it back to 0 instead", tool="sysctl", operation="set",
             args={"operation": "set", "key": "net.ipv4.ip_forward", "value": "0"}),
    )),
    V3(id="mt-eval-0060", tool="sysctl", kind="followup", turns=(
        Turn(user_input="get the current value of vm.swappiness", tool="sysctl", operation="get",
             args={"operation": "get", "key": "vm.swappiness"}),
        Turn(user_input="yes, persist it at 10", tool="sysctl", operation="persist",
             args={"operation": "persist", "key": "vm.swappiness", "value": "10"}),
    )),
    # -- tuned -------------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0061", tool="tuned", kind="followup", turns=(
        Turn(user_input="switch the tuned profile to throughput-performance", tool="tuned", operation="profile",
             args={"operation": "profile", "profile": "throughput-performance"}),
        Turn(user_input="and the same but use latency-performance this time", tool="tuned", operation="profile",
             args={"operation": "profile", "profile": "latency-performance"}),
    )),
    V3(id="mt-eval-0062", tool="tuned", kind="followup", turns=(
        Turn(user_input="show the recommended tuned profile", tool="tuned", operation="recommend",
             args={"operation": "recommend"}),
        Turn(user_input="ok now activate it", tool="tuned", operation="profile",
             args={"operation": "profile", "profile": "balanced"}),
    )),
    # -- kernel_modules ---------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0063", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="show modinfo for the nvidia module", tool="kernel_modules", operation="modinfo",
             args={"operation": "modinfo", "module": "nvidia"}),
        Turn(user_input="now check its dmesg errors", tool="logs", operation="dmesg_query",
             args={"operation": "dmesg_query", "grep": "nvidia"}),
    )),
    V3(id="mt-eval-0064", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="load the br_netfilter module", tool="kernel_modules", operation="modprobe",
             args={"operation": "modprobe", "module": "br_netfilter"}),
        Turn(user_input="actually, remove it instead", tool="kernel_modules", operation="rmmod",
             args={"operation": "rmmod", "module": "br_netfilter"}),
    )),
    # -- grub ---------------------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0065", tool="grub", kind="followup", turns=(
        Turn(user_input="which kernel is set as the grub default", tool="grub", operation="default-kernel",
             args={"operation": "default-kernel"}),
        Turn(user_input="yes, add the kernel argument nomodeset to it", tool="grub", operation="args-add",
             args={"operation": "args-add", "kernel": "default", "kernel_args": "nomodeset"}),
    )),
    V3(id="mt-eval-0066", tool="grub", kind="followup", turns=(
        Turn(user_input="remove the kernel argument quiet for kernel 5.14.0-100", tool="grub",
             operation="args-remove",
             args={"operation": "args-remove", "kernel": "5.14.0-100", "kernel_args": "quiet"}),
        Turn(user_input="and the same for kernel 5.14.0-95", tool="grub", operation="args-remove",
             args={"operation": "args-remove", "kernel": "5.14.0-95", "kernel_args": "quiet"}),
    )),
    # -- hostname --------------------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0067", tool="hostname", kind="followup", turns=(
        Turn(user_input="what hostname is this machine currently set to", tool="hostname", operation="status",
             args={"operation": "status"}),
        Turn(user_input="ok now set it to db-primary", tool="hostname", operation="set-hostname",
             args={"operation": "set-hostname", "name": "db-primary"}),
    )),
    V3(id="mt-eval-0068", tool="hostname", kind="followup", turns=(
        Turn(user_input="view the /etc/hosts entries", tool="hostname", operation="hosts-view",
             args={"operation": "hosts-view"}),
        Turn(user_input="now check its dns resolution", tool="dns", operation="dig",
             args={"operation": "dig", "name": "db-primary"}),
    )),
    # -- locale ------------------------------------------------------------------------------------------------------------------ #
    V3(id="mt-eval-0069", tool="locale", kind="followup", turns=(
        Turn(user_input="change the system locale over to en_GB.UTF-8", tool="locale", operation="set-locale",
             args={"operation": "set-locale", "locale": "en_GB.UTF-8"}),
        Turn(user_input="no, use en_US.UTF-8 instead", tool="locale", operation="set-locale",
             args={"operation": "set-locale", "locale": "en_US.UTF-8"}),
    )),
    V3(id="mt-eval-0070", tool="locale", kind="followup", turns=(
        Turn(user_input="check the current timedatectl status", tool="locale", operation="timedatectl-status",
             args={"operation": "timedatectl-status"}),
        Turn(user_input="yes, set the timezone to America/Chicago while you're at it", tool="locale",
             operation="set-timezone",
             args={"operation": "set-timezone", "timezone": "America/Chicago"}),
    )),
    # -- quota -------------------------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0071", tool="quota", kind="followup", turns=(
        Turn(user_input="show the quota report for /home", tool="quota", operation="repquota",
             args={"operation": "repquota", "filesystem": "/home"}),
        Turn(user_input="and the same for /srv", tool="quota", operation="repquota",
             args={"operation": "repquota", "filesystem": "/srv"}),
    )),
    V3(id="mt-eval-0072", tool="quota", kind="followup", turns=(
        Turn(user_input="check the quota for user rpatel", tool="quota", operation="quota_user",
             args={"operation": "quota_user", "username": "rpatel"}),
        Turn(user_input="ok now set the soft block limit to 5000000 and hard to 6000000 on /home for that user",
             tool="quota", operation="edquota",
             args={"operation": "edquota", "username": "rpatel", "filesystem": "/home",
                   "soft_blocks": 5000000, "hard_blocks": 6000000}),
    )),
    # -- stratis ------------------------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0073", tool="stratis", kind="followup", turns=(
        Turn(user_input="list the filesystems in pool data-pool", tool="stratis", operation="filesystem-list",
             args={"operation": "filesystem-list", "pool": "data-pool"}),
        Turn(user_input="now check its disk usage", tool="disk", operation="usage",
             args={"operation": "usage", "path": "/stratis/data-pool"}),
    )),
    V3(id="mt-eval-0074", tool="stratis", kind="followup", turns=(
        Turn(user_input="create a filesystem named archive in pool data-pool", tool="stratis",
             operation="filesystem-create",
             args={"operation": "filesystem-create", "pool": "data-pool", "filesystem": "archive"}),
        Turn(user_input="no wait, destroy that filesystem instead", tool="stratis",
             operation="filesystem-destroy",
             args={"operation": "filesystem-destroy", "pool": "data-pool", "filesystem": "archive"}),
    )),
    # -- bond ----------------------------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0075", tool="bond", kind="followup", turns=(
        Turn(user_input="show the bond0 interface details", tool="bond", operation="show",
             args={"operation": "show", "bond": "bond0"}),
        Turn(user_input="yes, modify its mode to active-backup", tool="bond", operation="modify",
             args={"operation": "modify", "bond": "bond0", "property": "mode", "value": "active-backup"}),
    )),
    V3(id="mt-eval-0076", tool="bond", kind="followup", turns=(
        Turn(user_input="remove the bond1 interface", tool="bond", operation="remove",
             args={"operation": "remove", "bond": "bond1"}),
        Turn(user_input="and the same for bond2", tool="bond", operation="remove",
             args={"operation": "remove", "bond": "bond2"}),
    )),
    # -- routing --------------------------------------------------------------------------------------------------------------------- #
    V3(id="mt-eval-0077", tool="routing", kind="followup", turns=(
        Turn(user_input="what does the current routing table look like", tool="routing", operation="route_show",
             args={"operation": "route_show"}),
        Turn(user_input="ok now add a route to 10.20.0.0/16 via 10.10.0.1", tool="routing", operation="route_add",
             args={"operation": "route_add", "dest": "10.20.0.0/16", "gateway": "10.10.0.1"}),
    )),
    V3(id="mt-eval-0078", tool="routing", kind="followup", turns=(
        Turn(user_input="add a policy rule from 192.168.5.0/24 to table 100", tool="routing",
             operation="policy_rule_add",
             args={"operation": "policy_rule_add", "src": "192.168.5.0/24", "table": "100"}),
        Turn(user_input="now check its interface status", tool="network", operation="interfaces",
             args={"operation": "interfaces"}),
    )),
    # -- crypto_policies ------------------------------------------------------------------------------------------------------------------ #
    V3(id="mt-eval-0079", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="set the crypto policy to FUTURE", tool="crypto_policies", operation="set",
             args={"operation": "set", "policy": "FUTURE"}),
        Turn(user_input="no, revert to DEFAULT instead", tool="crypto_policies", operation="set",
             args={"operation": "set", "policy": "DEFAULT"}),
    )),
    V3(id="mt-eval-0080", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="check the current crypto policy", tool="crypto_policies", operation="get",
             args={"operation": "get"}),
        Turn(user_input="yes, check the fips status too", tool="crypto_policies", operation="fips-status",
             args={"operation": "fips-status"}),
    )),
]

for _t in sorted({s.tool for s in EVAL_MULTITURN}):
    check_module(_t, [s for s in EVAL_MULTITURN if s.tool == _t])
assert len(EVAL_MULTITURN) == 80


# --------------------------------------------------------------------------- #
# Overlap guard -- no eval user_input may be near-duplicate of a v3 training  #
# user_input (Jaccard similarity on lowercase alphanumeric tokens > 0.7).     #
# --------------------------------------------------------------------------- #

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_TOKEN.findall(text.lower()))


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _check_no_overlap() -> None:
    train_inputs = [t.user_input for s in _load_all_v3() for t in s.turns]
    train_token_sets = [_tokens(u) for u in train_inputs]
    for s in EVAL_MULTITURN:
        for t in s.turns:
            eval_tokens = _tokens(t.user_input)
            for train_text, train_tokens in zip(train_inputs, train_token_sets):
                sim = _jaccard(eval_tokens, train_tokens)
                assert sim <= 0.7, (
                    f"{s.id}: eval user_input {t.user_input!r} too similar "
                    f"(jaccard={sim:.2f}) to v3 training input {train_text!r}"
                )


_check_no_overlap()
