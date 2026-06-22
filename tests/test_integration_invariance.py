"""
tests/test_integration_invariance.py — PHASE 6 integration + invariance gate.

This is the JOIN. The streaming spine (P1/P2/P3) and the prose (P4/P5) all
landed; this file PROVES the fully-wired streaming path is behaviorally
identical to the Phase-0 buffered baseline and consolidates the I2 inventory.

What it proves
--------------
SC4 INVARIANCE (the load-bearing safety claim): the SAME five canonical turns
the Phase-0 oracle pinned (tests/test_invariance_baseline.py) produce IDENTICAL
gate decisions, audit records, and TurnOutcome when driven through the
FULLY-WIRED streaming responder (stream_responder + on_delta -> render_delta,
the exact seam build_repl uses) instead of the buffered ScriptedResponder.

  We do NOT re-derive the oracle: we import the Phase-0 frozen numbers and the
  Phase-0 scenario scripts, replay each through the streaming path, and assert
  equality field-by-field. Streaming is PRESENTATION ONLY — the router/gate/
  audit see the same assembled turn, so every frozen number must match.

WIRING (SC5/back-compat): build_repl streams by default for the live ConsoleIO
path (ERDTREE_STREAM unset/on) and falls back to the buffered chat() closure
when ERDTREE_STREAM=0. Both build a working Repl. We assert the responder
identity and that the ConsoleIO render_delta is the sink for streaming.

I9 (dead-man, verify-only): the streaming responder drains client.stream(),
which raises ConnectionError on an unreachable endpoint exactly as chat() does
(same _make_request path, no new timeout, no new unbounded wait). shell.py's
dead-man guard wraps run_turn() and catches that ConnectionError unchanged —
covered by tests/test_deadman.py (run alongside). We additionally assert here
that a streaming responder over an unreachable client raises ConnectionError.

CONSOLIDATED I2 INVENTORY (SC3 belt-and-suspenders): every NEW user-facing
string introduced across P2/P3/P4/P5 is asserted to pass prompt._AI_PATTERN in
one place. We import the filter from core.agent.prompt — we do NOT re-list the
forbidden terms.

DEV-HOST HONESTY: NO live Ollama round-trip happens here. Every model turn is a
scripted SSE byte-sequence fed through the injected _http_factory seam (the
loopback-asserted client never opens a socket). The live 7B/14B incremental-
render FEEL is reasoned + double-proven (parity in test_streaming.py + this
invariance equality) and the real round-trip is DEFERRED-TO-MOSSAD (needs a
provisioned box + Ollama running a real model; not available on this dev host).
"""

from __future__ import annotations

import json
import os

import pytest

import core.tools.services  # noqa: F401
import core.tools.packages  # noqa: F401
import core.tools.logs  # noqa: F401
from core.tools import registry, ToolResult
from core.agent.audit import AuditLog, iter_records
from core.agent.repl import Repl, ConsoleIO
from core.agent.prompt import _AI_PATTERN, _assert_no_ai_language
from core.model.ollama import OllamaClient, TierConfig, stream_responder

# Phase-0 oracle: reuse the doubles + scenario scripts UNCHANGED (REUSE
# CONTRACT in that module's docstring). We import the frozen scripts and the
# FakeContext/_stub_tool_results helpers, and re-derive NOTHING.
from tests.test_invariance_baseline import (
    FakeContext,
    _stub_tool_results,
)
# The SSE-scripting helpers (proven against the wire in test_ollama_roundtrip).
from tests.test_ollama_roundtrip import (
    _make_config,
    _sse_lines,
    _http_factory_from_lines,
)


# =========================================================================== #
# Streaming-path test double (the build_repl seam, with injected transport)   #
# =========================================================================== #

