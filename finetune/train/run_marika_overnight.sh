#!/usr/bin/env bash
# Overnight Marika QLoRA run. Launch: ~/erdtree-train/run_marika_overnight.sh
# Logs: ~/erdtree-train/train.log   Checkpoints: ~/erdtree-train/out/marika-qlora
# Resumes from the last checkpoint automatically if re-run.
set -euo pipefail
cd ~/erdtree-train
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
nohup venv/bin/python train_marika.py > train.log 2>&1 &
echo "PID $! — tail -f ~/erdtree-train/train.log"
