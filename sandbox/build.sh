#!/usr/bin/env bash
# Build the Erdtree tier-sandbox image.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
podman build -t erdtree-sandbox:latest -f "$HERE/Containerfile" "$HERE"
echo "Built erdtree-sandbox:latest. Launch a tier with:  sandbox/run.sh radagon"
