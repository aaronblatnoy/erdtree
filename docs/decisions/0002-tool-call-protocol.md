# 0002 — Tool-Call Protocol (FROZEN CONTRACT)

- Status: ACCEPTED — **FROZEN**
- Date: 2026-06-21
- Phase: 0 (Gating Spikes)
- Read by: Phase 3 (`core/agent/prompt.py`), Phase 4 (`core/agent/router.py`), Phase 10 (training data)
- Gates: the central internal contract (plan §5); decision #2 (tool-call reliability is the #1 bet)

## Decision

The frozen tool-call I/O format is **OpenAI Chat Completions function/tool calling**, exactly as
emitted and parsed by the selected harness (OpenCode, on the Vercel AI SDK via
`@ai-sdk/openai-compatible`) and exactly as **Ollama's `/v1/chat/completions` endpoint presents**.
This is the contract `router.py` parses, `prompt.py` formats, and training data (Phase 10) must
match byte-for-byte.

Source of truth: OpenCode defines each tool with a JSON-Schema-7 parameter schema
(`packages/opencode/src/tool/tool.ts`: `parameters` / `jsonSchema?: JSONSchema7`) and drives the
model through the AI SDK, whose openai-compatible provider speaks OpenAI Chat Completions tool
calls. A malformed call is a typed `ToolInvalidArgumentsError` whose message asks the model to
"rewrite the input so it satisfies the expected schema" — this defines our re-ask contract.

## Endpoint shape Ollama must present (decision)

- **Endpoint:** `POST http://localhost:11434/v1/chat/completions` (Ollama's OpenAI-compatible API).
- **Streaming:** `"stream": true` → Server-Sent Events, one `data: {…chunk…}` line per event,
  terminated by `data: [DONE]`. Tool calls arrive as **deltas** assembled across chunks.
- **Auth:** none (localhost). I1: client asserts host is loopback before connecting.
- **Model:** the pinned tier tag (never `:latest`), e.g. `qwen2.5:14b-instruct-q4_K_M`.

## 1. Tool advertisement (request → model)

```json
{
  "model": "qwen2.5:14b-instruct-q4_K_M",
  "stream": true,
  "messages": [ /* see §4 */ ],
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
input so it satisfies the expected schema."* — and re-asks; it never crashes. This MISS definition
is what `bench/` measures (target ≥99.5% valid; see `bench/README.md`).

## Freeze statement

This contract is **FROZEN** for v0.1. `prompt.py` formats tool schemas per §1, `router.py` parses
per §2/§4 and re-asks per §5, tool results follow §3, and Phase-10 training traces are generated in
exactly this shape (decision #2 — training data must match the harness I/O format byte-for-byte).
Any change requires a new superseding decision doc; it cannot be edited in place.