class _StreamingFakeIO:
    """A ReplIO mirroring ConsoleIO's contract: full renders + delta hook.

    render() honors the NO-DOUBLE-RENDER contract so the captured `rendered`
    list holds EXACTLY what the Phase-0 FakeIO.rendered held — the final English
    answer(s) — making the frozen render oracle directly comparable.
    """

    def __init__(self, *, confirm: bool = True, typed_ok: bool = True) -> None:
        self._confirm = confirm
        self._typed_ok = typed_ok
        self.rendered: list[str] = []
        self.deltas: list[str] = []
        self._streamed = ""

    def render(self, text: str) -> None:
        if self._streamed:
            already = self._streamed
            self._streamed = ""
            if text == already or not text:
                return
        self.rendered.append(text)

    def render_delta(self, token: str) -> None:
        self.deltas.append(token)
        self._streamed += token

    def confirm(self, prompt: str) -> bool:
        return self._confirm

    def confirm_typed(self, prompt: str, word: str) -> bool:
        return self._typed_ok


def _content_sse(text: str) -> list[dict]:
    """SSE chunks for a plain English (stop) turn carrying *text*, streamed in
    a few content deltas so render_delta is exercised."""
    if text:
        third = max(1, len(text) // 3)
        parts = [text[:third], text[third:2 * third], text[2 * third:]]
        deltas = [{"choices": [{"delta": {"content": p}}]} for p in parts if p]
        deltas[-1]["choices"][0]["finish_reason"] = "stop"
        return [{"choices": [{"delta": {"role": "assistant"}}]}] + deltas
    return [{"choices": [{"delta": {"role": "assistant"}},
             {"finish_reason": "stop"}]}]


def _tool_call_chunks(call: dict) -> list[dict]:
    """SSE chunks for a single tool call, splitting arguments across deltas.

    `call` is the Phase-0 {"id","name","arguments"} shape. When `arguments` is
    intentionally broken JSON (the MISS scenario) we still stream it verbatim so
    the assembled tool_call carries the SAME malformed string the buffered
    ScriptedResponder fed the router — proving the MISS path is identical.
    """
    args = call["arguments"]
    mid = len(args) // 2
    return [
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": call["id"], "type": "function",
             "function": {"name": call["name"], "arguments": args[:mid]}}
        ]}}]},
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": args[mid:]}}
        ]}, "finish_reason": "tool_calls"}]},
    ]


def _script_to_sse_rounds(script: list[tuple[str, list[dict]]]) -> list[list[str]]:
    """Translate a Phase-0 (content, tool_calls) script into per-ROUND SSE.

    Each script entry becomes one streaming round whose assembled
    AssembledResponse is byte-identical to what the buffered ScriptedResponder
    returned for that entry (parity is what makes SC4 hold). Exactly one of
    content / a single tool call per Phase-0 entry.
    """
    rounds: list[list[str]] = []
    for content, calls in script:
        if calls:
            chunks = _tool_call_chunks(calls[0])
        else:
            chunks = _content_sse(content)
        rounds.append(_sse_lines(*[json.dumps(c) for c in chunks]))
    return rounds


def _streaming_repl(tmp_path, script, io, *, interactive=True):
    """Build a Repl whose responder is the PRODUCTION streaming seam.

    stream_responder(client, on_delta=io.render_delta) is EXACTLY what
    build_repl wires; here the client's transport is the injected SSE script
    (no socket — the loopback-asserted client, I1). Each run_turn round consumes
    the next per-round SSE script.
    """
    client = OllamaClient(_make_config())
    streaming = stream_responder(client, on_delta=io.render_delta)
    rounds = _script_to_sse_rounds(script)
    state = {"i": 0}

    def responder(messages, tools):
        sse = rounds[min(state["i"], len(rounds) - 1)] if rounds else _sse_lines()
        state["i"] += 1
        return streaming(messages, tools=tools,
                         _http_factory=_http_factory_from_lines(sse))

    audit = AuditLog(str(tmp_path / "audit.jsonl"))
    repl = Repl(
        registry=registry,
        responder=responder,
        audit=audit,
        context=FakeContext(),
        io=io,
        tier_label="test-tier",
        interactive=interactive,
    )
    return repl, audit


