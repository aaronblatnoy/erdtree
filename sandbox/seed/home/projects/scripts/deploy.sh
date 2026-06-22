#!/usr/bin/env bash
# Deploy the webapp: pull, install deps, restart the service.
set -euo pipefail
cd /opt/webapp
git pull --ff-only
pip install -r requirements.txt
systemctl restart webapp
echo "deployed $(git rev-parse --short HEAD)"
