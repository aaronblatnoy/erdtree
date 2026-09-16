"""finetune/scenarios_v3/files.py — corpus v3 multi-turn scenarios for 'files'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="files-v3-0001", tool="files", kind="followup", turns=(
        Turn(user_input="list what's in /var/www/html", tool="files", operation="list",
             args={"operation": "list", "path": "/var/www/html"}),
        Turn(user_input="now the same for /var/www/staging", tool="files", operation="list",
             args={"operation": "list", "path": "/var/www/staging"}),
    )),
    V3(id="files-v3-0002", tool="files", kind="followup", turns=(
        Turn(user_input="stat /etc/nginx/nginx.conf for me", tool="files", operation="stat",
             args={"operation": "stat", "path": "/etc/nginx/nginx.conf"}),
        Turn(user_input="ok, chmod it to 644", tool="files", operation="chmod",
             args={"operation": "chmod", "mode": "644", "path": "/etc/nginx/nginx.conf"}),
    )),
    V3(id="files-v3-0003", tool="files", kind="followup", turns=(
        Turn(user_input="find every .log file under /var/log/httpd", tool="files", operation="find",
             args={"operation": "find", "path": "/var/log/httpd", "name": "*.log", "type": "f"}),
        Turn(user_input="and do the same search under /var/log/nginx", tool="files", operation="find",
             args={"operation": "find", "path": "/var/log/nginx", "name": "*.log", "type": "f"}),
    )),
    V3(id="files-v3-0004", tool="files", kind="followup", turns=(
        Turn(user_input="copy /etc/httpd/conf/httpd.conf to /etc/httpd/conf/httpd.conf.bak", tool="files", operation="copy",
             args={"operation": "copy", "src": "/etc/httpd/conf/httpd.conf", "dst": "/etc/httpd/conf/httpd.conf.bak"}),
        Turn(user_input="now read that backup to confirm it copied cleanly", tool="files", operation="read",
             args={"operation": "read", "path": "/etc/httpd/conf/httpd.conf.bak", "lines": 50}),
    )),
    V3(id="files-v3-0005", tool="files", kind="followup", turns=(
        Turn(user_input="make a directory /srv/backups/2026-09-16", tool="files", operation="mkdir",
             args={"operation": "mkdir", "path": "/srv/backups/2026-09-16", "parents": True}),
        Turn(user_input="undo that, wrong date, remove it", tool="files", operation="remove",
             args={"operation": "remove", "path": "/srv/backups/2026-09-16", "recursive": True}),
    )),
    V3(id="files-v3-0006", tool="files", kind="followup", turns=(
        Turn(user_input="move /opt/releases/app-1.2.tar.gz to /opt/releases/archive/app-1.2.tar.gz", tool="files", operation="move",
             args={"operation": "move", "src": "/opt/releases/app-1.2.tar.gz", "dst": "/opt/releases/archive/app-1.2.tar.gz"}),
        Turn(user_input="no wait, use the other target instead, /opt/releases/archive/app-1.2-final.tar.gz", tool="files", operation="move",
             args={"operation": "move", "src": "/opt/releases/archive/app-1.2.tar.gz", "dst": "/opt/releases/archive/app-1.2-final.tar.gz"}),
    )),
    V3(id="files-v3-0007", tool="files", kind="followup", turns=(
        Turn(user_input="chown deploy:deploy on /srv/app recursively", tool="files", operation="chown",
             args={"operation": "chown", "owner": "deploy:deploy", "path": "/srv/app", "recursive": True}),
        Turn(user_input="also do the same for /srv/app-static", tool="files", operation="chown",
             args={"operation": "chown", "owner": "deploy:deploy", "path": "/srv/app-static", "recursive": True}),
    )),
    V3(id="files-v3-0008", tool="files", kind="followup", turns=(
        Turn(user_input="write a systemd drop-in to /etc/systemd/system/app.service.d/override.conf with content [Service]\nMemoryMax=2G", tool="files", operation="write",
             args={"operation": "write", "path": "/etc/systemd/system/app.service.d/override.conf", "content": "[Service]\nMemoryMax=2G"}),
        Turn(user_input="now check that same unit's status", tool="services", operation="status",
             args={"operation": "status", "unit": "app.service"}),
    )),
    V3(id="files-v3-0009", tool="files", kind="followup", turns=(
        Turn(user_input="find every core dump file under /var/crash", tool="files", operation="find",
             args={"operation": "find", "path": "/var/crash", "name": "core.*", "type": "f"}),
        Turn(user_input="yes, remove them all, force it", tool="files", operation="remove",
             args={"operation": "remove", "path": "/var/crash", "recursive": True, "force": True}),
        Turn(user_input="now recreate that directory so crash dumps have somewhere to land", tool="files", operation="mkdir",
             args={"operation": "mkdir", "path": "/var/crash", "parents": True}),
    )),
    V3(id="files-v3-0010", tool="files", kind="question", turns=(
        Turn(user_input="stat /var/lib/pgsql/data/postgresql.conf", tool="files", operation="stat",
             args={"operation": "stat", "path": "/var/lib/pgsql/data/postgresql.conf"}),
        Turn(user_input="what does that permission bit mean for who can edit this file",
             answer="Those are standard owner/group/other rwx bits — if it shows postgres as owner with 600, only the postgres user can read or write it, which is the expected lockdown for a config holding connection settings. Anyone else needs sudo to touch it."),
    )),
    V3(id="files-v3-0011", tool="files", kind="question", turns=(
        Turn(user_input="find any file larger than expected under /var/log named messages*", tool="files", operation="find",
             args={"operation": "find", "path": "/var/log", "name": "messages*", "type": "f"}),
        Turn(user_input="why did that turn up so many rotated copies",
             answer="logrotate is doing its job — messages, messages-1, messages-2.gz and so on are the rotated history kept per the retention count in /etc/logrotate.conf. If the count looks too high, tighten the rotate setting there rather than deleting files by hand."),
    )),
    V3(id="files-v3-0012", tool="files", kind="question", turns=(
        Turn(user_input="remove /tmp/build-cache recursively and force it", tool="files", operation="remove",
             args={"operation": "remove", "path": "/tmp/build-cache", "recursive": True, "force": True}),
        Turn(user_input="what happened, did that need confirmation",
             answer="Recursive+force removal of a normal path under /tmp runs straight through without a prompt — the typed-confirmation requirement only kicks in for recursive or forced deletes against system paths. The directory and everything under it is gone."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("files", SCENARIOS_V3)
