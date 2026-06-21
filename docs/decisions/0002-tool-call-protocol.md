# 0002 — Tool-Call Protocol (FROZEN CONTRACT)

- Status: ACCEPTED — **FROZEN**
- Date: 2026-06-21
- Phase: 0 (Gating Spikes)
- Read by: Phase 3 (`core/agent/prompt.py`), Phase 4 (`core/agent/router.py`), Phase 10 (training data)
- Gates: the central internal contract (plan §5); decision #2 (tool-call reliability is the #1 bet)
- Scope: **framework-level and portable.** This is Erdtree's OWN tool-call contract (per 0001 we
  build our own framework; we do NOT import or ship OpenCode). The OpenCode files cited below are
  read as INSPIRATION/GROUNDING ONLY — to confirm the wire shape `core/` independently targets is
  the same OpenAI-Chat function-calling shape a real compatible harness emits AND, critically, the
  shape **Ollama's `/v1/chat/completions` endpoint presents**.

## Decision

The frozen tool-call I/O format is **OpenAI Chat Completions function/tool calling**, exactly as
**Ollama's `/v1/chat/completions` endpoint presents** (Ollama's OpenAI-compatible API). This is the
contract `core/agent/router.py` parses, `core/agent/prompt.py` formats, and training data (Phase 10)
must match byte-for-byte. It is independent of any harness: `core/` speaks this shape directly to
localhost Ollama.

Grounding sources (read as INSPIRATION ONLY; NOT imported, NOT shipped — all paths under
`vendor/opencode`, pinned v1.17.9, commit `f12ac6f`, verified present). They are cited to prove the
shape we target equals what a real OpenAI-Chat-compatible implementation emits/parses:
- `packages/llm/src/protocols/openai-chat.ts` — the actual OpenAI Chat wire schema OpenCode emits and
  parses. The request body (`bodyFields`, lines 89-105) carries `model`, `messages`, `tools`,
  `tool_choice`, `stream: true`. A tool is `{type:"function", function:{name, description, parameters}}`
  (`OpenAIChatTool` / `lowerTool`, lines 41-44, 177-184). An assistant tool call is
  `{id, type:"function", function:{name, arguments}}` where `arguments` is a **string**
  (`OpenAIChatAssistantToolCall`, lines 47-55; `lowerToolCall` JSON-encodes input at line 199). A tool
  result is `{role:"tool", tool_call_id, content}` (message union line 77; `lowerToolMessages` lines
  262-283). Streaming deltas accumulate by `index` with `id`/`name` once and `arguments` concatenated
  (`OpenAIChatToolCallDelta` lines 136-141; `step` accumulator lines 416-428; `mapFinishReason` maps
  `"tool_calls"`/`"function_call"` → tool-calls, lines 370-376; args are JSON-finalized eagerly at the
  finish boundary, `ToolStream.finishAll`, lines 432-435).
- `packages/llm/src/protocols/openai-compatible-chat.ts` — confirms non-OpenAI providers (Ollama)
  reuse `OpenAIChat.protocol` end-to-end at endpoint `/chat/completions` with SSE framing (lines 17-22).
  So Ollama's `/v1/chat/completions` is parsed by the identical state machine.
- `packages/llm/src/tool.ts` — each tool bundles a JSON-Schema parameter schema; the record key
  becomes the wire tool name (`toDefinitions`, lines 221-230). This is the per-tool schema our Phase-2
  registry must emit.
- `packages/llm/src/tool-runtime.ts` — the dispatch/validity contract: an unregistered tool yields
  `"Unknown tool: <name>"` (line 25) and a parameter decode failure yields
  `"Invalid tool input: <error>"` (line 39) as a `ToolFailure` — these are the low-level MISS signals
  our `router.py` mirrors.
- `packages/opencode/src/tool/tool.ts` — the higher-level typed `ToolInvalidArgumentsError`
  (`"ToolInvalidArgumentsError"`, line 25) whose message is *"The `<tool>` tool was called with
  invalid arguments: `<detail>`. Please rewrite the input so it satisfies the expected schema."*
  (line 32) — this is the exact re-ask wording §5 adopts.

NOTE: this contract is framework-level and portable. Erdtree's `core/` does NOT import OpenCode; the
above files are read only to confirm the wire format we independently target equals what a real
OpenAI-Chat-compatible harness emits AND what Ollama presents.

## Endpoint shape Ollama must present (decision)

