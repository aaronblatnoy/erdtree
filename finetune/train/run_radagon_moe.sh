#!/usr/bin/env bash
# Radagon: Qwen3-30B-A3B-Instruct-2507 LoRA, bf16 weights in CPU RAM, compute on
# both 3060 Tis via DeepSpeed ZeRO-3 param+optimizer offload.
#
# Launch: ~/erdtree-train/run_radagon_moe.sh          (full run, auto-resumes)
#         SMOKE=1 ~/erdtree-train/run_radagon_moe.sh  (32 records, 10 steps)
#
# Stop Ollama and vLLM first -- this needs all 16 GB of VRAM and most of the RAM.
# Logs: ~/erdtree-train/train_radagon_moe.log
# Checkpoints: ~/erdtree-train/out/radagon-moe-lora
#
# Backend: ZeRO-3 if deepspeed is importable, otherwise the FSDP CPU-offload
# fallback (fsdp_offload_config.yaml). Force one with BACKEND=deepspeed|fsdp.
set -euo pipefail
cd ~/erdtree-train

# Cross-NUMA cards, no P2P: force socket transport (same fix as vLLM TP=2)
export NCCL_P2P_DISABLE=1
export NCCL_SHM_DISABLE=1
export NCCL_NET=Socket
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false
# 32 cores; leave headroom for the CPU-offloaded optimizer math.
export OMP_NUM_THREADS=8

BACKEND="${BACKEND:-auto}"
if [ "$BACKEND" = "auto" ]; then
  if venv/bin/python -c "import deepspeed" 2>/dev/null; then
    BACKEND=deepspeed
  else
    BACKEND=fsdp
    echo "deepspeed not installed -- falling back to FSDP CPU offload" >&2
  fi
fi

case "$BACKEND" in
  deepspeed)
    LAUNCH_ARGS=(--num_processes 2 --num_machines 1 --mixed_precision bf16
                 --use_deepspeed --deepspeed_config_file ds_zero3_offload.json
                 --zero3_init_flag true)
    ;;
  fsdp)
    LAUNCH_ARGS=(--config_file fsdp_offload_config.yaml)
    ;;
  *)
    echo "unknown BACKEND: $BACKEND (want deepspeed or fsdp)" >&2; exit 2 ;;
esac

echo "backend: $BACKEND"
nohup venv/bin/python train_radagon_moe.py   # single-process device_map layout; BACKEND kept only for the log line \
  > train_radagon_moe.log 2>&1 &
echo "PID $! -- tail -f ~/erdtree-train/train_radagon_moe.log"
