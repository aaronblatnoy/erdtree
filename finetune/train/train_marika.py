"""Radagon SFT: QLoRA fine-tune of Qwen2.5-7B-Instruct on the Erdtree trace corpus.

Single-GPU (8GB 3060 Ti). Unsloth 4-bit + offloaded gradient checkpointing.
Loss is masked to assistant turns via train_on_responses_only.
Smoke mode: SMOKE=1 runs 10 steps on 32 records to verify VRAM fit.
"""
import json, os, sys

SMOKE = os.environ.get("SMOKE") == "1"
MAX_SEQ = 15360
OUT = os.path.expanduser("~/erdtree-train/out/marika-qlora")

from unsloth import FastLanguageModel
from unsloth.chat_templates import train_on_responses_only
from datasets import Dataset
from trl import SFTTrainer, SFTConfig

model, tokenizer = FastLanguageModel.from_pretrained(
    "unsloth/Qwen2.5-3B-Instruct-bnb-4bit",
    max_seq_length=MAX_SEQ,
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r=16, lora_alpha=32, lora_dropout=0,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing="unsloth",
    random_state=42,
)

records = []
with open(os.path.expanduser("~/erdtree-train/data/traces.jsonl")) as f:
    for line in f:
        r = json.loads(line)
        records.append({"text": tokenizer.apply_chat_template(
            r["messages"], tools=r.get("tools"), tokenize=False)})
if SMOKE:
    records = records[:32]
ds = Dataset.from_list(records)

trainer = SFTTrainer(
    model=model, tokenizer=tokenizer, train_dataset=ds,
    args=SFTConfig(
        dataset_text_field="text",
        max_seq_length=MAX_SEQ,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        num_train_epochs=1,
        max_steps=10 if SMOKE else -1,
        learning_rate=1e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=1 if SMOKE else 5,
        save_strategy="no" if SMOKE else "steps",
        save_steps=25,
        save_total_limit=3,
        output_dir=OUT,
        optim="adamw_8bit",
        bf16=True,
        seed=42,
        report_to="none",
    ),
)
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|im_start|>user\n",
    response_part="<|im_start|>assistant\n",
)

resume = (not SMOKE) and os.path.isdir(OUT) and any(
    d.startswith("checkpoint-") for d in os.listdir(OUT))
trainer.train(resume_from_checkpoint=resume)

if not SMOKE:
    model.save_pretrained(os.path.join(OUT, "final"))
    tokenizer.save_pretrained(os.path.join(OUT, "final"))
    print("DONE: adapter saved to", os.path.join(OUT, "final"))
