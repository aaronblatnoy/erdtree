"""
tests/test_streaming.py

Phase 1 validation: the ADDITIVE streaming responder adapter in
core/model/ollama.py (stream_responder / _StreamAccumulator).

The streaming responder drains OllamaClient.stream() and, for each content
delta, emits a token to an injected on_delta sink BEFORE returning an
AssembledResponse.  It is presentation-only: the AssembledResponse it returns
MUST be byte-identical to what chat() assembles from the same chunks (parity),
so the router/gate/audit see the same assembled turn (SC4).

Validation gates (plan §3 Phase 1):

  1.  on_delta is called >= 3 times, IN ORDER, for a 3-content-delta script.
  2.  PARITY: stream_responder(...) returns an AssembledResponse EQUAL to
      client.chat() over the SAME SSE script (tool-call path AND English path).
  3.  on_delta is wrapped: a raising sink degrades to no-stream and never
      aborts assembly (the AssembledResponse is still correct).
  4.  A None sink degrades to today's buffered behavior (no crash, parity).
  5.  I1: the responder opens no socket; it reuses the loopback-asserted
      stream() seam (injected _http_factory, mirroring test_ollama_roundtrip).
  6.  I2: every NEW user-facing string introduced here passes the AI-language
      filter imported from core.agent.prompt (no ai/llm/model/agent/...).

All tests run on any host with standard Python.  No Ollama, no network.

DEFERRED-TO-MOSSAD: live 7B/14B round-trip FEEL of incremental token render
  (needs a provisioned box + Ollama running a real model).
"""

from __future__ import annotations

import json
import os
import sys

import pytest

# Ensure the repo root is on sys.path so imports work from the tests/ dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.model.ollama import (
    AssembledResponse,
    OllamaClient,
    TierConfig,
    stream_responder,
)
from core.agent.prompt import _assert_no_ai_language

# Reuse the proven SSE-scripting helpers from the round-trip suite so the
# streaming path is fed EXACTLY the same wire bytes chat() is tested against.
from tests.test_ollama_roundtrip import (
    _english_sse,
    _http_factory_from_lines,
    _make_config,
    _sse_lines,
    _tool_call_sse,
    _TOOL_SCHEMAS,
)
from core.agent.prompt import build_tool_list


# =========================================================================== #
# Test double: a chunked streaming-responder fake                             #
# =========================================================================== #
#
# This mirrors the _http_factory injection used by test_ollama_roundtrip.py.
# It is a streaming responder built over a REAL OllamaClient (loopback-asserted
# at construction) whose stream() is fed a SCRIPT of SSE lines via the existing
# _http_factory seam — so the loop's incremental rendering is provable WITHOUT
# Ollama.  on_delta is captured into a list so emission order is assertable.

class _RecordingSink:
    """An on_delta sink that records every token in emission order."""

    def __init__(self) -> None:
        self.tokens: list[str] = []

    def __call__(self, token: str) -> None:
        self.tokens.append(token)


def _make_streaming_double(sse_lines, on_delta):
    """
    Return a zero-arg-callable that runs the streaming responder over the given
    SSE script, threading on_delta as the side-channel sink.  No socket opens:
    the OllamaClient is loopback-asserted and stream() is fed via _http_factory.
    """
    client = OllamaClient(_make_config())
    responder = stream_responder(client, on_delta=on_delta)

    def run(messages=None, tools=None):
        return responder(
            messages or [{"role": "user", "content": "check nginx"}],
            tools=tools,
            _http_factory=_http_factory_from_lines(sse_lines),
        )

    return client, run


# =========================================================================== #
# 1. on_delta called >= 3 times, in order                                     #
# =========================================================================== #

def _three_content_delta_then_tool_call_sse():
    """
    A script with THREE content deltas followed by a tool call (mixed turn).
    Exercises both the token side-channel and the shared accumulator.
    """
    full_args = '{"operation":"status","unit":"nginx.service"}'
    mid = len(full_args) // 2
    chunks = [
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "one "}}]},
        {"choices": [{"delta": {"content": "two "}}]},
        {"choices": [{"delta": {"content": "three"}}]},
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "call_mix", "type": "function",
             "function": {"name": "services", "arguments": full_args[:mid]}}
        ]}}]},
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": full_args[mid:]}}
        ]}, "finish_reason": "tool_calls"}]},
    ]
    return _sse_lines(*[json.dumps(c) for c in chunks])


