# Erdtree Linux Suite

## Linux CLI Commands Suck

I recently set up my first server on Linux Arch. Nothing crazy. Just getting services running, configuring storage, opening the right ports. But I kept hitting the same wall: I knew *what* I wanted to do, I just didn't know the command. So I'd tab over to Claude, describe what I needed, paste the command back into the terminal, and run it. This was a hassle.

Eventually I set up Claude Code on the server so I could talk to it directly. I'd tell Claude what I wanted in plain English, and it would figure out the commands and run them. This works remarkably well. But it also felt like a workaround -- bolting a natural language interface onto an OS that was never designed for it, dependent on a cloud API, sending every command and context to someone else's servers.

That's when the question hit me:

**What if Linux just understood English straight out of the box?**

---

## What the Erdtree Suite Is

Erdtree is a suite of Linux distributions where natural language is the native interface to the operating system, powered by custom-trained models that run entirely on your hardware.

You don't learn new syntax. You don't look up man pages. You don't paste commands from Stack Overflow. You don't have a gimmicky 'AI-Assistant' that only tells you what to do. You type what you want, and Linux does it.

```
$ show me all failing services
$ why is nginx not starting
$ install postgresql and configure it for production
$ what opened port 3306 and when
```

The intelligence comes from models we train specifically for Linux operations. These are not general-purpose LLMs prompted to act like sysadmins, but models built from the ground up to understand system state, diagnose failures, and execute operations correctly. These models run locally. No cloud dependency. No API keys. No data leaving your machine.

The LLM is completely invisible in user-facing output. No chatbot UI, no "as an AI language model" hedging, no mention of LLMs anywhere. No gimmicks for the CEO to be able to say that "we're doing AI". Just Linux that understands what you mean.

Erdtree distros ship as ISO installers built on Rocky Linux 9. RHEL-compatible, enterprise-grade, SELinux-enabled. The model ships with the OS. They are one product.

---

## The Models

This is the core of what we're building.

General-purpose LLMs, even strong ones, underperform at small scale on Linux operations tasks. They hallucinate flags, misread log formats, and generate plausible-looking commands that are wrong for your specific kernel version or package manager state. We train models that specialize in exactly this domain: system diagnostics, service management, storage operations, network configuration, log analysis, security hardening.

The model's job is narrow on purpose. It receives the request, a live snapshot of the machine, and the schemas of the tools relevant to that request. It replies with one structured tool call: a tool name plus arguments. It never runs anything itself. The runtime validates the call, applies the permission gate, executes it, and asks the model for a short operator-style summary of the real output.

### Current models

| Model | Tier | Base | Trained on | Status |
|-------|------|------|------------|--------|
| `marika-v2.1` | Linux Marika | Qwen2.5-7B-Instruct | corpus v3, 6,543 traces | current |
| `radagon-v3` | Linux Radagon | Qwen3-30B-A3B-Instruct-2507 (mixture of experts, about 3B parameters active per token) | corpus v3, LoRA on attention and expert layers | trained 2026-09-21, evaluation pending |

Held-out results, percent of requests where the model chose the right tool and operation. Neither pool is ever trained on.

| Model | First request (100) | Follow-up (80) |
|-------|---------------------|----------------|
| `marika-v2.1` | 94 | 88 |
| `radagon-v3` | pending | pending |
| untuned Qwen2.5-7B, for reference | 72 | 81 |
| untuned Qwen3-30B-A3B, for reference | 69 | not run |

### Superseded models

Kept for the record. Their weights remain under Releases, but none of them should be used.

| Model | Base | Trained on | First request | Follow-up |
|-------|------|------------|---------------|-----------|
| `radagon-ft` | Qwen3-30B-A3B-Instruct-2507 | corpus v2, attention-only LoRA | 84 | 5 |
| `marika-v2` | Qwen2.5-7B-Instruct | corpus v2 | 92 | 4 |
| `marika-ft` | Qwen2.5-3B-Instruct | corpus v1 | 64 | 74 |

The follow-up scores of 4 and 5 came from training only on single-request records: the model learned to write a plausible result instead of calling a tool. Corpus v3 adds multi-turn records and fixes it. The full method, results and lessons are in [docs/MODELS.md](docs/MODELS.md).

### Download and run a model on its own

