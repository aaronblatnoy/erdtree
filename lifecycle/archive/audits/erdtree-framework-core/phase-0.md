# Phase 0 (re-scoped) — Erdtree framework core: build-our-own + tool-call protocol freeze + bench seed

- Date: 2026-06-21
- Scope touched: `docs/decisions/` and `bench/` ONLY (per brief).
- Host honesty boundary: macOS dev host — NO Ollama, NO GPU, NO Linux. Only source-level audit +
  parseable-fixture validation is performable here. Anything needing a live model or real Linux is
  written as a DEFERRED-TO-MOSSAD test, never reported as a passing live result.
- Framing honored: the PRODUCT is Erdtree's OWN framework in `core/`. `vendor/claude-code` and
  `vendor/opencode` are INSPIRATION ONLY — read to ground the wire contract, never imported/shipped.

## Re-scope applied (this run)

The harness question is RESOLVED: we build our OWN framework; the references are inspiration only.
A prior run had left the docs in the OLD "adopt OpenCode as the shipped harness" framing
(`0001-harness-selection.md`) and 0002 framed around "the selected harness." I re-scoped to match
the brief:
- CREATED `docs/decisions/0001-framework.md` — the build-our-own decision + rationale.
- REMOVED the stale `docs/decisions/0001-harness-selection.md` (superseded by the above).
- RE-FRAMED `docs/decisions/0002-tool-call-protocol.md` to a portable, framework-level contract
  grounded in (not adopting) the references; kept it FROZEN and its faithful body intact.
- Verified the bench seed (README validity definition + 10 cases) — unchanged, found faithful.

## Deliverables

### (1) docs/decisions/0001-framework.md  [CREATED]
Records the build-our-own decision: `core/` is Erdtree's own framework, never imports `vendor/`, and
only ever opens the loopback Ollama socket (`http://localhost:11434/v1`) — so I1 holds **by
construction**, with no egress to enumerate-and-strip and no third-party license/attribution/
telemetry baggage. Reference-tree verdicts (both INSPIRATION ONLY):
- **Claude Code = NO-GO to ship** — proprietary (All Rights Reserved / Anthropic Commercial ToS),
  cloud-bound, Statsig telemetry in the proprietary build we don't control. Disqualified on license
  AND I1 regardless. Read for agentic-loop / tool-use / terminal-UX inspiration only.
- **OpenCode = MIT inspiration, not shipped** — clean MIT (would permit redistribution with
  attribution), read freely to ground the wire format; still not shipped because building our own
  removes the strip/attribution/version-bump-re-audit burden and keeps `core/` portable.
Rationale covers: zero telemetry to strip, no redistribution license, native invisible-AI (I2),
no hardcoded tier name (I6 via `ERDTREE_TIER`), and "the framework IS the moat." Includes the
operational boundary (`core/` never imports `vendor/`; nothing from either tree is redistributed)
and a CI-grep follow-up to enforce it.

### (2) docs/decisions/0002-tool-call-protocol.md  [RE-FRAMED, kept FROZEN]
Freezes Erdtree's OWN tool-call contract, grounded in Ollama's real `/v1/chat/completions`
function-calling format. The contract body (request shape, `tool_calls` parsing, `role:"tool"`
result messages, SSE delta assembly by `index`, malformed/re-ask handling, VALID/MISS definition)
was already faithful and is preserved; I re-framed the header + Decision + source block so it reads
as a portable framework contract GROUNDED in (not adopting) the references.

### (3) bench/README.md + bench/cases/*.json  [PRESENT, validated]
README fixes the validity-rate definition (VALID iff >=1 `tool_calls[]` with `type=="function"`,
`function.name` registered, `function.arguments` parses as JSON, parsed args validate against the
tool's JSON-Schema; else MISS). Targets: Radagon 7B/14B >=99.5% (ship gate); Marika 3B
recorded-not-gated (GO/HOLE). 10 seed cases span services/packages/logs across read/write/
destructive plus 2 negative controls (`df -h` raw command must NOT be mistranslated; chitchat stays
English) correctly EXCLUDED from the validity denominator.

## Source verification (grounding, all on this host, static)

Vendored tree: `vendor/opencode`, pinned **version 1.17.9** (`packages/opencode/package.json:3`),
checkout commit `f12ac6f`. Every 0002 citation re-verified present in the real source:
- `protocols/openai-chat.ts`: tool advert `{type:"function",function:{name,description,parameters}}`
  (`OpenAIChatTool` L41-44, `lowerTool` L177-184); assistant call
  `{id,type:"function",function:{name,arguments:STRING}}` (`OpenAIChatAssistantToolCall` L47-55;
  `lowerToolCall` JSON-encodes input L199); tool result `{role:"tool",tool_call_id,content}` (union
  L77; `lowerToolMessages` L262-283); SSE deltas by `index`, args concatenated + finalized eagerly
  (`OpenAIChatToolCallDelta` L136-141, `step` L416-435); `finish_reason "tool_calls"/"function_call"`
  → tool-calls (`mapFinishReason` L370-376). ✓
- `protocols/openai-compatible-chat.ts` L17-22: non-OpenAI providers (Ollama) reuse
  `OpenAIChat.protocol` end-to-end at `/chat/completions` with SSE framing → Ollama's
  `/v1/chat/completions` is the identical schema. ✓
- `tool.ts`: record key = wire tool name; per-tool JSON-Schema via `toDefinitions` L221-230
  (`inputSchema` L182/202/227). ✓
- `tool-runtime.ts`: `"Unknown tool: <name>"` L25; `"Invalid tool input: <error>"` L39. ✓
- `opencode/src/tool/tool.ts`: `ToolInvalidArgumentsError` L25; exact "rewrite the input so it
  satisfies the expected schema" wording L32 (the §5 re-ask text). ✓

## Tests / output (this host, reproducible)

```
0002 JSON blocks (request body, tool-call, tool-result): block 0/1/2 OK
bench/cases/*.json (all 10): OK (10/10)
ALL_MACHINE_JSON_PARSE: True
no stray "selected harness"/"adopt OpenCode" framing except the intentional 0001 Supersedes note
docs/decisions/ = {0001-framework.md, 0002-tool-call-protocol.md}  (stale 0001-harness-selection.md removed)
```
(The bench README's lone JSON block is an illustrative schema with `//` comments — not
machine-consumed.)

## Deferred (honest, requires mossad / real Linux — NOT run here)

- LIVE tool-call validity rate (Radagon 7B/14B >=99.5% ship gate; Marika 3B GO/HOLE verdict). Needs
  running Ollama + the pinned tier model. → DEFERRED-TO-MOSSAD / Phase-4 runner `bench/run_bench.py`.
- LIVE zero-egress IMAGE proof (firewall floor allow-only `127.0.0.1:11434`). Needs real Linux. →
  DEFERRED-TO-MOSSAD / Phase-11 installed-image ship gate. (For `core/` itself, I1 is by
  construction — it opens only the loopback socket — but the whole-image proof still belongs to P11.)

## Verdicts

- Framework: **BUILD OUR OWN** (`core/`); references are inspiration only.
- Claude Code: **NO-GO to ship** (proprietary + cloud-bound). OpenCode: **MIT inspiration, not shipped**.
- 0002 tool-call contract: **FROZEN, parseable, faithful** to Ollama's `/v1/chat/completions`
  function-calling format and to the real OpenCode source.
- passed = TRUE for Phase 0's bar: 0002 parses + is faithful to Ollama's real format; 0001 records
  the build-our-own decision with correct reference verdicts; bench validity definition + 10 seed
  cases in place. Live model/Linux items honestly deferred above.
