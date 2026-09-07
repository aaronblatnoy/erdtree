"""Merge the Marika LoRA adapter into the base model as fp16 safetensors for Ollama import."""
import os
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    os.path.expanduser("~/erdtree-train/out/marika-qlora/final"),
    max_seq_length=15360,
    load_in_4bit=True,
)
model.save_pretrained_merged(
    os.path.expanduser("~/erdtree-train/out/marika-merged"),
    tokenizer,
    save_method="merged_16bit",
)
print("MERGED")
