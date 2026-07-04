"""tests/finetune/test_i2.py — INV-I2 gate over all simulator summaries.

Asserts that every simulate() summary and every hand-written assistant text
string passes core's _assert_no_ai_language (re-exported from coreimports as
assert_no_ai_language).

Forbidden terms (case-insensitive, whole-word): ai, llm, model, agent,
neural, machine learning, gpt, ollama, inference, etc.  The full canonical
list lives in core/agent/prompt.py; this test binds to that REAL function via
coreimports — never a hand-rolled copy.

Scope
-----
1. Every (tool, op) in the LIVE registry → simulate() → summary field.
   Uses a minimal but realistic probe-args dict so the simulator always
   returns output (not a missing-arg error).
2. Hand-written assistant text constants used by FakeBackend and the corpus
   scaffold (HOUSE_SYSTEM_PROMPT, _FAKE_ANSWER, etc.).

NOT in scope
------------
* operator / user_input text in Scenario objects — these represent raw user
  utterances (untrusted input) and must NOT be I2-filtered (INV-I2 applies
  only to assistant *content*, simulate *summary*, and injected system/snapshot
  strings, not to what the user types).

Load-bearing invariants
-----------------------
INV-schema-sync   Tool and op names are derived LIVE from the registry.
INV-read-only-core Tests import from finetune only; never from core/ directly.
INV-offline       Tests run with no network, no Ollama, no API key.
INV-I2            Every assertion here binds to the REAL filter in core/.
"""

from __future__ import annotations

import pytest

from finetune.coreimports import (
    assert_no_ai_language,
    HOUSE_SYSTEM_PROMPT,
    registry_schemas,
    registry,
)
from finetune.simulate import simulate, _PROBE_ARGS


# ---------------------------------------------------------------------------
# Build the full (tool, op, probe_args) fixture list from the live registry.
# ---------------------------------------------------------------------------

def _all_tool_op_pairs() -> list[tuple[str, str, dict]]:
    """Return [(tool, op, probe_args), ...] for every (tool, op) in the registry."""
    pairs: list[tuple[str, str, dict]] = []
    for schema in registry_schemas(registry):
        tool_name = schema["name"]
        props = schema["parameters"]["properties"]
        ops: list[str] = []
        for _key, spec in props.items():
            if isinstance(spec, dict) and "enum" in spec:
                ops = spec["enum"]
                break
        for op in ops:
            probe_args = _PROBE_ARGS.get((tool_name, op), {})
            pairs.append((tool_name, op, probe_args))
    return pairs


_TOOL_OP_PAIRS = _all_tool_op_pairs()


# ---------------------------------------------------------------------------
# 1. Simulator summary I2 scan — parametrized over every (tool, op).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool,op,probe_args", _TOOL_OP_PAIRS, ids=[
    f"{t}.{o}" for t, o, _ in _TOOL_OP_PAIRS
])
def test_simulate_summary_is_i2_clean(tool: str, op: str, probe_args: dict) -> None:
    """simulate(tool, op, ...) must return an I2-clean summary string."""
    result = simulate(tool, op, probe_args, ctx={})

    # Assert required keys present (belt-and-suspenders alongside __init__ assert)
    assert set(result.keys()) == {"exit_code", "stdout", "stderr", "summary"}, (
        f"{tool}.{op}: result has unexpected keys {set(result.keys())}"
    )

    summary = result["summary"]
    assert isinstance(summary, str), (
        f"{tool}.{op}: summary is not a str (got {type(summary).__name__})"
    )

    # Core filter — raises AssertionError with the forbidden term if it fires.
    assert_no_ai_language(summary, label=f"simulate({tool!r}, {op!r}).summary")


# ---------------------------------------------------------------------------
# 2. Simulator result shape — every (tool, op) must return the 4 required keys.
#    This is belt-and-suspenders alongside the module-level completeness assert
#    in finetune/simulate/__init__.py; having it here surfaces failures in pytest
#    output alongside the I2 failures so they are easy to diagnose together.
#
#    Note: stdout/stderr are raw system tool output (e.g. parted/lscpu lines
#    that legitimately contain "Model:" for hardware model numbers).  INV-I2
#    applies to assistant *content* strings, simulate *summary*, and injected
#    system-prompt/snapshot strings — NOT to raw stdout/stderr output.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool,op,probe_args", _TOOL_OP_PAIRS, ids=[
    f"{t}.{o}" for t, o, _ in _TOOL_OP_PAIRS
])
def test_simulate_returns_required_keys(tool: str, op: str, probe_args: dict) -> None:
    """simulate() must return a dict with exactly the four ToolResult keys."""
    result = simulate(tool, op, probe_args, ctx={})
    assert isinstance(result, dict), (
        f"{tool}.{op}: simulate() returned {type(result).__name__}, expected dict"
    )
    missing = {"exit_code", "stdout", "stderr", "summary"} - set(result.keys())
    assert not missing, (
        f"{tool}.{op}: result is missing keys: {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# 3. Hand-written assistant text — constants that appear verbatim in traces.
# ---------------------------------------------------------------------------

def test_house_system_prompt_is_i2_clean() -> None:
    """HOUSE_SYSTEM_PROMPT (from core/agent/prompt.py) must be I2-clean.

    This is the system prompt injected into every trace.  Its content must
    never expose forbidden AI-language terms to the corpus reader.
    """
    assert isinstance(HOUSE_SYSTEM_PROMPT, str) and HOUSE_SYSTEM_PROMPT, (
        "HOUSE_SYSTEM_PROMPT is empty or not a string"
    )
    assert_no_ai_language(HOUSE_SYSTEM_PROMPT, label="HOUSE_SYSTEM_PROMPT")


def test_fake_backend_answer_is_i2_clean() -> None:
    """The FakeBackend canned answer must be I2-clean.

    FakeBackend already asserts this at construction, but we test it
    independently here so a broken llm.py surfaces in test_i2.py too.
    """
    from finetune.llm import _FAKE_ANSWER  # deliberate: the real constant

    assert isinstance(_FAKE_ANSWER, str) and _FAKE_ANSWER, (
        "_FAKE_ANSWER is empty or not a string"
    )
    assert_no_ai_language(_FAKE_ANSWER, label="FakeBackend._FAKE_ANSWER")


# ---------------------------------------------------------------------------
# 4. Completeness self-check — ensure the parametrize list is non-empty and
#    covers all 11 tools.  If coreimports loses a tool, this catches it.
# ---------------------------------------------------------------------------

def test_i2_coverage_is_complete() -> None:
    """Verify the parametrized I2 scan covers all 11 registered tools."""
    from finetune.coreimports import TOOL_NAMES

    covered_tools = {t for t, _o, _a in _TOOL_OP_PAIRS}
    missing = set(TOOL_NAMES) - covered_tools
    assert not missing, (
        f"I2 coverage missing tools: {sorted(missing)}.  "
        "Did a new tool register without a (tool, op) entry in _PROBE_ARGS?"
    )

    assert len(_TOOL_OP_PAIRS) > 0, "No (tool, op) pairs found — registry is empty?"
