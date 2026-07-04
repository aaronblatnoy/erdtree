# finetune — ShareGPT Trace Generation for Erdtree

## Purpose

This module generates high-quality fine-tuning data for Erdtree's foundation models (Marika, Radagon). It produces JSONL training records in the ShareGPT/OpenAI messages format, where each record is a complete multi-turn conversation demonstrating:

- Correct tool calling against Erdtree's frozen wire format (docs/decisions/0002)
- The I2 house voice (zero forbidden terms)
- Permission-gated behavior: read ops execute immediately, write/destructive ops require confirmation before execution
- Real system context from Rocky Linux 9
- Coverage across all 11 registered tools

The corpus feeds downstream fine-tuning on the mossad server (TRL/Unsloth, outside this scope).

## Install

**Build/dev only — NOT shipped in the ISO.**

```bash
pip install anthropic tqdm
```

- `anthropic`: For real runs (`--backend anthropic`); lazy-loaded and optional for offline work.
- `tqdm`: Progress bar; optional fallback to silent progress.

## Environment

### Real backend (--backend anthropic)

```bash
export ANTHROPIC_API_KEY="sk-..."
```

Required for `--backend anthropic`. Never commit this value.

### Offline backend (--backend fake) — the default

No environment or credentials required. The Fake backend is deterministic and pre-canned, enabling zero-dependency builds, tests, and offline smoke runs.

## Commands

### Generate traces

```bash
python -m finetune.generate --n INT [OPTIONS]
```

**Required arguments:**
- `--n INT` — Target number of traces to generate.

**Options:**
- `--tier {marika,radagon}` — Target tier. Affects persona and system context depth; does NOT change trace structure (default: `radagon`).
- `--out PATH` — Output JSONL path (default: `finetune/data/traces.jsonl`).
- `--resume` — Append mode; skip already-produced scenario ids (idempotent re-runs).
- `--concurrency INT` — Max concurrent trace generations (default: `5`).
- `--backend {fake,anthropic}` — LLM backend. `fake` is offline/no-key; `anthropic` uses the live API (default: `anthropic`).
- `--claude-model STR` — Anthropic model id (default: `claude-sonnet-4-6`).
- `--seed INT` — RNG seed for scenario selection (default: `0`).

**Examples:**

Offline smoke (no key, no network):
```bash
python -m finetune.generate --n 20 --backend fake --out /tmp/smoke.jsonl
```

Real run with Radagon:
```bash
export ANTHROPIC_API_KEY="sk-..."
python -m finetune.generate --n 600 --tier radagon --backend anthropic
```

Resume a stopped run (skip IDs already in the file):
```bash
python -m finetune.generate --n 600 --tier radagon --resume
```

### Validate traces

```bash
python -m finetune.validate PATH
```

**Positional arguments:**
- `PATH` — JSONL file to validate.

**Behavior:**
- Replays every `tool_calls` entry through `finetune.coreimports.validate_arguments` (the LIVE router).
- Scans every assistant `content` string for I2 violations (forbidden words).
- Verifies `tool_call_id` correlation to following `role:"tool"` messages.
- Reports per-tool coverage, permission-class coverage, MISS rate, I2 violations.

**Exit codes:**
- `0` — MISS rate ≤ 0.5%, zero I2 violations, all 11 tools covered.
- `1` — MISS rate > 0.5%, I2 violation, or any tool has zero valid calls.
- `2` — Bad arguments, unreadable file, etc.

**Examples:**

Validate the offline smoke:
```bash
python -m finetune.generate --n 20 --backend fake --out /tmp/smoke.jsonl
python -m finetune.validate /tmp/smoke.jsonl
```

Validate a production corpus:
```bash
python -m finetune.validate finetune/data/traces.jsonl
```

## Output Format

