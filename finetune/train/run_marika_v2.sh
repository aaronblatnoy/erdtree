#!/usr/bin/env bash
# Marika v2: Qwen2.5-7B-Instruct FSDP QLoRA across both 3060 Tis.
# Launch: ~/erdtree-train/run_marika_v2.sh          (full run, auto-resumes)
#         SMOKE=1 ~/erdtree-train/run_marika_v2.sh  (32 records, 10 steps)
# Stop Ollama and vLLM first -- this needs all 16 GB of VRAM.
# Logs: ~/erdtree-train/train_marika_v2.log
# Checkpoints: ~/erdtree-train/out/marika-v2-qlora
set -euo pipefail
cd ~/erdtree-train
# Cross-NUMA cards, no P2P: force socket transport (same fix as vLLM TP=2)
export NCCL_P2P_DISABLE=1
export NCCL_SHM_DISABLE=1
export NCCL_NET=Socket
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false
CONFIG="${CONFIG:-fsdp_offload_config.yaml}"   # QUANT=1 CONFIG=fsdp_config.yaml for the NF4 path
nohup venv/bin/accelerate launch --config_file "$CONFIG" train_marika_v2.py \
  > train_marika_v2.log 2>&1 &
echo "PID $! -- tail -f ~/erdtree-train/train_marika_v2.log"
