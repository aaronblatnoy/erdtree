"""Tests for core/agent/pipeline/strategy.py — NativeToolCallStrategy.

Verifies that NativeToolCallStrategy.propose() produces the SAME ParsedCall
list that calling Router.route() directly produces, and that StrategyResult
fields match the raw model response.

Coverage:
  * TOOL_CALL turn: calls non-empty, misses empty, english_content empty.
  * ENGLISH turn: english_content non-empty, calls empty, misses empty.
  * MISS turn: misses non-empty, reask_messages populated, source == "native".
  * raw_content and raw_calls match the scripted model response exactly.
  * source is always "native".
"""

from __future__ import annotations

import json

import core.tools.services  # noqa: F401
import core.tools.packages  # noqa: F401
import core.tools.logs  # noqa: F401
from core.tools import registry
from core.agent.router import Router
from core.agent.pipeline import NativeToolCallStrategy, StrategyResult


# --------------------------------------------------------------------------- #
# Test doubles                                                                  #
# --------------------------------------------------------------------------- #

class _FakeResponse:
    """Minimal AssembledResponse-like object for tests."""

    def __init__(self, content: str, tool_calls: list[dict]) -> None:
        self.content = content
        self.tool_calls = tool_calls


def _scripted_responder(content: str, tool_calls: list[dict]):
    """Return a responder that always returns the given (content, tool_calls)."""
    resp = _FakeResponse(content, tool_calls)

    def _responder(messages, tools):
        return resp

    return _responder


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _make_router() -> Router:
    return Router(registry)


def _make_strategy() -> NativeToolCallStrategy:
    return NativeToolCallStrategy(_make_router())


# --------------------------------------------------------------------------- #
# TOOL_CALL turn                                                                #
# --------------------------------------------------------------------------- #

def test_tool_call_turn_matches_router_directly():
    """propose() yields the same ParsedCalls as Router.route() called directly."""
    raw_calls = [
        {
            "id": "c1",
            "name": "services",
            "arguments": json.dumps({"operation": "status", "unit": "sshd.service"}),
        }
    ]
    content = ""
    router = _make_router()
    strategy = NativeToolCallStrategy(router)

    # Direct router path (reference).
    direct_verdict = router.route(content=content, tool_calls=raw_calls)

    # Strategy path.
    result: StrategyResult = strategy.propose(
        user_input="is sshd running?",
        snapshot_text="Host: testbox",
        messages=[],
        tools=[],
        responder=_scripted_responder(content, raw_calls),
        router=router,
    )

    assert result.source == "native"
    assert result.english_content == ""
    assert result.misses == []
    assert len(result.calls) == len(direct_verdict.calls) == 1
    assert result.calls[0].tool == direct_verdict.calls[0].tool
    assert result.calls[0].operation == direct_verdict.calls[0].operation
    assert result.calls[0].args == direct_verdict.calls[0].args
    assert result.calls[0].call_id == direct_verdict.calls[0].call_id
    assert result.reask_messages == []


def test_raw_fields_match_model_response():
    """raw_content and raw_calls reflect exactly what the scripted responder returned."""
    raw_calls = [
        {
            "id": "c2",
            "name": "packages",
            "arguments": json.dumps({"operation": "list"}),
        }
    ]
    content = ""
    router = _make_router()
    strategy = NativeToolCallStrategy(router)

    result = strategy.propose(
        user_input="list packages",
        snapshot_text="",
        messages=[],
        tools=[],
        responder=_scripted_responder(content, raw_calls),
        router=router,
    )

    assert result.raw_content == content
    assert result.raw_calls == raw_calls


# --------------------------------------------------------------------------- #
# ENGLISH turn                                                                  #
# --------------------------------------------------------------------------- #

def test_english_turn_populates_english_content():
    """An English-only response -> english_content non-empty, calls empty."""
    router = _make_router()
    strategy = NativeToolCallStrategy(router)

    result = strategy.propose(
        user_input="hello",
        snapshot_text="",
        messages=[],
        tools=[],
        responder=_scripted_responder("sshd is running.", []),
        router=router,
    )

    assert result.english_content == "sshd is running."
    assert result.calls == []
    assert result.misses == []
    assert result.reask_messages == []
    assert result.source == "native"
    assert result.raw_content == "sshd is running."
    assert result.raw_calls == []


# --------------------------------------------------------------------------- #
# MISS turn                                                                     #
# --------------------------------------------------------------------------- #

def test_miss_turn_populates_misses_and_reask():
    """A malformed tool call -> misses non-empty, reask_messages populated."""
    # Deliberately malformed: unknown tool name.
    raw_calls = [
        {
            "id": "c3",
            "name": "nonexistent_tool_xyz",
            "arguments": json.dumps({"operation": "do_thing"}),
        }
    ]
    router = _make_router()
    strategy = NativeToolCallStrategy(router)

    result = strategy.propose(
        user_input="do something",
        snapshot_text="",
        messages=[],
        tools=[],
        responder=_scripted_responder("", raw_calls),
        router=router,
    )

    assert result.misses  # at least one miss
    assert result.reask_messages  # at least one re-ask message
    assert result.english_content == ""
    assert result.source == "native"
    # Each reask message must have role:"tool"
    for msg in result.reask_messages:
        assert msg["role"] == "tool"
        assert "content" in msg


def test_miss_turn_matches_router_reask_messages():
    """reask_messages from propose() == reask_messages from Router.route() directly."""
    raw_calls = [
        {
            "id": "c4",
            "name": "completely_unknown",
            "arguments": json.dumps({"operation": "foo"}),
        }
    ]
    router = _make_router()
    strategy = NativeToolCallStrategy(router)

    direct_verdict = router.route(content="", tool_calls=raw_calls)

    result = strategy.propose(
        user_input="do something else",
        snapshot_text="",
        messages=[],
        tools=[],
        responder=_scripted_responder("", raw_calls),
        router=router,
    )

    assert result.reask_messages == direct_verdict.reask_messages


# --------------------------------------------------------------------------- #
# source invariant                                                              #
# --------------------------------------------------------------------------- #

def test_source_is_always_native():
    """source == 'native' regardless of turn kind."""
    router = _make_router()
    strategy = NativeToolCallStrategy(router)

    for content, calls in [
        ("hello", []),  # ENGLISH
        ("", [{"id": "x", "name": "bad", "arguments": "{}"}]),  # MISS
    ]:
        result = strategy.propose(
            user_input="test",
            snapshot_text="",
            messages=[],
            tools=[],
            responder=_scripted_responder(content, calls),
            router=router,
        )
        assert result.source == "native"
