#!/usr/bin/env bash
# Launch an Erdtree tier in the sandbox container.
#
#   sandbox/run.sh marika           # 3B tier        (gold prompt)
#   sandbox/run.sh radagon          # 7B-14B tier    (red prompt) — defaults to 7B
#   sandbox/run.sh radagon 14b      # Radagon at the top of its range (qwen2.5:14b)
#
# Tier model ranges follow the product plan:
#   marika  ~3B quantized
#   radagon 7B-14B  (PRIMARY tier; 7B default, 14B is the high end of the range)
#   radahn  massive / dedicated-infra (NOT a 14B — no model that large ships in
#           this sandbox; radahn is deferred to real infra)
#
# The repo is mounted READ-ONLY; the audit log + any writes land in the
# container's ephemeral overlay and vanish on exit (--rm). Inference goes to the
# host's Ollama over loopback (--network=host).
set -euo pipefail

TIER="${1:-radagon}"
case "$TIER" in
  marika)  MODEL="qwen2.5:3b" ;;
  radagon) MODEL="qwen2.5:7b" ;;   # 7B-14B range; pass "14b" as arg 2 for the top end
  radahn)
    echo "radahn is the massive / dedicated-infra tier — no model that large ships in" >&2
    echo "this sandbox. Use 'radagon' (7B-14B) or 'marika' (3B)." >&2
    exit 2 ;;
  *) echo "unknown tier: $TIER (use: marika | radagon)" >&2; exit 2 ;;
esac
# An explicit second arg overrides the model tag (e.g. 'radagon 14b' -> qwen2.5:14b).
if [ "${2:-}" != "" ]; then
  case "$2" in
    3b|7b|14b) MODEL="qwen2.5:$2" ;;
    *)         MODEL="$2" ;;
  esac
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"

exec podman run --rm -it \
  --network=host \
  --security-opt label=disable \
  -v "$REPO":/opt/erdtree:ro \
  -e ERDTREE_TIER="$TIER" \
  -e ERDTREE_MODEL="$MODEL" \
  -e ERDTREE_BASE_URL=http://localhost:11434 \
  -e ERDTREE_AUDIT_LOG=/var/log/erdtree-audit.jsonl \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -w /opt/erdtree \
  erdtree-sandbox:latest \
  /usr/bin/python3.11 -m shell.shell
