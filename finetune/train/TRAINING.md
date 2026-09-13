# Erdtree fine-tune runbook (black-sky)

Two runs live here.

| Run | Script | Base model | Method | Output |
| --- | --- | --- | --- | --- |
| Marika v2 | `train_marika_v2.py` / `run_marika_v2.sh` | Qwen/Qwen2.5-7B-Instruct | QLoRA 4-bit, FSDP FULL_SHARD over 2 GPUs | `~/erdtree-train/out/marika-v2-qlora` |
| Radagon | `train_radagon_moe.py` / `run_radagon_moe.sh` | Qwen/Qwen3-30B-A3B-Instruct-2507 (MoE) | bf16 LoRA, DeepSpeed ZeRO-3 param+optimizer CPU offload (FSDP CPU-offload fallback) | `~/erdtree-train/out/radagon-moe-lora` |

Both use assistant-only masked loss, per-device batch 1, grad accum 8 (global
batch 16 across the two GPUs), `max_seq_length` 8192, LoRA r=16 alpha=32,
lr 1e-4 cosine, checkpoints every 25 steps with `save_total_limit 3`, and
automatic resume from the newest checkpoint in the output directory.

## Prerequisites

1. **Host.** black-sky, Arch Linux, booted on the standard `linux` kernel (NOT
   `linux-lts`). 2x RTX 3060 Ti 8 GB, 125 GB RAM, 32 cores, CUDA 13.3.
   Never open an interactive SSH session from Claude Code; run
   `ssh black-sky "command"`.
2. **Venv.** `~/erdtree-train/venv` (Python 3.11). Verified present:
   torch 2.11.0, transformers 5.5.0, trl 0.24.0, peft 0.20.0,
   accelerate 1.14.0, bitsandbytes 0.50.2, datasets 4.3.0, unsloth 2026.8.22.
   **deepspeed is NOT installed.** Install it with
   `~/erdtree-train/venv/bin/pip install deepspeed` for the preferred Radagon
   path, or run Radagon on the FSDP fallback (`BACKEND=fsdp`, which is what the
   launcher picks automatically when deepspeed is missing).
3. **Data.** `~/erdtree-train/data/traces_v2.jsonl`, one JSON object per line
   with `messages` and optional `tools`. As of this writing only the v1
   `traces.jsonl` exists on the box; v2 must be exported before a full run.
   Override with the `DATA` environment variable.
4. **Files on the box.** The scripts run from `~/erdtree-train`, so copy them
   there next to the venv:

   ```
   scp finetune/train/train_marika_v2.py finetune/train/run_marika_v2.sh \
       finetune/train/fsdp_config.yaml \
       finetune/train/train_radagon_moe.py finetune/train/run_radagon_moe.sh \
       finetune/train/ds_zero3_offload.json finetune/train/fsdp_offload_config.yaml \
       black-sky:~/erdtree-train/
   ssh black-sky "chmod +x ~/erdtree-train/run_marika_v2.sh ~/erdtree-train/run_radagon_moe.sh"
   ```

5. **NCCL.** Both launchers already export
   `NCCL_P2P_DISABLE=1 NCCL_SHM_DISABLE=1 NCCL_NET=Socket`. The two cards are
   cross-NUMA with no peer-to-peer; without this NCCL hangs. Do not remove it.

## Stop Ollama and vLLM before training

This is a hard rule, not a suggestion. A single 8 GB card cannot hold both an
inference server and a training shard, and a mid-run OOM takes the whole box
down rather than failing cleanly.

```
ssh black-sky "sudo systemctl stop ollama; pkill -f vllm; sleep 5; nvidia-smi"
```

`nvidia-smi` must show roughly 0 MiB used on both GPUs before you launch.
Restart the inference stack only after the run finishes or is killed.

## The three commands

Run each from the Mac. Marika and Radagon both need both GPUs, so never run
them at the same time.

### Smoke (32 records, 10 steps, no checkpoints)

```
ssh black-sky "SMOKE=1 ~/erdtree-train/run_marika_v2.sh"
ssh black-sky "SMOKE=1 ~/erdtree-train/run_radagon_moe.sh"
```

Watch it: `ssh black-sky "tail -f ~/erdtree-train/train_marika_v2.log"`.
A smoke run is good if it reaches step 10 with a falling-or-flat loss and no
OOM. A loss of exactly 0.0 or `nan` on step 1 means the assistant-only mask
matched nothing; stop and fix the markers before burning a full run.

