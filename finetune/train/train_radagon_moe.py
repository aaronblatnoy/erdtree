"""Radagon SFT: LoRA fine-tune of Qwen/Qwen3-30B-A3B-Instruct-2507 (MoE, 30B total /
3B active) on black-sky's 2x RTX 3060 Ti (8 GB each) + 125 GB CPU RAM.

The weights do NOT fit in 16 GB of VRAM, so they are held in bf16 in CPU RAM and
streamed to the GPUs layer by layer. That is done by DeepSpeed ZeRO-3 with
parameter + optimizer offload to CPU (ds_zero3_offload.json), or, if deepspeed is
not installed, by accelerate FSDP with full CPU offload (fsdp_offload_config.yaml).
Either way this script is launcher-agnostic: it never constructs the plugin
itself, it just trains whatever accelerate hands it.

NOT 4-bit. bitsandbytes 4-bit quantization does not combine with ZeRO-3 offload
(the quantized Params4bit cannot be partitioned/offloaded), so weights stay bf16.

Launch via run_radagon_moe.sh -- NOT directly with python.

Key choices:
  - LoRA r=16 alpha=32 on attention q/k/v/o plus the MoE router (mlp.gate) and any
    shared-expert linears. The 128 per-expert MLPs are deliberately NOT targeted:
    they are the bulk of the parameters and each expert sees only a sliver of the
    tokens, so adapting them is both huge and badly undertrained.
    NOTE (verified 2026-09-12 on black-sky against the real module tree):
    Qwen3-30B-A3B has num_experts=128 and NO shared expert (unlike Qwen2-MoE), so
    the shared-expert pattern matches nothing here and is kept only for Qwen-MoE
    variants that do have one. Also, under transformers 5.5 the router
    (layers.N.mlp.gate) is a Qwen3MoeTopKRouter holding a bare weight Parameter,
    not an nn.Linear, and PEFT cannot wrap it -- the script detects this, prints a
    NOTE, and leaves the router frozen. In practice the effective target set on
    this checkpoint is attention q/k/v/o on all 48 layers (192 modules).
  - Assistant-only masked loss. Marker token ids are read from the live tokenizer
    at runtime, never copied from Qwen2.5.
  - Thinking disabled when applying the chat template (enable_thinking=False).

Data: ~/erdtree-train/data/traces_v2.jsonl (messages + tools JSONL).
Smoke mode: SMOKE=1 runs 10 steps on 32 records.
"""
import json, os, re

SMOKE = os.environ.get("SMOKE") == "1"
MAX_SEQ = int(os.environ.get("MAX_SEQ", 6144))  # p99 of traces_v2 is 5.3k tokens
DATA = os.path.expanduser(
    os.environ.get("DATA", "~/erdtree-train/data/traces_v2.jsonl"))
OUT = os.path.expanduser(
    os.environ.get("OUT", "~/erdtree-train/out/radagon-moe-lora"))

import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig
from datasets import Dataset
from trl import SFTTrainer, SFTConfig

# Verified to exist on the Hugging Face Hub (HTTP 200, config.json model_type
# qwen3_moe) on 2026-09-12. "Qwen/Qwen3-30B-A3B-Instruct" without the -2507 date
# suffix does NOT resolve.
MODEL = os.environ.get("MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")

tokenizer = AutoTokenizer.from_pretrained(MODEL)


def render(messages, tools):
    """Apply the chat template with thinking off, tolerating templates that do
    not accept the enable_thinking kwarg."""
    try:
        return tokenizer.apply_chat_template(
            messages, tools=tools, tokenize=False, enable_thinking=False)
    except TypeError:
        return tokenizer.apply_chat_template(messages, tools=tools, tokenize=False)


# ---------------------------------------------------------------- loss masking
# Derive the assistant-turn span markers from THIS tokenizer. Do not assume they
# match Qwen2.5's ids.
RESP_IDS = tokenizer("<|im_start|>assistant\n", add_special_tokens=False).input_ids
END_IDS = tokenizer("<|im_end|>", add_special_tokens=False).input_ids
assert RESP_IDS and END_IDS, "empty assistant/end marker ids for this tokenizer"

# Sanity check: the markers must actually appear in a rendered sample, otherwise
# every label would be masked to -100 and the run would silently learn nothing.
_probe = tokenizer(
    render([{"role": "user", "content": "ping"},
            {"role": "assistant", "content": "pong"}], None),
    add_special_tokens=False).input_ids


def _find(seq, pat):
    n = len(pat)
    return [i for i in range(len(seq) - n + 1) if seq[i:i+n] == pat]


assert _find(_probe, RESP_IDS), (
    "assistant marker not found in the rendered chat template; "
    "loss masking would zero out every token")