Each line in the JSONL file is a single training record. Example structure:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "<HOUSE_SYSTEM_PROMPT>\n\n<tier addendum>\n\n<Rocky Linux 9 system context snapshot>"
    },
    {
      "role": "user",
      "content": "is nginx running?"
    },
    {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {
          "id": "toolu_1234567890",
          "type": "function",
          "function": {
            "name": "services",
            "arguments": "{\"operation\":\"status\",\"unit\":\"nginx.service\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "toolu_1234567890",
      "content": "{\"exit_code\":0,\"stdout\":\"● nginx.service - The NGINX HTTP...\",\"stderr\":\"\",\"summary\":\"nginx.service is active (running)\"}"
    },
    {
      "role": "assistant",
      "content": "nginx.service is active and running."
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "services",
        "description": "...",
        "parameters": { ... }
      }
    },
    ...
  ],
  "meta": {
    "tier": "radagon",
    "scenario_id": "services-status-0007",
    "tool": "services",
    "operation": "status",
    "permission_class": "read"
  }
}
```

**Key points:**
- `messages` — Standard OpenAI messages array.
- `tool_calls[].function.arguments` — JSON-encoded string, not a nested object (docs/decisions/0002 §2).
- `content` — `null` on assistant tool-call turns; a string on final answer turns.
- `tool_call_id` correlation — Each `toolu_...` id in `tool_calls` has a matching `role:"tool"` message in the same record.
- `tools` — The full 0002 §1 function schema list, derived LIVE from the registry at generation time.
- `meta` — Scenario metadata for downstream filtering/analysis (tier, operation, permission class, etc.).

## Load-Bearing Invariants

These are the rules that keep the corpus correct and aligned with Erdtree's frozen contract. Code and tests enforce them; this README documents their intent.

### INV-schema-sync: Live Registry, Never Hardcoded

**Rule:** Tool schemas, operation names, argument names, and permission classes come LIVE from `finetune.coreimports` (which imports from `core/`), never hardcoded.

**Why:** Erdtree's tools evolve in `core/`. The corpus must track that evolution. If a tool schema changes in `core/`, the traces generated before the change should not be re-validated against the new schema (they won't validate). By always deriving schemas at generation and validation time, the corpus stays in sync with the snapshot of `core/` it was built against.

**Enforcement:**
- `generate.py` calls `coreimports.live_tool_list()` to get current schemas.
- `validate.py` replays calls through `coreimports.validate_arguments()` (the authoritative router).
- Tests assert that converted calls pass the LIVE router.

### INV-house-prompt: System Prompt from Core

**Rule:** The system prompt injected into every trace **must** come from `core/agent/prompt._HOUSE_SYSTEM_PROMPT` (re-exported as `coreimports.HOUSE_SYSTEM_PROMPT`), never hand-written.

**Why:** The house prompt is part of the contract. If it drifts between training and production, the model learns a different voice than it will see in the field. By re-exporting the exact same string, we guarantee fidelity.

**Enforcement:**
- `generate.py` calls `coreimports.assemble_messages()`, which injects the prompt automatically.
- `validate.py` is read-only; it doesn't verify the prompt content, only the message structure.
- Tests can call `coreimports.assert_no_ai_language(coreimports.HOUSE_SYSTEM_PROMPT)` to prove it's clean.

### INV-I2 (No AI Language): I2-Clean Content

**Rule:** Every synthesized assistant `content` string, and every injected snapshot/system-prompt string, **must** pass `finetune.coreimports.assert_no_ai_language()`.

**Forbidden words:** "AI", "LLM", "model", "agent", "ollama", "inference", and related terms. The user never sees those words in the output — the technology is invisible.

**Note:** User input (`scenario.user_input`) is NOT asserted I2-clean; users can say what they want. Only synthesized/injected text (assistant replies, confirmation prompts, system messages) must be clean.

**Enforcement:**
- `generate.py` asserts final answers before emitting.
- `simulate.py` summaries are pre-checked.
- `context.py` snapshots are pre-checked.
- `validate.py` scans and reports any violations.
- Tests in `tests/finetune/test_i2.py` scan the full corpus.

### INV-0002 (Frozen Wire Format): Exact Message Shape

**Rule:** Emitted records **must** match docs/decisions/0002 §1, §2, §3 EXACTLY:

- **§1:** `tools` array is a function-schema list.
- **§2:** `tool_calls[].type == "function"`; `function.arguments` is a JSON-encoded **string** (not a nested object); `content` is `null` on tool-call turns.
- **§3:** `role:"tool"` messages carry `tool_call_id` (the `toolu_...` from the call) and JSON-compact `content` (the result dict as a string).

**Why:** The model is fine-tuned on this exact wire shape. Any deviation breaks the contract and degrades performance.

**Enforcement:**
- `convert.py` is the pure format converter; all assertions are here.
- `json.dumps(arguments, separators=(',',':'))` ensures string, not object.
- Tests in `tests/finetune/test_convert.py` round-trip known-good inputs through `validate.py` to prove compliance.

### INV-offline: Fake Backend Default

**Rule:** The LLM is behind a seam (`finetune.llm`). The `FakeBackend` is the default in all builds and smoke runs. No network, no key required for offline work.

**Why:** Enables CI, fast iteration, and testing without API costs or credentials.

**Enforcement:**
- `generate.py` defaults `--backend fake`.
- `llm.py` lazy-imports `anthropic` only inside `AnthropicBackend` so offline doesn't require it.
- CI runs use `--backend fake`.

### INV-read-only-core: Unidirectional Dependency

**Rule:** `finetune/` imports FROM `core/` via `finetune.coreimports`. **Never** modify anything under `core/`. If a core schema looks wrong, report it — never patch it in `finetune/`.

**Why:** `core/` is the single source of truth. `finetune/` is a read-only consumer. This keeps the architecture clean and prevents tangled circular dependencies.

### INV-data-gitignored: Generated Data Never Committed

**Rule:** `finetune/data/` (where `traces.jsonl` lives) is gitignored. Generated traces are not committed to the repo.

**Why:** Traces are bulky and regenerable. They clutter history and can be reproduced deterministically from code.

**How to check:**
```bash
git check-ignore finetune/data/traces.jsonl
# Should print the path, confirming it's ignored.
```

## Integration with Downstream Training

This module produces **data only**, not trained weights. The next step is:

**mossad fine-tuning job** (separate plan):
- Reads `finetune/data/traces.jsonl`.
- Runs TRL/Unsloth to fine-tune Qwen2.5 (3B or 7B) on the ShareGPT corpus.
- Outputs quantized weights (GGUF) for bundling in the Ollama Modelfile.
- The mossad job is orchestrated outside this scope.

For details on the training infrastructure, see the mossad server docs and the TRL/Unsloth configs.

## Testing

Run all finetune tests locally (fully offline):

```bash
python -m pytest tests/finetune/ -q
```

This includes:
- `test_convert.py` — Round-trip Anthropic → OpenAI format, verify against LIVE router.
- `test_scenarios.py` — Coverage: ≥600 scenarios, all tools, all permission classes, unique ids.
- `test_validate.py` — Good and bad records, verdict consistency with RouterResult.
- `test_i2.py` — Scan all text for forbidden terms.

## Glossary

- **Tier** — Target model size / persona (Marika ~3B, Radagon 7B–14B). Affects system context depth and tone, not trace structure.
- **Scenario** — A user request + the tool/operation it targets. Scenarios are authored once, then used to seed random traces.
- **ShareGPT** — The JSONL training format used by TRL/Unsloth. Messages + tools metadata + per-record annotations.
- **I2** — "No AI Language" invariant. The output is strictly system terminology, never mentions LLMs.
- **0002** — The frozen wire format contract. Defines exactly how tool calls and results are encoded.
- **LIVE router** — `coreimports.validate_arguments()`, the authoritative validator. Traces must pass it.
- **MISS** — A tool call that fails validation (invalid arguments, wrong operation, etc.). Target: ≤ 0.5%.

## Quick Start

### 1. Smoke test (offline, no key)
```bash
python -m finetune.generate --n 10 --backend fake --out /tmp/test.jsonl
python -m finetune.validate /tmp/test.jsonl
```

### 2. Generate a real corpus (requires ANTHROPIC_API_KEY)
```bash
export ANTHROPIC_API_KEY="sk-..."
python -m finetune.generate --n 600 --tier radagon
python -m finetune.validate finetune/data/traces.jsonl
```

### 3. Resume a partial run
```bash
python -m finetune.generate --n 600 --resume
python -m finetune.validate finetune/data/traces.jsonl
```

---

**Last updated:** Phase 7, finetune-data-generation plan.