### Full

```
ssh black-sky "~/erdtree-train/run_marika_v2.sh"
ssh black-sky "~/erdtree-train/run_radagon_moe.sh"
```

Both `nohup` themselves into the background and print a PID. Radagon prints its
chosen backend (`deepspeed` or `fsdp`) as the first log line.

### Resume

Identical to the full command. Each script checks its output directory for a
`checkpoint-*` folder and passes `resume_from_checkpoint=True` when it finds
one. There is nothing extra to type.

```
ssh black-sky "~/erdtree-train/run_marika_v2.sh"
```

To start clean instead, move the old output directory aside first:
`ssh black-sky "mv ~/erdtree-train/out/marika-v2-qlora{,.old}"`.

## Expected time and disk

Corpus assumption: ~5,700 records at 5-8k tokens each, so roughly 35-45 M
tokens per epoch. These are estimates extrapolated from the 3B v1 run and from
the arithmetic below, not measured numbers for these exact configs. Time the
first 25 steps of a real run and rescale.

**Marika v2 (7B QLoRA, FSDP, both GPUs)**

- Per sample: roughly 4-8 s (one 8k-token sequence, 4-bit weights, gradient
  checkpointing, sharded across two cards with socket-transport NCCL).
- Per optimizer step (16 samples): roughly 60-120 s.
- Per epoch: 5,700 samples, so roughly 7-13 hours.
- 3 epochs: roughly 1 to 1.5 days. Plan for an overnight-plus run and keep the
  auto-resume path clear in case the box drops.

**Radagon (30B-A3B LoRA, ZeRO-3 CPU offload)**

- Only ~3B parameters are active per token, but every layer's full bf16 weights
  are pulled over PCIe from host RAM on each forward and backward pass, and
  that transfer, not the math, is the bottleneck.
- Per sample: roughly 45-120 s with deepspeed ZeRO-3 offload; expect the upper
  end or worse (1.5-3x slower) on the FSDP-offload fallback.
- Per optimizer step (16 samples): roughly 12-30 minutes.
- Per epoch: roughly 3-8 days. 2 epochs is a week-plus of wall clock.
  Treat Radagon as a long-running job: check it daily, and consider trimming to
  a subset of the corpus or 1 epoch for a first real pass.

**Disk** (`/` has ~467 GB free as of 2026-09-12)

- Hugging Face cache: Qwen2.5-7B-Instruct bf16 ~15 GB; Qwen3-30B-A3B-Instruct-2507
  bf16 ~61 GB. Budget ~80 GB for `~/.cache/huggingface` with both present.
- Marika v2 checkpoints: LoRA adapter plus optimizer state, well under 1 GB
  each; `save_total_limit 3` keeps it to a few GB.
- Radagon checkpoints: sharded ZeRO-3 state, a few GB each; the config sets
  `stage3_gather_16bit_weights_on_model_save: false` so no 61 GB consolidated
  copy is written. Budget 20 GB.
- Total headroom to keep free: 150 GB.

**RAM.** Radagon holds the full 30B bf16 model in host RAM (~61 GB) plus pinned
offload buffers. With 125 GB installed and 16 GB of swap this fits, but do not
run anything else memory-hungry alongside it.

## Notes on the two loss masks

Both scripts mask everything except assistant turns, and both derive the span
markers (`<|im_start|>assistant\n` and `<|im_end|>`) from the live tokenizer
rather than hardcoding ids. Radagon additionally asserts at startup that the
assistant marker actually appears in a rendered sample, so a chat-template
change fails loudly instead of silently training on nothing. Radagon renders
with `enable_thinking=False`.

Radagon's LoRA targets are discovered by walking the loaded model: attention
q/k/v/o on every layer, plus the MoE router (`mlp.gate`) and any shared-expert
linears. Everything under `.experts.` is excluded on purpose. Two things were
checked against the real module tree on black-sky and are worth knowing:

- Qwen3-30B-A3B has 128 experts and **no shared expert**, so that pattern
  matches nothing on this checkpoint.
- Under transformers 5.5 the router is a `Qwen3MoeTopKRouter` holding a bare
  weight `Parameter`, **not** an `nn.Linear`. PEFT cannot wrap it, so the script
  detects this, prints a NOTE, and leaves the router frozen instead of crashing.

The effective target set on this checkpoint is therefore attention q/k/v/o on
all 48 layers, 192 modules. The script prints the per-category counts at
startup; check that line on the smoke run.