# ------------------------------------------------------------------ the model
model = AutoModelForCausalLM.from_pretrained(
    MODEL,
    dtype=torch.bfloat16,
    attn_implementation="sdpa",
    low_cpu_mem_usage=True,
)
model.config.use_cache = False
if hasattr(model.config, "output_router_logits"):
    model.config.output_router_logits = False

# -------------------------------------------------------- LoRA target discovery
# Attention projections everywhere, plus the MoE router (".mlp.gate") and any
# shared-expert linear. Explicitly exclude anything under ".experts." (the 128
# per-expert MLPs) and the LM head.
_ATTN = re.compile(r"\.(q_proj|k_proj|v_proj|o_proj)$")
_ROUTER = re.compile(r"\.mlp\.gate$")
_SHARED = re.compile(r"shared_expert.*\.(gate_proj|up_proj|down_proj)$")

target_modules, n_attn, n_router, n_shared = [], 0, 0, 0
skipped_router = []
for name, mod in model.named_modules():
    if ".experts." in name or name.endswith(".experts"):
        continue                     # per-expert MLPs: never adapt
    is_linear = isinstance(mod, nn.Linear)
    if _ATTN.search(name):
        if is_linear:
            target_modules.append(name); n_attn += 1
    elif _ROUTER.search(name):
        # PEFT can only wrap nn.Linear (and a few other known layer types). In
        # transformers 5.5 the Qwen3-MoE router is a Qwen3MoeTopKRouter holding a
        # bare weight Parameter, so it is NOT adaptable and is skipped rather
        # than crashing LoraConfig. Verified on black-sky 2026-09-12.
        if is_linear:
            target_modules.append(name); n_router += 1
        else:
            skipped_router.append((name, type(mod).__name__))
    elif _SHARED.search(name) and is_linear:
        target_modules.append(name); n_shared += 1

if not target_modules:
    raise SystemExit("no LoRA target modules matched -- check the model architecture")
print(f"LoRA targets: {len(target_modules)} modules "
      f"(attention={n_attn}, router={n_router}, shared_expert={n_shared})")
if skipped_router:
    name, cls = skipped_router[0]
    print(f"NOTE: {len(skipped_router)} router module(s) are {cls}, not nn.Linear "
          f"(e.g. {name}) -- LoRA cannot wrap them, so the router is left frozen.")

peft_config = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.0, bias="none",
    task_type="CAUSAL_LM",
    target_modules=target_modules,
)

# -------------------------------------------------------------------- the data
records = []
with open(DATA) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        records.append({"text": render(r["messages"], r.get("tools"))})
if SMOKE:
    records = records[:32]
ds = Dataset.from_list(records)

trainer = SFTTrainer(
    model=model,
    processing_class=tokenizer,
    train_dataset=ds,
    peft_config=peft_config,
    args=SFTConfig(
        dataset_text_field="text",
        max_length=MAX_SEQ,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,      # x2 GPUs = global batch 16
        num_train_epochs=2,
        max_steps=10 if SMOKE else -1,
        learning_rate=1e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=1 if SMOKE else 5,
        save_strategy="no" if SMOKE else "steps",
        save_steps=25,
        save_total_limit=3,
        output_dir=OUT,
        # ZeRO-3 CPU offload supplies its own optimizer (DeepSpeedCPUAdam) when a
        # deepspeed config is active; adamw_torch is the portable choice that also
        # works under the FSDP-offload fallback. adamw_8bit is bitsandbytes and is
        # avoided here for the same reason 4-bit weights are.
        optim="adamw_torch",
        bf16=True,
        use_liger_kernel=True,  # fused loss where supported; avoids the 152k-vocab fp32 logits copy
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        seed=42,
        report_to="none",
    ),
)

_base_collator = trainer.data_collator


def masked_collator(features):
    batch = _base_collator(features)
    labels = batch["labels"]
    for b in range(labels.shape[0]):
        ids = batch["input_ids"][b].tolist()
        mask = [False] * len(ids)
        for start in _find(ids, RESP_IDS):
            i = start + len(RESP_IDS)
            while i < len(ids):
                mask[i] = True
                if ids[i-len(END_IDS)+1:i+1] == END_IDS:
                    break
                i += 1
        for i, keep in enumerate(mask):
            if not keep:
                labels[b, i] = -100
    return batch


trainer.data_collator = masked_collator

resume = (not SMOKE) and os.path.isdir(OUT) and any(
    d.startswith("checkpoint-") for d in os.listdir(OUT))
trainer.train(resume_from_checkpoint=resume)

if not SMOKE:
    trainer.save_model(os.path.join(OUT, "final"))
    tokenizer.save_pretrained(os.path.join(OUT, "final"))
    if trainer.accelerator.is_main_process:
        print("DONE: adapter saved to", os.path.join(OUT, "final"))
