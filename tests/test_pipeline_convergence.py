"""
tests/test_pipeline_convergence.py — Phase 5 GATE-CONVERGENCE / no-bypass proof.

This is the load-bearing safety test for the whole decomposed-understanding
design (R1 — the #1 risk). It proves the single most important property:

    EVERY call produced by DecomposedStrategy reaches registry.dispatch ONLY via
    permissions.classify, with the SAME synthesized argv the native path uses.

and its destructive corollary:

    A destructive decomposed intent hits CONFIRM_TYPED / REFUSE IDENTICALLY to
    the native path — decomposition can never under-state blast radius or slip a
    write/destructive op past the single hardened gate.

How it proves this WITHOUT a live model
---------------------------------------
The DecomposedStrategy's intent step uses an injected responder/embedder and its
slot step resolves closed-world from the injected snapshot — both fully
dev-host testable. We drive a real Repl whose ``strategy`` is a DecomposedStrategy
and SPY on both seams the spine uses:

  * ``core.agent.repl.perm.classify`` — the SINGLE gate. Every command that
    reaches it is recorded (the real classifier still runs; we only observe).
  * ``registry.dispatch`` — the SINGLE executor. Every (tool, op, args) that
    reaches it is recorded (a benign fake stands in so no real command runs).

Then we assert:
  * dispatch NEVER happens without a preceding classify of the SAME argv
    (no-bypass);
  * that argv is byte-identical to synthesize_command() of the equivalent NATIVE
    ParsedCall (convergence — one renderer, one gate);
  * a destructive decomposed op gets the SAME Gate the native path would
    (CONFIRM_TYPED interactive / REFUSE non-interactive).

No network, no live Ollama, no real Linux side effects.
"""

from __future__ import annotations

import pytest

# Register the tools the cases exercise (self-register on import).
import core.tools.services  # noqa: F401
import core.tools.packages  # noqa: F401
import core.tools.logs  # noqa: F401
import core.tools.disk  # noqa: F401
from core.tools import registry, ToolResult

from core.agent import permissions as perm
from core.agent.permissions import ExecContext, Gate, OpClass
from core.agent.repl import Repl, synthesize_command
from core.agent.router import ParsedCall, Router
from core.agent.pipeline import DecomposedStrategy, FastThenDecomposeStrategy
from core.agent.pipeline.strategy import NativeToolCallStrategy, StrategyResult
from core.agent.pipeline import intent as intent_mod


# --------------------------------------------------------------------------- #
# Test doubles                                                                  #
# --------------------------------------------------------------------------- #

class _FakeResponse:
    def __init__(self, content: str = "", tool_calls=None) -> None:
        self.content = content
        self.tool_calls = list(tool_calls or [])


def _intent_responder(pick: str):
    """A responder whose content is a fixed 'tool.operation' the intent model
    backend parses. Slot workers are never reached in these cases (slots resolve
    deterministically from the snapshot), so this only drives intent."""

    def _respond(messages, tools):
        return _FakeResponse(content=pick, tool_calls=[])

    return _respond


class FakeContext:
    def __init__(self, text: str) -> None:
        self.text = text
        self.invalidations = 0

    def snapshot_text(self, *, force: bool = False) -> str:
        return self.text

    def invalidate(self) -> None:
        self.invalidations += 1


class FakeIO:
    """Scripted IO: confirm/typed answers pre-set; renders captured."""

    def __init__(self, *, confirm: bool = True, typed_ok: bool = True) -> None:
        self._confirm = confirm
        self._typed_ok = typed_ok
        self.rendered: list[str] = []

    def render(self, text: str) -> None:
        self.rendered.append(text)

    def confirm(self, prompt: str) -> bool:
        return self._confirm

    def confirm_typed(self, prompt: str, word: str) -> bool:
        return self._typed_ok


# --------------------------------------------------------------------------- #
# Spy installation                                                              #
# --------------------------------------------------------------------------- #

