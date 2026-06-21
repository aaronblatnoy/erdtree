# CLAUDE.md — Erdtree

## What This Is

Erdtree builds shippable Linux distributions where natural language is the native interface to the OS. The pitch: **Type in English. Linux does it.** The AI is invisible — no chatbot UI, no cloud dependency, no mention of LLMs in user-facing output. Just Linux that speaks English, in the terminal, with direct system access.

The product ships as ISO installers built on **Rocky Linux 9** (RHEL-compatible, enterprise-grade — a build dependency only, never user-visible). The intelligence runs locally via **Ollama**. The agent framework is **Erdtree's own**, built in `core/` and inspired by how Claude Code and OpenCode do direct, LLM-driven CLI interaction — but **neither is shipped or depended on**; both are *reference/inspiration only* (`vendor/claude-code`, `vendor/opencode`). Building our own keeps the framework clean by construction: Ollama-native, invisible-AI, with zero third-party telemetry to strip and no redistribution license to honor — the framework only ever talks to localhost Ollama. (Claude Code is additionally proprietary + cloud-bound, never shippable regardless.) See `docs/decisions/0001`.

The framework is a **general paradigm** — direct natural-language control of a computer at the CLI level. Linux is the first instantiation (the Erdtree distro line); the framework itself is not intrinsically Linux-bound.

**The product is the framework, not the harness.** What Erdtree owns is Layer 2 — the system-context layer, the Linux tool abstraction, the permission seam, the audit spine, the seamless command/English dispatch, and the invisible-memory UX, all in `core/`. The harness underneath is a *swappable substrate* (OpenCode today, anything tomorrow) and the model is a *swappable engine*. Keep `core/` harness-portable and model-portable; never hardwire a specific harness's internals into the framework. The framework — how an LLM safely and invisibly drives a real computer — is the durable IP and the moat.

---

## Product Tiers

| Tier | Name | Model Size | Target | Status |
|------|------|-----------|--------|--------|
| 1 | Linux Marika | ~3B quantized | Hobbyists, homelabbers | Active buildout |
| 2 | Linux Radagon | 7B–14B specialized | Professional sysadmins, data centers | Active buildout, PRIMARY |
| 3 | Linux Radahn | Massive, dedicated infra | Hyperscale enterprise | Future |
| 4 | Linux Starscourge | Unknown | Unknown | Distant horizon |

**Radagon is the core business.** Every architectural decision must serve Radagon's data center use case first.

---

## Architecture

```
erdtree/
├── agent/          Agent harness (Claude Code-style, adapted for Linux sysadmin)
├── context/        System context layer — live model of the OS environment
├── tools/          Agent toolset: systemctl, dnf, journalctl, firewalld, etc.
├── models/         Model configs, Ollama integration, per-tier model specs
├── distro/         ISO build scripts, Rocky Linux base customization
├── audit/          Audit log infrastructure (every operation logged)
└── lifecycle/      Brainstorm → plan → execute working docs (see below)
```

**Stack:**
- **Base OS:** Rocky Linux 9 (RHEL byte-for-byte rebuild, RPM/dnf, SELinux)
- **Inference:** Ollama (local, no external API calls, ever)
- **Agent layer:** Python
- **System integration:** Shell
- **Model:** Specialized fine-tune on Linux man pages, Arch wiki, RHEL docs, Stack Overflow, kernel mailing lists, CVEs, sysadmin postmortems

---

## Core Domain Concepts

**System Context Layer** — On startup and continuously, the agent maintains a live model of the running system: distro/kernel version, installed packages, running services, hardware topology, recent logs, open ports, firewall rules, disk health, recent agent changes. This context is injected automatically into every query. The user never explains their environment.

**Interaction Model** — Terminal-native, agentic, executes real operations:
```
$ radagon show me all failing services
$ radagon why is nginx not starting
$ radagon install postgresql and configure it for production
$ marika set up a personal nextcloud instance
```

**Permission Model:**
- Read ops → execute immediately, no confirmation
- Write/config ops → confirm before executing
- Destructive/privileged ops → explicit confirmation required, always logged

**Audit Trail** — Every operation logged: timestamp, natural language input, translated command, output, result. Non-negotiable.

---

## Load-Bearing Invariants

These are the things that, when violated, break the product's core promise:

1. **No external API calls.** All inference is local via Ollama. Private data never leaves the machine. Absolute.
2. **No AI language in user-facing output.** Never say "AI", "LLM", "agent", "model", "agentic". The technology is invisible.
3. **Never execute destructive operations without explicit confirmation.** No exceptions.
4. **Audit log every operation.** Every single one. No silent execution.
5. **System context is always injected.** The user never explains their environment — if the agent doesn't know the environment, that's a bug.
6. **Performance is a feature.** Simple operations must feel instant. Latency breaks the illusion. Optimize for p50 latency on common operations.
7. **Architecture must support both Marika (3B) and Radagon (7B–14B)** without rebuilding. The difference is model size and context depth, not structure.

---

## What This Is NOT

- Not a chatbot UI
- Not a GUI product
- Not cloud-dependent
- Not a wrapper around an external API
- Not Copilot for Linux
- Not a product that advertises its AI

---

## Common Commands

*(Populated as the build progresses — commands here are verified, not guessed)*

---

## Conventions & Gotchas

- Rocky Linux 9 uses `dnf` not `apt`. Package management tooling must target RPM/dnf.
- SELinux is enabled by default on Rocky — agent tooling must be SELinux-aware.
- Ollama model names follow the pattern `model:tag` — pin specific quantization tags in model configs, don't use `latest`.
- The tier difference between Marika and Radagon is model size and system context depth — never architecture.
- Do not add features that require cloud connectivity.

---

## Working Flow

```
lifecycle/brainstorms/      ← exploratory idea docs (feature-brainstormer agent)
lifecycle/pending/plans/    ← active buildout phase plans (phase-plan-architect agent)
lifecycle/archive/plans/    ← executed plans, moved here on completion (phase-plan-executor)
```

Flow: **brainstorm → plan → execute**

1. New ideas go to `brainstorms/` via `/brainstorm` or the feature-brainstormer agent
2. Approved ideas become phase plans in `pending/plans/` via phase-plan-architect
3. phase-plan-executor fans out agents to build, then moves the plan to `archive/plans/`
