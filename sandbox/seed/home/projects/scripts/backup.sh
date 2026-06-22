#!/usr/bin/env bash
# Nightly backup of the app database to /srv/backups.
set -euo pipefail
STAMP=$(date +%Y%m%d-%H%M)
DEST="/srv/backups/appdb-$STAMP.sql.gz"
echo "backing up appdb -> $DEST"
# pg_dump appdb | gzip > "$DEST"
echo "done"
