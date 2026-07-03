"""
core/agent/pipeline/strategy.py

Defines the UnderstandingStrategy Protocol and its default implementation
NativeToolCallStrategy, plus the StrategyResult dataclass that carries the
output of ONE model round through the REPL loop.

Design contract:
  * StrategyResult wraps everything run_turn needs from a single propose() call:
    the parsed calls, misses, English content, raw model response (for
    _assistant_message), and re-ask messages.
  * UnderstandingStrategy is a typing.Protocol — any object with the right
    propose() signature satisfies it without subclassing.
  * NativeToolCallStrategy encapsulates EXACTLY the two-line seam that existed
    in run_turn before this refactor (responder call + Router.route call).
    It is the DEFAULT and produces byte-identical behavior.
  * source="native" always for this implementation; future strategies may emit
    "decomposed" or "fallback".

Hard constraints (from the refactor spec):
  * NEVER re-implement, weaken, or bypass permissions.classify.
  * NEVER build a second executor or second gate.
  * This module has NO side effects: it calls the injected responder and router
    and returns a plain dataclass. All dispatch/gate/audit logic stays in repl.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from core.agent.router import MissDetail, ParsedCall, Router, RouterResult, TurnKind
from core.tools import ToolRegistry

# Local alias for the responder callable (mirrors repl.py's Responder alias).
# We cannot import it from repl.py without creating a circular import.
Responder = Callable[[list[dict], list[dict]], Any]


# --------------------------------------------------------------------------- #
# StrategyResult                                                               #
# --------------------------------------------------------------------------- #

@dataclass
class StrategyResult:
    """Result of ONE propose() call — everything run_turn needs from that round.

    Fields
    ------
    calls:           valid parsed calls (from RouterResult.calls).
    misses:          miss details (from RouterResult.misses).
    english_content: English text for a turn that terminated in plain prose
                     (non-empty iff the model answered in English without tool
                     calls; mirrors RouterResult.content for ENGLISH turns).
    source:          which strategy produced this result.
                     Literal "native" | "decomposed" | "fallback".
    raw_content:     the raw .content string from the model response; needed by
                     run_turn to build the _assistant_message entry.
    raw_calls:       the raw .tool_calls list from the model response; needed by
                     run_turn to build the _assistant_message entry.
    reask_messages:  0002 §3 tool-result re-ask messages (mirrors
                     RouterResult.reask_messages); run_turn appends these to
                     the conversation on a MISS turn.
    """

    calls: list[ParsedCall] = field(default_factory=list)
    misses: list[MissDetail] = field(default_factory=list)
    english_content: str = ""
    source: str = "native"
    raw_content: str = ""
    raw_calls: list[dict] = field(default_factory=list)
    reask_messages: list[dict] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# UnderstandingStrategy Protocol                                               #
# --------------------------------------------------------------------------- #

@runtime_checkable
class UnderstandingStrategy(Protocol):
    """One round of model interaction + result classification.

    Implementors receive the full conversation state and produce a StrategyResult
    that encodes what happened in exactly ONE model round.  run_turn drives the
    multi-round loop; the strategy is responsible only for the single seam of
    (call model -> classify response).

    propose() MUST NOT:
      * append to messages — that is run_turn's responsibility.
      * call dispatch, the permission gate, or the audit log.
      * open sockets or perform I/O beyond the injected responder.
    """

    def propose(
        self,
        user_input: str,
        snapshot_text: str,
        messages: list[dict],
        tools: list[dict],
        responder: Responder,
        router: Router,
    ) -> StrategyResult:
        """Run one model round and classify the result.

        Parameters
        ----------
        user_input:    the raw English string from the user (for context).
        snapshot_text: the system-context snapshot injected into the prompt.
        messages:      the current conversation history (NOT mutated here).
        tools:         the advertised tool schemas.
        responder:     the injected model callable (messages, tools) -> response.
        router:        the Router instance (for parse/validate).

        Returns
        -------
        StrategyResult capturing calls, misses, English content, and the raw
        model response fields needed to build the _assistant_message entry.
        """
        ...


# --------------------------------------------------------------------------- #
# NativeToolCallStrategy — default implementation                              #
# --------------------------------------------------------------------------- #

class NativeToolCallStrategy:
    """Default strategy: calls the responder then routes through the Router.

    This is a PURE MOVE of the two-line seam that existed in run_turn before
    this refactor:

        response = responder(messages, tools)
        verdict  = router.route(content=..., tool_calls=...)

    Behavior is byte-identical to the pre-refactor path.  source is always
    "native".
    """

    def __init__(self, router: Router) -> None:
        # Store the router so the default Repl construction (which passes
        # self._router) works without requiring the caller to supply it again
        # on every propose() call.  The propose() method also receives a router
        # argument (Protocol parity) and uses that directly; this stored copy
        # is available for introspection / subclass convenience.
        self._router = router

    def propose(
        self,
        user_input: str,
        snapshot_text: str,
        messages: list[dict],
        tools: list[dict],
        responder: Responder,
        router: Router,
    ) -> StrategyResult:
        """Exactly the two-line seam from run_turn, wrapped into StrategyResult."""
        response = responder(messages, tools)
        content: str = getattr(response, "content", "") or ""
        raw_calls: list[dict] = list(getattr(response, "tool_calls", []) or [])

        verdict: RouterResult = router.route(content=content, tool_calls=raw_calls)

        english_content = verdict.content if verdict.kind is TurnKind.ENGLISH else ""

        return StrategyResult(
            calls=verdict.calls,
            misses=verdict.misses,
            english_content=english_content,
            source="native",
            raw_content=content,
            raw_calls=raw_calls,
            reask_messages=verdict.reask_messages,
        )


# --------------------------------------------------------------------------- #
# Helper: synthesize an assistant-shape tool_calls list from ParsedCalls       #
# --------------------------------------------------------------------------- #

def _raw_calls_for(calls: list[ParsedCall]) -> list[dict]:
    """Build the raw ``{"id","name","arguments"}`` list run_turn needs to write
    the assistant history message for a set of assembled ParsedCalls.

    The decomposed path did not receive a model-issued tool_calls[] array (the
    calls were ASSEMBLED deterministically). We reconstruct the same wire shape
    the native path would have carried so:
      * run_turn's ``_assistant_message`` records a coherent tool-call turn, and
      * the ``tool_call_id`` correlation in the tool-result messages matches the
        ``call_id`` on each ParsedCall (the assembler's ``asm-*`` id).

    ``arguments`` is the 0002 §2 JSON-encoded STRING carrying the selected
    operation plus the per-op args — the exact form the native path emits.
    """
    out: list[dict] = []
    for c in calls:
        payload = {"operation": c.operation, **c.args}
        out.append({
            "id": c.call_id,
            "name": c.tool,
            "arguments": json.dumps(payload, separators=(",", ":")),
        })
    return out


# --------------------------------------------------------------------------- #
# DecomposedStrategy — the escalation-tier understanding path (Phase 5)         #
# --------------------------------------------------------------------------- #

class DecomposedStrategy:
    """Decomposed understanding: intent -> slots -> assembler -> list[ParsedCall].

    This turns a small model's hard one-shot tool-call problem into a chain of
    easy ones:

        [1] classify_intent(...)   -> a ranked (tool, operation) candidate
        [2] extract_slots(...)     -> deterministic-first + narrow model workers
        [3] assemble(...)          -> a validated ParsedCall (frozen router shape)

    HARD CONVERGENCE CONTRACT (R1, the #1 risk this whole design manages):
      * propose() returns a StrategyResult carrying ``calls: list[ParsedCall]``
        and NOTHING executable. It has NO dispatch code, NO gate code, NO audit
        code. The calls flow into the UNCHANGED repl._dispatch_calls spine, which
        is the ONLY place that runs synthesize_command -> permissions.classify ->
        registry.dispatch -> AuditLog. There is no second executor and no second
        gate. (Verified by tests/test_pipeline_convergence.py.)
      * The assembled ParsedCall is byte-for-byte the same shape the native
        Router produces, so synthesize_command renders the IDENTICAL argv and the
        SAME hardened classifier assigns the SAME gate — a destructive decomposed
        intent hits CONFIRM_TYPED / REFUSE exactly as the native path would.

    Invariants
    ----------
    I1  Every inference call is via the injected responder (localhost Ollama) or
        the injected embedder — never a new socket here.
    I2  No AI/LLM/model/agent language in any user-facing string.
    I3  This strategy NEVER calls permissions.classify; it only produces the
        ParsedCall the spine's single gate consumes.
    I4  This strategy writes NO audit records; the spine owns I4.
    I6  No tier/product names.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        embedder: Optional[Callable[[str], list[float]]] = None,
        max_workers: int = 4,
    ) -> None:
        self._registry = registry
        self._embedder = embedder
        self._max_workers = max(1, max_workers)

    def propose(
        self,
        user_input: str,
        snapshot_text: str,
        messages: list[dict],
        tools: list[dict],
        responder: Responder,
        router: Router,
    ) -> StrategyResult:
        """Run intent -> slots -> assembler and return the assembled ParsedCall(s).

        On any failure to resolve (NoConfidentMatch, unresolved required slots,
        validation failure) the returned StrategyResult carries NO calls, NO
        English, and NO misses — the caller (run_turn or FastThenDecompose)
        treats an empty decomposed result as "escalation produced nothing" and
        falls back to re-asking / the native miss, never fabricating a call.
        """
        # Imported lazily to keep the module import graph shallow and avoid any
        # import-time cost on the native-only fast path.
        from core.agent.pipeline.intent import (
            IntentMatch,
            NoConfidentMatch,
            classify_intent,
        )

        intent = classify_intent(
            user_input,
            snapshot_text,
            self._registry,
            embedder=self._embedder,
            responder=responder,
        )
        if isinstance(intent, NoConfidentMatch):
            return StrategyResult(source="decomposed")

        # Try the best candidate first, then any top-K ties. The assembler's
        # required-slot fit disambiguates near-identical descriptions (Phase 3).
        candidates: list[IntentMatch] = intent.top_k or [intent]
        for cand in candidates:
            call = self._resolve_candidate(
                cand.tool, cand.operation, user_input, snapshot_text, responder
            )
            if call is not None:
                return StrategyResult(
                    calls=[call],
                    source="decomposed",
                    raw_calls=_raw_calls_for([call]),
                )

        return StrategyResult(source="decomposed")

    def _resolve_candidate(
        self,
        tool: str,
        operation: str,
        user_input: str,
        snapshot_text: str,
        responder: Responder,
    ) -> Optional[ParsedCall]:
        """Slot-fill + assemble ONE (tool, operation) candidate, or None.

        Two-pass assembly (matches the plan's slot contract): assemble first with
        NO slots to learn exactly which REQUIRED slots are missing, extract only
        those, then assemble again. Optional args are filled by the assembler
        from ArgSpec.default (A1) — they never reach a model worker, so a READ
        or a fully-defaulted op needs no slot round-trip at all.
        """
        from core.agent.pipeline.assembler import Unresolved, assemble
        from core.agent.pipeline.slots import extract_slots

        spec = self._registry.get(tool)
        if spec is None:
            return None
        op_spec = spec.get_op(operation)
        if op_spec is None:
            return None

        # Pass 1: what required slots are missing?
        first = assemble(tool, operation, {}, self._registry)
        if isinstance(first, ParsedCall):
            return first
        if not isinstance(first, Unresolved) or not first.missing:
            # A non-missing Unresolved (unknown op / validation error) — nothing
            # slot extraction can fix.
            return None

        type_by_name = {a.name: a.type for a in op_spec.args}
        needed: list[tuple[str, type]] = [
            (name, type_by_name.get(name, str)) for name in first.missing
        ]

        slot_values = extract_slots(
            user_input,
            snapshot_text,
            tool,
            operation,
            needed,
            self._registry,
            responder=responder,
            max_workers=self._max_workers,
        )

        second = assemble(tool, operation, slot_values, self._registry)
        if isinstance(second, ParsedCall):
            return second
        return None


# --------------------------------------------------------------------------- #
# FastThenDecomposeStrategy — escalation policy (Phase 5)                       #
# --------------------------------------------------------------------------- #

class FastThenDecomposeStrategy:
    """Try the native fast path FIRST; escalate to decomposition on a MISS.

    This is the ``fast-then-decompose`` policy expressed as ONE Understanding
    strategy so run_turn's loop body stays byte-identical (the seam already
    calls ``self._strategy.propose(...)``; escalation lives entirely here, inside
    the pipeline package — never in the spine).

    Per round:
      1. Run the NATIVE strategy (today's single-shot fast path / latency).
      2. If native produced ANY valid calls OR an English answer -> return it
         verbatim. This is the COMMON path; its behavior + latency are exactly
         today's (decomposition NEVER fires here — I8, and the Phase-5 mossad
         latency checkpoint measures this p50 == native p50).
      3. ONLY on a MISS / no-valid-calls (or intent NoConfidentMatch surfaced by
         the decomposed round returning nothing) -> run the DECOMPOSED strategy
         BEFORE re-asking. If it assembles a call, return the decomposed result;
         otherwise return the native miss so run_turn re-asks + audits exactly as
         it does today (max_rounds + audit-every-op preserved by the unchanged
         loop).

    The escalation decision is made on native's result, not by mutating the
    loop, so the native code path is untouched and remains the default.
    """

    def __init__(
        self,
        native: UnderstandingStrategy,
        decomposed: UnderstandingStrategy,
    ) -> None:
        self._native = native
        self._decomposed = decomposed

    def propose(
        self,
        user_input: str,
        snapshot_text: str,
        messages: list[dict],
        tools: list[dict],
        responder: Responder,
        router: Router,
    ) -> StrategyResult:
        native = self._native.propose(
            user_input, snapshot_text, messages, tools, responder, router
        )

        # Fast path: native produced usable output (a valid tool call OR an
        # English answer). Return it untouched — byte-identical to native.
        if native.calls or native.english_content:
            return native

        # MISS / no-valid-calls -> escalate to decomposition BEFORE re-asking.
        decomposed = self._decomposed.propose(
            user_input, snapshot_text, messages, tools, responder, router
        )
        if decomposed.calls:
            return decomposed

        # Decomposition produced nothing either -> preserve the native miss so
        # run_turn's existing re-ask + audit-every-op path runs unchanged.
        return native
