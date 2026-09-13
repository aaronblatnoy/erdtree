#!/usr/bin/env bash
# Train Marika v2 (7B) to completion, then Radagon (30B MoE): smoke, then full.
# Runs in the foreground of one nohup'd shell so the hand-off is automatic.
#   nohup ~/erdtree-train/chain.sh > ~/erdtree-train/chain.log 2>&1 &
# Stop Ollama first. Each stage auto-resumes from checkpoints if re-run.
set -uo pipefail
cd ~/erdtree-train
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=8
stamp() { echo "[$(date '+%F %T')] $*"; }

stamp "stage 1: marika v2 (Qwen2.5-7B) full run"
venv/bin/python train_marika_v2.py > train_marika_v2.log 2>&1
rc=$?; stamp "marika v2 exit $rc"
[ $rc -eq 0 ] || { stamp "stopping chain: marika v2 failed"; exit $rc; }

stamp "stage 2: radagon smoke (32 records)"
SMOKE=1 venv/bin/python train_radagon_moe.py > train_radagon_smoke.log 2>&1
rc=$?; stamp "radagon smoke exit $rc"
[ $rc -eq 0 ] || { stamp "stopping chain: radagon smoke failed, see train_radagon_smoke.log"; exit $rc; }

stamp "stage 3: radagon full run"
venv/bin/python train_radagon_moe.py > train_radagon_moe.log 2>&1
rc=$?; stamp "radagon exit $rc"
stamp "chain done"