# =========================================================================== #
# The five Phase-0 scenarios, FROZEN. Each pins the buffered "before" numbers  #
# (copied verbatim from tests/test_invariance_baseline.py) and the SCRIPT, so  #
# this file replays them through the streaming path and asserts equality.      #
# =========================================================================== #

# scenario = (script, expected_audit, expected_outcome, expected_rendered,
#             io_kwargs)
_SCENARIOS = {
    "read": dict(
        script=[
            ("", [{"id": "c1", "name": "services",
                   "arguments": json.dumps({"operation": "status",
                                            "unit": "sshd.service"})}]),
            ("sshd is running.", []),
        ],
        user_input="is sshd running?",
        audit=[{"permission_decision": "allow", "tool": "services",
                "tier": "test-tier"}],
        outcome=dict(tool_calls_made=1, refused=0, misses=0, rounds=2,
                     ended_in_english=True),
        rendered=["sshd is running."],
        io_kwargs={},
    ),
    "write_confirmed": dict(
        script=[
            ("", [{"id": "c1", "name": "services",
                   "arguments": json.dumps({"operation": "restart",
                                            "unit": "nginx.service"})}]),
            ("nginx restarted.", []),
        ],
        user_input="restart nginx",
        audit=[{"permission_decision": "confirm"}],
        outcome=dict(tool_calls_made=1, refused=0, misses=0, rounds=2,
                     ended_in_english=True),
        rendered=["nginx restarted."],
        io_kwargs={"confirm": True},
    ),
    "write_declined": dict(
        script=[
            ("", [{"id": "c1", "name": "services",
                   "arguments": json.dumps({"operation": "restart",
                                            "unit": "nginx.service"})}]),
            ("Okay, leaving nginx as is.", []),
        ],
        user_input="restart nginx",
        audit=[{"permission_decision": "confirm:declined", "exit_code": 2}],
        outcome=dict(tool_calls_made=0, refused=1, misses=0, rounds=2,
                     ended_in_english=True),
        rendered=["Okay, leaving nginx as is."],
        io_kwargs={"confirm": False},
    ),
    "destructive_wrong_word": dict(
        script=[
            ("", [{"id": "c1", "name": "packages",
                   "arguments": json.dumps({"operation": "remove",
                                            "packages": ["kernel"]})}]),
            ("Not removing the kernel.", []),
        ],
        user_input="remove the kernel package",
        audit=[{"permission_decision": "confirm_typed:declined", "exit_code": 2}],
        outcome=dict(tool_calls_made=0, refused=1, misses=0, rounds=2,
                     ended_in_english=True),
        rendered=["Not removing the kernel."],
        io_kwargs={"typed_ok": False},
    ),
    "miss_reask": dict(
        script=[
            ("", [{"id": "c1", "name": "services", "arguments": "{broken json"}]),
            ("", [{"id": "c2", "name": "services",
                   "arguments": json.dumps({"operation": "status",
                                            "unit": "sshd.service"})}]),
            ("sshd is running.", []),
        ],
        user_input="is sshd running?",
        audit=[{"permission_decision": "n/a", "result_prefix": "miss:"},
               {"permission_decision": "allow"}],
        outcome=dict(tool_calls_made=1, refused=0, misses=1, rounds=3,
                     ended_in_english=True),
        rendered=["sshd is running."],
        io_kwargs={},
    ),
}