class TestOnDeltaEmission:
    def test_on_delta_called_at_least_three_times_in_order(self):
        sse = _three_content_delta_then_tool_call_sse()
        sink = _RecordingSink()
        _client, run = _make_streaming_double(sse, sink)
        run()
        assert len(sink.tokens) >= 3
        assert sink.tokens[:3] == ["one ", "two ", "three"]

    def test_pure_english_emits_each_content_delta(self):
        chunks = [
            {"choices": [{"delta": {"content": "nginx"}}]},
            {"choices": [{"delta": {"content": ".service "}}]},
            {"choices": [{"delta": {"content": "active"},
                          "finish_reason": "stop"}]},
        ]
        sse = _sse_lines(*[json.dumps(c) for c in chunks])
        sink = _RecordingSink()
        _client, run = _make_streaming_double(sse, sink)
        run()
        assert sink.tokens == ["nginx", ".service ", "active"]


# =========================================================================== #
# 2. PARITY: streaming AssembledResponse == chat() assembly                   #
# =========================================================================== #

class TestParityWithChat:
    """
    The streaming responder MUST return an AssembledResponse byte-identical to
    what chat() assembles from the SAME SSE script.  This is the load-bearing
    SC4 / transport-correctness gate: a fork would assemble a tool call
    differently in the two paths.
    """

    def _chat_assembled(self, sse_lines, tools=None):
        client = OllamaClient(_make_config())
        return client.chat(
            messages=[{"role": "user", "content": "check nginx"}],
            tools=tools,
            _http_factory=_http_factory_from_lines(sse_lines),
        )

    def test_parity_tool_call_path(self):
        sse = _tool_call_sse(
            call_id="call_abc123",
            tool_name="services",
            arguments='{"operation":"status","unit":"nginx.service"}',
        )
        tools = build_tool_list(_TOOL_SCHEMAS)
        sink = _RecordingSink()
        _client, run = _make_streaming_double(sse, sink)
        streamed = run(tools=tools)
        buffered = self._chat_assembled(sse, tools=tools)
        assert isinstance(streamed, AssembledResponse)
        assert streamed == buffered

    def test_parity_english_path(self):
        sse = _english_sse("nginx.service is active.")
        sink = _RecordingSink()
        _client, run = _make_streaming_double(sse, sink)
        streamed = run()
        buffered = self._chat_assembled(sse)
        assert streamed == buffered
        # And the side-channel reconstructs the same content.
        assert "".join(sink.tokens) == buffered.content

    def test_parity_mixed_content_and_tool_call(self):
        sse = _three_content_delta_then_tool_call_sse()
        sink = _RecordingSink()
        _client, run = _make_streaming_double(sse, sink)
        streamed = run()
        buffered = self._chat_assembled(sse)
        assert streamed == buffered
        assert streamed.tool_calls[0]["arguments"] == (
            '{"operation":"status","unit":"nginx.service"}'
        )

    def test_parity_multiple_parallel_tool_calls(self):
        two_call_chunks = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_A", "type": "function",
                 "function": {"name": "services",
                              "arguments": '{"operation":"status","unit":"nginx.service"}'}},
                {"index": 1, "id": "call_B", "type": "function",
                 "function": {"name": "services",
                              "arguments": '{"operation":"status","unit":"sshd.service"}'}},
            ]}, "finish_reason": "tool_calls"}]},
        ]
        sse = _sse_lines(*[json.dumps(c) for c in two_call_chunks])
        sink = _RecordingSink()
        _client, run = _make_streaming_double(sse, sink)
        streamed = run()
        buffered = OllamaClient(_make_config()).chat(
            messages=[],
            _http_factory=_http_factory_from_lines(sse),
        )
        assert streamed == buffered
        assert len(streamed.tool_calls) == 2


# =========================================================================== #
# 3. on_delta never raises into the loop (degrade to no-stream)               #
# =========================================================================== #

class TestSinkResilience:
    def test_raising_sink_does_not_abort_assembly(self):
        """A sink that raises must NOT corrupt or abort the AssembledResponse."""
        def boom(_token):
            raise RuntimeError("render fault")

        sse = _english_sse("nginx.service is active.")
        _client, run = _make_streaming_double(sse, boom)
        streamed = run()
        buffered = OllamaClient(_make_config()).chat(
            messages=[],
            _http_factory=_http_factory_from_lines(sse),
        )
        # Assembly still completes and is byte-identical to buffered.
        assert streamed == buffered

    def test_none_sink_degrades_to_buffered(self):
        """Absence of a sink degrades to today's buffered behavior (parity)."""
        sse = _tool_call_sse()
        client = OllamaClient(_make_config())
        responder = stream_responder(client, on_delta=None)
        streamed = responder(
            [{"role": "user", "content": "x"}],
            _http_factory=_http_factory_from_lines(sse),
        )
        buffered = OllamaClient(_make_config()).chat(
            messages=[{"role": "user", "content": "x"}],
            _http_factory=_http_factory_from_lines(sse),
        )
        assert streamed == buffered


# =========================================================================== #
# 4. I1: no new socket / no new host — reuses the loopback-asserted client     #
# =========================================================================== #

