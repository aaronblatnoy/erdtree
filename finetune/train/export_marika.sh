#!/usr/bin/env bash
# Export the trained Marika adapter to an Ollama model named marika-ft.
#
#   1. merge the QLoRA adapter into the base as fp16 safetensors (merge_marika.py)
#   2. convert safetensors -> f16 GGUF with llama.cpp   (Ollama's own safetensors
#      import produced garbage output for this model: "???" tokens)
#   3. ollama create -q q4_K_M from Modelfile.marika, which carries the Qwen2.5
#      chat template + stop tokens and num_ctx 16384.  A bare `FROM <dir>`
#      Modelfile ships no template, so the model never emits a stop token and
#      babbles.  16384 ctx is required: the 55-tool system prompt is ~14k tokens
#      and Ollama's 4096 default silently truncates it.
#
# Run on black-sky from ~/erdtree-train (venv + llama.cpp checkout present).
set -euo pipefail
cd ~/erdtree-train
NAME="${1:-marika-ft}"

[ -d out/marika-merged ] || venv/bin/python merge_marika.py
[ -f out/marika-f16.gguf ] || venv/bin/python llama.cpp/convert_hf_to_gguf.py \
    out/marika-merged --outtype f16 --outfile out/marika-f16.gguf

# Modelfile.marika uses a path relative to ~/erdtree-train/out.
cp Modelfile.marika out/Modelfile.marika
( cd out && ollama create "$NAME" -q q4_K_M -f Modelfile.marika )
ollama show "$NAME" | head -20
echo "smoke: ollama run $NAME 'reply with the single word ready'"
