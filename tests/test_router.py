"""Tests for core/agent/router.py — the strict tool-call parser/validator.

Pure unit tests against the FROZEN contract (docs/decisions/0002 §2/§5). No
model, no network, no Linux. Green on any host.

Coverage:
  * Valid single call parses -> TurnKind.TOOL_CALL, is_valid_action True.
  * Valid parallel calls both parse.
  * English turn (no tool_calls) -> ENGLISH, not a miss.
  * Unknown tool name -> MISS (Unknown tool re-ask), never raises.
  * Unparseable JSON arguments -> MISS (invalid-arguments re-ask).
  * Schema-invalid arguments (missing required / unknown op / bad type /
    rogue key) -> MISS.
  * Raw OpenAI {function:{...}} shape accepted as well as assembled shape.
  * type != "function" -> MISS.
  * A turn with a mix of valid + invalid calls is a MISS for validity scoring.
  * reask_messages carry the verbatim 0002 §5 text and correlate by id.
  * Schemas advertised match the registry (operation enum + union args).
"""

from __future__ import annotations

import json

import pytest

# Register the core tools on the default registry.
import core.tools.services  # noqa: F401
import core.tools.packages  # noqa: F401
import core.tools.logs  # noqa: F401
from core.tools import registry
from core.agent.permissions import OpClass
from core.agent.router import (
    Router,
    TurnKind,
    reask_invalid_arguments,
    reask_unknown_tool,
)


@pytest.fixture
def router() -> Router:
    return Router(registry)


def _args(d: dict) -> str:
    return json.dumps(d)


# --------------------------------------------------------------------------- #
# Valid calls                                                                  #
# --------------------------------------------------------------------------- #

def test_valid_single_call(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services",
         "arguments": _args({"operation": "restart", "unit": "nginx.service"})}
    ])
    assert res.kind is TurnKind.TOOL_CALL
    assert res.is_valid_action is True
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.tool == "services"
    assert call.operation == "restart"
    assert call.args == {"unit": "nginx.service"}
    assert call.call_id == "c1"
    assert call.permission_class is OpClass.WRITE


def test_valid_read_call_is_classified_read(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services",
         "arguments": _args({"operation": "status", "unit": "sshd.service"})}
    ])
    assert res.is_valid_action
    assert res.calls[0].permission_class is OpClass.READ


def test_valid_parallel_calls(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services",
         "arguments": _args({"operation": "status", "unit": "sshd.service"})},
        {"id": "c2", "name": "services",
         "arguments": _args({"operation": "status", "unit": "nginx.service"})},
    ])
    assert res.kind is TurnKind.TOOL_CALL
    assert res.is_valid_action
    assert len(res.calls) == 2


def test_raw_openai_function_shape_accepted(router):
    res = router.route(tool_calls=[
        {"id": "c1", "type": "function", "function": {
            "name": "services",
            "arguments": _args({"operation": "status", "unit": "sshd.service"})}}
    ])
    assert res.is_valid_action
    assert res.calls[0].tool == "services"


# --------------------------------------------------------------------------- #
# English (not a miss)                                                          #
# --------------------------------------------------------------------------- #

def test_english_turn_is_not_a_miss(router):
    res = router.route(content="The noatime flag avoids access-time writes.")
    assert res.kind is TurnKind.ENGLISH
    assert res.is_valid_action is False
    assert res.misses == []
    assert res.content.startswith("The noatime")


def test_empty_turn_is_english(router):
    res = router.route(content="", tool_calls=[])
    assert res.kind is TurnKind.ENGLISH


# --------------------------------------------------------------------------- #
# Misses — never crash, always re-ask                                          #
# --------------------------------------------------------------------------- #

def test_unknown_tool_is_miss(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "frobnicate", "arguments": _args({"operation": "x"})}
    ])
    assert res.kind is TurnKind.MISS
    assert res.is_valid_action is False
    assert res.misses[0].reason == "unknown_tool"
    assert res.misses[0].reask == reask_unknown_tool("frobnicate")


def test_bad_json_arguments_is_miss(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services", "arguments": "{not valid json"}
    ])
    assert res.kind is TurnKind.MISS
    assert res.misses[0].reason == "bad_json"
    assert "invalid arguments" in res.misses[0].reask