def _install_spies(monkeypatch):
    """Spy on the two spine seams; return (classify_calls, dispatch_calls).

    classify_calls: list of (command, Decision) — the real classifier runs.
    dispatch_calls: list of (tool, op, args) — a benign fake stands in so no
                    real command executes on the dev host.
    """
    classify_calls: list[tuple[str, object]] = []
    dispatch_calls: list[tuple[str, str, dict]] = []

    real_classify = perm.classify

    def spy_classify(command, context=None):
        decision = real_classify(command, context)
        classify_calls.append((command, decision))
        return decision

    def spy_dispatch(tool, operation, args):
        dispatch_calls.append((tool, operation, dict(args)))
        return ToolResult(exit_code=0, stdout="ok", stderr="", summary="done")

    # The spine reaches the gate via repl's ``perm`` alias and the executor via
    # the shared registry.dispatch (router.dispatch delegates to it).
    monkeypatch.setattr("core.agent.repl.perm.classify", spy_classify)
    monkeypatch.setattr(registry, "dispatch", spy_dispatch)

    return classify_calls, dispatch_calls


def _make_repl(strategy, io, context, *, interactive=True, max_rounds=1) -> Repl:
    from core.agent.audit import AuditLog
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    return Repl(
        registry=registry,
        responder=lambda m, t: _FakeResponse(),  # unused by these strategies' paths
        audit=AuditLog(path),
        context=context,
        io=io,
        interactive=interactive,
        max_rounds=max_rounds,
        strategy=strategy,
    )


# --------------------------------------------------------------------------- #
# 1. Convergence + no-bypass: a decomposed WRITE reaches dispatch only via gate #
# --------------------------------------------------------------------------- #

def test_decomposed_write_reaches_dispatch_only_via_classify(monkeypatch):
    """A decomposed services.restart converges on the SAME argv + gate as native.

    Proves: (a) dispatch is preceded by a classify of the SAME command; (b) that
    command == synthesize_command() of the equivalent native ParsedCall.
    """
    classify_calls, dispatch_calls = _install_spies(monkeypatch)

    user_input = "restart the nginx service"
    snapshot = "distro=Rocky Linux 9; nginx.service: active(running)"
    strategy = DecomposedStrategy(registry, embedder=None)
    io = FakeIO(confirm=True)
    repl = _make_repl(strategy, io, FakeContext(snapshot), max_rounds=1)

    # Drive the intent model backend to services.restart.
    repl._responder = _intent_responder("services.restart")

    outcome = repl.run_turn(user_input)

    # The decomposed strategy produced a call that actually dispatched.
    assert outcome.tool_calls_made == 1
    assert dispatch_calls == [("services", "restart", {"unit": "nginx"})]

    # No-bypass: exactly one classify, and it precedes the one dispatch with the
    # SAME argv (dispatch cannot be reached except through the gate).
    assert len(classify_calls) == 1
    gated_command, decision = classify_calls[0]

    # Convergence: the classified argv is byte-identical to what the NATIVE path
    # would synthesize for the same (tool, op, args). ONE renderer, ONE gate.
    native_equiv = ParsedCall(
        call_id="native",
        tool="services",
        operation="restart",
        args={"unit": "nginx"},
        permission_class=OpClass.WRITE,
    )
    assert gated_command == synthesize_command(native_equiv) == "systemctl restart nginx"
    assert decision.op_class is OpClass.WRITE
    assert decision.gate is Gate.CONFIRM


def test_decomposed_never_dispatches_without_a_preceding_classify(monkeypatch):
    """General no-bypass invariant across a batch: #dispatch <= #classify and
    every dispatched argv appears among the classified argvs."""
    classify_calls, dispatch_calls = _install_spies(monkeypatch)

    strategy = DecomposedStrategy(registry, embedder=None)
    io = FakeIO(confirm=True)
    repl = _make_repl(strategy, io, FakeContext("nginx.service active"), max_rounds=1)
    repl._responder = _intent_responder("services.restart")

    repl.run_turn("restart the nginx service")

    classified_cmds = {c for c, _ in classify_calls}
    for tool, op, args in dispatch_calls:
        call = ParsedCall("x", tool, op, args, OpClass.WRITE)
        assert synthesize_command(call) in classified_cmds
    assert len(dispatch_calls) <= len(classify_calls)


