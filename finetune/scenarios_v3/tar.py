"""finetune/scenarios_v3/tar.py — corpus v3 multi-turn scenarios for 'tar'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="tar-v3-0001", tool="tar", kind="followup", turns=(
        Turn(user_input="create a tar archive at /backup/etc.tar from /etc", tool="tar", operation="create", args={"operation": "create", "archive": "/backup/etc.tar", "sources": ["/etc"]}),
        Turn(user_input="now list what's in it to confirm", tool="tar", operation="list", args={"operation": "list", "archive": "/backup/etc.tar"}),
    )),
    V3(id="tar-v3-0002", tool="tar", kind="followup", turns=(
        Turn(user_input="create a gzip archive at /backup/www.tar.gz from /var/www", tool="tar", operation="create_gz", args={"operation": "create_gz", "archive": "/backup/www.tar.gz", "sources": ["/var/www"]}),
        Turn(user_input="do the same for /srv/data into /backup/data.tar.gz", tool="tar", operation="create_gz", args={"operation": "create_gz", "archive": "/backup/data.tar.gz", "sources": ["/srv/data"]}),
    )),
    V3(id="tar-v3-0003", tool="tar", kind="followup", turns=(
        Turn(user_input="list the contents of /backup/db-dump.tar.gz", tool="tar", operation="list", args={"operation": "list", "archive": "/backup/db-dump.tar.gz"}),
        Turn(user_input="extract it to /restore/db", tool="tar", operation="extract", args={"operation": "extract", "archive": "/backup/db-dump.tar.gz", "dest": "/restore/db"}),
    )),
    V3(id="tar-v3-0004", tool="tar", kind="followup", turns=(
        Turn(user_input="extract /backup/app-release.tar.bz2 into /opt/app", tool="tar", operation="extract", args={"operation": "extract", "archive": "/backup/app-release.tar.bz2", "dest": "/opt/app"}),
        Turn(user_input="undo that, we need the previous archive instead, extract /backup/app-release-prev.tar.bz2 to /opt/app", tool="tar", operation="extract", args={"operation": "extract", "archive": "/backup/app-release-prev.tar.bz2", "dest": "/opt/app"}),
    )),
    V3(id="tar-v3-0005", tool="tar", kind="followup", turns=(
        Turn(user_input="build an xz archive of /var/lib/pgsql/data at /backup/pgdata.tar.xz", tool="tar", operation="create_xz", args={"operation": "create_xz", "archive": "/backup/pgdata.tar.xz", "sources": ["/var/lib/pgsql/data"]}),
        Turn(user_input="verify it against the live filesystem", tool="tar", operation="verify", args={"operation": "verify", "archive": "/backup/pgdata.tar.xz"}),
    )),
    V3(id="tar-v3-0006", tool="tar", kind="followup", turns=(
        Turn(user_input="compress /home/deploy/logs into a bzip2 archive at /backup/deploy-logs.tar.bz2", tool="tar", operation="create_bz2", args={"operation": "create_bz2", "archive": "/backup/deploy-logs.tar.bz2", "sources": ["/home/deploy/logs"]}),
        Turn(user_input="yes, and also list what went into it", tool="tar", operation="list", args={"operation": "list", "archive": "/backup/deploy-logs.tar.bz2"}),
    )),
    V3(id="tar-v3-0007", tool="tar", kind="followup", turns=(
        Turn(user_input="create /backup/nightly.tar.gz from /var/spool/mail and /etc/mail", tool="tar", operation="create_gz", args={"operation": "create_gz", "archive": "/backup/nightly.tar.gz", "sources": ["/var/spool/mail", "/etc/mail"]}),
        Turn(user_input="now sync it out to the offsite mirror at /mnt/offsite/nightly/", tool="rsync", operation="sync", args={"operation": "sync", "src": "/backup/nightly.tar.gz", "dest": "/mnt/offsite/nightly/"}),
    )),
    V3(id="tar-v3-0008", tool="tar", kind="followup", turns=(
        Turn(user_input="verify /backup/etc-20260901.tar.gz against the live filesystem", tool="tar", operation="verify", args={"operation": "verify", "archive": "/backup/etc-20260901.tar.gz"}),
        Turn(user_input="it drifted, list the archive contents so I can see what it actually has", tool="tar", operation="list", args={"operation": "list", "archive": "/backup/etc-20260901.tar.gz"}),
        Turn(user_input="go ahead and extract it to /tmp/etc-check for comparison", tool="tar", operation="extract", args={"operation": "extract", "archive": "/backup/etc-20260901.tar.gz", "dest": "/tmp/etc-check"}),
    )),
    V3(id="tar-v3-0009", tool="tar", kind="followup", turns=(
        Turn(user_input="archive /etc/httpd and /etc/pki into /backup/httpd-config.tar", tool="tar", operation="create", args={"operation": "create", "archive": "/backup/httpd-config.tar", "sources": ["/etc/httpd", "/etc/pki"]}),
        Turn(user_input="confirm the archive by listing it", tool="tar", operation="list", args={"operation": "list", "archive": "/backup/httpd-config.tar"}),
        Turn(user_input="also restart apache since we just touched its config backup path", tool="httpd", operation="restart", args={"operation": "restart"}),
    )),
    V3(id="tar-v3-0010", tool="tar", kind="question", turns=(
        Turn(user_input="run a verify on /backup/etc.tar.gz against the live filesystem", tool="tar", operation="verify", args={"operation": "verify", "archive": "/backup/etc.tar.gz"}),
        Turn(user_input="what does drift in that result actually indicate", answer="It means files on disk have changed since the archive was made, or the archive is missing something now present live.\nDrift itself isn't dangerous, but it tells you the backup is out of date.\nTake a fresh archive if the drifted paths matter for your restore point."),
    )),
    V3(id="tar-v3-0011", tool="tar", kind="question", turns=(
        Turn(user_input="create a gzip archive of /var/lib/mysql at /backup/mysql.tar.gz", tool="tar", operation="create_gz", args={"operation": "create_gz", "archive": "/backup/mysql.tar.gz", "sources": ["/var/lib/mysql"]}),
        Turn(user_input="was that safe, should I have stopped the database first", answer="Yes, ideally the database should be stopped or a consistent snapshot taken before archiving its data directory.\nA live archive of an open database can capture files mid-write and be inconsistent on restore.\nIf you can't take downtime, use the engine's own backup tool instead of a raw tar of the data directory."),
    )),
    V3(id="tar-v3-0012", tool="tar", kind="question", turns=(
        Turn(user_input="extract /backup/config-snapshot.tar.xz to /etc/restore-staging", tool="tar", operation="extract", args={"operation": "extract", "archive": "/backup/config-snapshot.tar.xz", "dest": "/etc/restore-staging"}),
        Turn(user_input="is it safe to extract straight into /etc instead next time", answer="Extracting an untrusted archive straight into /etc can overwrite live config files without warning.\nStage it somewhere neutral first, diff the extracted files against what's live, then copy over only what you want.\nThat also protects you if the archive contains paths that don't match what you expect."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("tar", SCENARIOS_V3)
