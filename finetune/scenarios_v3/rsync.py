"""finetune/scenarios_v3/rsync.py — corpus v3 multi-turn scenarios for 'rsync'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="rsync-v3-0001", tool="rsync", kind="followup", turns=(
        Turn(user_input="dry-run a sync from /data/backups/ to /mnt/archive/", tool="rsync", operation="dry-run", args={"operation": "dry-run", "src": "/data/backups/", "dest": "/mnt/archive/"}),
        Turn(user_input="that looks right, go ahead and do it for real", tool="rsync", operation="sync", args={"operation": "sync", "src": "/data/backups/", "dest": "/mnt/archive/"}),
    )),
    V3(id="rsync-v3-0002", tool="rsync", kind="followup", turns=(
        Turn(user_input="sync /srv/www/site1/ to /mnt/nfs/site1/", tool="rsync", operation="sync", args={"operation": "sync", "src": "/srv/www/site1/", "dest": "/mnt/nfs/site1/"}),
        Turn(user_input="now the same for site2", tool="rsync", operation="sync", args={"operation": "sync", "src": "/srv/www/site2/", "dest": "/mnt/nfs/site2/"}),
    )),
    V3(id="rsync-v3-0003", tool="rsync", kind="followup", turns=(
        Turn(user_input="show estimated transfer size for /home/deploy/releases/ into /mnt/archive/releases/", tool="rsync", operation="progress", args={"operation": "progress", "src": "/home/deploy/releases/", "dest": "/mnt/archive/releases/"}),
        Turn(user_input="ok, sync it", tool="rsync", operation="sync", args={"operation": "sync", "src": "/home/deploy/releases/", "dest": "/mnt/archive/releases/"}),
    )),
    V3(id="rsync-v3-0004", tool="rsync", kind="followup", turns=(
        Turn(user_input="sync-delete /var/log/app/ to /mnt/logs-mirror/ to keep the mirror exact", tool="rsync", operation="sync-delete", args={"operation": "sync-delete", "src": "/var/log/app/", "dest": "/mnt/logs-mirror/"}),
        Turn(user_input="show what that same pair looks like now, dry-run it", tool="rsync", operation="dry-run", args={"operation": "dry-run", "src": "/var/log/app/", "dest": "/mnt/logs-mirror/"}),
    )),
    V3(id="rsync-v3-0005", tool="rsync", kind="followup", turns=(
        Turn(user_input="preview a sync-delete from /data/staging/ to /data/prod-mirror/", tool="rsync", operation="dry-run", args={"operation": "dry-run", "src": "/data/staging/", "dest": "/data/prod-mirror/"}),
        Turn(user_input="instead, use /data/prod-mirror-old/ as the destination", tool="rsync", operation="dry-run", args={"operation": "dry-run", "src": "/data/staging/", "dest": "/data/prod-mirror-old/"}),
    )),
    V3(id="rsync-v3-0006", tool="rsync", kind="followup", turns=(
        Turn(user_input="sync /opt/app/config/ to /opt/app-standby/config/", tool="rsync", operation="sync", args={"operation": "sync", "src": "/opt/app/config/", "dest": "/opt/app-standby/config/"}),
        Turn(user_input="and the same for /opt/app/data/ into /opt/app-standby/data/", tool="rsync", operation="sync", args={"operation": "sync", "src": "/opt/app/data/", "dest": "/opt/app-standby/data/"}),
    )),
    V3(id="rsync-v3-0007", tool="rsync", kind="followup", turns=(
        Turn(user_input="sync /backup/db-dumps/ to /mnt/offsite/db-dumps/", tool="rsync", operation="sync", args={"operation": "sync", "src": "/backup/db-dumps/", "dest": "/mnt/offsite/db-dumps/"}),
        Turn(user_input="also check disk usage on /mnt/offsite so I know how much room is left", tool="disk", operation="usage", args={"operation": "usage", "path": "/mnt/offsite"}),
    )),
    V3(id="rsync-v3-0008", tool="rsync", kind="followup", turns=(
        Turn(user_input="dry-run a sync-delete from /srv/media/ to /mnt/media-mirror/", tool="rsync", operation="dry-run", args={"operation": "dry-run", "src": "/srv/media/", "dest": "/mnt/media-mirror/"}),
        Turn(user_input="that plan is fine, run the sync-delete for real", tool="rsync", operation="sync-delete", args={"operation": "sync-delete", "src": "/srv/media/", "dest": "/mnt/media-mirror/"}),
        Turn(user_input="confirm what's on the mirror now with a fresh dry-run against the same paths", tool="rsync", operation="dry-run", args={"operation": "dry-run", "src": "/srv/media/", "dest": "/mnt/media-mirror/"}),
    )),
    V3(id="rsync-v3-0009", tool="rsync", kind="followup", turns=(
        Turn(user_input="estimate the transfer for /var/lib/pgsql/backups/ into /mnt/nas/pg-backups/", tool="rsync", operation="progress", args={"operation": "progress", "src": "/var/lib/pgsql/backups/", "dest": "/mnt/nas/pg-backups/"}),
        Turn(user_input="that is a lot smaller than expected, sync it anyway", tool="rsync", operation="sync", args={"operation": "sync", "src": "/var/lib/pgsql/backups/", "dest": "/mnt/nas/pg-backups/"}),
        Turn(user_input="now sync the wal archive too, same source pattern but /var/lib/pgsql/wal/ into /mnt/nas/pg-wal/", tool="rsync", operation="sync", args={"operation": "sync", "src": "/var/lib/pgsql/wal/", "dest": "/mnt/nas/pg-wal/"}),
    )),
    V3(id="rsync-v3-0010", tool="rsync", kind="question", turns=(
        Turn(user_input="dry-run a sync from /data/reports/ to /mnt/cold-storage/reports/", tool="rsync", operation="dry-run", args={"operation": "dry-run", "src": "/data/reports/", "dest": "/mnt/cold-storage/reports/"}),
        Turn(user_input="does that dry-run change anything on disk", answer="No, dry-run only previews which files would transfer, nothing is copied or written.\nUse it to sanity check the file list before committing to a real sync.\nWhen the plan looks right, rerun the same source and destination with sync instead."),
    )),
    V3(id="rsync-v3-0011", tool="rsync", kind="question", turns=(
        Turn(user_input="sync-delete /srv/exports/ to /mnt/replica/exports/", tool="rsync", operation="sync-delete", args={"operation": "sync-delete", "src": "/srv/exports/", "dest": "/mnt/replica/exports/"}),
        Turn(user_input="what's the risk with that one specifically", answer="sync-delete removes anything on the destination that no longer exists on the source, so it can permanently delete files.\nThere's no undo once those destination files are gone.\nAlways run a plain dry-run against the same paths first to see exactly what would be removed."),
    )),
    V3(id="rsync-v3-0012", tool="rsync", kind="question", turns=(
        Turn(user_input="check the estimated transfer size for /home/shared/ into /mnt/backup/shared/", tool="rsync", operation="progress", args={"operation": "progress", "src": "/home/shared/", "dest": "/mnt/backup/shared/"}),
        Turn(user_input="how should I use those numbers to plan the sync window", answer="Use the file count and total size to estimate transfer time against your link speed.\nIf the number is much larger than expected, check whether the destination already has a stale partial copy.\nSchedule the real sync for a low-traffic window if the estimate points to a long-running transfer."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("rsync", SCENARIOS_V3)
