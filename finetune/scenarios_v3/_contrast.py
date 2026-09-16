"""finetune/scenarios_v3/_contrast.py — contrastive single-turn scenarios."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [

    # ---- Pair 1: sssd.status vs services.status (sssd/realm/AD login state) ----
    V3(id="contrast-0001", tool="sssd", kind="contrast", turns=(
        Turn(user_input="Users say AD logins are failing again — check whether sssd itself is up before we start poking at realm config.",
             tool="sssd", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0002", tool="sssd", kind="contrast", turns=(
        Turn(user_input="Before I touch the domain join, confirm the identity daemon is actually running — not the systemd unit table, the sssd status itself.",
             tool="sssd", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0003", tool="sssd", kind="contrast", turns=(
        Turn(user_input="realm list looks fine but I want the sssd daemon's own status report before we blame the domain controller.",
             tool="sssd", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0004", tool="sssd", kind="contrast", turns=(
        Turn(user_input="AD-backed logins are hanging on this box. Get me sssd's current status, not a generic unit list.",
             tool="sssd", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0005", tool="sssd", kind="contrast", turns=(
        Turn(user_input="I know there are a dozen services running on this host, but specifically pull the identity service status for sssd since realm login is broken.",
             tool="sssd", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0006", tool="sssd", kind="contrast", turns=(
        Turn(user_input="Someone said 'the login service is down' — check sssd's status directly since that's what handles AD/realm auth here.",
             tool="sssd", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0007", tool="services", kind="contrast", turns=(
        Turn(user_input="Give me a general systemd status check on the sssd.service unit — I just want to know if it's active, failed, or masked at the unit level.",
             tool="services", operation="status", args={"operation": "status", "unit": "sssd.service"}),
    )),
    V3(id="contrast-0008", tool="services", kind="contrast", turns=(
        Turn(user_input="Forget the realm/AD side for a second — show me the plain systemd unit status for sssd.service, load state and all.",
             tool="services", operation="status", args={"operation": "status", "unit": "sssd.service"}),
    )),
    V3(id="contrast-0009", tool="services", kind="contrast", turns=(
        Turn(user_input="I'm auditing every unit on this host including the identity ones — pull the systemd status for sssd.service like you would for any other service.",
             tool="services", operation="status", args={"operation": "status", "unit": "sssd.service"}),
    )),
    V3(id="contrast-0010", tool="services", kind="contrast", turns=(
        Turn(user_input="Check whether the sssd.service unit is enabled at boot and what its systemd state is right now.",
             tool="services", operation="status", args={"operation": "status", "unit": "sssd.service"}),
    )),
    V3(id="contrast-0011", tool="services", kind="contrast", turns=(
        Turn(user_input="For the change ticket I need the raw systemctl status output for sssd.service, not a domain/realm summary.",
             tool="services", operation="status", args={"operation": "status", "unit": "sssd.service"}),
    )),
    V3(id="contrast-0012", tool="services", kind="contrast", turns=(
        Turn(user_input="Sweep the unit table and tell me sssd.service's systemd status specifically, same as you'd check any other unit.",
             tool="services", operation="status", args={"operation": "status", "unit": "sssd.service"}),
    )),

    # ---- Pair 2a: postgresql.status vs services.status ----
    V3(id="contrast-0013", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="Our reporting app can't connect to postgres. Before checking units, get postgresql's own status — is the database engine itself up.",
             tool="postgresql", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0014", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="I want the database-level status for postgresql, not the systemd unit table — is postgres accepting connections.",
             tool="postgresql", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0015", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="Check postgres's own status before we go poking at postgresql.service in systemd — I want the database's view first.",
             tool="postgresql", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0016", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="There are a dozen services on this box; I specifically need postgres's database status, not a generic service listing.",
             tool="postgresql", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0017", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="Get me postgresql's status directly — I need to know if the cluster is up before checking any systemd unit.",
             tool="postgresql", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0018", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="Queries are timing out on the postgres side. Pull postgresql's status via its own tooling, not the general services list.",
             tool="postgresql", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0019", tool="services", kind="contrast", turns=(
        Turn(user_input="I'm doing a general unit audit across the host — show me the plain systemd status for postgresql.service, active/failed/masked.",
             tool="services", operation="status", args={"operation": "status", "unit": "postgresql.service"}),
    )),
    V3(id="contrast-0020", tool="services", kind="contrast", turns=(
        Turn(user_input="Forget the database internals for now — just give me the systemctl status output for postgresql.service like any other unit.",
             tool="services", operation="status", args={"operation": "status", "unit": "postgresql.service"}),
    )),
    V3(id="contrast-0021", tool="services", kind="contrast", turns=(
        Turn(user_input="For the change record I need the raw systemd state of postgresql.service, not a database-engine health report.",
             tool="services", operation="status", args={"operation": "status", "unit": "postgresql.service"}),
    )),
    V3(id="contrast-0022", tool="services", kind="contrast", turns=(
        Turn(user_input="Check if postgresql.service is enabled at boot and what its unit state currently is.",
             tool="services", operation="status", args={"operation": "status", "unit": "postgresql.service"}),
    )),
    V3(id="contrast-0023", tool="services", kind="contrast", turns=(
        Turn(user_input="Same sweep I run on every unit — give me postgresql.service's systemd status, nothing database-specific.",
             tool="services", operation="status", args={"operation": "status", "unit": "postgresql.service"}),
    )),
    V3(id="contrast-0024", tool="services", kind="contrast", turns=(
        Turn(user_input="I only care about the systemd load/active/sub triad for postgresql.service right now, not query health.",
             tool="services", operation="status", args={"operation": "status", "unit": "postgresql.service"}),
    )),

    # ---- Pair 2b: postgresql.dropdb vs mariadb.drop_database ----
    V3(id="contrast-0025", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="This old database 'staging_pg' was a postgres cluster we spun up for testing — permanently drop it, we already migrated everything off.",
             tool="postgresql", operation="dropdb", args={"operation": "dropdb", "dbname": "staging_pg"}),
    )),
    V3(id="contrast-0026", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="We're decommissioning the 'legacy_reports' postgres database — drop it via psql tooling, it's not a mysql instance.",
             tool="postgresql", operation="dropdb", args={"operation": "dropdb", "dbname": "legacy_reports"}),
    )),
    V3(id="contrast-0027", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="Even though this server also runs mariadb for other apps, the 'test_pg_db' database itself lives in postgres — permanently drop that one.",
             tool="postgresql", operation="dropdb", args={"operation": "dropdb", "dbname": "test_pg_db"}),
    )),
    V3(id="contrast-0028", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="Drop the postgres database named 'scratch_analytics' — confirmed with the team, all data is disposable.",
             tool="postgresql", operation="dropdb", args={"operation": "dropdb", "dbname": "scratch_analytics"}),
    )),
    V3(id="contrast-0029", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="The postgres cluster has a stray database 'old_migration' left from the cutover — permanently remove it.",
             tool="postgresql", operation="dropdb", args={"operation": "dropdb", "dbname": "old_migration"}),
    )),
    V3(id="contrast-0030", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="Wipe the 'pgtest01' database out of the postgres instance entirely — it's a throwaway load-test DB.",
             tool="postgresql", operation="dropdb", args={"operation": "dropdb", "dbname": "pgtest01"}),
    )),
    V3(id="contrast-0031", tool="mariadb", kind="contrast", turns=(
        Turn(user_input="Even though the app also talks to postgres elsewhere, this particular 'staging_mysql' database is on the mariadb server — permanently drop it there.",
             tool="mariadb", operation="drop_database", args={"operation": "drop_database", "database": "staging_mysql"}),
    )),
    V3(id="contrast-0032", tool="mariadb", kind="contrast", turns=(
        Turn(user_input="Decommission the 'legacy_orders' database on mariadb — that's the mysql-compatible engine, not the postgres cluster.",
             tool="mariadb", operation="drop_database", args={"operation": "drop_database", "database": "legacy_orders"}),
    )),
    V3(id="contrast-0033", tool="mariadb", kind="contrast", turns=(
        Turn(user_input="Drop the 'test_maria_db' database — it lives on the mariadb instance even though this box also has a postgres cluster running.",
             tool="mariadb", operation="drop_database", args={"operation": "drop_database", "database": "test_maria_db"}),
    )),
    V3(id="contrast-0034", tool="mariadb", kind="contrast", turns=(
        Turn(user_input="Permanently remove the mariadb database 'scratch_maria' — everyone's confirmed it's disposable, and it's not the postgres one.",
             tool="mariadb", operation="drop_database", args={"operation": "drop_database", "database": "scratch_maria"}),
    )),
    V3(id="contrast-0035", tool="mariadb", kind="contrast", turns=(
        Turn(user_input="There's a stray database 'old_migration_mysql' on the mariadb server from the cutover — permanently drop it.",
             tool="mariadb", operation="drop_database", args={"operation": "drop_database", "database": "old_migration_mysql"}),
    )),
    V3(id="contrast-0036", tool="mariadb", kind="contrast", turns=(
        Turn(user_input="Wipe out the 'mariatest01' database on the mariadb engine — throwaway load-test data, not related to the postgres box.",
             tool="mariadb", operation="drop_database", args={"operation": "drop_database", "database": "mariatest01"}),
    )),

    # ---- Pair 3: systemd_timers.list-timers vs services (timers, not units) ----
    V3(id="contrast-0037", tool="systemd_timers", kind="contrast", turns=(
        Turn(user_input="I know we manage plenty of services on this box, but right now I specifically want to see every scheduled timer and its next trigger time.",
             tool="systemd_timers", operation="list-timers", args={"operation": "list-timers"}),
    )),
    V3(id="contrast-0038", tool="systemd_timers", kind="contrast", turns=(
        Turn(user_input="Forget individual service units for a second — list all the timer units so I can see what's scheduled to fire next.",
             tool="systemd_timers", operation="list-timers", args={"operation": "list-timers"}),
    )),
    V3(id="contrast-0039", tool="systemd_timers", kind="contrast", turns=(
        Turn(user_input="Something ran a backup job overnight and I need to know which scheduled timer triggered it — show me all timers with their last-run times.",
             tool="systemd_timers", operation="list-timers", args={"operation": "list-timers"}),
    )),
    V3(id="contrast-0040", tool="systemd_timers", kind="contrast", turns=(
        Turn(user_input="Give me the full timer schedule across the host — next and last trigger for every .timer unit, not the service unit list.",
             tool="systemd_timers", operation="list-timers", args={"operation": "list-timers"}),
    )),
    V3(id="contrast-0041", tool="systemd_timers", kind="contrast", turns=(
        Turn(user_input="Before I restart any daemon, I want to confirm no scheduled timer is about to fire — list all active timers.",
             tool="systemd_timers", operation="list-timers", args={"operation": "list-timers"}),
    )),
    V3(id="contrast-0042", tool="systemd_timers", kind="contrast", turns=(
        Turn(user_input="Even though there are services running everywhere, I only care about the recurring schedule right now — dump the timer list.",
             tool="systemd_timers", operation="list-timers", args={"operation": "list-timers"}),
    )),
    V3(id="contrast-0043", tool="services", kind="contrast", turns=(
        Turn(user_input="I'm not asking about the backup schedule — just restart the backup.service unit directly, right now.",
             tool="services", operation="restart", args={"operation": "restart", "unit": "backup.service"}),
    )),
    V3(id="contrast-0044", tool="services", kind="contrast", turns=(
        Turn(user_input="Even though logrotate.timer exists, what I actually need is the current systemd status of the logrotate.service unit itself.",
             tool="services", operation="status", args={"operation": "status", "unit": "logrotate.service"}),
    )),
    V3(id="contrast-0045", tool="services", kind="contrast", turns=(
        Turn(user_input="Skip the scheduling question — stop the cleanup.service unit outright, I'll deal with its timer separately.",
             tool="services", operation="stop", args={"operation": "stop", "unit": "cleanup.service"}),
    )),
    V3(id="contrast-0046", tool="services", kind="contrast", turns=(
        Turn(user_input="Disable the report-generator.service unit at boot — not the timer, the underlying unit's boot-enable state.",
             tool="services", operation="disable", args={"operation": "disable", "unit": "report-generator.service"}),
    )),
    V3(id="contrast-0047", tool="services", kind="contrast", turns=(
        Turn(user_input="Pull the last 50 journal lines for snapshot.service — I want the unit's execution log, not its timer schedule.",
             tool="services", operation="logs", args={"operation": "logs", "unit": "snapshot.service", "lines": 50}),
    )),
    V3(id="contrast-0048", tool="services", kind="contrast", turns=(
        Turn(user_input="Just enable the vacuum.service unit at boot directly — I already know when it runs, I don't need timer info.",
             tool="services", operation="enable", args={"operation": "enable", "unit": "vacuum.service"}),
    )),

    # ---- Pair 4: fapolicyd.deny vs selinux (allowlisting, not labels/booleans) ----
    V3(id="contrast-0049", tool="fapolicyd", kind="contrast", turns=(
        Turn(user_input="I know SELinux is enforcing on this box, but I need to block a specific binary from ever executing — add a fapolicyd deny rule for /opt/vendor/bin/legacy_tool.",
             tool="fapolicyd", operation="deny", args={"operation": "deny", "path": "/opt/vendor/bin/legacy_tool"}),
    )),
    V3(id="contrast-0050", tool="fapolicyd", kind="contrast", turns=(
        Turn(user_input="Forget SELinux contexts for a moment — I want application execution blocked outright for /usr/local/bin/suspicious_script via the allowlisting daemon.",
             tool="fapolicyd", operation="deny", args={"operation": "deny", "path": "/usr/local/bin/suspicious_script"}),
    )),
    V3(id="contrast-0051", tool="fapolicyd", kind="contrast", turns=(
        Turn(user_input="Security flagged /tmp/downloaded_payload as untrusted — I need it denied from execution at the allowlist layer, not just relabeled.",
             tool="fapolicyd", operation="deny", args={"operation": "deny", "path": "/tmp/downloaded_payload"}),
    )),
    V3(id="contrast-0052", tool="fapolicyd", kind="contrast", turns=(
        Turn(user_input="Even with SELinux booleans already tightened, add an explicit deny rule for /opt/shadyapp/bin/run so it can never execute.",
             tool="fapolicyd", operation="deny", args={"operation": "deny", "path": "/opt/shadyapp/bin/run"}),
    )),
    V3(id="contrast-0053", tool="fapolicyd", kind="contrast", turns=(
        Turn(user_input="This isn't a file-context labeling issue — I want /home/shared/uploads/payload.bin denied by the execution allowlisting policy.",
             tool="fapolicyd", operation="deny", args={"operation": "deny", "path": "/home/shared/uploads/payload.bin"}),
    )),
    V3(id="contrast-0054", tool="fapolicyd", kind="contrast", turns=(
        Turn(user_input="Block /srv/tools/unverified_binary from running entirely — I need a deny rule in the allowlisting daemon, not a policy boolean flip.",
             tool="fapolicyd", operation="deny", args={"operation": "deny", "path": "/srv/tools/unverified_binary"}),
    )),
    V3(id="contrast-0055", tool="selinux", kind="contrast", turns=(
        Turn(user_input="I'm not trying to block execution of a binary — I need to know the current SELinux enforcement mode on this host, enforcing or permissive.",
             tool="selinux", operation="getenforce", args={"operation": "getenforce"}),
    )),
    V3(id="contrast-0056", tool="selinux", kind="contrast", turns=(
        Turn(user_input="This is purely a labeling question, not an allowlisting one — show me the current value of the httpd_can_network_connect boolean.",
             tool="selinux", operation="getsebool", args={"operation": "getsebool", "boolean": "httpd_can_network_connect"}),
    )),
    V3(id="contrast-0057", tool="selinux", kind="contrast", turns=(
        Turn(user_input="The web app can't write to /srv/www — I need to add a file context mapping for it as httpd_sys_content_t, this is a labeling fix not a deny rule.",
             tool="selinux", operation="semanage_fcontext_add", args={"operation": "semanage_fcontext_add", "fcontext_type": "httpd_sys_content_t", "fcontext_spec": "/srv/www(/.*)?"}),
    )),
    V3(id="contrast-0058", tool="selinux", kind="contrast", turns=(
        Turn(user_input="Flip the httpd_can_network_connect boolean on and persist it — that's the SELinux policy switch we need, not an execution block.",
             tool="selinux", operation="setsebool", args={"operation": "setsebool", "boolean": "httpd_can_network_connect", "value": "on", "persist": True}),
    )),
    V3(id="contrast-0059", tool="selinux", kind="contrast", turns=(
        Turn(user_input="Give me the overall sestatus output — policy type and enforcement — I don't need any binary blocked right now.",
             tool="selinux", operation="sestatus", args={"operation": "sestatus"}),
    )),
    V3(id="contrast-0060", tool="selinux", kind="contrast", turns=(
        Turn(user_input="List the current SELinux port label mappings — I'm checking labeling, not whether some app can execute.",
             tool="selinux", operation="semanage_port_list", args={"operation": "semanage_port_list"}),
    )),

    # ---- Pair 5: services.restart (generic) vs nginx.restart / httpd.restart (only when literally about nginx/apache) ----
    V3(id="contrast-0061", tool="services", kind="contrast", turns=(
        Turn(user_input="rsyslog is choking, not the web server — restart the rsyslog.service unit through the generic unit manager.",
             tool="services", operation="restart", args={"operation": "restart", "unit": "rsyslog.service"}),
    )),
    V3(id="contrast-0062", tool="services", kind="contrast", turns=(
        Turn(user_input="Even though nginx runs on this host too, right now I need crond.service restarted — the cron daemon, not the web layer.",
             tool="services", operation="restart", args={"operation": "restart", "unit": "crond.service"}),
    )),
    V3(id="contrast-0063", tool="services", kind="contrast", turns=(
        Turn(user_input="haproxy is the one wedged, not apache — restart haproxy.service directly.",
             tool="services", operation="restart", args={"operation": "restart", "unit": "haproxy.service"}),
    )),
    V3(id="contrast-0064", tool="services", kind="contrast", turns=(
        Turn(user_input="This request is about the chrony time daemon, not the reverse proxy — restart chronyd.service.",
             tool="services", operation="restart", args={"operation": "restart", "unit": "chronyd.service"}),
    )),
    V3(id="contrast-0065", tool="services", kind="contrast", turns=(
        Turn(user_input="sshd needs a bounce after the config change, not the web frontend — restart sshd.service via the general unit tool.",
             tool="services", operation="restart", args={"operation": "restart", "unit": "sshd.service"}),
    )),
    V3(id="contrast-0066", tool="services", kind="contrast", turns=(
        Turn(user_input="firewalld picked up a stale ruleset and the app team is asking about the site being slow — but what I actually need restarted is firewalld.service, not the web server.",
             tool="services", operation="restart", args={"operation": "restart", "unit": "firewalld.service"}),
    )),
    V3(id="contrast-0067", tool="nginx", kind="contrast", turns=(
        Turn(user_input="Even though a dozen other services are running fine, nginx specifically needs a restart after the vhost config change — restart it directly.",
             tool="nginx", operation="restart", args={"operation": "restart"}),
    )),
    V3(id="contrast-0068", tool="nginx", kind="contrast", turns=(
        Turn(user_input="This is literally the nginx web server that's stuck, not a generic unit — restart nginx.",
             tool="nginx", operation="restart", args={"operation": "restart"}),
    )),
    V3(id="contrast-0069", tool="nginx", kind="contrast", turns=(
        Turn(user_input="Reload didn't clear the stale worker processes for nginx — go ahead and restart the nginx web server outright.",
             tool="nginx", operation="restart", args={"operation": "restart"}),
    )),
    V3(id="contrast-0070", tool="nginx", kind="contrast", turns=(
        Turn(user_input="The site is served by nginx specifically here, not apache — restart the nginx service.",
             tool="nginx", operation="restart", args={"operation": "restart"}),
    )),
    V3(id="contrast-0071", tool="httpd", kind="contrast", turns=(
        Turn(user_input="This box runs Apache, not nginx, for the legacy app — restart the httpd service after the config edit.",
             tool="httpd", operation="restart", args={"operation": "restart"}),
    )),
    V3(id="contrast-0072", tool="httpd", kind="contrast", turns=(
        Turn(user_input="Apache HTTP Server is the one hanging on this host, specifically httpd — restart it directly, not some other unit.",
             tool="httpd", operation="restart", args={"operation": "restart"}),
    )),

    # ---- Pair 6: cron.edit (modify existing crontab) vs cron.crond-add (new /etc/cron.d drop-in) ----
    V3(id="contrast-0073", tool="cron", kind="contrast", turns=(
        Turn(user_input="I know /etc/cron.d/ exists too, but this is about the root user's personal crontab — replace it with an updated set of entries including the new backup line.",
             tool="cron", operation="edit", args={"operation": "edit", "content": "0 2 * * * /usr/local/bin/backup.sh\n*/15 * * * * /usr/local/bin/healthcheck.sh\n", "user": "root"}),
    )),
    V3(id="contrast-0074", tool="cron", kind="contrast", turns=(
        Turn(user_input="Update deploy user's existing crontab to add a nightly cleanup job — this is a per-user crontab edit, not a system-wide drop-in file.",
             tool="cron", operation="edit", args={"operation": "edit", "content": "30 3 * * * /home/deploy/cleanup.sh\n", "user": "deploy"}),
    )),
    V3(id="contrast-0075", tool="cron", kind="contrast", turns=(
        Turn(user_input="Modify my own personal crontab to change the report job's schedule from hourly to every 30 minutes — replace the whole crontab content.",
             tool="cron", operation="edit", args={"operation": "edit", "content": "*/30 * * * * /usr/local/bin/report.sh\n"}),
    )),
    V3(id="contrast-0076", tool="cron", kind="contrast", turns=(
        Turn(user_input="The www-data user's crontab needs the log rotation line removed — write back the trimmed crontab content for that user.",
             tool="cron", operation="edit", args={"operation": "edit", "content": "0 4 * * * /usr/local/bin/rotate_assets.sh\n", "user": "www-data"}),
    )),
    V3(id="contrast-0077", tool="cron", kind="contrast", turns=(
        Turn(user_input="I need to change what's already in postgres user's crontab, not drop a new file into /etc/cron.d — install this updated content.",
             tool="cron", operation="edit", args={"operation": "edit", "content": "0 1 * * * /usr/local/bin/pg_vacuum.sh\n", "user": "postgres"}),
    )),
    V3(id="contrast-0078", tool="cron", kind="contrast", turns=(
        Turn(user_input="Replace the admin user's personal crontab entirely with this new set of scheduled jobs.",
             tool="cron", operation="edit", args={"operation": "edit", "content": "15 6 * * * /usr/local/bin/audit_report.sh\n", "user": "admin"}),
    )),
    V3(id="contrast-0079", tool="cron", kind="contrast", turns=(
        Turn(user_input="I don't want this tied to any single user's personal crontab — drop a brand new system-wide job file into /etc/cron.d/ named 'nightly-backup'.",
             tool="cron", operation="crond-add", args={"operation": "crond-add", "name": "nightly-backup", "content": "0 2 * * * root /usr/local/bin/backup.sh\n"}),
    )),
    V3(id="contrast-0080", tool="cron", kind="contrast", turns=(
        Turn(user_input="Create a fresh /etc/cron.d/ drop-in called 'log-cleanup' for this new maintenance job — don't touch anyone's individual crontab.",
             tool="cron", operation="crond-add", args={"operation": "crond-add", "name": "log-cleanup", "content": "30 3 * * * root /usr/local/bin/clean_logs.sh\n"}),
    )),
    V3(id="contrast-0081", tool="cron", kind="contrast", turns=(
        Turn(user_input="Install a new system cron job as a standalone file in /etc/cron.d/ named 'metrics-export' rather than adding it to a user crontab.",
             tool="cron", operation="crond-add", args={"operation": "crond-add", "name": "metrics-export", "content": "*/10 * * * * root /usr/local/bin/export_metrics.sh\n"}),
    )),
    V3(id="contrast-0082", tool="cron", kind="contrast", turns=(
        Turn(user_input="This maintenance task shouldn't live under any single account's crontab — write it as a new drop-in file in /etc/cron.d/ called 'db-vacuum'.",
             tool="cron", operation="crond-add", args={"operation": "crond-add", "name": "db-vacuum", "content": "0 1 * * 0 root /usr/local/bin/vacuum_db.sh\n"}),
    )),
    V3(id="contrast-0083", tool="cron", kind="contrast", turns=(
        Turn(user_input="Add a brand-new /etc/cron.d/ entry file named 'cert-renew' for the certificate renewal job — this is a new system drop-in, not an edit to an existing crontab.",
             tool="cron", operation="crond-add", args={"operation": "crond-add", "name": "cert-renew", "content": "0 5 1 * * root /usr/local/bin/renew_certs.sh\n"}),
    )),
    V3(id="contrast-0084", tool="cron", kind="contrast", turns=(
        Turn(user_input="Create a new /etc/cron.d/ file called 'session-cleanup' for this recurring task — it needs to be its own drop-in, not appended to a user's crontab.",
             tool="cron", operation="crond-add", args={"operation": "crond-add", "name": "session-cleanup", "content": "0 0 * * * root /usr/local/bin/clean_sessions.sh\n"}),
    )),

    # ---- Pair 7: disk.format (make a filesystem) vs disk.wipe (destroy signatures) ----
    V3(id="contrast-0085", tool="disk", kind="contrast", turns=(
        Turn(user_input="/dev/sdb1 is a blank disk we just partitioned — put a fresh ext4 filesystem on it so we can mount it and start using it.",
             tool="disk", operation="format", args={"operation": "format", "device": "/dev/sdb1", "fstype": "ext4"}),
    )),
    V3(id="contrast-0086", tool="disk", kind="contrast", turns=(
        Turn(user_input="We need /dev/nvme1n1p1 ready to mount and store data — create an xfs filesystem on it.",
             tool="disk", operation="format", args={"operation": "format", "device": "/dev/nvme1n1p1", "fstype": "xfs"}),
    )),
    V3(id="contrast-0087", tool="disk", kind="contrast", turns=(
        Turn(user_input="This new drive /dev/sdc1 needs to actually hold a filesystem before we can mount it — build an ext4 filesystem on it.",
             tool="disk", operation="format", args={"operation": "format", "device": "/dev/sdc1", "fstype": "ext4"}),
    )),
    V3(id="contrast-0088", tool="disk", kind="contrast", turns=(
        Turn(user_input="Prep /dev/sdd1 for the new volume group by giving it a usable filesystem — ext4 will do.",
             tool="disk", operation="format", args={"operation": "format", "device": "/dev/sdd1", "fstype": "ext4"}),
    )),
    V3(id="contrast-0089", tool="disk", kind="contrast", turns=(
        Turn(user_input="The backup target /dev/sde1 is unformatted right now — lay down an xfs filesystem so rsync has somewhere to write.",
             tool="disk", operation="format", args={"operation": "format", "device": "/dev/sde1", "fstype": "xfs"}),
    )),
    V3(id="contrast-0090", tool="disk", kind="contrast", turns=(
        Turn(user_input="Turn /dev/sdf1 into a usable ext4 volume — it's currently just raw, unformatted space.",
             tool="disk", operation="format", args={"operation": "format", "device": "/dev/sdf1", "fstype": "ext4"}),
    )),
    V3(id="contrast-0091", tool="disk", kind="contrast", turns=(
        Turn(user_input="Before we repurpose /dev/sdb2 for a new pool, strip off whatever old filesystem signature is left on it — don't build a new filesystem, just erase the old markers.",
             tool="disk", operation="wipe", args={"operation": "wipe", "device": "/dev/sdb2"}),
    )),
    V3(id="contrast-0092", tool="disk", kind="contrast", turns=(
        Turn(user_input="/dev/sdc2 still has stale LVM/ext4 signatures from its old life — clear those signatures off the device, no new filesystem needed yet.",
             tool="disk", operation="wipe", args={"operation": "wipe", "device": "/dev/sdc2"}),
    )),
    V3(id="contrast-0093", tool="disk", kind="contrast", turns=(
        Turn(user_input="This decommissioned drive /dev/sdd2 confuses the installer because of leftover partition signatures — wipe those off before we do anything else with it.",
             tool="disk", operation="wipe", args={"operation": "wipe", "device": "/dev/sdd2"}),
    )),
    V3(id="contrast-0094", tool="disk", kind="contrast", turns=(
        Turn(user_input="Erase all the existing filesystem/RAID signatures from /dev/sde2 — we just want the signatures gone, not a fresh filesystem laid down yet.",
             tool="disk", operation="wipe", args={"operation": "wipe", "device": "/dev/sde2"}),
    )),
    V3(id="contrast-0095", tool="disk", kind="contrast", turns=(
        Turn(user_input="/dev/sdf2 keeps getting auto-detected as an old btrfs volume — remove the stale signature from the device.",
             tool="disk", operation="wipe", args={"operation": "wipe", "device": "/dev/sdf2"}),
    )),
    V3(id="contrast-0096", tool="disk", kind="contrast", turns=(
        Turn(user_input="Clear the leftover filesystem signature on /dev/sdg2 from its previous life as a swap partition — just the signature wipe, nothing else.",
             tool="disk", operation="wipe", args={"operation": "wipe", "device": "/dev/sdg2"}),
    )),

    # ---- Pair 8: sysctl.set (runtime only) vs sysctl.persist (write to sysctl.d) ----
    V3(id="contrast-0097", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="I just want to test net.ipv4.ip_forward=1 for this debugging session — set it live, it's fine if it reverts on reboot.",
             tool="sysctl", operation="set", args={"operation": "set", "key": "net.ipv4.ip_forward", "value": "1"}),
    )),
    V3(id="contrast-0098", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="Temporarily bump vm.swappiness to 10 right now for this benchmark run — no need to write anything to sysctl.d.",
             tool="sysctl", operation="set", args={"operation": "set", "key": "vm.swappiness", "value": "10"}),
    )),
    V3(id="contrast-0099", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="Just apply net.core.somaxconn=1024 at runtime for this test — I'll revert it manually later, don't touch any config files.",
             tool="sysctl", operation="set", args={"operation": "set", "key": "net.core.somaxconn", "value": "1024"}),
    )),
    V3(id="contrast-0100", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="Set fs.file-max to 200000 live on this box right now — this is throwaway, don't persist it anywhere.",
             tool="sysctl", operation="set", args={"operation": "set", "key": "fs.file-max", "value": "200000"}),
    )),
    V3(id="contrast-0101", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="Runtime-only change: kernel.panic to 10 seconds, just for this session's testing, no drop-in file needed.",
             tool="sysctl", operation="set", args={"operation": "set", "key": "kernel.panic", "value": "10"}),
    )),
    V3(id="contrast-0102", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="Apply net.ipv4.tcp_keepalive_time=300 immediately for this troubleshooting window — it's fine if a reboot wipes it out.",
             tool="sysctl", operation="set", args={"operation": "set", "key": "net.ipv4.tcp_keepalive_time", "value": "300"}),
    )),
    V3(id="contrast-0103", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="This net.ipv4.ip_forward=1 change needs to survive a reboot — write it to sysctl.d and reload, don't just set it live.",
             tool="sysctl", operation="persist", args={"operation": "persist", "key": "net.ipv4.ip_forward", "value": "1"}),
    )),
    V3(id="contrast-0104", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="We want vm.swappiness=10 to stick permanently across reboots — persist it to a sysctl.d drop-in, not just a runtime tweak.",
             tool="sysctl", operation="persist", args={"operation": "persist", "key": "vm.swappiness", "value": "10"}),
    )),
    V3(id="contrast-0105", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="Make net.core.somaxconn=1024 a permanent setting by writing it into /etc/sysctl.d/ and reloading — this needs to outlive a reboot.",
             tool="sysctl", operation="persist", args={"operation": "persist", "key": "net.core.somaxconn", "value": "1024"}),
    )),
    V3(id="contrast-0106", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="fs.file-max=200000 is going into production config — persist it durably, not a one-off runtime change.",
             tool="sysctl", operation="persist", args={"operation": "persist", "key": "fs.file-max", "value": "200000"}),
    )),
    V3(id="contrast-0107", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="We need kernel.panic=10 to remain in effect even after the next reboot — write it durably to sysctl.d.",
             tool="sysctl", operation="persist", args={"operation": "persist", "key": "kernel.panic", "value": "10"}),
    )),
    V3(id="contrast-0108", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="Persist net.ipv4.tcp_keepalive_time=300 permanently via a sysctl.d drop-in — this must survive reboots, unlike a quick runtime set.",
             tool="sysctl", operation="persist", args={"operation": "persist", "key": "net.ipv4.tcp_keepalive_time", "value": "300"}),
    )),

    # ---- Pair 9: at.schedule (one-off) vs cron / systemd_timers (recurring) ----
    V3(id="contrast-0109", tool="at", kind="contrast", turns=(
        Turn(user_input="I know we usually use cron for scheduled work, but this is a single one-time reboot tonight at 23:00 — queue it as a one-off job.",
             tool="at", operation="schedule", args={"operation": "schedule", "time": "23:00", "command": "systemctl reboot"}),
    )),
    V3(id="contrast-0110", tool="at", kind="contrast", turns=(
        Turn(user_input="This maintenance script only needs to run once, in about an hour — not on a recurring schedule, just a single deferred run.",
             tool="at", operation="schedule", args={"operation": "schedule", "time": "now + 1 hour", "command": "/usr/local/bin/maintenance.sh"}),
    )),
    V3(id="contrast-0111", tool="at", kind="contrast", turns=(
        Turn(user_input="Queue a single execution of the cache-clear script for midnight tonight — this is a one-time thing, not a recurring cron entry.",
             tool="at", operation="schedule", args={"operation": "schedule", "time": "midnight", "command": "/usr/local/bin/clear_cache.sh"}),
    )),
    V3(id="contrast-0112", tool="at", kind="contrast", turns=(
        Turn(user_input="We just need this data migration to fire once, tomorrow at noon — schedule it as a single deferred job, no recurring timer.",
             tool="at", operation="schedule", args={"operation": "schedule", "time": "noon tomorrow", "command": "/usr/local/bin/migrate.sh"}),
    )),
    V3(id="contrast-0113", tool="at", kind="contrast", turns=(
        Turn(user_input="Run the certificate rollback script exactly one time, 30 minutes from now — not every day, just this once.",
             tool="at", operation="schedule", args={"operation": "schedule", "time": "now + 30 minutes", "command": "/usr/local/bin/rollback_cert.sh"}),
    )),
    V3(id="contrast-0114", tool="at", kind="contrast", turns=(
        Turn(user_input="Schedule the disk-check script to run once tonight at 02:00 — it's a single deferred run for tonight's maintenance window only.",
             tool="at", operation="schedule", args={"operation": "schedule", "time": "02:00", "command": "/usr/local/bin/disk_check.sh"}),
    )),
    V3(id="contrast-0115", tool="cron", kind="contrast", turns=(
        Turn(user_input="This backup needs to run every single night going forward at 2am, not just once — install it as a recurring crontab entry.",
             tool="cron", operation="edit", args={"operation": "edit", "content": "0 2 * * * /usr/local/bin/backup.sh\n", "user": "root"}),
    )),
    V3(id="contrast-0116", tool="cron", kind="contrast", turns=(
        Turn(user_input="We need the log-rotation script to run every day, indefinitely — set it up as a recurring drop-in in /etc/cron.d, not a single deferred job.",
             tool="cron", operation="crond-add", args={"operation": "crond-add", "name": "logrotate-daily", "content": "0 3 * * * root /usr/local/bin/rotate.sh\n"}),
    )),
    V3(id="contrast-0117", tool="cron", kind="contrast", turns=(
        Turn(user_input="This health check needs to keep running every 15 minutes forever, not just once tonight — put it in the crontab as a recurring entry.",
             tool="cron", operation="edit", args={"operation": "edit", "content": "*/15 * * * * /usr/local/bin/healthcheck.sh\n", "user": "monitor"}),
    )),
    V3(id="contrast-0118", tool="systemd_timers", kind="contrast", turns=(
        Turn(user_input="We want the metrics export to run on a recurring daily schedule going forward, managed as a proper systemd timer, not a single deferred run.",
             tool="systemd_timers", operation="create", args={"operation": "create", "timer": "metrics-export.timer", "content": "[Unit]\nDescription=Daily metrics export\n\n[Timer]\nOnCalendar=daily\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n"}),
    )),
    V3(id="contrast-0119", tool="systemd_timers", kind="contrast", turns=(
        Turn(user_input="This vacuum job needs to recur every week indefinitely — install and enable it as a systemd timer unit, not a one-shot deferred job.",
             tool="systemd_timers", operation="create", args={"operation": "create", "timer": "db-vacuum.timer", "content": "[Unit]\nDescription=Weekly DB vacuum\n\n[Timer]\nOnCalendar=weekly\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n"}),
    )),
    V3(id="contrast-0120", tool="systemd_timers", kind="contrast", turns=(
        Turn(user_input="Enable the existing snapshot.timer so it keeps recurring at boot going forward — this is ongoing, not a single deferred run.",
             tool="systemd_timers", operation="enable", args={"operation": "enable", "timer": "snapshot.timer"}),
    )),

    # ---- Pair 10: processes.signal / processes.kill vs services.stop (a PID vs a unit) ----
    V3(id="contrast-0121", tool="processes", kind="contrast", turns=(
        Turn(user_input="There's a runaway python process at PID 48213 that isn't tied to any systemd unit — send it a SIGTERM directly.",
             tool="processes", operation="signal", args={"operation": "signal", "pid": 48213, "signal_num": 15}),
    )),
    V3(id="contrast-0122", tool="processes", kind="contrast", turns=(
        Turn(user_input="PID 51022 is a stray worker process spawned outside systemd's control — kill it with SIGKILL directly by PID.",
             tool="processes", operation="signal", args={"operation": "signal", "pid": 51022, "signal_num": 9}),
    )),
    V3(id="contrast-0123", tool="processes", kind="contrast", turns=(
        Turn(user_input="This one specific process, PID 60934, is hung and needs to be force-killed — it's a standalone process, not something managed by systemd.",
             tool="processes", operation="signal", args={"operation": "signal", "pid": 60934, "signal_num": 9}),
    )),
    V3(id="contrast-0124", tool="processes", kind="contrast", turns=(
        Turn(user_input="Send SIGHUP to PID 33221 to make it reload its config — it's a manually-launched process, not a systemd-managed service.",
             tool="processes", operation="signal", args={"operation": "signal", "pid": 33221, "signal_num": 1}),
    )),
    V3(id="contrast-0125", tool="processes", kind="contrast", turns=(
        Turn(user_input="Terminate the orphaned process at PID 71284 directly — there's no unit tracking it, so target it by PID with SIGTERM.",
             tool="processes", operation="signal", args={"operation": "signal", "pid": 71284, "signal_num": 15}),
    )),
    V3(id="contrast-0126", tool="processes", kind="contrast", turns=(
        Turn(user_input="Kill PID 40017 outright — it's a leftover shell script process, not something with a systemd unit to stop.",
             tool="processes", operation="signal", args={"operation": "signal", "pid": 40017, "signal_num": 9}),
    )),
    V3(id="contrast-0127", tool="services", kind="contrast", turns=(
        Turn(user_input="I don't want to hunt down a PID for this — just stop the redis.service unit cleanly through systemd.",
             tool="services", operation="stop", args={"operation": "stop", "unit": "redis.service"}),
    )),
    V3(id="contrast-0128", tool="services", kind="contrast", turns=(
        Turn(user_input="Shut down the whole worker-queue.service unit properly via systemd, not by killing individual worker PIDs.",
             tool="services", operation="stop", args={"operation": "stop", "unit": "worker-queue.service"}),
    )),
    V3(id="contrast-0129", tool="services", kind="contrast", turns=(
        Turn(user_input="Stop the elasticsearch.service unit the normal systemd way — I don't need to touch any individual process IDs.",
             tool="services", operation="stop", args={"operation": "stop", "unit": "elasticsearch.service"}),
    )),
    V3(id="contrast-0130", tool="services", kind="contrast", turns=(
        Turn(user_input="Bring down the tomcat.service unit cleanly through systemctl stop, rather than signaling its process directly.",
             tool="services", operation="stop", args={"operation": "stop", "unit": "tomcat.service"}),
    )),
    V3(id="contrast-0131", tool="services", kind="contrast", turns=(
        Turn(user_input="Stop the celery-worker.service unit via systemd — I want the managed shutdown, not a raw kill on some PID.",
             tool="services", operation="stop", args={"operation": "stop", "unit": "celery-worker.service"}),
    )),
    V3(id="contrast-0132", tool="services", kind="contrast", turns=(
        Turn(user_input="Please stop the memcached.service unit through systemctl, since it's properly managed as a unit here.",
             tool="services", operation="stop", args={"operation": "stop", "unit": "memcached.service"}),
    )),

    # ---- Pair 11: files.remove (delete a file/dir) vs disk.unmount / disk.wipe ----
    V3(id="contrast-0133", tool="files", kind="contrast", turns=(
        Turn(user_input="This one stale log file /var/log/app/debug.log.old is cluttering the filesystem — delete it outright, don't touch the mount or the disk itself.",
             tool="files", operation="remove", args={"operation": "remove", "path": "/var/log/app/debug.log.old"}),
    )),
    V3(id="contrast-0134", tool="files", kind="contrast", turns=(
        Turn(user_input="The directory /srv/data/tmp_export is just leftover scratch files on an otherwise healthy mounted disk — remove it recursively, this isn't a disk-level operation.",
             tool="files", operation="remove", args={"operation": "remove", "path": "/srv/data/tmp_export", "recursive": True}),
    )),
    V3(id="contrast-0135", tool="files", kind="contrast", turns=(
        Turn(user_input="I need to get rid of /opt/app/cache/stale_build at the file level, not unmount the whole volume it lives on — remove that directory recursively.",
             tool="files", operation="remove", args={"operation": "remove", "path": "/opt/app/cache/stale_build", "recursive": True}),
    )),
    V3(id="contrast-0136", tool="files", kind="contrast", turns=(
        Turn(user_input="Just delete the single file /home/deploy/uploads/corrupt_upload.zip — the filesystem underneath is fine, leave it mounted.",
             tool="files", operation="remove", args={"operation": "remove", "path": "/home/deploy/uploads/corrupt_upload.zip"}),
    )),
    V3(id="contrast-0137", tool="files", kind="contrast", turns=(
        Turn(user_input="The /srv/www/old_site directory needs to go entirely — remove it recursively, we're not touching the block device it's stored on.",
             tool="files", operation="remove", args={"operation": "remove", "path": "/srv/www/old_site", "recursive": True}),
    )),
    V3(id="contrast-0138", tool="files", kind="contrast", turns=(
        Turn(user_input="Delete the single bad file /var/spool/mail/stuck.msg — this is a file-level cleanup, the mount stays as-is.",
             tool="files", operation="remove", args={"operation": "remove", "path": "/var/spool/mail/stuck.msg"}),
    )),
    V3(id="contrast-0139", tool="disk", kind="contrast", turns=(
        Turn(user_input="We're done with the /mnt/backup volume for this maintenance window — detach the mounted filesystem, don't just delete files off of it.",
             tool="disk", operation="unmount", args={"operation": "unmount", "target": "/mnt/backup"}),
    )),
    V3(id="contrast-0140", tool="disk", kind="contrast", turns=(
        Turn(user_input="Before we physically remove the drive, detach /dev/sdb1 from its mount point entirely — this is a device-level unmount, not clearing individual files.",
             tool="disk", operation="unmount", args={"operation": "unmount", "target": "/dev/sdb1"}),
    )),
    V3(id="contrast-0141", tool="disk", kind="contrast", turns=(
        Turn(user_input="Detach the /data volume from the system before we swap the drive — unmount the whole filesystem, not individual files inside it.",
             tool="disk", operation="unmount", args={"operation": "unmount", "target": "/data"}),
    )),
    V3(id="contrast-0142", tool="disk", kind="contrast", turns=(
        Turn(user_input="This old /dev/sdc1 partition needs its filesystem signatures erased entirely before reuse — wipe the whole device, not just clear out files.",
             tool="disk", operation="wipe", args={"operation": "wipe", "device": "/dev/sdc1"}),
    )),
    V3(id="contrast-0143", tool="disk", kind="contrast", turns=(
        Turn(user_input="We're repurposing the entire /dev/sdd1 device — wipe its filesystem signature, we're not just cleaning out a directory on it.",
             tool="disk", operation="wipe", args={"operation": "wipe", "device": "/dev/sdd1"}),
    )),
    V3(id="contrast-0144", tool="disk", kind="contrast", turns=(
        Turn(user_input="Unmount /mnt/scratch entirely so we can service the underlying disk — this is a device detach, not deleting the files stored on it.",
             tool="disk", operation="unmount", args={"operation": "unmount", "target": "/mnt/scratch"}),
    )),

    # ---- Pair 12: hostname.set-hostname vs dns.host ----
    V3(id="contrast-0145", tool="hostname", kind="contrast", turns=(
        Turn(user_input="We're renaming this box as part of the migration — set its actual hostname to db-primary-02.internal, persistently.",
             tool="hostname", operation="set-hostname", args={"operation": "set-hostname", "name": "db-primary-02.internal"}),
    )),
    V3(id="contrast-0146", tool="hostname", kind="contrast", turns=(
        Turn(user_input="This server needs a new identity after the rack move — change the system hostname itself to rack3-web-04.example.com.",
             tool="hostname", operation="set-hostname", args={"operation": "set-hostname", "name": "rack3-web-04.example.com"}),
    )),
    V3(id="contrast-0147", tool="hostname", kind="contrast", turns=(
        Turn(user_input="Update this host's own name in the system to app-worker-07 — persistent change, not a DNS lookup.",
             tool="hostname", operation="set-hostname", args={"operation": "set-hostname", "name": "app-worker-07"}),
    )),
    V3(id="contrast-0148", tool="hostname", kind="contrast", turns=(
        Turn(user_input="Rename this machine's hostname to cache-node-11.internal as part of the naming-convention cleanup.",
             tool="hostname", operation="set-hostname", args={"operation": "set-hostname", "name": "cache-node-11.internal"}),
    )),
    V3(id="contrast-0149", tool="hostname", kind="contrast", turns=(
        Turn(user_input="Set this system's hostname to monitoring-02.corp.local — that's the box's own identity, not something we're resolving over DNS.",
             tool="hostname", operation="set-hostname", args={"operation": "set-hostname", "name": "monitoring-02.corp.local"}),
    )),
    V3(id="contrast-0150", tool="hostname", kind="contrast", turns=(
        Turn(user_input="Change the local system hostname to build-runner-19 — we're reassigning this box's own name, nothing to do with looking up other hosts.",
             tool="hostname", operation="set-hostname", args={"operation": "set-hostname", "name": "build-runner-19"}),
    )),
    V3(id="contrast-0151", tool="dns", kind="contrast", turns=(
        Turn(user_input="I need to know what address db-primary-02.internal actually resolves to on the network, not rename anything — do a lookup with the host utility.",
             tool="dns", operation="host", args={"operation": "host", "name": "db-primary-02.internal"}),
    )),
    V3(id="contrast-0152", tool="dns", kind="contrast", turns=(
        Turn(user_input="Just resolve the name rack3-web-04.example.com to its IP using host — I'm not touching this machine's own hostname.",
             tool="dns", operation="host", args={"operation": "host", "name": "rack3-web-04.example.com"}),
    )),
    V3(id="contrast-0153", tool="dns", kind="contrast", turns=(
        Turn(user_input="Look up app-worker-07 via the host command to confirm what DNS returns for it — that's separate from what this box calls itself.",
             tool="dns", operation="host", args={"operation": "host", "name": "app-worker-07"}),
    )),
    V3(id="contrast-0154", tool="dns", kind="contrast", turns=(
        Turn(user_input="Resolve cache-node-11.internal with the host lookup tool so I can confirm its current DNS record, no renaming involved.",
             tool="dns", operation="host", args={"operation": "host", "name": "cache-node-11.internal"}),
    )),
    V3(id="contrast-0155", tool="dns", kind="contrast", turns=(
        Turn(user_input="I want to check what monitoring-02.corp.local resolves to via host — separate question from this server's own hostname.",
             tool="dns", operation="host", args={"operation": "host", "name": "monitoring-02.corp.local"}),
    )),
    V3(id="contrast-0156", tool="dns", kind="contrast", turns=(
        Turn(user_input="Use the host utility to resolve build-runner-19 and tell me what it returns — I'm querying DNS, not changing this machine's identity.",
             tool="dns", operation="host", args={"operation": "host", "name": "build-runner-19"}),
    )),

    # ---- Pair 13: docs.retrieve (how/what/why, no action) vs any read op ----
    V3(id="contrast-0157", tool="docs", kind="contrast", turns=(
        Turn(user_input="Before I mount anything, explain what the noexec mount flag actually does and when it's appropriate to use.",
             tool="docs", operation="retrieve", args={"operation": "retrieve", "query": "noexec mount flag behaviour"}),
    )),
    V3(id="contrast-0158", tool="docs", kind="contrast", turns=(
        Turn(user_input="I'm not asking you to check any live database right now — just explain how PostgreSQL's WAL (write-ahead log) mechanism works conceptually.",
             tool="docs", operation="retrieve", args={"operation": "retrieve", "query": "PostgreSQL write-ahead log mechanism"}),
    )),
    V3(id="contrast-0159", tool="docs", kind="contrast", turns=(
        Turn(user_input="What's the actual difference between SIGTERM and SIGKILL in terms of process cleanup behavior — no need to touch any real process right now.",
             tool="docs", operation="retrieve", args={"operation": "retrieve", "query": "SIGTERM vs SIGKILL process cleanup behaviour"}),
    )),
    V3(id="contrast-0160", tool="docs", kind="contrast", turns=(
        Turn(user_input="Why would fapolicyd deny a binary even if the file permissions look fine? Just explain the reasoning, don't check any current rules.",
             tool="docs", operation="retrieve", args={"operation": "retrieve", "query": "fapolicyd deny rule reasoning beyond file permissions"}),
    )),
    V3(id="contrast-0161", tool="docs", kind="contrast", turns=(
        Turn(user_input="How does SELinux enforcing mode differ from permissive mode in terms of what actually gets blocked versus logged? I just want the explanation.",
             tool="docs", operation="retrieve", args={"operation": "retrieve", "query": "SELinux enforcing vs permissive mode behaviour"}),
    )),
    V3(id="contrast-0162", tool="docs", kind="contrast", turns=(
        Turn(user_input="What does the sysctl vm.swappiness parameter actually control conceptually — I don't need its current value on this host, just the explanation.",
             tool="docs", operation="retrieve", args={"operation": "retrieve", "query": "vm.swappiness kernel parameter meaning"}),
    )),
    V3(id="contrast-0163", tool="processes", kind="contrast", turns=(
        Turn(user_input="Skip the theory — go check the actual current state of process PID 22019 on this host right now.",
             tool="processes", operation="info", args={"operation": "info", "pid": 22019}),
    )),
    V3(id="contrast-0164", tool="disk", kind="contrast", turns=(
        Turn(user_input="Don't explain how mount flags work in general — go check the actual current filesystem usage on this host right now.",
             tool="disk", operation="usage", args={"operation": "usage"}),
    )),
    V3(id="contrast-0165", tool="selinux", kind="contrast", turns=(
        Turn(user_input="Forget the conceptual explanation — check what enforcement mode SELinux is actually running in on this specific host right now.",
             tool="selinux", operation="getenforce", args={"operation": "getenforce"}),
    )),
    V3(id="contrast-0166", tool="sysctl", kind="contrast", turns=(
        Turn(user_input="I don't need the general explanation of what vm.swappiness means — read its actual current value on this box.",
             tool="sysctl", operation="get", args={"operation": "get", "key": "vm.swappiness"}),
    )),
    V3(id="contrast-0167", tool="postgresql", kind="contrast", turns=(
        Turn(user_input="Skip the WAL theory question — go check whether the actual postgres service on this host is currently up.",
             tool="postgresql", operation="status", args={"operation": "status"}),
    )),
    V3(id="contrast-0168", tool="fapolicyd", kind="contrast", turns=(
        Turn(user_input="Never mind the general reasoning behind fapolicyd deny rules — list the actual rules currently loaded on this host.",
             tool="fapolicyd", operation="list_rules", args={"operation": "list_rules"}),
    )),

    # ---- Pair 14: performance.iostat / performance.vmstat vs disk.usage / processes.list ----
    V3(id="contrast-0169", tool="performance", kind="contrast", turns=(
        Turn(user_input="The storage array feels slow under load, not full — I need I/O throughput and latency stats, not a free-space report.",
             tool="performance", operation="iostat", args={"operation": "iostat"}),
    )),
    V3(id="contrast-0170", tool="performance", kind="contrast", turns=(
        Turn(user_input="I don't care how much disk space is used right now — show me the actual I/O statistics, reads/writes per second, over 3 samples.",
             tool="performance", operation="iostat", args={"operation": "iostat", "interval": 2, "count": 3}),
    )),
    V3(id="contrast-0171", tool="performance", kind="contrast", turns=(
        Turn(user_input="Disk usage percentage isn't the issue here — I need to see disk I/O throughput to figure out if the array is bottlenecked.",
             tool="performance", operation="iostat", args={"operation": "iostat"}),
    )),
    V3(id="contrast-0172", tool="performance", kind="contrast", turns=(
        Turn(user_input="Memory feels tight but I'm not asking for a process list — give me vmstat's memory and swap statistics over 5 samples.",
             tool="performance", operation="vmstat", args={"operation": "vmstat", "interval": 1, "count": 5}),
    )),
    V3(id="contrast-0173", tool="performance", kind="contrast", turns=(
        Turn(user_input="I don't need to know which processes are running — just the virtual memory statistics: free, swap, buffers, from vmstat.",
             tool="performance", operation="vmstat", args={"operation": "vmstat"}),
    )),
    V3(id="contrast-0174", tool="performance", kind="contrast", turns=(
        Turn(user_input="Forget listing what's running — I want vmstat's paging and swap-in/swap-out numbers to see if we're thrashing.",
             tool="performance", operation="vmstat", args={"operation": "vmstat", "interval": 2, "count": 2}),
    )),
    V3(id="contrast-0175", tool="disk", kind="contrast", turns=(
        Turn(user_input="I don't need I/O throughput numbers right now — just tell me how much free space is left on /var.",
             tool="disk", operation="usage", args={"operation": "usage", "path": "/var"}),
    )),
    V3(id="contrast-0176", tool="disk", kind="contrast", turns=(
        Turn(user_input="Forget read/write latency stats — show me the plain used-versus-free breakdown per filesystem.",
             tool="disk", operation="usage", args={"operation": "usage"}),
    )),
    V3(id="contrast-0177", tool="disk", kind="contrast", turns=(
        Turn(user_input="Skip the I/O throughput question — I just need the free-space report for the filesystem holding /home.",
             tool="disk", operation="usage", args={"operation": "usage", "path": "/home"}),
    )),
    V3(id="contrast-0178", tool="processes", kind="contrast", turns=(
        Turn(user_input="I'm not asking about memory paging stats — just list every process currently running on this host.",
             tool="processes", operation="list", args={"operation": "list"}),
    )),
    V3(id="contrast-0179", tool="processes", kind="contrast", turns=(
        Turn(user_input="Skip vmstat's swap numbers for now — show me what's actually running, sorted by CPU usage.",
             tool="processes", operation="top", args={"operation": "top"}),
    )),
    V3(id="contrast-0180", tool="processes", kind="contrast", turns=(
        Turn(user_input="I don't need throughput or free-space figures right now — just give me the full process list on this host.",
             tool="processes", operation="list", args={"operation": "list"}),
    )),
]

from finetune.scenarios_v3 import check_module
# the file spans many tools; validate per tool
for _t in sorted({s.tool for s in SCENARIOS_V3}):
    check_module(_t, [s for s in SCENARIOS_V3 if s.tool == _t])