# --------------------------------------------------------------------------- #
# 2. Destructive parity: decomposed DESTRUCTIVE gates identically to native     #
# --------------------------------------------------------------------------- #

def test_decomposed_destructive_hits_confirm_typed_like_native(monkeypatch):
    """A decomposed disk.format gets CONFIRM_TYPED — identical to the native path."""
    classify_calls, dispatch_calls = _install_spies(monkeypatch)

    user_input = "format /dev/sdb"
    snapshot = "block devices: /dev/sda, /dev/sdb (unmounted)"
    strategy = DecomposedStrategy(registry, embedder=None)
    io = FakeIO(typed_ok=True)  # user types DESTROY
    repl = _make_repl(strategy, io, FakeContext(snapshot), interactive=True, max_rounds=1)
    repl._responder = _intent_responder("disk.format")

    outcome = repl.run_turn(user_input)

    # It dispatched (typed word given) — via the gate.
    assert outcome.tool_calls_made == 1
    assert dispatch_calls == [("disk", "format", {"device": "/dev/sdb", "fstype": "ext4"})]

    assert len(classify_calls) == 1
    gated_command, decomposed_decision = classify_calls[0]

    # The decomposed argv is the REAL dangerous mkfs form (never under-stated).
    native_equiv = ParsedCall(
        call_id="native",
        tool="disk",
        operation="format",
        args={"device": "/dev/sdb", "fstype": "ext4"},
        permission_class=OpClass.DESTRUCTIVE,
    )
    native_command = synthesize_command(native_equiv)
    assert gated_command == native_command == "mkfs.ext4 /dev/sdb"

    # Parity: classify the native argv directly and assert the SAME decision the
    # decomposed path got (same op_class + same gate).
    native_decision = perm.classify(native_command, ExecContext(interactive=True))
    assert decomposed_decision.op_class is OpClass.DESTRUCTIVE
    assert native_decision.op_class is OpClass.DESTRUCTIVE
    assert decomposed_decision.gate is Gate.CONFIRM_TYPED
    assert native_decision.gate is Gate.CONFIRM_TYPED
    assert decomposed_decision.gate is native_decision.gate


def test_decomposed_destructive_refused_non_interactive_like_native(monkeypatch):
    """Non-interactive: a decomposed destructive op is REFUSED, never auto-run —
    identical to the native path's REFUSE."""
    classify_calls, dispatch_calls = _install_spies(monkeypatch)

    strategy = DecomposedStrategy(registry, embedder=None)
    io = FakeIO()
    repl = _make_repl(
        strategy, io, FakeContext("/dev/sdb present"),
        interactive=False, max_rounds=1,
    )
    repl._responder = _intent_responder("disk.format")

    outcome = repl.run_turn("format /dev/sdb")

    # REFUSED: nothing dispatched, one refusal recorded.
    assert dispatch_calls == []
    assert outcome.tool_calls_made == 0
    assert outcome.refused == 1

    # The gate still ran (classify observed) and returned REFUSE — same verdict
    # the native argv gets non-interactively.
    assert len(classify_calls) == 1
    gated_command, decomposed_decision = classify_calls[0]
    assert gated_command == "mkfs.ext4 /dev/sdb"
    native_decision = perm.classify(gated_command, ExecContext(interactive=False))
    assert decomposed_decision.gate is Gate.REFUSE
    assert native_decision.gate is Gate.REFUSE


# --------------------------------------------------------------------------- #
# 3. Escalation policy: fast-then-decompose tries native FIRST, escalates on    #
#    a MISS — and the escalated call still converges on the single gate.        #
# --------------------------------------------------------------------------- #