Every model is published under [Releases](https://github.com/aaronblatnoy/erdtree/releases) as a q4_K_M GGUF with an Ollama Modelfile. Files over 2 GiB are split into parts.

```bash
cat marika-v2.1-q4_K_M.gguf.part-* > marika-v2.1-q4_K_M.gguf
ollama create marika-v2.1 -f Modelfile
ollama run marika-v2.1
```

Standalone, the model speaks OpenAI-style tool calls and terse operator English, so it works in any harness that sends tool schemas over an OpenAI-compatible API. It was trained against Erdtree's 55 tool schemas, and it is most accurate with them. Inside Erdtree it also gets the live system snapshot, the permission gate and the audit log.

---

## The Product Tiers

| Tier | Name | Model | Target |
|------|------|-------|--------|
| 1 | **Linux Marika** | `marika-v2.1`, 7B, about 4.7 GB quantized, runs on one 8 GB GPU | Hobbyists, homelabbers |
| 2 | **Linux Radagon** | 30B mixture of experts, about 18 GB quantized | Professional sysadmins, data centers |

*More robust, enterprise-grade distros to come.*

---

## Try It

The sandbox is a throwaway Rocky 9 container. Destructive operations hit a disposable overlay, never the host. It needs podman and a local [Ollama](https://ollama.com) with the model created as above.

```bash
sandbox/build.sh          # once
sandbox/run.sh marika     # marika-v2.1
sandbox/run.sh marika base            # untuned baseline, for comparison
sandbox/run.sh marika <ollama-model>  # any other served model
```

Type plain English. `!cmd` runs one bash command. `!!` toggles between natural-language mode and bash mode. The welcome screen shows which model build is loaded.

The sandbox sees the host's real hardware, network, listening ports and containers, all read-only. Container access goes through a filter on the host that forwards only read requests, so nothing in the sandbox can start, stop or remove a host container. Details are in [sandbox/README.md](sandbox/README.md).

---

## The Architecture

The agentic framework lives in `core/`. Built from the ground up to be model-native, invisible-AI, and auditable. The framework and the model are co-designed -- the system context layer informs how the model was trained, and the model's outputs are structured to feed directly back into the framework.

**System Context Layer** -- On startup and continuously, the agent builds and maintains a live model of the running system: kernel version, installed packages, running services, hardware topology, recent logs, open ports, firewall rules, disk health. This context is injected automatically into every query. The user never has to explain their environment.

**Tools** -- 55 tools in `core/tools/`, from services, packages, disk and network to SELinux, LVM, podman, nginx, PostgreSQL and SSSD. Each tool exposes named operations, and every operation is tagged read, write or destructive in code.

**Permission Model** -- enforced by deterministic code in `core/agent/permissions.py`, never by the model:
- Read operations → execute immediately
- Write/config operations → confirm before executing
- Destructive/privileged operations → explicit confirmation required, always logged

The model is not trained to ask permission and cannot skip the gate. When the tool's declared class and the command classifier disagree, the stricter one wins. A test sweeps every non-read operation in the registry against the gate.

**Runtime guards that do not depend on the model:**
- Tool selection: about 11 of the 55 tool schemas are advertised per request, chosen by a keyword scorer. This cut the prompt from about 14k tokens to about 4k.
- History gate: earlier turns are sent only when the request refers back to them.
- No-call guard: a reply that reads like command output is never shown when no operation actually ran.
- Re-ask: a malformed or unknown tool call is corrected once, and correction text never reaches the screen.

**Audit Trail** -- Every operation is logged: timestamp, natural language input, translated command, output, result. Non-negotiable.

---

## Repository Layout

| Path | Contents |
|------|----------|
| `core/agent/` | The loop: router, permission gate, tool selection, history gate, no-call guard, audit |
| `core/tools/` | The 55 system tools |
| `shell/` | The login shell with natural-language and bash modes |
| `rag/`, `runtime/` | Offline document index built from the machine's man pages and admin docs, plus session memory |
| `finetune/` | Training-data pipeline, simulators, held-out eval pools, `eval.py` |
| `finetune/train/` | Training and export scripts, Modelfiles, the rented-GPU spend guard |
| `sandbox/` | The container sandbox |
| `os/` | Distribution and ISO build work |
| `docs/` | [MODELS.md](docs/MODELS.md), output spec, corpus build notes, decision records |
| `tests/` | About 7,100 tests |

### Evaluate a model

```bash
python -m finetune.eval finetune/data/eval.jsonl --model marika-v2.1   # first requests
python -m finetune.eval - --multiturn --model marika-v2.1              # follow-ups
```

Rebuilding the corpus and training are covered in [docs/MODELS.md](docs/MODELS.md) and [finetune/train/TRAINING.md](finetune/train/TRAINING.md).

---

## The Moat

Existing tools in this space, Warp, Copilot CLI, shell AI wrappers, RHEL Lightspeed, use general-purpose models accessed via cloud APIs. They are not specialized. They are not autonomous. They cannot run offline. They cannot be used in air-gapped environments. They send your commands and system context to external servers.

We are building the model. It runs on your hardware. It knows Linux operations at a level general models don't. And it ships as part of an OS, not a plugin someone can fork and swap a different model into.

The moat is the model quality, the training data strategy behind it, and the tight integration between model and OS that makes the whole system faster and more accurate than any cloud-dependent alternative.

---

## The Ambition

A purpose-trained model running natively inside an OS is a new paradigm for human-computer interaction at the CLI level. Linux is the first instantiation. The goal is a system that feels as natural as talking to someone who knows your machine inside out -- running on hardware you already own, never phoning home, getting better with every release.

---

## Status

Active buildout. The agent loop runs end to end on local models today. Not production-ready.

**Working now:**
- The full loop: English in, tool call, permission gate, execute, audit, streamed English out, on local models through Ollama.
- The product shell: natural-language and raw-bash modes, live streaming, inline tool steps, and a fallback that drops you to bash if the engine is unavailable.
- 55 system tools, the deterministic permission gate, and an append-only audit log.
- Local document retrieval over the machine's own man pages and Rocky admin docs, built and queried on the box with no network, plus rolling compaction and episodic recall so sessions never hit a context wall.
- The fine-tuning pipeline end to end: corpus v3 (6,543 records, answers derived from simulated tool output, 655 multi-turn and 180 contrastive records), training, export to GGUF, and held-out evaluation.
- `marika-v2.1` published and set as the sandbox default. `radagon-v3` trained.

**Still ahead:** evaluating and publishing `radagon-v3`, per-tier configuration plumbing, how the reference corpus ships (bundled in the image or built on first boot), and the bootable ISO installer.

---

## Principles

- No external API calls. Ever. All inference is local.
- No AI language in user-facing output.
- Never execute destructive operations without explicit confirmation.
- Audit every operation.
- The model and the OS are one product. Neither is complete without the other.
- Performance is a feature -- simple operations must feel instant.
