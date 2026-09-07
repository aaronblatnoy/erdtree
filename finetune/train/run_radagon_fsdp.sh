#!/usr/bin/env bash
# Radagon 7B FSDP QLoRA across both 3060 Tis. Launch: ~/erdtree-train/run_radagon_fsdp.sh
# Do NOT run while Marika is training (needs both GPUs).
# Logs: ~/erdtree-train/train_radagon.log  Checkpoints: ~/erdtree-train/out/radagon-qlora
set -euo pipefail
cd ~/erdtree-train
# Cross-NUMA cards, no P2P: force socket transport (same fix as vLLM TP=2)
export NCCL_P2P_DISABLE=1
export NCCL_SHM_DISABLE=1
export NCCL_NET=Socket
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
nohup venv/bin/accelerate launch --config_file fsdp_config.yaml train_radagon_fsdp.py \
  > train_radagon.log 2>&1 &
echo "PID $! — tail -f ~/erdtree-train/train_radagon.log"