class TestI1NoNewSocket:
    def test_responder_does_not_open_a_socket_under_injection(self):
        """
        With _http_factory injected, the responder must drain that injected
        stream and NEVER touch urllib / a real socket.  We assert the factory
        is the only transport invoked.
        """
        calls = {"n": 0}

        def counting_factory(endpoint, body):
            calls["n"] += 1
            # The endpoint must be the loopback endpoint the client built.
            assert "localhost" in endpoint
            return _english_sse("ok")

        client = OllamaClient(_make_config())
        sink = _RecordingSink()
        responder = stream_responder(client, on_delta=sink)
        responder(
            [{"role": "user", "content": "x"}],
            _http_factory=counting_factory,
        )
        assert calls["n"] == 1


# =========================================================================== #
# 5. I2: new user-facing strings pass the AI-language filter                   #
# =========================================================================== #

class TestI2NoAiLanguage:
    def test_new_strings_pass_filter(self):
        # No NEW user-facing strings are introduced by the responder itself
        # (it only forwards model content tokens).  This guard documents that
        # any future progress/step wording added here must pass the filter.
        for s in ["running:", "done", "exit 0", "not run"]:
            _assert_no_ai_language(s, "phase-1 streaming string")


# =========================================================================== #
# PHASE 2: ReplIO incremental hook + stream drain (the loop-level wiring)      #
# =========================================================================== #
#
# Phase 1 proved the responder emits deltas and assembles with parity.  Phase 2
# wires that responder's on_delta to a ReplIO.render_delta THROUGH a real Repl
# and proves:
#   SC1  delta count/order at the IO == the content-delta sequence, in order.
#   NO-DOUBLE-RENDER  the assembled English answer appears EXACTLY once (the
#        streamed tokens), never re-printed by the turn-final render().
#   DEGRADE  a render_delta that raises does NOT kill the turn: it still
#        completes, ends in English, and AUDITS (SC4 byte-behavior intact).
#
# run_turn stays UNAWARE of streaming: the responder OWNS the sink (the seam).
# A buffered responder produces no deltas, so the SAME loop renders the full
# answer once (back-compat — proven against the buffered double below).

import core.tools.services  # noqa: E402,F401
from core.tools import registry as _registry, ToolResult  # noqa: E402
from core.agent.audit import AuditLog, iter_records  # noqa: E402
from core.agent.repl import Repl, ConsoleIO  # noqa: E402


class _StreamingFakeIO:
    """A ReplIO that captures both full renders and incremental deltas.

    Mirrors today's render() contract (full English line capture) AND the new
    optional render_delta() hook, so SC1 (delta order) and NO-DOUBLE-RENDER
    (render() must not re-print streamed content) are both assertable.
    """

    def __init__(self, *, delta_raises: bool = False) -> None:
        self.rendered: list[str] = []
        self.deltas: list[str] = []
        self._streamed = ""
        self._delta_raises = delta_raises

    def render(self, text: str) -> None:
        # Mirror ConsoleIO's NO-DOUBLE-RENDER contract: if this exact text was
        # already streamed token-by-token, do NOT capture it as a full render.
        if self._streamed:
            already = self._streamed
            self._streamed = ""
            if text == already or not text:
                return
        self.rendered.append(text)

    def render_delta(self, token: str) -> None:
        self.deltas.append(token)
        self._streamed += token
        if self._delta_raises:
            raise RuntimeError("render fault")

    def confirm(self, prompt: str) -> bool:
        return False

    def confirm_typed(self, prompt: str, word: str) -> bool:
        return False


class _FakeContext:
    def snapshot_text(self, *, force: bool = False) -> str:
        return "Host: testbox"

    def invalidate(self) -> None:
        pass


def _streaming_repl(tmp_path, sse_lines, io):
    """Build a Repl whose responder is the Phase-1 stream_responder with its
    on_delta wired to *io*.render_delta — the production seam, exercised with an
    injected SSE script instead of a live socket (I1: loopback-asserted client).
    """
    client = OllamaClient(_make_config())
    streaming = stream_responder(client, on_delta=io.render_delta)
    factory = _http_factory_from_lines(sse_lines)

    # The Repl calls responder(messages, tools); bind the injected transport
    # here exactly as build_repl will bind client.stream's real transport.
    def responder(messages, tools):
        return streaming(messages, tools=tools, _http_factory=factory)

    audit = AuditLog(str(tmp_path / "audit.jsonl"))
    repl = Repl(
        registry=_registry,
        responder=responder,
        audit=audit,
        context=_FakeContext(),
        io=io,
        tier_label="test-tier",
        interactive=True,
    )
    return repl, audit


