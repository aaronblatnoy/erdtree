"""tests/finetune/test_convert.py — the correctness gate for the format crux.

Proves the emitted records match docs/decisions/0002 §2/§3 EXACTLY and that
every converted tool call validates through the LIVE router (INV-0002 +
INV-schema-sync).  All offline: no anthropic, no key, no network.
"""

from __future__ import annotations

import json

import pytest

from finetune import coreimports, convert
from finetune.convert import (
    anthropic_tool_result_to_openai_tool_msg,
    anthropic_tool_use_to_openai_tool_calls,
    assemble_record,
    assistant_text_to_openai,
)
from finetune.llm import FakeBackend, ToolUseBlock


# A KNOWN Anthropic tool_use, as the SDK would deliver it: input is a DICT.
KNOWN_ID = "toolu_01A9c8b7D6e5F4g3H2i1J0kL"
KNOWN_TOOL = "services"
KNOWN_OP = "status"
KNOWN_INPUT = {"operation": KNOWN_OP, "unit": "nginx.service"}


def _known_blocks_objectshape():
    return [ToolUseBlock(id=KNOWN_ID, name=KNOWN_TOOL, input=dict(KNOWN_INPUT))]


def _known_blocks_dictshape():
    return [{"type": "tool_use", "id": KNOWN_ID, "name": KNOWN_TOOL, "input": dict(KNOWN_INPUT)}]


# --------------------------------------------------------------------------- #
# 1. Round-trip + shape (0002 §2)                                             #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("blocks", [_known_blocks_objectshape(), _known_blocks_dictshape()])
def test_tool_use_turn_shape(blocks):
    turn = anthropic_tool_use_to_openai_tool_calls(blocks)

    assert turn["role"] == "assistant"
    assert turn["content"] is None  # None on a tool-call turn (0002 §2)
    assert len(turn["tool_calls"]) == 1

    call = turn["tool_calls"][0]
    assert call["type"] == "function"          # always "function" (0002 §2)
    assert call["id"] == KNOWN_ID              # id flows through VERBATIM (A5)
    assert call["function"]["name"] == KNOWN_TOOL


@pytest.mark.parametrize("blocks", [_known_blocks_objectshape(), _known_blocks_dictshape()])
def test_arguments_is_json_string_not_object(blocks):
    call = anthropic_tool_use_to_openai_tool_calls(blocks)["tool_calls"][0]
    arguments = call["function"]["arguments"]

    # THE poison bug guard: arguments must be a STRING, never a nested object.
    assert isinstance(arguments, str)
    # And it must decode back to the original input dict.
    assert json.loads(arguments) == KNOWN_INPUT
    # Compact encoding (0002): no spaces after separators.
    assert ", " not in arguments and '": ' not in arguments


# --------------------------------------------------------------------------- #
# 2. Converted call validates through the LIVE router (INV-schema-sync)        #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("blocks", [_known_blocks_objectshape(), _known_blocks_dictshape()])
def test_converted_call_passes_live_router(blocks):
    call = anthropic_tool_use_to_openai_tool_calls(blocks)["tool_calls"][0]
    parsed = json.loads(call["function"]["arguments"])

    spec = coreimports.registry.get(call["function"]["name"])
    assert spec is not None, "tool must be registered live"

    # validate_arguments raises ValueError on any violation; returning cleanly
    # means VALID.  It returns (operation, per_op_args).
    operation, rest = coreimports.validate_arguments(spec, parsed)
    assert operation == KNOWN_OP
    assert rest == {"unit": "nginx.service"}


# --------------------------------------------------------------------------- #
# 3. tool_call_id correlation (0002 §3)                                        #
# --------------------------------------------------------------------------- #

def test_tool_call_id_correlation():
    turn = anthropic_tool_use_to_openai_tool_calls(_known_blocks_objectshape())
    call_id = turn["tool_calls"][0]["id"]

    result = {"exit_code": 0, "stdout": "", "stderr": "", "summary": "nginx.service is active (running)"}
    tool_msg = anthropic_tool_result_to_openai_tool_msg(call_id, result)

    assert tool_msg["role"] == "tool"
    # Correlation MUST hold: the result's tool_call_id equals the call's id.
    assert tool_msg["tool_call_id"] == call_id == KNOWN_ID
    # content is a compact-JSON STRING body (0002 §3).
    assert isinstance(tool_msg["content"], str)
    assert json.loads(tool_msg["content"]) == result


# --------------------------------------------------------------------------- #
# 4. assistant text + record assembly                                         #
# --------------------------------------------------------------------------- #

def test_assistant_text_turn():
    turn = assistant_text_to_openai("nginx.service is active and running.")
    assert turn == {"role": "assistant", "content": "nginx.service is active and running."}
    assert "tool_calls" not in turn  # English turn: content non-null, no tool_calls


def test_assemble_record_shape():
    tools = coreimports.live_tool_list()
    tool_use = anthropic_tool_use_to_openai_tool_calls(_known_blocks_objectshape())
    tool_msg = anthropic_tool_result_to_openai_tool_msg(
        KNOWN_ID, {"exit_code": 0, "stdout": "", "stderr": "", "summary": "ok"}
    )
    answer = assistant_text_to_openai("nginx.service is active and running.")

    meta = {"tier": "radagon", "scenario_id": "services-status-0001",
            "tool": KNOWN_TOOL, "operation": KNOWN_OP, "permission_class": "read"}
    record = assemble_record(coreimports.HOUSE_SYSTEM_PROMPT,
                             tools,
                             [{"role": "user", "content": "is nginx running?"},
                              tool_use, tool_msg, answer],
                             meta)

    msgs = record["messages"]
    assert msgs[0]["role"] == "system"
    assert coreimports.HOUSE_SYSTEM_PROMPT in msgs[0]["content"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool", "assistant"]
    assert record["tools"] is tools
    assert record["meta"] == meta


# --------------------------------------------------------------------------- #
# 5. FakeBackend end-to-end round-trip (offline determinism)                  #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_fake_backend_roundtrips_through_live_router():
    class _Scn:
        id = "services-status-0007"
        tool = KNOWN_TOOL
        operation = KNOWN_OP

    backend = FakeBackend(scenario=_Scn())
    tools = coreimports.live_tool_list()

    # First call -> a tool_use block.
    first = await backend.complete([{"role": "user", "content": "is nginx running?"}], tools)
    assert first["stop_reason"] == "tool_use"
    turn = anthropic_tool_use_to_openai_tool_calls(first["content_blocks"])
    call = turn["tool_calls"][0]
    assert isinstance(call["function"]["arguments"], str)

    # The Fake's canned args must validate LIVE.
    spec = coreimports.registry.get(call["function"]["name"])
    op, _rest = coreimports.validate_arguments(spec, json.loads(call["function"]["arguments"]))
    assert op == KNOWN_OP

    # Follow-up call (tool result present) -> I2-clean English answer.
    tool_msg = anthropic_tool_result_to_openai_tool_msg(
        call["id"], {"exit_code": 0, "stdout": "", "stderr": "", "summary": "ok"}
    )
    second = await backend.complete(
        [{"role": "user", "content": "is nginx running?"}, turn, tool_msg], tools
    )
    assert second["stop_reason"] == "end_turn"
    text = second["content_blocks"][0].text
    coreimports.assert_no_ai_language(text, "fake answer")  # must not raise