def test_missing_required_arg_is_miss(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services", "arguments": _args({"operation": "restart"})}
    ])
    assert res.kind is TurnKind.MISS
    assert res.misses[0].reason == "schema"
    assert "unit" in res.misses[0].reask


def test_unknown_operation_is_miss(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services",
         "arguments": _args({"operation": "explode", "unit": "x"})}
    ])
    assert res.kind is TurnKind.MISS
    assert res.misses[0].reason == "schema"


def test_rogue_extra_key_is_miss(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services",
         "arguments": _args({"operation": "status", "unit": "x", "rogue": 1})}
    ])
    assert res.kind is TurnKind.MISS


def test_wrong_arg_type_is_miss(router):
    # 'unit' must be a string.
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services",
         "arguments": _args({"operation": "status", "unit": 5})}
    ])
    assert res.kind is TurnKind.MISS


def test_bad_type_field_is_miss(router):
    res = router.route(tool_calls=[
        {"id": "c1", "type": "not_function", "name": "services",
         "arguments": _args({"operation": "status", "unit": "x"})}
    ])
    assert res.kind is TurnKind.MISS
    assert res.misses[0].reason == "bad_type"


def test_router_never_raises_on_garbage(router):
    # Whatever we throw at it, it returns a RouterResult — never an exception.
    for garbage in (
        [{"id": "c", "name": None, "arguments": None}],
        [{"weird": "shape"}],
        [{"name": "services", "arguments": 12345}],
        [{}],
    ):
        res = router.route(tool_calls=garbage)
        assert res.kind in (TurnKind.MISS, TurnKind.ENGLISH, TurnKind.TOOL_CALL)
        assert not res.is_valid_action  # none of these are clean calls


# --------------------------------------------------------------------------- #
# Mixed valid + invalid = MISS for validity                                    #
# --------------------------------------------------------------------------- #

def test_mixed_valid_and_invalid_is_miss(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services",
         "arguments": _args({"operation": "status", "unit": "sshd.service"})},
        {"id": "c2", "name": "services", "arguments": "{broken"},
    ])
    # One good call parsed, but the turn is a MISS because not every call is valid.
    assert res.kind is TurnKind.MISS
    assert res.is_valid_action is False
    assert len(res.calls) == 1   # the good one is still dispatchable
    assert len(res.misses) == 1


# --------------------------------------------------------------------------- #
# Re-ask messages (0002 §3 shape, §5 wording)                                  #
# --------------------------------------------------------------------------- #

def test_reask_messages_shape_and_correlation(router):
    res = router.route(tool_calls=[
        {"id": "c9", "name": "services", "arguments": "{broken"}
    ])
    msgs = res.reask_messages
    assert len(msgs) == 1
    assert msgs[0]["role"] == "tool"
    assert msgs[0]["tool_call_id"] == "c9"
    assert "rewrite the input" in msgs[0]["content"]


# --------------------------------------------------------------------------- #
# Advertised schemas match the registry                                        #
# --------------------------------------------------------------------------- #

def test_advertised_schema_has_operation_enum(router):
    schemas = router.advertised_schemas(["services"])
    assert len(schemas) == 1
    params = schemas[0]["parameters"]
    assert params["additionalProperties"] is False
    assert "operation" in params["required"]
    op_enum = params["properties"]["operation"]["enum"]
    assert "restart" in op_enum and "status" in op_enum


def test_advertised_schema_skips_unknown_tool(router):
    schemas = router.advertised_schemas(["services", "does-not-exist"])
    names = [s["name"] for s in schemas]
    assert names == ["services"]


# --------------------------------------------------------------------------- #
# Tool result message (0002 §3)                                                #
# --------------------------------------------------------------------------- #

def test_tool_result_message_shape():
    from core.tools import ToolResult

    msg = Router.tool_result_message(
        "c1", ToolResult(exit_code=0, stdout="ok", stderr="", summary="done")
    )
    assert msg["role"] == "tool"
    assert msg["tool_call_id"] == "c1"
    payload = json.loads(msg["content"])
    assert payload["exit_code"] == 0
    assert payload["summary"] == "done"
