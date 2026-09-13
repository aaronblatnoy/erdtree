"""Marika v2 SFT: FSDP QLoRA fine-tune of Qwen2.5-7B-Instruct across both 3060 Tis.

Launch via accelerate (see run_marika_v2.sh) -- NOT directly with python.
4-bit NF4 weights with bf16 quant storage (required for FSDP sharding),
LoRA on attention+MLP, gradient checkpointing, loss on assistant turns only.

Supersedes train_radagon_fsdp.py (same file, renamed with git mv). Radagon now
means the Qwen3-30B-A3B MoE run in train_radagon_moe.py.

Data: ~/erdtree-train/data/traces_v2.jsonl (messages + tools JSONL, ~5.7k records).
Smoke mode: SMOKE=1 runs 10 steps on 32 records.
"""
import json, os

SMOKE = os.environ.get("SMOKE") == "1"
MAX_SEQ = int(os.environ.get("MAX_SEQ", 6144))  # p99 of traces_v2 is 5.3k tokens
DATA = os.path.expanduser(
    os.environ.get("DATA", "~/erdtree-train/data/traces_v2.jsonl"))
OUT = os.path.expanduser(
    os.environ.get("OUT", "~/erdtree-train/out/marika-v2-qlora"))

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from datasets import Dataset
from trl import SFTTrainer, SFTConfig

MODEL = os.environ.get("MODEL", "Qwen/Qwen2.5-7B-Instruct")
tokenizer = AutoTokenizer.from_pretrained(MODEL)

bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_quant_storage=torch.bfloat16,  # required for FSDP to shard quantized weights
)
# Each rank loads onto ITS OWN card (otherwise both ranks land on cuda:0 and the
# second one OOMs before FSDP ever gets to shard).
LOCAL_RANK = int(os.environ.get("LOCAL_RANK", 0))
torch.cuda.set_device(LOCAL_RANK)
# QUANT=1 (default): NF4 QLoRA, every rank loads a full copy on its own card
# before FSDP shards it.  On the 8 GB cards that copy does not fit for a 7B
# (un-quantized embed+lm_head alone are ~2.2 GB), so the default here is
# QUANT=0: bf16 weights, rank 0 loads to host RAM (fsdp_cpu_ram_efficient_loading),
# other ranks start on meta, and FSDP keeps parameters offloaded to CPU
# (fsdp_offload_config.yaml).  Slower per step, but it fits and it is the same
# path the Radagon MoE run uses.
QUANT = os.environ.get("QUANT", "0") == "1"
if QUANT:
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, quantization_config=bnb, dtype=torch.bfloat16,
        attn_implementation="sdpa", device_map={"": LOCAL_RANK},
    )
else:
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, dtype=torch.bfloat16, attn_implementation="sdpa",
        low_cpu_mem_usage=True,
    )
model.config.use_cache = False

peft_config = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.0, bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
)

records = []
with open(DATA) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        records.append({"text": tokenizer.apply_chat_template(
            r["messages"], tools=r.get("tools"), tokenize=False)})
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
        num_train_epochs=int(os.environ.get("EPOCHS", 2)),  # 2 on black-sky: ~18 s/sample measured, 3 epochs would be ~4 days
        max_steps=10 if SMOKE else -1,
        learning_rate=1e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=1 if SMOKE else 5,
        save_strategy="no" if SMOKE else "steps",
        save_steps=25,
        save_total_limit=3,
        output_dir=OUT,
        optim="adamw_8bit" if QUANT else "adamw_torch",
        bf16=True,
        use_liger_kernel=True,  # fused linear+cross-entropy: never materialises the 152k-vocab logits
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        seed=42,
        report_to="none",
    ),
)

# Mask loss to assistant turns (Qwen2.5 ChatML markers). TRL 0.24 removed
# DataCollatorForCompletionOnlyLM, so re-implement its span logic here.
# Token ids are derived from the live tokenizer, never hardcoded.
RESP_IDS = tokenizer("<|im_start|>assistant\n", add_special_tokens=False).input_ids
END_IDS = tokenizer("<|im_end|>", add_special_tokens=False).input_ids
assert RESP_IDS and END_IDS, "empty assistant/end marker ids for this tokenizer"


def _find(seq, pat):
    n = len(pat)
    return [i for i in range(len(seq) - n + 1) if seq[i:i+n] == pat]


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
