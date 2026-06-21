# 0001 — Harness Selection, Telemetry Strip, License Verdict

- Status: ACCEPTED
- Date: 2026-06-21
- Phase: 0 (Gating Spikes)
- Gates: I1 (no external runtime egress), G1 (telemetry strip + zero-egress proof), G2 (license verdict)

## Decision

Adopt **OpenCode** (`sst/opencode`, upstream now `anomalyco/opencode`) as the Claude-Code-style
agent harness for Erdtree v0.1, pinned at **v1.17.9**, configured to drive the **local Ollama
OpenAI-compatible endpoint** and run with all phone-home egress disabled.

**License verdict: GO** (MIT — permissive, no copyleft reach, redistribution + commercial
branded-distro shipping permitted with attribution only).

**Egress verdict: egressZero = TRUE.** Baseline run phones home exactly once (`models.dev:443`);
the stripped run shows ZERO outbound across every exercised path. The strip is complete.

## Candidates considered

| Harness | License | Lang | Ollama / OpenAI-compat | Verdict |
|---|---|---|---|---|
| **OpenCode** | **MIT** | TS (Bun/Node) | yes, `baseURL` custom provider | **SELECTED** |
| Codex CLI | Apache-2.0 | Rust | yes (`--oss`, config.toml) | viable alt; OpenAI-centric defaults |
| Cline | Apache-2.0 | TS (VS Code ext) | yes | GUI/editor-bound — fails terminal-only |
| Aider | Apache-2.0 | Python | yes | edit-loop oriented, weaker generic tool-call agent loop |
| **Claude Code (anthropic)** | **Proprietary — All Rights Reserved, Anthropic Commercial ToS** | — | — | **NO-GO (not redistributable)** |

