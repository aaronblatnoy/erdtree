# Phase 0 Audit — Gating Spikes (Harness, Telemetry Strip, License, Protocol)

- Date: 2026-06-21
- Executor: general-purpose (opus)
- Verdict: **GO** | egressZero=**true** | licenseVerdict=**GO (MIT)** | protocolFrozen=**true**

## What was built (deliverables, scope = docs/decisions/ + bench/ only)

- `docs/decisions/0001-harness-selection.md` — harness = OpenCode (MIT) pinned v1.17.9; full
  telemetry/egress itemization (4 egress classes + kill switches); egress-test result; license
  verdict GO.
- `docs/decisions/0002-tool-call-protocol.md` — FROZEN contract: OpenAI Chat Completions
  function-calling as OpenCode emits / Ollama `/v1/chat/completions` presents. Request (§1), tool
  call parse target (§2), tool result (§3), SSE streaming/delta assembly (§4), malformed/re-ask +
  validity definition (§5).
- `bench/README.md` — validity-rate definition (frozen), targets (Radagon >=99.5% gate; Marika 3B
  recorded GO/HOLE), case schema, scoring contract.
- `bench/cases/*.json` — 10 seed cases (services/packages/logs × read/write/destructive + 2
  negative-control "stay English" turns). All validate as JSON.

Scope check: `git status` shows only `docs/` and `bench/` as my new paths (plus the pre-existing
`lifecycle/pending/workflows/erdtree-v0.1.workflow.js`, created by the orchestration script, not by
this phase). Compliant with "touch only docs/decisions/ and bench/".

## Harness identity

OpenCode (`sst/opencode`, upstream `anomalyco/opencode`), the de-facto open-source Claude-Code-style
terminal agent harness. TypeScript on the Vercel AI SDK; native custom-provider support pointing at
any OpenAI-compatible `baseURL` → local Ollama `http://localhost:11434/v1`. Cloned the v1.17.9 tag
and installed the published `opencode-ai@1.17.9` binary for the live egress test.

## License verdict — GO (MIT)

`LICENSE` = MIT, `Copyright (c) 2025 opencode`. Permissive: redistribution + modification +
commercial branded-distro shipping permitted; NO copyleft reach (does not infect core/ or the ISO).
One obligation: ship the MIT notice in the ISO third-party license manifest (Phase 11 action). No
trademark grant → rebrand required (aligns with I7/I2). Claude Code itself was ruled NO-GO:
proprietary, All-Rights-Reserved, Anthropic Commercial ToS, not redistributable (+ unstrippable
Statsig telemetry) — confirmed by fetching `anthropics/claude-code/LICENSE.md` (bare copyright +
pointer to commercial ToS).

## Telemetry strip — COMPLETE (gates I1)

Static enumeration of `packages/**/*.ts` outbound hosts → isolated 4 runtime egress classes beyond
the LLM endpoint, each with a first-class kill switch (no hardcoded Statsig/PostHog/Sentry):
1. Auto-update check → `opencode.ai/install` (+npm/brew) — `OPENCODE_DISABLE_AUTOUPDATE=1` + config
   `autoupdate:false`; Phase 11 packages as RPM so self-upgrade is inert.
2. Model catalog → `models.dev:443` — `OPENCODE_DISABLE_MODELS_FETCH=1` + baked
   `OPENCODE_MODELS_PATH=/etc/<tier>/models.json`.
3. Share → `opncd.ai`/`opencode.ai` — `OPENCODE_DISABLE_SHARE=1` + config `share:"disabled"`.
4. OTLP → only if `OTEL_EXPORTER_OTLP_ENDPOINT` set (off by default) — keep unset.
The LLM endpoint is localhost Ollama (not egress under I1).

## Egress test — PASS (egressZero=true)

Rig: `opencode@1.17.9` binary behind a logging sink proxy (`HTTP(S)_PROXY → 127.0.0.1:8899`) that
records + refuses every TCP connect; caches cleared before each run to force fetches.

- BASELINE (no strips, `opencode models`): **1 outbound** — `CONNECT models.dev:443 HTTP/1.1`.
  Confirmed live: returned the *remote* hosted-model catalog (e.g. `deepseek-v4-flash-free`),
  proving the phone-home fired.
- STRIPPED (all 4 kill switches + local manifest) across `models`, `--version`, `run`, `upgrade`:
  **ZERO outbound.** Catalog resolved from the local manifest; no network fallback.
- Diff: `{models.dev:443 ×1}` → `{}`. Full session egress log = exactly one attempt total, all
  baseline, none stripped.

## Protocol freeze — DONE (protocolFrozen=true)

0002 is parseable and frozen. The two machine-consumed JSON examples (tool-call §2, tool-result §3)
parse as pure JSON; the request example (§1) carries one `/* see §4 */` illustrative placeholder
comment and the §4 block is intentionally an SSE stream (multiple `data:` lines), as documented.
Format = OpenAI Chat Completions tool calling, grounded in OpenCode source
(`tool.ts`: JSONSchema7 `parameters`/`jsonSchema`; `InvalidArgumentsError` → "rewrite the input"
re-ask) and Ollama's `/v1/chat/completions`. Frozen for v0.1; changes require a superseding doc.

## Tests / commands run (evidence)

- `git clone --depth 1 https://github.com/sst/opencode` → cloned (LICENSE = MIT).
- `npm i opencode-ai@1.17.9` → binary `opencode-darwin-arm64`, `--version` = 1.17.9.
- Sink-proxy egress capture: baseline = `CONNECT models.dev:443`; stripped = ZERO across all paths.
- `jq -e .` on all 10 `bench/cases/*.json` → all ok.
- 0002 JSON-block parse check → 2 pure-JSON machine examples ok; §1 comment + §4 SSE expected.

## Open items handed downstream

- Phase 11 must: bundle MIT notice; set the env strip contract in the launch unit; bake
  `/etc/<tier>/models.json`; package so self-upgrade is inert (updates via dnf); optionally enforce a
  localhost-only egress firewall (defense-in-depth floor for I1); re-run this egress rig on the
  installed image as a ship gate.
- Pin is v1.17.9; any version bump re-opens the egress audit (new upstream phone-home = hard I1
  regression). Run this rig in CI on the pinned binary per bump.
- Per the plan, the egress-zero claim + license verdict route to the audit-duo SKILL (two
  independent agents) for adversarial confirmation before downstream phases build on them.
