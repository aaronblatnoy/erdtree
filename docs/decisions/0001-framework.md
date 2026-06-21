# 0001 — Framework: Build Our Own (harness question RESOLVED)

- Status: ACCEPTED
- Date: 2026-06-21
- Phase: 0 (Gating Spikes)
- Supersedes: the earlier "adopt OpenCode as the shipped harness" framing. The harness question is
  now RESOLVED in favor of building Erdtree's own framework in `core/`.
- Gates: I1 (localhost-only egress), I2 (invisible AI), I6 (no hardcoded tier/product name in core)

## Decision

**Erdtree builds its own agent framework in `core/`.** We do NOT ship, vendor, import, or depend on
any third-party agentic CLI at runtime. `vendor/claude-code` and `vendor/opencode` are **reference /
inspiration ONLY** — we study how they do the agentic loop, tool-use dispatch, and terminal UX, then
write our own clean-room implementation that only ever talks to **localhost Ollama**
(`http://localhost:11434/v1`).

The framework is harness-portable and model-portable by construction: `core/` owns Layer 2 (system
context, the Linux tool abstraction, the permission seam, the audit spine, command/English dispatch,
invisible-memory UX). The wire contract it speaks is frozen independently in
`docs/decisions/0002-tool-call-protocol.md` (OpenAI Chat-style function calling, exactly as Ollama's
`/v1/chat/completions` presents it).

## Why build our own (rationale: clean by construction)

1. **Zero telemetry to strip.** A vendored harness drags phone-home surfaces (auto-update checks,
   model-catalog fetches, session-share upload, OTLP export) that each must be enumerated and
   disabled, then re-audited on every version bump — a permanent I1 liability. Our own framework has
   **no egress to strip**: it is written to open exactly one socket, to loopback Ollama, asserted in
   code before connect. I1 holds by construction, not by configuration.
2. **No redistribution license to honor.** Shipping a third-party tree inside a sold ISO means
   carrying its license, attribution manifest, trademark constraints, and transitive dependency
   license set forever. Our own code carries none of that baggage.
3. **Invisible AI (I2) is native, not retrofitted.** Third-party harnesses surface "model",
   "agent", "assistant" strings throughout their UX. We would be rebranding/suppressing those
   continuously. Erdtree's own surface emits **zero** AI/LLM/agent/model language because it never
   had any — I2 is a property of the source, not a patch over it.
4. **No hardcoded tier/product name (I6).** Our framework selects tier behavior via `ERDTREE_TIER`;
   `core/` never hardcodes "Marika"/"Radagon". A vendored harness has its own branding baked in.
5. **The framework IS the product (the moat).** Per CLAUDE.md, the durable IP is Layer 2 — how an
   LLM safely and invisibly drives a real computer. Outsourcing that to a vendor tree would be
   outsourcing the moat. The harness underneath is a swappable substrate; the model is a swappable
   engine; what we own is the safe-drive framework in between.

## Verdicts on the two reference trees (inspiration only — NEITHER is shipped)

| Tree | License | Status for Erdtree | Why |
|---|---|---|---|
| **Claude Code** (`vendor/claude-code`, `anthropics/claude-code`) | **Proprietary — All Rights Reserved, Anthropic Commercial ToS** | **NO-GO to ship — inspiration only** | Not redistributable (bundling in a sold ISO violates the ToS); additionally cloud-bound (hosted-API + Statsig telemetry we do not control). Disqualified on license AND on I1 regardless. Read it to study the agentic loop / tool-use / terminal UX; never import it. |
| **OpenCode** (`vendor/opencode`, `sst/opencode`) | **MIT (permissive)** | **MIT inspiration — not shipped** | MIT *would* permit redistribution with attribution, so it is a legitimate reference whose source we read freely. But we still do not ship it: building our own removes the telemetry-strip + attribution + version-bump-re-audit burden entirely and keeps `core/` portable. We read its `packages/llm/src/protocols/*` and `tool*.ts` to ground 0002 against a real OpenAI-Chat-compatible implementation. |

Key point: the choice is NOT "OpenCode vs Claude Code as the thing we ship." Both are
**inspiration only**. Claude Code is additionally a hard NO-GO (proprietary + cloud-bound) so it
could never be shipped even if we wanted to. OpenCode is clean MIT and a faithful reference for the
wire format, which is exactly how we use it (see 0002's cited file paths).

## What "inspiration only" means operationally (the boundary)

- `core/` **never** imports from `vendor/`. No `vendor/` module is a runtime dependency.
- `vendor/opencode` and `vendor/claude-code` are read to learn the agentic loop, tool dispatch,
  streaming assembly, and terminal UX — and `vendor/opencode/packages/llm/src/*` is cited in 0002
  to confirm our independently-targeted wire format matches a real OpenAI-Chat-compatible harness
  AND what Ollama presents.
- Nothing from either tree is redistributed in any Erdtree artifact (ISO, RPM, container).
- The framework only ever opens a connection to `http://localhost:11434/v1` (Ollama). The client
  asserts the host is loopback before connecting (I1).

## Consequences

- Phase 1+ build `core/` from scratch: `core/model/ollama.py` (the localhost-only client speaking
  the 0002 contract), `core/tools/` (the Linux tool registry emitting per-tool JSON-Schema),
  `core/agent/router.py` (parse/dispatch/re-ask per 0002), `core/agent/prompt.py` (system-context
  injection per I5), the permission gate (I3), and the append-only JSONL audit spine (I4).
- 0002 is framework-level and portable. It targets the OpenAI Chat function-calling shape that
  Ollama's `/v1/chat/completions` presents; the cited OpenCode files only **confirm** that shape,
  they are not a dependency.
- Phase 11 (ISO build) ships **no** third-party harness license/attribution manifest for an agentic
  CLI, because none is shipped. (Ollama and the base OS carry their own, handled separately.)
- I1: because `core/` opens only the loopback Ollama socket, the "enumerate-and-disable egress"
  audit that a vendored harness would require does not exist. The live zero-egress proof for the
  *whole image* (firewall floor: allow only `127.0.0.1:11434`) is still a Phase-11 ship gate on real
  Linux — **DEFERRED-TO-MOSSAD** (no Linux/Ollama on this macOS dev host; no live result claimed).

## Residual risk / follow-ups

- Building our own means we own the agentic-loop reliability (tool-call validity) ourselves — that
  is exactly the #1 bet measured by `bench/` and frozen by 0002. Mitigation: the validity benchmark
  + Phase-10 fine-tune close the loop to the >=99.5% target.
- We must stay disciplined that `core/` never imports `vendor/`. Mitigation: a CI check that greps
  `core/` for any `vendor/` / `opencode` / `claude_code` import (add at Phase 1).
- DEV-HOST honesty boundary: on macOS (no Ollama, no Linux) only source-level reasoning + the static
  wire-format grounding in 0002 are performable here. The live zero-egress image proof is written as
  a deferred Phase-11 test, never reported as a passing live run.
