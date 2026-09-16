"""finetune/scenarios_v3/restic.py — corpus v3 multi-turn scenarios for 'restic'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="restic-v3-0001", tool="restic", kind="followup", turns=(
        Turn(user_input="list the snapshots in /srv/backup/restic-repo", tool="restic", operation="snapshots", args={"operation": "snapshots", "repo": "/srv/backup/restic-repo"}),
        Turn(user_input="now filter those to tag nightly", tool="restic", operation="snapshots", args={"operation": "snapshots", "repo": "/srv/backup/restic-repo", "tag": "nightly"}),
    )),
    V3(id="restic-v3-0002", tool="restic", kind="followup", turns=(
        Turn(user_input="back up /var/lib/pgsql/data to repo /srv/backup/restic-repo tagged postgres", tool="restic", operation="backup", args={"operation": "backup", "path": "/var/lib/pgsql/data", "repo": "/srv/backup/restic-repo", "tag": "postgres"}),
        Turn(user_input="now do the same for /etc, tagged config", tool="restic", operation="backup", args={"operation": "backup", "path": "/etc", "repo": "/srv/backup/restic-repo", "tag": "config"}),
    )),
    V3(id="restic-v3-0003", tool="restic", kind="followup", turns=(
        Turn(user_input="show snapshots on host db-prod-02 in /srv/backup/restic-repo", tool="restic", operation="snapshots", args={"operation": "snapshots", "repo": "/srv/backup/restic-repo", "host": "db-prod-02"}),
        Turn(user_input="ok, restore the latest one to /mnt/restore", tool="restic", operation="restore", args={"operation": "restore", "snapshot_id": "latest", "target": "/mnt/restore", "repo": "/srv/backup/restic-repo"}),
    )),
    V3(id="restic-v3-0004", tool="restic", kind="followup", turns=(
        Turn(user_input="back up /home to sftp:backup-host:/repos/home-repo", tool="restic", operation="backup", args={"operation": "backup", "path": "/home", "repo": "sftp:backup-host:/repos/home-repo"}),
        Turn(user_input="yes, go ahead and list the snapshots there to confirm it landed", tool="restic", operation="snapshots", args={"operation": "snapshots", "repo": "sftp:backup-host:/repos/home-repo"}),
    )),
    V3(id="restic-v3-0005", tool="restic", kind="followup", turns=(
        Turn(user_input="restore snapshot a3f9c21b to /mnt/restore-test from /srv/backup/restic-repo", tool="restic", operation="restore", args={"operation": "restore", "snapshot_id": "a3f9c21b", "target": "/mnt/restore-test", "repo": "/srv/backup/restic-repo"}),
        Turn(user_input="no, use snapshot 7be21dd0 instead", tool="restic", operation="restore", args={"operation": "restore", "snapshot_id": "7be21dd0", "target": "/mnt/restore-test", "repo": "/srv/backup/restic-repo"}),
    )),
    V3(id="restic-v3-0006", tool="restic", kind="followup", turns=(
        Turn(user_input="drop snapshot a3f9c21b from the index in /srv/backup/restic-repo", tool="restic", operation="forget", args={"operation": "forget", "snapshot_id": "a3f9c21b", "repo": "/srv/backup/restic-repo"}),
        Turn(user_input="wait, list the snapshots again so I can see if it's really gone", tool="restic", operation="snapshots", args={"operation": "snapshots", "repo": "/srv/backup/restic-repo"}),
    )),
    V3(id="restic-v3-0007", tool="restic", kind="followup", turns=(
        Turn(user_input="back up /var/www/html to /srv/backup/restic-repo tagged webroot", tool="restic", operation="backup", args={"operation": "backup", "path": "/var/www/html", "repo": "/srv/backup/restic-repo", "tag": "webroot"}),
        Turn(user_input="also check the nginx service status since that serves it", tool="services", operation="status", args={"operation": "status", "unit": "nginx.service"}),
    )),
    V3(id="restic-v3-0008", tool="restic", kind="followup", turns=(
        Turn(user_input="forget snapshot 9e21ab44 and prune the repo /srv/backup/restic-repo, keeping the last 5", tool="restic", operation="forget_prune", args={"operation": "forget_prune", "keep_last": 5, "repo": "/srv/backup/restic-repo"}),
        Turn(user_input="yes, do it", tool="restic", operation="forget_prune", args={"operation": "forget_prune", "keep_last": 5, "repo": "/srv/backup/restic-repo"}),
    )),
    V3(id="restic-v3-0009", tool="restic", kind="followup", turns=(
        Turn(user_input="back up /var/lib/mysql to /srv/backup/restic-repo tagged mysql-nightly", tool="restic", operation="backup", args={"operation": "backup", "path": "/var/lib/mysql", "repo": "/srv/backup/restic-repo", "tag": "mysql-nightly"}),
        Turn(user_input="list snapshots for that same tag to confirm", tool="restic", operation="snapshots", args={"operation": "snapshots", "repo": "/srv/backup/restic-repo", "tag": "mysql-nightly"}),
        Turn(user_input="now forget the oldest one, id 11cd0a2f", tool="restic", operation="forget", args={"operation": "forget", "snapshot_id": "11cd0a2f", "repo": "/srv/backup/restic-repo"}),
    )),
    V3(id="restic-v3-0010", tool="restic", kind="question", turns=(
        Turn(user_input="list the snapshots in /srv/backup/restic-repo", tool="restic", operation="snapshots", args={"operation": "snapshots", "repo": "/srv/backup/restic-repo"}),
        Turn(user_input="what do the columns in that output mean", answer="Each row is one snapshot: the short ID you use for restores, the timestamp it was taken, the hostname it ran on, and the paths it covers. Tags, when set, show alongside so you can filter later with snapshots --tag."),
    )),
    V3(id="restic-v3-0011", tool="restic", kind="question", turns=(
        Turn(user_input="forget the last 3 snapshots and prune /srv/backup/restic-repo, keeping only 10", tool="restic", operation="forget_prune", args={"operation": "forget_prune", "keep_last": 10, "repo": "/srv/backup/restic-repo"}),
        Turn(user_input="is that data actually gone now", answer="Yes — unlike a plain forget, forget_prune also rewrites the pack files to physically remove data no longer referenced by any remaining snapshot. There is no recovery for the deleted snapshots after this runs; only the snapshots covered by keep_last remain restorable."),
    )),
    V3(id="restic-v3-0012", tool="restic", kind="question", turns=(
        Turn(user_input="restore snapshot latest to /mnt/dr-test from /srv/backup/restic-repo", tool="restic", operation="restore", args={"operation": "restore", "snapshot_id": "latest", "target": "/mnt/dr-test", "repo": "/srv/backup/restic-repo"}),
        Turn(user_input="does that overwrite anything already in the target directory", answer="Restic writes files into the target directory and overwrites any file paths that collide with the snapshot's contents, but it does not delete files in the target that aren't part of the snapshot. Restore to an empty directory if you want a clean, exact copy of the backed-up tree."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("restic", SCENARIOS_V3)