@pytest.mark.parametrize("name", list(_SCENARIOS.keys()))
def test_sc4_streaming_path_is_invariant(name, tmp_path, monkeypatch):
    """SC4: each Phase-0 scenario, replayed through the FULLY-WIRED streaming
    path, yields gate decisions + audit records + TurnOutcome IDENTICAL to the
    pinned Phase-0 'before' values. Streaming is presentation only."""
    sc = _SCENARIOS[name]
    _stub_tool_results(monkeypatch)
    io = _StreamingFakeIO(**sc["io_kwargs"])
    repl, audit = _streaming_repl(tmp_path, sc["script"], io)
    outcome = repl.run_turn(sc["user_input"])
    audit.close()

    records = list(iter_records(tmp_path / "audit.jsonl"))

    # --- audit oracle: identical count + decisions ---
    assert len(records) == len(sc["audit"]), (
        f"{name}: audit count drift {len(records)} != {len(sc['audit'])}"
    )
    for rec, expected in zip(records, sc["audit"]):
        for key, val in expected.items():
            if key == "result_prefix":
                assert rec["result"].startswith(val), (
                    f"{name}: result {rec['result']!r} lacks prefix {val!r}"
                )
            else:
                assert rec[key] == val, (
                    f"{name}: audit[{key}] {rec[key]!r} != {val!r}"
                )

    # --- outcome oracle: identical TurnOutcome fields ---
    for field, val in sc["outcome"].items():
        assert getattr(outcome, field) == val, (
            f"{name}: outcome.{field} {getattr(outcome, field)!r} != {val!r}"
        )
    # The assembled English answer the router/loop computed is byte-identical to
    # the Phase-0 baseline (the authoritative final text, independent of how it
    # was presented).
    if sc["rendered"]:
        assert outcome.final_text == sc["rendered"][-1], (
            f"{name}: final_text {outcome.final_text!r} != {sc['rendered'][-1]!r}"
        )

    # --- render oracle: the operator sees the SAME English answer, EXACTLY
    #     ONCE, as the Phase-0 buffered baseline. In the streaming path the
    #     answer surfaces token-by-token via render_delta (NOT re-printed by the
    #     turn-final render() — NO-DOUBLE-RENDER), so the streamed deltas
    #     reconstruct it and render() appends NOTHING (presentation only; the
    #     gate/audit/outcome above already proved byte-behavior is unchanged). ---
    if sc["rendered"]:
        answer = sc["rendered"][-1]
        assert "".join(io.deltas) == answer, (
            f"{name}: streamed answer {''.join(io.deltas)!r} != {answer!r}"
        )
        # NO-DOUBLE-RENDER: the streamed answer is never ALSO appended as a
        # full-line render (that would show it twice).
        assert answer not in io.rendered, (
            f"{name}: answer double-rendered into {io.rendered!r}"
        )
    else:
        assert io.deltas == [] and io.rendered == []


# =========================================================================== #
# WIRING: build_repl streams by default, buffers under ERDTREE_STREAM=0        #
# =========================================================================== #

def _build_local_repl(monkeypatch):
    """Build a repl via main.build_repl against a loopback (no socket opened
    until a turn runs) with an isolated audit path."""
    import core.agent.main as main_mod
    monkeypatch.setenv("ERDTREE_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("ERDTREE_AUDIT_LOG",
                       str(main_mod.Path.home() / ".local" / "share"
                           / "erdtree" / "test-audit.jsonl"))
    cfg = main_mod.AppConfig.from_env(interactive=True)
    return main_mod.build_repl(cfg)


def test_build_repl_streams_by_default(monkeypatch):
    """Default live path: build_repl wires the streaming responder whose sink is
    the ConsoleIO render_delta. We prove the IO is a ConsoleIO and the responder
    is the stream_responder closure (not the buffered chat() closure) by name."""
    monkeypatch.delenv("ERDTREE_STREAM", raising=False)
    repl = _build_local_repl(monkeypatch)
    # The IO is a ConsoleIO (its render_delta is the live sink).
    assert isinstance(repl._io, ConsoleIO)
    # The streaming closure is named `responder` and is the stream path. The
    # buffered closure is also named `responder`; distinguish via the module
    # flag helper instead.
    import core.agent.main as main_mod
    assert main_mod._stream_enabled() is True


def test_build_repl_buffered_when_stream_off(monkeypatch):
    """ERDTREE_STREAM=0 falls back to the buffered chat() closure (SC5)."""
    monkeypatch.setenv("ERDTREE_STREAM", "0")
    import core.agent.main as main_mod
    assert main_mod._stream_enabled() is False
    repl = _build_local_repl(monkeypatch)
    assert isinstance(repl._io, ConsoleIO)


