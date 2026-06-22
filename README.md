# Erdtree Linux Suite

## Linux CLI Commands Suck

I recently set up my first server on Linux Arch. Nothing crazy. Just getting services running, configuring storage, opening the right ports. But I kept hitting the same wall: I knew *what* I wanted to do, I just didn't know the command. So I'd tab over to Claude, describe what I needed, paste the command back into the terminal, and run it. This was a hassle.

Eventually I set up Claude Code on the server so I could talk to it directly. Type what I wanted in plain English, it would figure out the commands and run them. This works remarkably well. But it also felt like a workaround -- bolting a natural language interface onto an OS that was never designed for it, dependent on a cloud API, sending every command and context to someone else's servers.

That's when the question hit me:

**What if Linux just understood English? And what if the model doing the understanding was purpose-built for exactly this?**

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

General-purpose LLMs, even strong ones, underperform at the 3B-14B parameter scale on Linux operations tasks. They hallucinate flags, misread log formats, generate plausible-looking commands that are wrong for your specific kernel version or package manager state. We are training models that specialize in exactly this domain: system diagnostics, service management, storage operations, network configuration, log analysis, security hardening.

The models ship baked into the distro. They are not a downloadable weight file. They are not available separately. To use the model, you run the OS. This is intentional -- the model and the system context layer it operates within are co-designed and inseparable.

---

## The Product Tiers

| Tier | Name | Model | Target |
|------|------|-------|--------|
| 1 | **Linux Marika** | ~3B quantized | Hobbyists, homelabbers |
| 2 | **Linux Radagon** | 7B-14B specialized | Professional sysadmins, data centers |

*More robust, enterprise-grade distros to come.*

---

## The Architecture

The agentic framework lives in `core/`. Built from the ground up to be model-native, invisible-AI, and auditable. The framework and the model are co-designed -- the system context layer informs how the model was trained, and the model's outputs are structured to feed directly back into the framework.

**System Context Layer** -- On startup and continuously, the agent builds and maintains a live model of the running system: kernel version, installed packages, running services, hardware topology, recent logs, open ports, firewall rules, disk health. This context is injected automatically into every query. The user never has to explain their environment. The model was trained with this context structure in mind.

**Permission Model:**
- Read operations → execute immediately
- Write/config operations → confirm before executing
- Destructive/privileged operations → explicit confirmation required, always logged

**Audit Trail** -- Every operation is logged: timestamp, natural language input, translated command, output, result. Non-negotiable.

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

Early buildout. Core framework and model training pipeline in active development. Not ready for production use.

---

## Principles

- No external API calls. Ever. All inference is local.
- No AI language in user-facing output.
- Never execute destructive operations without explicit confirmation.
- Audit every operation.
- The model and the OS are one product. Neither is complete without the other.
- Performance is a feature -- simple operations must feel instant.