def _stub_embedder_for(tool: str, operation: str):
    """A deterministic offline embedder that makes (tool, operation) the unique
    best match (cosine 1.0) and everything else orthogonal (0.0). Uses the real
    candidate space so the target's description string is matched exactly."""
    cands = intent_mod._build_candidate_space(registry)
    target = next(c for c in cands if c.tool == tool and c.operation == operation)

    def _embed(text: str) -> list[float]:
        if text == target.description:
            return [1.0, 0.0]
        return [0.0, 1.0]

    # The query embeds to the same axis as the target so it wins.
    def embedder(text: str) -> list[float]:
        # Any text that is NOT a candidate description is treated as the query.
        descs = {c.description for c in cands}
        if text in descs:
            return _embed(text)
        return [1.0, 0.0]

    return embedder


class _RecordingStrategy:
    """A decomposed stand-in that records whether propose() was called."""

    def __init__(self) -> None:
        self.called = False

    def propose(self, *a, **k) -> StrategyResult:
        self.called = True
        return StrategyResult(source="decomposed")


def test_fast_path_returns_native_without_touching_decomposition():
    """When native yields a valid call, decomposition NEVER runs (I8 fast path)."""
    router = Router(registry)
    native = NativeToolCallStrategy(router)
    recorder = _RecordingStrategy()
    strategy = FastThenDecomposeStrategy(native, recorder)

    # A responder that emits a valid native tool call.
    import json

    def responder(messages, tools):
        return _FakeResponse(
            content="",
            tool_calls=[{
                "id": "c1",
                "name": "services",
                "arguments": json.dumps({"operation": "status", "unit": "sshd.service"}),
            }],
        )

    result = strategy.propose(
        "is sshd up?", "sshd.service active", [], [], responder, router
    )
    assert result.source == "native"
    assert len(result.calls) == 1
    assert recorder.called is False  # decomposition never fired on the fast path


def test_miss_escalates_to_decomposition_before_reask():
    """A native MISS escalates into DecomposedStrategy, which assembles a valid
    call — converging on the same ParsedCall shape the native path emits."""
    router = Router(registry)
    native = NativeToolCallStrategy(router)
    decomposed = DecomposedStrategy(
        registry, embedder=_stub_embedder_for("services", "restart")
    )
    strategy = FastThenDecomposeStrategy(native, decomposed)

    # Responder makes NATIVE miss (unknown tool). Decomposition uses the embedder
    # for intent + deterministic slots, so it ignores this responder for intent.
    def miss_responder(messages, tools):
        return _FakeResponse(
            content="",
            tool_calls=[{"id": "x", "name": "not_a_tool", "arguments": "{}"}],
        )

    result = strategy.propose(
        "restart the nginx service",
        "nginx.service active(running)",
        [],
        [],
        miss_responder,
        router,
    )

    assert result.source == "decomposed"
    assert len(result.calls) == 1
    call = result.calls[0]
    assert call.tool == "services"
    assert call.operation == "restart"
    assert call.args == {"unit": "nginx"}
    # Convergence: it renders + gates exactly like the native equivalent.
    assert synthesize_command(call) == "systemctl restart nginx"
    decision = perm.classify(synthesize_command(call), ExecContext(interactive=True))
    assert decision.gate is Gate.CONFIRM


def test_escalation_yields_nothing_preserves_native_miss():
    """If decomposition also cannot resolve, the native MISS is preserved so the
    unchanged loop re-asks + audits exactly as today."""
    router = Router(registry)
    native = NativeToolCallStrategy(router)
    # No embedder + a responder that can't classify -> decomposition returns empty.
    decomposed = DecomposedStrategy(registry, embedder=None)
    strategy = FastThenDecomposeStrategy(native, decomposed)

    def miss_responder(messages, tools):
        # Native miss AND (for intent) an unparseable classification -> no match.
        return _FakeResponse(
            content="not a tool.operation line",
            tool_calls=[{"id": "x", "name": "not_a_tool", "arguments": "{}"}],
        )

    result = strategy.propose(
        "do something impossible", "", [], [], miss_responder, router
    )
    # Native miss preserved (source native, misses present, no calls).
    assert result.source == "native"
    assert result.calls == []
    assert result.misses  # the loop will re-ask + audit this, unchanged