Rationale for OpenCode: de-facto open-source Claude-Code-style harness; MIT is the cleanest
license for a commercial branded distro; first-class custom-provider support pointing at any
OpenAI-compatible `baseURL` (Ollama's `http://localhost:11434/v1`); built on the Vercel AI SDK, so
the tool-call wire format is plain OpenAI Chat Completions tool-calling (frozen in 0002).

### Why Claude Code itself is NO-GO

`anthropics/claude-code` `LICENSE.md` is a bare copyright notice pointing at Anthropic's
**Commercial Terms of Service** — All Rights Reserved, proprietary, NOT redistributable. Shipping
it inside a sold ISO would violate those terms. The plan's phrase "modeled on the Claude Code
open-source architecture" means a Claude-Code-*style* OSS harness, which is OpenCode. Additionally,
Claude Code's proprietary build carries hardcoded operational telemetry (Statsig) that cannot be
fully excised from source we do not control — itself disqualifying under I1.

## LICENSE analysis (the GO)

- **License:** MIT. `LICENSE`: `Copyright (c) 2025 opencode` + standard MIT grant.
- **Redistribution:** permitted (including inside a commercial product / ISO).
- **Modification:** permitted (we fork-config and may patch; no source-disclosure obligation).
- **Copyleft reach:** NONE. MIT is non-copyleft; it does not infect `core/`, the distro, or our
  RPMs. Linking/bundling imposes no license on our code.
- **Attribution (the one obligation):** the MIT copyright notice + permission text must ship with
  the distribution. ACTION for Phase 11: include OpenCode's `LICENSE` in the ISO's third-party
  license manifest (`/usr/share/licenses/erdtree/` + installer about screen). This is the only
  condition; verdict remains **GO**.
- **Trademark:** MIT grants no trademark rights. We must not present the product as "OpenCode" or
  use its marks — consistent with I7 (no upstream branding user-visible) and I2 (AI invisible).
  We ship a configured, rebranded fork; user-facing strings are Erdtree's.
- Per-provider model SDK packages (`@ai-sdk/*`) pulled transitively are Apache-2.0 / MIT; none are
  copyleft. (Re-verify the exact dependency license set at Phase 11 image-build, but no blocker.)

## Telemetry / egress audit (the strip)

Method: cloned `sst/opencode` at the v1.17.9 tag; static-enumerated every outbound host in
`packages/**/*.ts`; isolated the runtime egress paths (excluding test/`example.*`/`*.test`
fixtures and per-provider hosted-API endpoints that only fire when a hosted provider is selected —
we select local Ollama only). Then ran the published binary behind a logging sink proxy
(`HTTP(S)_PROXY` → `127.0.0.1:8899`, every connection attempt logged and refused) to capture
real outbound attempts, baseline vs stripped.

OpenCode, unlike proprietary Claude Code, has **no hardcoded Statsig / PostHog / Sentry / Segment
phone-home**. There are exactly **four** runtime egress classes beyond the LLM endpoint itself,
each with a first-class kill switch:

| # | Egress | Host | Source | Default | Strip applied |
|---|---|---|---|---|---|
| 1 | Auto-update check / self-upgrade | `opencode.ai/install` (+ npm registry / brew formula) | `packages/opencode/src/installation/index.ts`, `cli/upgrade.ts` | on (`autoupdate`), gated | `OPENCODE_DISABLE_AUTOUPDATE=1` **and** config `autoupdate: false`. Phase 11: package as RPM `method:"unknown"` so self-upgrade is a no-op; updates ship via dnf, not phone-home. |
| 2 | Model catalog fetch | `models.dev` (`:443`) | `packages/core/src/models-dev.ts` | fetched + cached | `OPENCODE_DISABLE_MODELS_FETCH=1` **and** ship a baked local manifest via `OPENCODE_MODELS_PATH=/etc/<tier>/models.json` (the single Ollama tier model). |
| 3 | Share (session upload) | `opncd.ai` / `opencode.ai` | `packages/opencode/src/share/share-next.ts` | opt-in feature | `OPENCODE_DISABLE_SHARE=1` **and** config `share: "disabled"`. |
| 4 | OpenTelemetry OTLP export | user OTLP collector | `packages/core/src/observability/otlp.ts` | **off unless** `OTEL_EXPORTER_OTLP_ENDPOINT` set | guarantee `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_HEADERS` are UNSET in the shipped environment. |

The LLM endpoint itself is NOT egress under I1: it is pointed at `http://localhost:11434/v1`
(local Ollama). No hosted provider is configured; the `@ai-sdk/anthropic|openai|...` hosted hosts
only resolve when a hosted provider is selected, which Erdtree never does.

### Erdtree harness env contract (bake into the systemd unit / shell launch)

```
OPENCODE_DISABLE_AUTOUPDATE=1
OPENCODE_DISABLE_MODELS_FETCH=1
OPENCODE_DISABLE_SHARE=1
OPENCODE_MODELS_PATH=/etc/<tier>/models.json     # local, baked at install
# OTEL_EXPORTER_OTLP_ENDPOINT  — MUST remain unset
# provider baseURL -> http://localhost:11434/v1  (local Ollama only)
# config: autoupdate=false, share="disabled"
```
Belt-and-suspenders (defense in depth, recommended for the shipped image): the harness runs with
NO route to anything but `localhost` (no NetworkManager default route required for the agent;
or an egress firewall that allows only `127.0.0.1:11434`). The env strips are the primary control;
the firewall is the floor that makes a future upstream egress regression non-fatal to I1.

## Egress test result (the proof)

Rig: published `opencode@1.17.9` binary, `HTTP(S)_PROXY` → local logging sink that records and
refuses every TCP connect; caches cleared before each run to force fetches.

- **BASELINE (no strips), `opencode models`:** 1 outbound attempt —
  `CONNECT models.dev:443 HTTP/1.1`. (Confirmed live: command returned the *remote* hosted-model
  catalog, e.g. `deepseek-v4-flash-free`, proving the phone-home fired.)
- **STRIPPED (all four kill switches + local manifest), across `models`, `--version`, `run`,
  `upgrade`:** **ZERO outbound attempts.** With the model fetch disabled the catalog resolves from
  the local manifest and never falls back to the network.
- **Diff:** baseline `{models.dev:443 ×1}` → stripped `{}`. Strip is complete.

`egressZero = TRUE` (offline re-run shows zero outbound AND every enumerated egress point has an
applied, verified strip).

## Consequences

- Phase 3 (`core/model/ollama.py`) targets the OpenAI-compatible endpoint OpenCode already speaks
  (`/v1/chat/completions`); the tool-call contract is frozen in 0002. An adapter shim (plan A7) is
  unlikely to be needed because both sides are OpenAI Chat Completions.
- Phase 11 MUST: (a) include OpenCode's MIT `LICENSE` in the ISO third-party license manifest;
  (b) set the env contract above in the launch unit; (c) bake `/etc/<tier>/models.json`;
  (d) package so `autoupdate` self-upgrade is inert (updates via dnf); (e) optionally enforce the
  localhost-only egress firewall; (f) re-run this egress rig on the *installed image* as a ship gate.
- I7/I2: ship a rebranded configuration; no "OpenCode"/AI strings user-visible. MIT grants no
  trademark, so rebrand is required, not merely allowed.

## Residual risk / follow-ups

- Pin is v1.17.9. Any version bump re-opens the egress audit — a new upstream phone-home is a hard
  I1 regression. Mitigation: the localhost-only firewall floor + re-running this rig in CI on the
  pinned binary on every bump.
- This audit covers the published binary's runtime paths. Plugins/MCP servers a user adds are a
  separate egress surface and out of scope for the shipped default (no plugins shipped enabled).
- Verification: per the plan, the egress-zero claim and the license verdict route to the audit-duo
  SKILL (two independent agents) for adversarial confirmation before downstream phases build on it.
