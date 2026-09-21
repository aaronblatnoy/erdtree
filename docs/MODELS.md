# Erdtree models: training and evaluation record

Last updated 2026-09-21. Weights for every model listed here are published under
[Releases](https://github.com/aaronblatnoy/erdtree/releases).

## What the models do

A request typed by the operator is sent to the model together with the house system prompt, a
live snapshot of the machine, and the schemas of the tools relevant to that request. The model's
job is to reply with one structured tool call: a tool name plus arguments, one of which
(`operation`) names the action inside that tool. The runtime validates the call, applies the
permission gate, executes it, and asks the model for a short operator-style summary of the real
output. The model never runs anything itself.

## Models

| Name | Base | Method | Training data | Status |
|------|------|--------|---------------|--------|
| `marika-ft` | Qwen2.5-3B-Instruct | QLoRA, 1 epoch, loss on all tokens | corpus v1, 2,721 single-turn traces | superseded |
| `marika-v2` | Qwen2.5-7B-Instruct | NF4 QLoRA, 2 epochs, assistant-token loss | corpus v2, 5,742 single-turn traces | superseded (follow-up defect, see below) |
| `marika-v2.1` | Qwen2.5-7B-Instruct | NF4 QLoRA, 2 epochs, assistant-token loss | corpus v3, 6,543 traces | **current Marika tier** |
| `radagon-v3` | Qwen3-30B-A3B-Instruct-2507 (mixture of experts, about 3B active) | bf16 LoRA r=16 on attention projections and the fused expert tensors (PEFT `target_parameters`), 2 epochs, 818 steps, final train loss 0.038 | corpus v3, 6,543 traces | **current Radagon tier** |
| `radagon-ft` | same 30B base | bf16 LoRA on attention projections only, 2 epochs | corpus v2 | superseded (follow-up defect) |

Licenses follow the bases: Qwen2.5-3B is under the Qwen Research License (non-commercial);
Qwen2.5-7B and Qwen3-30B-A3B are Apache 2.0.

## Evaluation method

Two held-out pools, written separately from the training scenarios and checked for verbatim and
near-duplicate overlap with every training request. They are never trained on.

- **First-request pool** (`finetune/scenarios/eval_pool.py`, 100 traces): a fresh request with no
  history. 2 scenarios per tool across all 55 tools.
- **Follow-up pool** (`finetune/scenarios/eval_pool_multiturn.py`, 80 scenarios, 40 tools): the
  first exchange is replayed exactly as the runtime would record it (reference call, simulated
  result, answer derived from that result), then the model is asked for the second turn's call:
  "now the same for haproxy", "ok restart it", "undo that", a cross-tool next step, or a
  confirmation that implies a specific call.

The harness (`python -m finetune.eval`) drives the model through Ollama the way the product does:
tools are advertised by the runtime's per-request selector, temperature 0, 16k context, and one
re-ask round when a call fails schema validation. Checks, as a percentage of records:

- *called*: the reply was a structured tool call rather than prose
- *tool + operation*: the right tool and the right action inside it
- *accepted*: the arguments pass the live router's schema validation (a rejected call never runs)
- *required args*: every required argument matches the reference after normalisation

## Results

| Model | First request: tool + operation | accepted | required args | Follow-up: called | tool + operation | required args |
|-------|------|------|------|------|------|------|
| `marika-v2.1` | **94** | **96** | **84** | **100** | **88** | **80** |
| `radagon-v3` | **96** | **99** | **85** | **100** | **88** | **81** |
| `marika-v2` | 92 | 91 | 78 | 4 | 4 | 4 |
| `marika-ft` | 64 | 65 | 51 | 89 | 74 | 63 |
| `radagon-ft` | 84 | 83 | 71 | 5 | 5 | 5 |
| Qwen2.5-7B-Instruct, untuned | 72 | 67 | 61 | 99 | 81 | 71 |
| Qwen2.5-3B-Instruct, untuned | 44 | 41 | 35 | not run | | |
| Qwen3-30B-A3B, untuned | 69 | 81 | 63 | not run | | |

No model produced a banned word in any reply.

## What the numbers taught us

1. **Single-turn training destroys follow-up ability.** Every record in corpora v1 and v2 ended
   with an assistant answer directly after a tool result. A model trained hard on that shape
   (`marika-v2`, `radagon-ft`) learns "after an answer comes another answer": on a follow-up it
   writes a plausible result, for example `crond.service started; active (running); PID 1420`,
   and calls nothing. The untuned base handles the same follow-ups at 81 percent, so the
   fine-tune removed an ability rather than failing to add one. `marika-ft` kept it only because
   it was trained more weakly. Corpus v3's 655 multi-turn records fix this (4 to 88).
2. **Answers must be derived from the tool output.** In corpus v2, 990 of 5,742 records paired a
   failing simulated result (unit not found, exit 4) with an author-written success answer. That
   teaches the model to ignore output. In v3 the assembler writes the answer from the result.
3. **Advertise fewer tools.** All 55 schemas cost about 14k tokens per request. A deterministic
   keyword selector advertises about 11; the right tool is advertised for 100 percent of both
   held-out pools, records shrink to about 4k tokens, and training cost drops accordingly.
4. **Contrastive data for near neighbours.** Most residual misses are confusions between adjacent
   tools or operations (sssd status vs generic services status, disk format vs wipe, sysctl set vs
   persist). 180 contrastive records target exactly those pairs.
5. **Guards belong in code, not in the model.** The permission gate, the history gate (earlier
   turns are sent only when the request refers back), and the no-call guard (a reply that reads
   like command output is never shown when nothing was dispatched) are deterministic and tested.
   A full-registry sweep found and fixed four write operations that had been executing without
   confirmation because their synthesized command string looked like a read.

## Training notes

- Marika (7B) trains on two 8 GB cards only with NF4 weights split by hand across both cards, a
  loss computed on assistant-token positions in checkpointed chunks (the 152k-vocabulary logits
  tensor never exists in full), an explicit bf16 autocast around the decoder call so attention
  uses the flash kernel, and sequences capped near 5.6k tokens. Corpus v3's multi-turn records
  do not fit that setup; v2.1 was trained on a rented 96 GB card (3.4 hours).
- Radagon (30B mixture of experts) does not fit 16 GB of VRAM for training in any form. On a
  96 GB card the bf16 model trains at 28 s per 16-record step with attention-only LoRA.
  transformers 5 fuses the experts into 3-D parameters that module-level LoRA cannot wrap;
  transformers 4.57 exposes them as linears but runs 2.7x slower before any adapter is added.
  `radagon-v3` uses PEFT parameter-level LoRA (`target_parameters`) on the 96 fused expert
  tensors plus the 192 attention modules: 38 s per step, 8.7 hours for 818 steps, about 19 USD.
  The merged model saves back in the per-expert layout, so llama.cpp converts it unchanged.
  On black-sky the 4-bit 30B runs mostly from system memory: about 20 s per request against
  about 1.7 s for the 7B, for 2 points more on first requests and the same follow-up score.
- Rented pods must run under `finetune/train/pod_guard.sh`, which stops the pod when the job
  exits and at a hard spend cap. Pull the small adapter and terminate; build GGUFs locally.
- Export pitfalls: a Modelfile without the chat template makes the model run on forever; Ollama's
  direct safetensors import produced garbage for the 3B; the thinking-variant Qwen3 template
  routes all output into a hidden field, so the 2507 Instruct model needs the plain template.

## Reproduce

```bash
python -m finetune.assemble --pool train --judgments finetune/data/judgments --out traces.jsonl --no-confirm --select-tools --ground-answers
python -m finetune.assemble --pool v2 --out traces.jsonl --no-confirm --select-tools --ground-answers --append
python -m finetune.assemble --pool v3 --out traces.jsonl --append
python -m finetune.validate traces.jsonl
python -m finetune.eval finetune/data/eval.jsonl --model marika-v2.1          # first requests
python -m finetune.eval - --multiturn --model marika-v2.1                     # follow-ups
```
