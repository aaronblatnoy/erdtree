"""Marika v2 SFT: FSDP QLoRA fine-tune of Qwen2.5-7B-Instruct across both 3060 Tis.

Launch: venv/bin/python train_marika_v2.py (single process; see run_marika_v2.sh / chain.sh).
4-bit NF4 weights with bf16 quant storage (required for FSDP sharding),
LoRA on attention+MLP, gradient checkpointing, loss on assistant turns only.

Supersedes train_radagon_fsdp.py (same file, renamed with git mv). Radagon now
means the Qwen3-30B-A3B MoE run in train_radagon_moe.py.

Data: ~/erdtree-train/data/traces_v2.jsonl (messages + tools JSONL, ~5.7k records).
Smoke mode: SMOKE=1 runs 10 steps on 32 records.
"""
import json, os

SMOKE = os.environ.get("SMOKE") == "1"
MAX_SEQ = int(os.environ.get("MAX_SEQ", 5632))  # p99 of traces_v2 is 5.3k tokens; ~1% truncated
DATA = os.path.expanduser(
    os.environ.get("DATA", "~/erdtree-train/data/traces_v2.jsonl"))
OUT = os.path.expanduser(
    os.environ.get("OUT", "~/erdtree-train/out/marika-v2-qlora"))

import torch
from torch.nn.attention import sdpa_kernel, SDPBackend
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig
from datasets import Dataset
from trl import SFTTrainer, SFTConfig

MODEL = os.environ.get("MODEL", "Qwen/Qwen2.5-7B-Instruct")
tokenizer = AutoTokenizer.from_pretrained(MODEL)

# Single process, no FSDP, no NCCL: accelerate's device_map places whole decoder
# layers on cuda:0, cuda:1 and (the remainder) host RAM; offloaded layers are
# streamed to the GPU per forward/backward by hooks.  FSDP was tried first and
# OOM'd at checkpoint time (saving the adapter unshards every layer at once).
# This layout saves adapters normally and needs no collective ops.
def explicit_layout(n_layers: int, on0: int, on1: int) -> dict:
    """Whole-layer placement: embeddings + first ``on0`` layers on cuda:0, the
    next ``on1`` layers + final norm + lm_head on cuda:1, the rest in host RAM
    (streamed per pass).  lm_head MUST be on a GPU: the Liger fused loss runs a
    Triton kernel on it."""
    dm = {"model.embed_tokens": 0, "model.rotary_emb": 0}
    for i in range(n_layers):
        dm[f"model.layers.{i}"] = 0 if i < on0 else (1 if i < on0 + on1 else "cpu")
    dm["model.norm"] = 1
    dm["lm_head"] = 1
    return dm

class MaskedLMTrainer(SFTTrainer):
    """Loss over assistant tokens only, computed WITHOUT the full-vocabulary
    logits tensor: run the decoder, select the positions whose label is not
    -100 (a few hundred per record), and apply lm_head to just those.  This is
    what kept the 8 GB cards from OOM-ing at loss time; it also needs no Triton
    kernels, so it works with layers offloaded to host RAM."""

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        base = model.get_base_model() if hasattr(model, "get_base_model") else model
        # Batch size is 1 and sequences are unpadded, so an all-ones mask carries no
        # information; passing None lets SDPA take the memory-efficient causal
        # kernel instead of materialising heads x T x T scores (2 GB at 6k tokens).
        am = inputs.get("attention_mask")
        if am is not None and bool(am.all()):
            am = None
        # Never allow the math SDPA kernel (it materialises heads x T x T scores,
        # 2 GB at 6k tokens).  Flash/efficient/cuDNN all run this shape on sm86.
        # Calling the decoder submodule bypasses accelerate's autocast wrapper on the
        # top-level forward, so autocast explicitly: without it the k-bit prep's fp32
        # norms push fp32 q/k/v into SDPA, which rejects every fast kernel.
        with torch.autocast("cuda", dtype=torch.bfloat16), sdpa_kernel(
            [SDPBackend.FLASH_ATTENTION, SDPBackend.EFFICIENT_ATTENTION, SDPBackend.CUDNN_ATTENTION]
        ):
            out = base.model(input_ids=inputs["input_ids"], attention_mask=am, use_cache=False)
        h = out.last_hidden_state
        labels = inputs["labels"].to(h.device)
        shift_h, shift_y = h[:, :-1], labels[:, 1:]
        keep = shift_y != -100
        logits = base.lm_head(shift_h[keep].to(base.lm_head.weight.dtype)).float()
        loss_sum = torch.nn.functional.cross_entropy(logits, shift_y[keep], reduction="sum")
        denom = num_items_in_batch if num_items_in_batch is not None else keep.sum().clamp(min=1)
        if torch.is_tensor(denom):
            denom = denom.to(loss_sum.device)
        loss = (loss_sum / denom).to("cuda:0")  # Trainer expects the loss on the input device
        return (loss, out) if return_outputs else loss


