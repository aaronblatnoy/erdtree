#!/usr/bin/env bash
# Self-contained Radagon training pipeline for a rented single-GPU pod.
# Launch ONLY through pod_guard.sh so the pod stops when this exits or at the cap:
#   /workspace/pod_guard.sh 28 2.12 -- /workspace/run_radagon_pod.sh
# Inputs expected under /workspace/erdtree-train: train_radagon_moe.py, data/traces_v3.jsonl(.gz), UPLOAD_OK
set -uo pipefail
W=/workspace/erdtree-train; L=/workspace/pipeline.log
export HF_HOME=/workspace/hf HF_HUB_ENABLE_HF_TRANSFER=1 SINGLE_GPU=1
export DATA=$W/data/traces_v3.jsonl OUT=$W/out/radagon-v3-lora
say() { echo "[$(date '+%F %T')] $*" | tee -a $L; }
mkdir -p $W/data $W/out

say "installing stack"
pip install --break-system-packages -q "transformers>=5.17" "trl>=1.13" "peft>=0.20" datasets accelerate sentencepiece hf_transfer huggingface_hub > /workspace/pip.log 2>&1
python -c "import transformers, trl, peft; print('STACK', transformers.__version__, trl.__version__, peft.__version__)" | tee -a $L

say "downloading base"
python -c "from huggingface_hub import snapshot_download; print(snapshot_download('Qwen/Qwen3-30B-A3B-Instruct-2507'))" >> $L 2>&1 || { say "base download failed"; exit 1; }

say "waiting for upload"
while [ ! -f $W/UPLOAD_OK ]; do sleep 5; done
[ -f $W/data/traces_v3.jsonl.gz ] && gunzip -f $W/data/traces_v3.jsonl.gz
say "corpus lines: $(wc -l < $DATA)"

# Smoke the candidate configs in order; first one that completes 10 steps at <= 70 s/step wins.
pick=""
for cfg in "EXPERTS=1 LORA_R=16 LR=2e-4" "EXPERTS=1 LORA_R=8 LR=2e-4" "EXPERTS=0 LORA_R=16 LR=1e-4"; do
  say "smoke: $cfg"
  rm -rf $OUT
  if env $cfg SMOKE=1 python $W/train_radagon_moe.py > $W/smoke.log 2>&1; then
    sit=$(tr '\r' '\n' < $W/smoke.log | grep -oE '[0-9.]+s/it' | tail -1 | tr -d 's/it')
    say "smoke ok: ${sit:-?} s/step ($(grep -E 'LoRA targets|fused expert' $W/smoke.log | tr '\n' ' '))"
    if python3 -c "import sys; sys.exit(0 if float('${sit:-999}') <= 70 else 1)"; then pick="$cfg"; break; fi
    say "too slow for the budget, trying next"
  else
    say "smoke FAILED: $(grep -E 'Error' $W/smoke.log | tail -1 | cut -c1-200)"
  fi
done
[ -n "$pick" ] || { say "no config passed the smoke test"; exit 2; }

say "FULL RUN with: $pick"
rm -rf $OUT
env $pick EPOCHS=2 python $W/train_radagon_moe.py > $W/train_radagon_v3.log 2>&1
rc=$?
say "training exit $rc"
[ -d $OUT/final ] && say "ADAPTER_READY $(du -sh $OUT/final | cut -f1)"
exit $rc