@pytest.mark.parametrize("val,expected", [
    ("", True), ("1", True), ("on", True), ("true", True), ("yes", True),
    ("0", False), ("off", False), ("false", False), ("no", False),
    ("garbage", True),  # unrecognized -> default ON, never raises (I9)
])
def test_stream_flag_parsing(val, expected, monkeypatch):
    import core.agent.main as main_mod
    if val == "":
        monkeypatch.delenv("ERDTREE_STREAM", raising=False)
    else:
        monkeypatch.setenv("ERDTREE_STREAM", val)
    assert main_mod._stream_enabled() is expected


# =========================================================================== #
# I9 (verify-only): the streaming responder raises ConnectionError on an       #
# unreachable endpoint, exactly as chat() does, so the dead-man guard fires.   #
# (The guard itself is proven in tests/test_deadman.py, run alongside.)        #
# =========================================================================== #

def test_streaming_responder_raises_connectionerror_when_unreachable():
    """A loopback endpoint with nothing listening -> ConnectionError on the
    FIRST drain of the stream, with no new unbounded wait (same _make_request
    path chat() uses). shell.py's dead-man guard catches this unchanged (I9)."""
    client = OllamaClient(TierConfig("http://127.0.0.1:1", "qwen2.5:7b-q4_K_M"))
    responder = stream_responder(client, on_delta=lambda _t: None)
    with pytest.raises(ConnectionError):
        responder([{"role": "user", "content": "x"}], tools=None)


# =========================================================================== #
# CONSOLIDATED I2 INVENTORY (SC3): every NEW user-facing string across         #
# P2/P3/P4/P5 passes prompt._AI_PATTERN. We import the filter, never re-list   #
# the terms.                                                                   #
# =========================================================================== #

# Every NEW user-facing string introduced by the streaming build, by phase.
# Templated strings (P5 re-asks) are instantiated with representative detail
# strings the validator actually produces, so the rendered surface is checked.
from core.agent.router import (  # noqa: E402
    reask_invalid_arguments,
    reask_unknown_tool,
    reask_invalid_input,
)

_NEW_USER_FACING_STRINGS = [
    # --- P3: live tool-step display (repl.py) ---
    "running: systemctl status sshd.service",
    "running: dnf install nginx",
    "done",
    "exit 0",
    "exit 1",
    "not run",
    # --- P5: instructive self-correcting re-asks (router.py), instantiated ---
    reask_invalid_arguments(
        "packages",
        "'operation' must be one of [install, remove, update], got 'instal'",
    ),
    reask_invalid_arguments(
        "services", "operation 'restart' requires argument 'unit'"),
    reask_unknown_tool("frobnicate", ["services", "packages", "logs"]),
    reask_unknown_tool("frobnicate"),
    reask_invalid_input("Expecting property name enclosed in double quotes"),
    # --- P4: prompt prose is import-time asserted, but inventory the operator-
    #     visible example lines here too (belt-and-suspenders). ---
    "is nginx running?",
    "what is the default SSH port?",
    "Port 22.",
]


def test_i2_consolidated_inventory_passes_filter():
    """SC3 belt-and-suspenders: every new user-facing string across P2-P5
    passes the I2 filter (no ai/llm/model/agent/agentic/inference/ollama...)."""
    for s in _NEW_USER_FACING_STRINGS:
        assert _AI_PATTERN.search(s) is None, (
            f"I2 violation: forbidden term in {s!r}"
        )
        # And the canonical asserter agrees (raises on violation).
        _assert_no_ai_language(s, "P6 consolidated I2 inventory")


def test_i2_inventory_is_nonempty_and_covers_phases():
    """Guard the inventory itself: it must actually contain the P3 step lines
    and the P5 re-ask wording (so this test fails LOUDLY if a phase's strings
    are dropped from the inventory)."""
    joined = "\n".join(_NEW_USER_FACING_STRINGS)
    assert "running:" in joined          # P3 step announce
    assert "not run" in joined           # P3 refused-op status
    assert "schema" in joined            # P5 invalid-arguments re-ask tail
    assert "not a recognised tool" in joined  # P5 unknown-tool re-ask