class TestPhase2ReplStreaming:
    def test_sc1_rendered_deltas_count_and_order(self, tmp_path):
        """SC1: deltas at the IO == the content deltas, in order."""
        chunks = [
            {"choices": [{"delta": {"content": "nginx"}}]},
            {"choices": [{"delta": {"content": ".service "}}]},
            {"choices": [{"delta": {"content": "is active"},
                          "finish_reason": "stop"}]},
        ]
        sse = _sse_lines(*[json.dumps(c) for c in chunks])
        io = _StreamingFakeIO()
        repl, _audit = _streaming_repl(tmp_path, sse, io)
        outcome = repl.run_turn("is nginx up")
        # Exactly the three content deltas, in order.
        assert io.deltas == ["nginx", ".service ", "is active"]
        assert outcome.ended_in_english is True
        assert outcome.final_text == "nginx.service is active"

    def test_no_double_render_english_appears_once(self, tmp_path):
        """The English answer is the streamed tokens; render() must NOT
        re-emit it.  The reconstructed stream == the assembled final_text, and
        the buffered full-line render() carries no DUPLICATE of that text."""
        sse = _english_sse("nginx.service is active.")
        io = _StreamingFakeIO()
        repl, _audit = _streaming_repl(tmp_path, sse, io)
        outcome = repl.run_turn("is nginx up")
        streamed = "".join(io.deltas)
        assert streamed == outcome.final_text
        # NO-DOUBLE-RENDER: the answer text is never additionally printed as a
        # full line on top of the streamed tokens.
        assert outcome.final_text not in io.rendered

    def test_no_double_render_console_io_streams_once(self, tmp_path, capsys):
        """End-to-end against the REAL ConsoleIO: stdout contains the answer
        EXACTLY once (streamed), with a single trailing newline — not twice."""
        sse = _english_sse("nginx.service is active.")
        io = ConsoleIO(interactive=True)
        # Route the live render_delta sink into ConsoleIO.
        repl, _audit = _streaming_repl(tmp_path, sse, io)
        repl.run_turn("is nginx up")
        out = capsys.readouterr().out
        assert out.count("nginx.service is active.") == 1
        # The streamed line is closed by exactly one newline (render() no-op'd
        # the re-print and emitted only the newline).
        assert out == "nginx.service is active.\n"

    def test_buffered_console_io_prints_full_answer(self, tmp_path, capsys):
        """BACK-COMPAT: with no deltas streamed (buffered path), ConsoleIO's
        render() prints the full English answer exactly as today."""
        io = ConsoleIO(interactive=True)
        io.render("nginx.service is active.")
        out = capsys.readouterr().out
        assert out == "nginx.service is active.\n"

    def test_degrade_raising_render_delta_completes_and_audits(self, tmp_path):
        """A render_delta that RAISES must not kill the turn: it still ends in
        English and the MISS/tool audit spine is untouched (SC4)."""
        # A turn that dispatches one read then answers in English, so there is
        # an audit record to prove the spine survived the render fault.
        full_args = '{"operation":"status","unit":"nginx.service"}'
        tool_chunks = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_x", "type": "function",
                 "function": {"name": "services", "arguments": full_args}}
            ]}, "finish_reason": "tool_calls"}]},
        ]
        english_chunks = [
            {"choices": [{"delta": {"content": "nginx is "}}]},
            {"choices": [{"delta": {"content": "active"},
                          "finish_reason": "stop"}]},
        ]
        tool_sse = _sse_lines(*[json.dumps(c) for c in tool_chunks])
        english_sse = _sse_lines(*[json.dumps(c) for c in english_chunks])

        # Two-round script: round 1 = tool call, round 2 = English answer.
        scripts = [tool_sse, english_sse]
        client = OllamaClient(_make_config())
        io = _StreamingFakeIO(delta_raises=True)
        streaming = stream_responder(client, on_delta=io.render_delta)

        state = {"i": 0}

        def responder(messages, tools):
            sse = scripts[min(state["i"], len(scripts) - 1)]
            state["i"] += 1
            return streaming(messages, tools=tools,
                             _http_factory=_http_factory_from_lines(sse))

        # Stub dispatch so the read "runs" without shelling out.
        orig = _registry.dispatch
        _registry.dispatch = lambda tool, op, args: ToolResult(
            exit_code=0, stdout="ok", stderr="", summary=f"{tool} {op} ok")
        try:
            audit = AuditLog(str(tmp_path / "audit.jsonl"))
            repl = Repl(
                registry=_registry, responder=responder, audit=audit,
                context=_FakeContext(), io=io, tier_label="test-tier",
                interactive=True,
            )
            outcome = repl.run_turn("is nginx up")
        finally:
            _registry.dispatch = orig

        # The raising sink did NOT abort the turn.
        assert outcome.ended_in_english is True
        assert outcome.final_text == "nginx is active"
        # SC4: the dispatched read was still audited (spine intact).
        recs = list(iter_records(str(tmp_path / "audit.jsonl")))
        assert len(recs) >= 1
        assert outcome.audit_records >= 1