- **Endpoint:** `POST http://localhost:11434/v1/chat/completions` (Ollama's OpenAI-compatible API).
- **Streaming:** `"stream": true` → Server-Sent Events, one `data: {…chunk…}` line per event,
  terminated by `data: [DONE]`. Tool calls arrive as **deltas** assembled across chunks.
- **Auth:** none (localhost). I1: client asserts host is loopback before connecting.
- **Model:** the pinned tier tag (never `:latest`), e.g. `qwen2.5:14b-instruct-q4_K_M`.

## 1. Tool advertisement (request → model)

(`"messages"` is shown empty here for brevity; the assembled message array is specified in §4 and the
prompt layer, Phase 3. The example below is a complete, parseable request body.)

```json
{
  "model": "qwen2.5:14b-instruct-q4_K_M",
  "stream": true,
  "messages": [],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "services",
        "description": "Inspect and control systemd units (status/start/stop/restart/enable).",
        "parameters": {
          "type": "object",
          "properties": {
            "operation": { "type": "string", "enum": ["status","start","stop","restart","enable","disable","logs"] },
            "unit":      { "type": "string", "description": "systemd unit name, e.g. nginx.service" }
          },
          "required": ["operation","unit"],
          "additionalProperties": false
        }
      }
    }
  ],
  "tool_choice": "auto"
}
```

- `tools[].type` is always `"function"`.
- `tools[].function.parameters` is a **JSON Schema (draft-07 subset)** object. This is the schema
  `core/tools/__init__.py` (Phase 2) emits per tool; the tool registry is the single source of
  these schemas.
- `tool_choice`: `"auto"` (default). Erdtree does not force a specific tool.

## 2. Tool call (model → us) — the parse target for router.py

Non-streaming shape of one assistant turn that calls tools:

```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "services",
        "arguments": "{\"operation\":\"restart\",\"unit\":\"nginx.service\"}"
      }
    }
  ]
}
```

Frozen parse rules (`router.py` MUST implement exactly):
- A tool call is identified by an entry in `tool_calls[]` with `type == "function"`.
- `function.name` MUST match a registered tool id (Phase 2 registry). Unknown name → MISS (re-ask).
- `function.arguments` is a **JSON-encoded string**, NOT a nested object. Parse it; on JSON parse
  failure or schema-validation failure → MISS, count it against validity (bench), emit the
  re-ask message (§5), do NOT crash.
- `id` is the correlation key echoed back in the tool result (§3).
- Multiple entries in `tool_calls[]` = parallel tool calls; each gets its own result message.
- An assistant turn with `content` non-null and no `tool_calls` = a plain English answer (loop end
  or intermediate narration), not a tool call.

## 3. Tool result (us → model)

After executing a tool (through permissions + audit, Phases 1–2), append ONE message per call:

```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "{\"exit_code\":0,\"stdout_summary\":\"nginx.service restarted\",\"stderr_summary\":\"\"}"
}
```

- `tool_call_id` MUST equal the `id` from §2 (correlation).
- `content` is a string; Erdtree puts the **structured tool result** (the Phase-2 `execute()` shape)
  in as compact JSON so the model can reason over exit code + summaries.

## 4. Streaming shape (the wire, what ollama.py consumes)

SSE chunks; tool calls assemble across deltas:

```
data: {"choices":[{"delta":{"role":"assistant"}}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_abc123","type":"function","function":{"name":"services","arguments":""}}]}}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"operation\":\"res"}}]}}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"tart\",\"unit\":\"nginx.service\"}"}}]}}]}
data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}
data: [DONE]
```

Frozen streaming-assembly rules:
- Accumulate `tool_calls[]` by `index`. The `id`, `type`, `function.name` appear once (first delta
  for that index); `function.arguments` is concatenated across deltas into the full JSON string.
- `finish_reason: "tool_calls"` → the model is calling tools; dispatch after `[DONE]` (or after the
  finish event) once arguments are complete.
- `finish_reason: "stop"` with accumulated `content` → English answer; render it (I8: stream to the
  user as it arrives for instant feel).
- `[DONE]` terminates the stream.

## 5. Malformed-call / re-ask contract (validity definition anchor)

A turn is a VALID tool call iff: it contains ≥1 `tool_calls[]` entry, `function.name` is a
registered tool, and `function.arguments` parses as JSON AND validates against that tool's parameter
schema. Anything else (prose where a tool was required, unknown tool, unparseable/invalid args) is a
MISS. On a MISS, `router.py` feeds back a `role:"tool"` (or system) message mirroring OpenCode's
contract — *"The `<tool>` tool was called with invalid arguments: `<detail>`. Please rewrite the
input so it satisfies the expected schema."* (verbatim from
`packages/opencode/src/tool/tool.ts:32`; the lower-level `tool-runtime.ts` equivalents are
`"Unknown tool: <name>"` at line 25 and `"Invalid tool input: <error>"` at line 39) — and re-asks; it
never crashes. This MISS definition is what `bench/` measures (target ≥99.5% valid; see
`bench/README.md`).

## Freeze statement

This contract is **FROZEN** for v0.1. `prompt.py` formats tool schemas per §1, `router.py` parses
per §2/§4 and re-asks per §5, tool results follow §3, and Phase-10 training traces are generated in
exactly this shape (decision #2 — training data must match the harness I/O format byte-for-byte).
Any change requires a new superseding decision doc; it cannot be edited in place.
