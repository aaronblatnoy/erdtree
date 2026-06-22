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
#   radahn  massive / dedicated-infra (NOT a 14B — refused here)
#
# You land in a seeded /root playground (documents, a webapp project, logs, data,
# junk to clean up). The repo is mounted READ-ONLY; the playground + audit log
# live in the container's overlay and reset on exit (--rm). Inference goes to the
# host's Ollama over loopback (--network=host).
#
# HARDWARE TELEMETRY (testing): the host GPUs (nvidia-smi), sensors/fans/temps
# (/sys + lm_sensors), and CPU/PCI info are passed through read-only so the agent
# can see real hardware.
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
if [ "${2:-}" != "" ]; then
  case "$2" in
    3b|7b|14b) MODEL="qwen2.5:$2" ;;
    *)         MODEL="$2" ;;
  esac
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"

# --- GPU passthrough (no nvidia-container-toolkit needed): bind the nvidia-smi
#     binary + NVML library + the nvidia devices, read-only. Skipped cleanly on a
#     host without an nvidia GPU.
GPU_ARGS=()
if command -v nvidia-smi >/dev/null 2>&1; then
  SMI="$(command -v nvidia-smi)"
  ML="$(ldconfig -p 2>/dev/null | awk '/libnvidia-ml.so.1/{print $NF; exit}')"
  GPU_ARGS+=(-v "$SMI":/usr/bin/nvidia-smi:ro)
  [ -n "$ML" ] && GPU_ARGS+=(-v "$ML":"$ML":ro)
  for d in /dev/nvidiactl /dev/nvidia0 /dev/nvidia1 /dev/nvidia2 /dev/nvidia3 \
           /dev/nvidia-uvm /dev/nvidia-uvm-tools; do
    [ -e "$d" ] && GPU_ARGS+=(--device "$d")
  done
fi

exec podman run --rm -it \
  --network=host \
  --hostname "$(uname -n 2>/dev/null || echo erdtree)" \
  --security-opt label=disable \
  -v "$REPO":/opt/erdtree:ro \
  -v /sys:/sys:ro \
  "${GPU_ARGS[@]}" \
  -e ERDTREE_TIER="$TIER" \
  -e ERDTREE_MODEL="$MODEL" \
  -e ERDTREE_BASE_URL=http://localhost:11434 \
  -e ERDTREE_AUDIT_LOG=/var/log/erdtree-audit.jsonl \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -w /root \
  erdtree-sandbox:latest \
  /usr/bin/python3.11 -m shell.shell
