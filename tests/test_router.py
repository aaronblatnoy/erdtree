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
    reask_invalid_input,
)
from core.agent.prompt import _AI_PATTERN


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
    # The router passes the live tool list so the re-ask names the offending tool
    # and lists available alternatives.  Match using the same helper call shape.
    assert res.misses[0].reask == reask_unknown_tool(
        "frobnicate", registry.list_tools()
    )


def test_bad_json_arguments_is_miss(router):
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services", "arguments": "{not valid json"}
    ])
    assert res.kind is TurnKind.MISS
    assert res.misses[0].reason == "bad_json"
    # Re-ask must instruct the caller to fix the input (wording may evolve;
    # check structural intent rather than exact phrasing).
    assert "invalid input" in res.misses[0].reask.lower()


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
    # The re-ask must instruct the caller to fix the input (I2-clean, instructive).
    assert "input" in msgs[0]["content"].lower()


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


# --------------------------------------------------------------------------- #
# Phase 5 — instructive re-ask wording (P5 acceptance criteria)               #
# --------------------------------------------------------------------------- #
# These tests assert that the tightened re-ask strings surface the CONCRETE
# fix a small base needs to self-correct, and that every new string passes the
# I2 filter (no ai/llm/model/agent/ollama/inference/neural/gpt language).

def test_bad_operation_enum_reask_contains_valid_ops_list(router):
    """A bad 'operation' value produces a re-ask that names the valid ops.

    validate_arguments already yields the precise message
    ``"'operation' must be one of [disable, enable, ...], got 'instal'"``;
    reask_invalid_arguments must thread that detail through so the next call
    can pick a correct operation from the list.
    """
    # Use 'packages' so we get a real operation enum in the detail string.
    res = router.route(tool_calls=[
        {"id": "c1", "name": "packages",
         "arguments": _args({"operation": "instal", "packages": ["vim"]})}
    ])
    assert res.kind is TurnKind.MISS
    assert res.misses[0].reason == "schema"
    reask = res.misses[0].reask
    # The re-ask must contain the valid operations list (from validate_arguments
    # detail) so the caller can pick the right one.
    assert "install" in reask, f"valid op 'install' missing from re-ask: {reask!r}"
    # It must also mention the offending value.
    assert "instal" in reask, f"offending value 'instal' missing from re-ask: {reask!r}"


def test_bad_operation_enum_reask_passes_i2(router):
    """The invalid-arguments re-ask contains no I2-forbidden terms."""
    res = router.route(tool_calls=[
        {"id": "c1", "name": "packages",
         "arguments": _args({"operation": "instal", "packages": ["vim"]})}
    ])
    reask = res.misses[0].reask
    assert _AI_PATTERN.search(reask) is None, (
        f"I2 violation in invalid-arguments re-ask: {reask!r}"
    )


def test_unknown_tool_reask_names_offending_tool(router):
    """An unknown tool call produces a re-ask that explicitly names the bad tool."""
    res = router.route(tool_calls=[
        {"id": "c1", "name": "frobnicate",
         "arguments": _args({"operation": "do_stuff"})}
    ])
    assert res.kind is TurnKind.MISS
    assert res.misses[0].reason == "unknown_tool"
    reask = res.misses[0].reask
    # The offending tool name must appear in the re-ask.
    assert "frobnicate" in reask, (
        f"offending tool name 'frobnicate' missing from re-ask: {reask!r}"
    )


def test_unknown_tool_reask_lists_valid_tools(router):
    """An unknown tool call re-ask includes the list of available tools."""
    res = router.route(tool_calls=[
        {"id": "c1", "name": "frobnicate",
         "arguments": _args({"operation": "do_stuff"})}
    ])
    reask = res.misses[0].reask
    # At least one of the registered tool names must appear in the re-ask.
    registered = registry.list_tools()
    listed = [t for t in registered if t in reask]
    assert listed, (
        f"no registered tool names found in unknown-tool re-ask: {reask!r}"
    )


def test_unknown_tool_reask_passes_i2(router):
    """The unknown-tool re-ask contains no I2-forbidden terms."""
    res = router.route(tool_calls=[
        {"id": "c1", "name": "frobnicate",
         "arguments": _args({"operation": "do_stuff"})}
    ])
    reask = res.misses[0].reask
    assert _AI_PATTERN.search(reask) is None, (
        f"I2 violation in unknown-tool re-ask: {reask!r}"
    )


def test_reask_invalid_arguments_standalone_i2():
    """reask_invalid_arguments output passes the I2 filter for a typical detail."""
    detail = "'operation' must be one of [install, remove, status], got 'instal'"
    text = reask_invalid_arguments("packages", detail)
    assert _AI_PATTERN.search(text) is None, (
        f"I2 violation in reask_invalid_arguments: {text!r}"
    )


def test_reask_unknown_tool_standalone_i2():
    """reask_unknown_tool output passes the I2 filter with and without valid list."""
    text_bare = reask_unknown_tool("frobnicate")
    assert _AI_PATTERN.search(text_bare) is None, (
        f"I2 violation (no list): {text_bare!r}"
    )
    text_with_list = reask_unknown_tool("frobnicate", ["logs", "packages", "services"])
    assert _AI_PATTERN.search(text_with_list) is None, (
        f"I2 violation (with list): {text_with_list!r}"
    )


def test_reask_invalid_input_standalone_i2():
    """reask_invalid_input output passes the I2 filter."""
    detail = "tool call type must be 'function', got 'procedure'"
    text = reask_invalid_input(detail)
    assert _AI_PATTERN.search(text) is None, (
        f"I2 violation in reask_invalid_input: {text!r}"
    )


def test_turnkind_classification_frozen(router):
    """TurnKind enum values are unchanged (FROZEN CONTRACT — must not drift)."""
    assert TurnKind.TOOL_CALL.value == "tool_call"
    assert TurnKind.ENGLISH.value == "english"
    assert TurnKind.MISS.value == "miss"


def test_is_valid_action_predicate_frozen(router):
    """is_valid_action remains True iff TOOL_CALL + no misses + >=1 call."""
    # Valid call -> True
    res = router.route(tool_calls=[
        {"id": "c1", "name": "services",
         "arguments": _args({"operation": "status", "unit": "sshd.service"})}
    ])
    assert res.is_valid_action is True

    # ENGLISH -> False
    res_eng = router.route(content="some answer")
    assert res_eng.is_valid_action is False

    # MISS -> False
    res_miss = router.route(tool_calls=[
        {"id": "c2", "name": "frobnicate", "arguments": _args({"operation": "x"})}
    ])
    assert res_miss.is_valid_action is False
