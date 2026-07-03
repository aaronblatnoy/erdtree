"""
core/agent/pipeline/plan.py — Phase 8: compound / multi-step planning
(static plan first, dynamic re-plan of the remainder only).

A single English request can pack several operations ("restart nginx AND
install postgresql AND open the firewall for it"). A small base is far more
reliable resolving one operation at a time than emitting a whole batch in one
turn. This module:

  1. CHEAP HEURISTIC COMPOUND DETECTION FIRST (before any inference): a request
     with conjunctions ("and" / "then" / ";" / ",") or more than one action
     verb is flagged compound. A positive detection is the escalation trigger
     into the compound path; a negative one leaves the fast single-op path
     completely alone (detection is pure string work — I8, zero latency).

  2. STATIC PLANNING: split the request into ordered clauses and decompose each
     (Phase 5: intent -> slots -> assemble) into ONE single-operation
     ParsedCall. The FULL plan is rendered and shown BEFORE ANY step runs, and
     the whole plan must be confirmed to proceed. Nothing executes speculatively.

  3. SEQUENTIAL EXECUTION THROUGH THE SPINE + PER-STEP VERIFICATION (Phase 6):
     each step is synthesized, classified by THE single gate, gated
     individually (a destructive step still demands its own typed confirmation),
     dispatched, audited, and then verified. State lives HERE, deterministically
     — never in the model; each step is a fresh, stateless resolution.

  4. BOUNDED DYNAMIC RE-PLAN: when a step's verification INVALIDATES the rest of
     the plan (the change did not land / cannot be confirmed and a person is
     needed), the REMAINDER ONLY is re-planned — the already-run prefix is never
     touched — and only up to ``max_replans`` times. There is NO silent
     auto-continue: once the re-plan budget is spent, execution HALTS.

HARD SAFETY LINE (identical to verify.py / the spine this converges on):
  * This module builds NO second executor and NO second gate. Every step is run
    through the EXACT spine primitives the native path uses:
    ``repl.synthesize_command`` (one renderer) -> ``permissions.classify`` (THE
    single gate) -> the injected registry's ``dispatch`` (one executor) ->
    ``AuditLog.write`` (one audit spine). ``permissions.classify`` is never
    re-implemented, weakened, or bypassed — its ``Decision`` is only consumed.
  * Per-step verification is delegated to ``pipeline.verify.verify`` (Phase 6),
    which is the ONLY place idempotent retries live and which NEVER auto-retries
    a destructive op.

Load-bearing invariants:
  I1  No egress: no socket is opened here; inference is only ever the injected
      responder (localhost Ollama) reached via the Phase-5 planner.
  I2  No AI/LLM/model/agent language in ANY user-facing string (the rendered
      plan, statuses, halt messages).
  I3  ``permissions.classify`` is THE single gate, resolved before every
      write/destructive step. Never re-implemented or bypassed.
  I4  Every attempted op writes exactly one append-only JSONL audit record —
      cleared dispatches, gate refusals/declines, and unresolved-step misses.
      Verification reads/retries are audited by verify.py.
  I5  Context is invalidated after a successful mutation so the next step (and
      any re-plan) sees reality, not a stale snapshot.
  I6  No tier/product names; the audit ``tier`` field is opaque.
  I8  Detection is pure string work; the fast single-op path never pays for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

from core.agent import permissions as perm
from core.agent.permissions import Decision, ExecContext, Gate, OpClass
from core.agent.router import ParsedCall, Router
from core.tools import ToolRegistry, ToolResult

from core.agent.pipeline.verify import VerifyOutcome, VerifyStatus, verify as verify_step


# --------------------------------------------------------------------------- #
# Cheap heuristic compound detection (runs FIRST, before any inference)         #
# --------------------------------------------------------------------------- #

#: Conjunction tokens that separate independent clauses. "and then" collapses to
#: a single split; a bare "," or ";" also delimits. Matched case-insensitively
#: with word boundaries so "command" / "android" never trip the word forms.
_CONJUNCTION_RE = re.compile(
    r"\s*(?:;|,|\band\s+then\b|\bthen\b|\band\b|&&)\s*",
    re.IGNORECASE,
)

#: A small lexicon of imperative sysadmin ACTION verbs. Two or more distinct
#: action verbs in one request is a compound signal even without a conjunction
#: (e.g. "restart nginx / check disk"). Deliberately conservative: a false
#: positive only escalates into the plan path, which still shows + confirms.
_ACTION_VERBS = frozenset({
    "install", "remove", "uninstall", "update", "upgrade", "reinstall",
    "start", "stop", "restart", "reload", "enable", "disable", "mask",
    "create", "make", "mkdir", "add", "delete", "erase", "wipe",
    "copy", "move", "rename", "write", "chmod", "chown",
    "configure", "config", "set", "setup", "provision",
    "open", "close", "allow", "block", "format", "mount", "unmount",
    "bring", "reboot", "shutdown", "lock", "unlock", "kill",
})

#: Tokenizer for the verb scan — words only, lowercased by the caller.
_WORD_RE = re.compile(r"[a-zA-Z]+")


@dataclass(frozen=True)
class CompoundDetection:
    """Result of the cheap heuristic compound scan.

    is_compound:   True iff the request looks like more than one operation.
    conjunctions:  the conjunction tokens found (verbatim, lowercased).
    verbs:         the distinct action verbs found, in first-seen order.
    """

    is_compound: bool
    conjunctions: list[str] = field(default_factory=list)
    verbs: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # ergonomic: `if detect_compound(x): ...`
        return self.is_compound


def detect_compound(user_input: str) -> CompoundDetection:
    """Cheaply decide whether ``user_input`` packs more than one operation.

    Pure string work (no inference, no I/O) so the fast single-op path pays
    nothing (I8). A positive result is the escalation trigger into the compound
    plan path; a negative result means the caller keeps the ordinary path.

    Positive when EITHER a clause conjunction is present OR two or more distinct
    action verbs appear.
    """
    text = user_input or ""
    lowered = text.lower()

    conjunctions: list[str] = []
    for m in _CONJUNCTION_RE.finditer(text):
        tok = m.group(0).strip().lower()
        if tok:
            conjunctions.append(tok)

    seen: list[str] = []
    for w in _WORD_RE.findall(lowered):
        if w in _ACTION_VERBS and w not in seen:
            seen.append(w)

    is_compound = bool(conjunctions) or len(seen) >= 2
    return CompoundDetection(
        is_compound=is_compound,
        conjunctions=conjunctions,
        verbs=seen,
    )


def split_clauses(user_input: str) -> list[str]:
    """Split a compound request into ordered, non-empty clause strings.

    Splits on the same conjunction tokens the detector recognises. Order is
    preserved (steps run in the order written). Whitespace-only fragments and
    dangling connectives are dropped.
    """
    parts = _CONJUNCTION_RE.split(user_input or "")
    return [p.strip() for p in parts if p and p.strip()]


# --------------------------------------------------------------------------- #
# Plan model                                                                    #
# --------------------------------------------------------------------------- #

@dataclass
class PlanStep:
    """One ordered single-operation unit of a static plan.

    clause: the sub-request English this step was decomposed from (kept so the
            remainder can be re-planned deterministically — state lives here).
    call:   the resolved single-op ParsedCall, or None when the clause could
            not be turned into exactly one operation.
    reason: an I2-clean explanation when ``call`` is None.
    """

    index: int
    clause: str
    call: Optional[ParsedCall] = None
    reason: str = ""


@dataclass
class StepReport:
    """What happened to one step during execution (for the caller + tests)."""

    index: int
    clause: str
    command: str = ""
    op_class: Optional[OpClass] = None
    gate: str = ""              # decision gate value, or "unresolved"
    cleared: bool = False       # gate cleared -> the op actually ran
    ran: bool = False
    exit_code: Optional[int] = None
    verify_status: Optional[VerifyStatus] = None
    invalidated: bool = False   # verification invalidated the remaining plan
    status: str = ""            # short, I2-clean human status


@dataclass
class PlanRun:
    """The full result of planning + executing one compound request."""

    is_compound: bool
    detection: CompoundDetection
    plan_text: str = ""
    confirmed: bool = False
    steps: list[StepReport] = field(default_factory=list)
    replans: int = 0
    audit_records: int = 0
    halted: bool = False
    completed: bool = False


# --------------------------------------------------------------------------- #
# Planner seam (Phase 5 decomposition per clause)                              #
# --------------------------------------------------------------------------- #

#: A planner turns an ordered list of clauses into ordered PlanSteps. It is the
#: single injection seam for both the initial static plan AND each bounded
#: re-plan of the remainder. The default wires the Phase-5 DecomposedStrategy.
Planner = Callable[[list[str], str], list[PlanStep]]


class Responder(Protocol):
    def __call__(self, messages: list[dict], tools: list[dict]) -> Any: ...


def decomposed_planner(
    registry: ToolRegistry,
    responder: "Responder",
    *,
    embedder: Optional[Callable[[str], list[float]]] = None,
    router: Optional[Router] = None,
) -> Planner:
    """Build the default planner: decompose each clause with Phase 5.

    Each clause is resolved INDEPENDENTLY (a fresh, stateless intent -> slots ->
    assemble pass) into a single-op ParsedCall. Cross-step state is never held
    by the model — it lives in the returned PlanStep list (deterministic).
    """
    from core.agent.pipeline.strategy import DecomposedStrategy

    strat = DecomposedStrategy(registry, embedder=embedder)
    the_router = router if router is not None else Router(registry)

    def _plan(clauses: list[str], snapshot_text: str) -> list[PlanStep]:
        steps: list[PlanStep] = []
        for i, clause in enumerate(clauses):
            result = strat.propose(clause, snapshot_text, [], [], responder, the_router)
            call = result.calls[0] if result.calls else None
            steps.append(PlanStep(
                index=i,
                clause=clause,
                call=call,
                reason="" if call else "could not be turned into a single operation",
            ))
        return steps

    return _plan


# --------------------------------------------------------------------------- #
# Confirmation seams                                                            #
# --------------------------------------------------------------------------- #

class Confirmer(Protocol):
    """Per-step gate prompts. Mirrors the repl IO the spine already uses; the
    Decision it acts on always comes from permissions.classify (I3)."""

    def confirm(self, command: str) -> bool: ...
    def confirm_typed(self, reason: str, word: str) -> bool: ...


class _DenyAllConfirmer:
    """Safe default: clears nothing. A real caller injects an interactive one."""

    def confirm(self, command: str) -> bool:
        return False

    def confirm_typed(self, reason: str, word: str) -> bool:
        return False


#: The "proceed with the whole plan?" gate, shown the rendered plan. Default
#: denies — a compound plan never runs unattended without an explicit yes.
ProceedConfirm = Callable[[str], bool]


def _deny_proceed(plan_text: str) -> bool:
    return False


# --------------------------------------------------------------------------- #
# Rendering the full plan (I2-clean) BEFORE any step runs                       #
# --------------------------------------------------------------------------- #

def render_plan(steps: list[PlanStep]) -> str:
    """Render the whole plan as plain text to show BEFORE anything executes.

    Resolved steps show the concrete command they map to (the same argv the gate
    and executor will use). Unresolved steps are shown honestly so the person
    sees exactly what will and will not be attempted. I2-clean throughout.
    """
    n = len(steps)
    header = f"Plan ({n} step{'s' if n != 1 else ''}):"
    lines = [header]
    for step in steps:
        if step.call is not None:
            lines.append(f"  {step.index + 1}. {synthesize_command(step.call)}")
        else:
            note = step.reason or "could not be turned into a single operation"
            lines.append(f"  {step.index + 1}. {step.clause} — {note}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Spine reuse — synthesize -> classify -> gate -> dispatch -> audit             #
# (NO second gate, NO second executor; identical primitives to verify.py)       #
# --------------------------------------------------------------------------- #

def synthesize_command(call: ParsedCall) -> str:
    # Imported lazily so this module never participates in repl.py's import.
    from core.agent.repl import synthesize_command as _synth

    return _synth(call)


def _safe_args(call: ParsedCall) -> dict:
    out = dict(call.args)
    out["operation"] = call.operation
    return out


def _resolve_gate(decision: Decision, command: str, confirmer: Confirmer) -> tuple[bool, str]:
    """Turn one permission Decision into (cleared, note) — mirrors the spine.

    This CONSUMES the Decision from permissions.classify; it does NOT
    re-classify or weaken the gate (I3). Unknown gates default-deny.
    """
    if decision.gate is Gate.ALLOW:
        return True, "read — allowed"
    if decision.gate is Gate.REFUSE:
        return False, decision.reason
    if decision.gate is Gate.CONFIRM:
        ok = confirmer.confirm(command)
        return ok, ("confirmed" if ok else "declined")
    if decision.gate is Gate.CONFIRM_TYPED:
        word = decision.confirm_word or perm.DESTRUCTIVE_CONFIRM_WORD
        ok = confirmer.confirm_typed(decision.reason, word)
        return ok, ("confirmed (typed)" if ok else "declined")
    return False, "blocked for safety"


def _safe_dispatch(registry: ToolRegistry, call: ParsedCall) -> ToolResult:
    """Dispatch one validated call through the ONE executor; never crash."""
    try:
        return registry.dispatch(call.tool, call.operation, call.args)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            exit_code=1, stdout="", stderr=str(exc),
            summary=f"operation could not be completed: {exc}",
        )


def _verify_invalidates(outcome: VerifyOutcome) -> bool:
    """Does this verification outcome invalidate the REST of the plan?

    Only a verification that says a person must intervene (the change did not
    land / could not be confirmed and cannot be safely repeated) invalidates the
    remainder — this is the SOLE trigger for a re-plan. VERIFIED / RETRIED_OK /
    READ_ONLY / UNVERIFIABLE do not (a bare "couldn't confirm" is not treated as
    a failure, to avoid runaway re-planning; verify.py owns that distinction).
    """
    return outcome.escalated


# --------------------------------------------------------------------------- #
# Executing one step                                                           #
# --------------------------------------------------------------------------- #

def _execute_step(
    step: PlanStep,
    registry: ToolRegistry,
    exec_ctx: ExecContext,
    audit,
    confirmer: Confirmer,
    *,
    context,
    tier: str,
    nl_input: str,
    retry_max: Optional[int],
) -> tuple[StepReport, int, bool]:
    """Run ONE step through the spine + verify it.

    Returns (report, audit_records_written, invalidated_remainder).
    """
    # Unresolved clause: nothing to run. Record exactly one miss record (I4).
    if step.call is None:
        note = step.reason or "could not be turned into a single operation"
        audit.write(
            tier=tier, nl_input=nl_input, translated_command="",
            tool="", args={}, permission_decision="unresolved",
            exit_code=2, result=note,
        )
        report = StepReport(
            index=step.index, clause=step.clause, gate="unresolved",
            cleared=False, ran=False, status="not run",
        )
        # A step we could not resolve means later steps can no longer assume its
        # effect — the remainder is invalidated (bounded re-plan may recover it).
        return report, 1, True

    call = step.call
    command = synthesize_command(call)
    # THE single gate (I3): the SAME hardened classifier the native path uses.
    decision: Decision = perm.classify(command, exec_ctx)
    cleared, note = _resolve_gate(decision, command, confirmer)

    if not cleared:
        # Refused / declined: one audit record (I4). A declined step does NOT
        # by itself invalidate the remainder — each step gates individually.
        audit.write(
            tier=tier, nl_input=nl_input, translated_command=command,
            tool=call.tool, args=_safe_args(call),
            permission_decision=f"{decision.gate.value}:{note}",
            exit_code=2, result=note,
        )
        report = StepReport(
            index=step.index, clause=step.clause, command=command,
            op_class=decision.op_class, gate=decision.gate.value,
            cleared=False, ran=False, status="not run",
        )
        return report, 1, False

    # Gate cleared -> run the real op through the ONE executor and audit it (I4).
    result = _safe_dispatch(registry, call)
    audit.write(
        tier=tier, nl_input=nl_input, translated_command=command,
        tool=call.tool, args=_safe_args(call),
        permission_decision=decision.gate.value,
        exit_code=result.exit_code, stdout_summary=result.stdout,
        stderr_summary=result.stderr, result=result.summary,
    )
    records = 1

    # I5: a successful mutation changes the box — invalidate context so the next
    # step (and any verification read / re-plan) sees reality.
    if decision.op_class is not OpClass.READ and result.ok and context is not None:
        try:
            context.invalidate()
        except Exception:  # noqa: BLE001 — invalidation never breaks the plan.
            pass

    # Verify the step (Phase 6). verify.py owns its own audit records + the
    # op-class-keyed retry policy (destructive is NEVER auto-retried there).
    outcome: VerifyOutcome = verify_step(
        call, result, registry, exec_ctx, audit,
        context=context, tier=tier, nl_input=nl_input, retry_max=retry_max,
    )
    records += outcome.audit_records

    invalidated = _verify_invalidates(outcome)
    report = StepReport(
        index=step.index, clause=step.clause, command=command,
        op_class=decision.op_class, gate=decision.gate.value,
        cleared=True, ran=True, exit_code=result.exit_code,
        verify_status=outcome.status, invalidated=invalidated,
        status=("done" if not invalidated else "needs attention"),
    )
    return report, records, invalidated


# --------------------------------------------------------------------------- #
# The entry point: plan + confirm + execute + bounded re-plan                  #
# --------------------------------------------------------------------------- #

def run_plan(
    user_input: str,
    snapshot_text: str,
    registry: ToolRegistry,
    exec_ctx: ExecContext,
    audit,
    *,
    planner: Planner,
    confirmer: Optional[Confirmer] = None,
    proceed: Optional[ProceedConfirm] = None,
    context=None,
    tier: str = "",
    nl_input: Optional[str] = None,
    max_replans: int = 1,
    retry_max: Optional[int] = None,
    sink: Optional[Callable[[str], None]] = None,
) -> PlanRun:
    """Plan a compound request statically, confirm the whole plan, then run it
    step-by-step through the spine, verifying each step and re-planning the
    REMAINDER (bounded) only when a verification invalidates it.

    The flow, in order:
      1. Cheap heuristic compound detection. Not compound -> return immediately
         with ``is_compound=False`` and run NOTHING (caller keeps the fast path).
      2. Split into clauses and decompose each (via ``planner``) into a single-op
         step. Render the FULL plan and hand it to ``sink`` (if given).
      3. Ask ``proceed`` to confirm the WHOLE plan before ANY step runs. Declined
         -> return with ``confirmed=False`` and run NOTHING.
      4. Execute steps in order. Each step is gated INDIVIDUALLY (destructive
         steps demand their own typed confirmation) and verified (Phase 6).
      5. On a verification that INVALIDATES the remainder, re-plan the remaining
         clauses only — never the already-run prefix — up to ``max_replans``
         times. Once the budget is spent, HALT (never silently auto-continue).

    Defaults deny: with no ``proceed`` / ``confirmer`` supplied, the plan is
    shown but nothing runs — a compound plan never executes unattended.
    """
    nl = user_input if nl_input is None else nl_input
    confirmer = confirmer if confirmer is not None else _DenyAllConfirmer()
    proceed = proceed if proceed is not None else _deny_proceed

    detection = detect_compound(user_input)
    if not detection.is_compound:
        # Fast path stays untouched: not our request.
        return PlanRun(is_compound=False, detection=detection)

    clauses = split_clauses(user_input)
    steps: list[PlanStep] = list(planner(clauses, snapshot_text))
    plan_text = render_plan(steps)
    if sink is not None:
        sink(plan_text)

    run = PlanRun(
        is_compound=True, detection=detection, plan_text=plan_text,
    )

    # Confirm the WHOLE plan before ANY step runs.
    if not proceed(plan_text):
        run.confirmed = False
        return run
    run.confirmed = True

    i = 0
    while i < len(steps):
        step = steps[i]
        report, records, invalidated = _execute_step(
            step, registry, exec_ctx, audit, confirmer,
            context=context, tier=tier, nl_input=nl,
            retry_max=retry_max,
        )
        run.steps.append(report)
        run.audit_records += records

        if invalidated and (i + 1) < len(steps):
            # The remaining plan can no longer be trusted. Re-plan the REMAINDER
            # ONLY (the already-run prefix steps[:i+1] are never touched), and
            # only within the bounded budget — otherwise HALT.
            if run.replans < max_replans:
                run.replans += 1
                remaining_clauses = [s.clause for s in steps[i + 1:]]
                new_steps = list(planner(remaining_clauses, snapshot_text))
                # Re-index the fresh remainder so it continues the sequence.
                for offset, ns in enumerate(new_steps):
                    ns.index = i + 1 + offset
                steps = steps[: i + 1] + new_steps
            else:
                # Bounded: budget spent, a verification still failed with work
                # left. Stop rather than blindly continuing (no auto-continue).
                run.halted = True
                run.completed = False
                return run

        i += 1

    run.completed = not run.halted
    return run
