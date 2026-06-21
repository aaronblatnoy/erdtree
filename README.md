# Erdtree

## Linux CLI Commands are a Hassle

I recently set up my first server on Linux Arch. Nothing crazy — just getting services running, configuring storage, opening the right ports. But I kept hitting the same wall: I knew *what* I wanted to do, I just didn't know the  command. So I'd tab over to Claude, describe what I needed, paste the command back into the terminal, and run it. This was a hassle.

After a few hours of this I realized I was essentially using AI as a translation layer between English and Linux. The AI understood me perfectly. The computer just needed a middleman.

Eventually I went further — I set up Claude Code on the server so I could talk to it directly from my machine. Type what I wanted in plain English, and it would figure out the commands and run them. This works remarkably well. But it also felt like a workaround. I was bolting a natural language interface onto an OS that was never designed for it.

That's when the question hit me:

**What if Linux just understood English?**

Not as a chatbot. Not as a GUI overlay. Not as a cloud service you ping for every command. What if the OS itself — in the terminal, with full system access, running entirely on your hardware — just spoke your language?

---

## What Erdtree Is

Erdtree is a suite of Linux distribution where natural language is the native interface to the operating system.

You don't learn new syntax. You don't look up man pages. You don't paste commands from Stack Overflow. You type what you want, in plain English, and Linux does it.

```
$ show me all failing services
$ why is nginx not starting
$ install postgresql and configure it for production
$ what opened port 3306 and when
```

The intelligence runs locally via [Ollama](https://ollama.com) — no cloud dependency, no API keys, no data leaving your machine. The AI is completely invisible in user-facing output. There's no chatbot UI, no "as an AI language model" hedging, no mention of LLMs anywhere. Just Linux that understands what you mean.

Erdtree distros ship as an ISO installer built on Rocky Linux 9 — RHEL-compatible, enterprise-grade, SELinux-enabled. It's a real operating system, not a demo.

---

## The Product Tiers

| Tier | Name | Model | Target |
|------|------|-------|--------|
| 1 | **Linux Marika** | ~3B quantized | Hobbyists, homelabbers |
| 2 | **Linux Radagon** | 7B–14B specialized | Professional sysadmins, data centers |
| 3 | **Linux Radahn** | Massive, dedicated infra | Hyperscale enterprise |

---

## The Architecture

Erdtree's own agent framework lives in `core/`. It's not a wrapper around Claude Code or any other harness — it's built from the ground up to be Ollama-native, invisible-AI, and harness-portable. The framework is what matters: the system-context layer, the permission model, the audit spine, the seamless dispatch between English and shell.

**System Context Layer** — On startup and continuously, the agent builds and maintains a live model of the running system: kernel version, installed packages, running services, hardware topology, recent logs, open ports, firewall rules, disk health. This context is injected automatically into every query. The user never has to explain their environment.

**Permission Model:**
- Read operations → execute immediately
- Write/config operations → confirm before executing
- Destructive/privileged operations → explicit confirmation required, always logged

**Audit Trail** — Every operation is logged: timestamp, natural language input, translated command, output, result. Non-negotiable.

---

## The Ambition

The framework is a general paradigm — direct natural-language control of a computer at the CLI level. Linux is the first instantiation. The goal is an operating system that feels as natural to use as talking to someone who knows the system inside out, runs on commodity hardware you already own, and never phones home.

The moat isn't the model. Models are swappable. The moat is the framework: how an LLM safely and invisibly drives a real computer, with the right context, the right permissions, and zero latency on common operations.

---

## Status

Early buildout. Core framework is in active development. Not ready for production use.

---

## Principles

- No external API calls. Ever. All inference is local.
- No AI language in user-facing output.
- Never execute destructive operations without explicit confirmation.
- Audit log every operation.
- Performance is a feature — simple operations must feel instant.