# NF4 QLoRA, single process, weights split across BOTH cards by device_map
# (naive pipeline parallelism, no FSDP, no NCCL, no host offload).  4-bit 7B
# weights are ~4.5 GB plus ~2.2 GB of bf16 embeddings/lm_head, so ~3.4 GB per
# card, leaving room for activations at 6k tokens.  Host-RAM offload was tried
# and cannot train (accelerate's offload hooks are inference-only: backward
# fails with "expected device meta"); FSDP offload trained but OOM'd when
# saving the adapter.
from transformers import BitsAndBytesConfig
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
_cfg = AutoConfig.from_pretrained(MODEL)
ON0 = int(os.environ.get("GPU0_LAYERS", _cfg.num_hidden_layers // 2))  # device_map="auto" stacked ~3x more on card 1; split by hand
model = AutoModelForCausalLM.from_pretrained(
    MODEL, quantization_config=bnb, dtype=torch.bfloat16, attn_implementation="sdpa",
    device_map=explicit_layout(_cfg.num_hidden_layers, ON0, _cfg.num_hidden_layers - ON0),  # even split, nothing on cpu
)
assert all(v != "cpu" for v in model.hf_device_map.values()), model.hf_device_map
_split = {d: sum(1 for k, v in model.hf_device_map.items() if v == d and ".layers." in k) for d in (0, 1)}
print("device map: layers per card", _split, "lm_head on", model.hf_device_map.get("lm_head"),
      "alloc GB", [round(torch.cuda.memory_allocated(i) / 1e9, 2) for i in (0, 1)], flush=True)
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

trainer = MaskedLMTrainer(
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
        optim="paged_adamw_8bit",
        bf16=True,
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

# prepare_model_for_kbit_training upcasts embed_tokens and lm_head to fp32
# (+1.1 GB on each card for a 152k vocab).  Put them back to bf16; the tiny
# norms stay fp32.  LoRA params stay as PEFT made them.
_n = 0
for _name, _p in trainer.model.named_parameters():
    if _p.dtype == torch.float32 and ("embed_tokens" in _name or "lm_head" in _name):
        _p.data = _p.data.to(torch.bfloat16); _n += 1
print(f"recast {_n} large fp32 params to bf16; alloc GB after trainer init",
      [round(torch.cuda.memory_allocated(i) / 1e9, 2) for i in (0, 1)],
      "grad ckpt:", getattr(trainer.model.get_base_model().model, "gradient_checkpointing", None), flush=True)
_fp32 = sum(p.numel() for p in trainer.model.parameters() if p.dtype == torch.float32) / 1e6
print(f"fp32 params: {_fp32:.1f}M", flush=True)
torch.cuda.empty_cache()

resume = (not SMOKE) and os.path.isdir(OUT) and any(
    d.startswith("checkpoint-") for d in os.listdir(OUT))
trainer.train(resume_from_checkpoint=resume)

if not SMOKE:
    trainer.save_model(os.path.join(OUT, "final"))
    tokenizer.save_pretrained(os.path.join(OUT, "final"))
    if trainer.accelerator.is_main_process:
        print("DONE: adapter saved to", os.path.join(OUT, "final"))
