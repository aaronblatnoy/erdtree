"""
tests/test_pipeline_plan.py — Phase 8 proof for compound / multi-step planning.

The load-bearing properties this file pins:

  1. Cheap heuristic compound detection runs FIRST (pure string work, no
     inference): conjunctions OR two-plus action verbs -> compound; a lone op
     stays on the fast path and the planner is never invoked.
  2. A conjunction request produces a MULTI-STEP plan that is shown in FULL
     BEFORE ANY step runs, and the whole plan must be confirmed to proceed.
  3. Steps run in order through the SAME spine (synthesize -> classify -> gate
     -> dispatch -> audit) and each is verified (Phase 6).
  4. A mid-plan verification failure triggers a BOUNDED re-plan of the REMAINDER
     ONLY (the already-run prefix is untouched, and never the whole plan); once
     the re-plan budget is spent, execution HALTS (no silent auto-continue).
  5. Destructive steps gate INDIVIDUALLY (their own typed confirmation);
     declining one does not stop the plan.
  6. Every attempted op writes exactly one append-only audit record (I4).

Driven with the REAL registry (so real synthesize_command + permissions.classify
run) plus a controllable stand-in for registry.dispatch, so nothing touches the
host. The planner is injected (a deterministic fake) so the control-flow — not a
model — is what these tests exercise.
"""

from __future__ import annotations

import pytest

# Register the tools the cases exercise (self-register on import).
import core.tools.services  # noqa: F401
import core.tools.packages  # noqa: F401
import core.tools.files  # noqa: F401

from core.tools import registry, ToolResult
from core.agent.permissions import ExecContext, OpClass
from core.agent.router import ParsedCall
from core.agent.audit import AuditLog, iter_records
from core.agent.pipeline.verify import VerifyStatus
from core.agent.pipeline.plan import (
    CompoundDetection,
    PlanStep,
    detect_compound,
    render_plan,
    run_plan,
    split_clauses,
)


CTX = ExecContext(interactive=True)


# --------------------------------------------------------------------------- #
# Test doubles                                                                  #
# --------------------------------------------------------------------------- #

class FakeContext:
    def __init__(self) -> None:
        self.invalidations = 0

    def invalidate(self) -> None:
        self.invalidations += 1


class DispatchStub:
    """Stand in for registry.dispatch; scripted ToolResult per (tool, op) and a
    record of every dispatch so we can prove what ran (and what did NOT)."""

    def __init__(self, results: dict) -> None:
        self._results = results
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, tool, op, args):
        self.calls.append((tool, op, dict(args)))
        r = self._results.get((tool, op))
        if r is None:
            return ToolResult(exit_code=0, stdout="", stderr="", summary="done")
        return r

    def count(self, tool, op) -> int:
        return sum(1 for (t, o, _) in self.calls if t == tool and o == op)


class ApproveConfirmer:
    """Clears every gate; records each prompt so per-step gating is observable."""

    def __init__(self) -> None:
        self.confirms: list[str] = []
        self.typed: list[str] = []

    def confirm(self, command: str) -> bool:
        self.confirms.append(command)
        return True

    def confirm_typed(self, reason: str, word: str) -> bool:
        self.typed.append(word)
        return True


class SelectiveConfirmer:
    """Approves plain confirms, DENIES typed (destructive) confirms."""

    def __init__(self) -> None:
        self.confirms: list[str] = []
        self.typed: list[str] = []

    def confirm(self, command: str) -> bool:
        self.confirms.append(command)
        return True

    def confirm_typed(self, reason: str, word: str) -> bool:
        self.typed.append(word)
        return False


class RecordingPlanner:
    """Deterministic planner: maps each clause -> a ParsedCall (or None). Records
    the clause list it was called with each time so re-plan scope is observable."""

    def __init__(self, mapping: dict) -> None:
        self.mapping = mapping
        self.calls: list[list[str]] = []

    def __call__(self, clauses, snapshot_text):
        self.calls.append(list(clauses))
        steps = []
        for i, c in enumerate(clauses):
            call = self.mapping.get(c)
            steps.append(PlanStep(
                index=i, clause=c, call=call,
                reason="" if call else "could not be turned into a single operation",
            ))
        return steps


def _ok(stdout="ok"):
    return ToolResult(exit_code=0, stdout=stdout, stderr="", summary="completed")


def _fail(stderr="nope"):
    return ToolResult(exit_code=1, stdout="", stderr=stderr, summary="exited 1")


def _pc(tool, op, args, cls=OpClass.WRITE):
    return ParsedCall(
        call_id=f"c-{tool}-{op}", tool=tool, operation=op,
        args=args, permission_class=cls,
    )


@pytest.fixture
def audit(tmp_path):
    path = tmp_path / "audit.jsonl"
    return AuditLog(path), path


def _boom_planner(*_a, **_k):
    raise AssertionError("planner must NOT be called on the fast (non-compound) path")


def _always_yes(_plan_text: str) -> bool:
    return True


# --------------------------------------------------------------------------- #
# 1. Cheap heuristic compound detection (FIRST, pure string work)              #
# --------------------------------------------------------------------------- #

def test_detect_conjunction_and():
    d = detect_compound("restart nginx and install postgresql")
    assert isinstance(d, CompoundDetection)
    assert d.is_compound is True
    assert "and" in d.conjunctions


def test_detect_conjunction_then_and_semicolon():
    assert detect_compound("restart nginx then check the logs").is_compound
    assert detect_compound("restart nginx; enable nginx").is_compound


def test_detect_multiple_action_verbs_without_conjunction():
    # Two distinct action verbs -> compound even with no conjunction token.
    d = detect_compound("restart nginx format the disk")
    assert d.is_compound is True
    assert set(["restart", "format"]).issubset(set(d.verbs))


def test_single_operation_is_not_compound():
    assert detect_compound("restart nginx").is_compound is False
    assert detect_compound("show me all failing services").is_compound is False
    # "and" inside a word must not trip the detector.
    assert detect_compound("run the command handler").is_compound is False


def test_split_clauses_preserves_order():
    clauses = split_clauses("restart nginx and install postgresql and enable nginx")
    assert clauses == ["restart nginx", "install postgresql", "enable nginx"]


def test_detection_runs_before_planner_on_fast_path(audit):
    """A non-compound request returns immediately and NEVER invokes the planner
    (detection is pure string work — the fast path pays nothing)."""
    log, _ = audit
    run = run_plan(
        "restart nginx", "snap", registry, CTX, log,
        planner=_boom_planner, proceed=_always_yes,
    )
    assert run.is_compound is False
    assert run.steps == []
    assert run.confirmed is False


# --------------------------------------------------------------------------- #
# 2. Full plan shown BEFORE any step runs; confirmation required to proceed     #
# --------------------------------------------------------------------------- #

def test_full_plan_shown_before_any_step_runs(audit, monkeypatch):
    log, _ = audit
    stub = DispatchStub({("services", "status"): _ok(), ("services", "restart"): _ok(),
                         ("packages", "install"): _ok(), ("packages", "info"): _ok()})
    monkeypatch.setattr(registry, "dispatch", stub)

    planner = RecordingPlanner({
        "restart nginx": _pc("services", "restart", {"unit": "nginx"}),
        "install vim": _pc("packages", "install", {"packages": ["vim"]}),
    })

    shown: list[str] = []

    def proceed(plan_text: str) -> bool:
        # HARD PROOF: at confirmation time, the plan is fully rendered and NOT a
        # single step has been dispatched yet.
        shown.append(plan_text)
        assert stub.calls == []
        return True

    captured: list[str] = []
    run = run_plan(
        "restart nginx and install vim", "snap", registry, CTX, log,
        planner=planner, proceed=proceed, confirmer=ApproveConfirmer(),
        sink=captured.append,
    )

    assert run.is_compound is True
    assert run.confirmed is True
    # The rendered plan lists BOTH steps and was emitted to the sink.
    assert captured and captured[0] == run.plan_text
    assert "1." in run.plan_text and "2." in run.plan_text
    assert shown and shown[0] == run.plan_text
    # Only AFTER confirmation did the steps run, in order.
    assert stub.count("services", "restart") == 1
    assert stub.count("packages", "install") == 1


def test_declining_the_plan_runs_nothing(audit, monkeypatch):
    log, _ = audit
    stub = DispatchStub({})
    monkeypatch.setattr(registry, "dispatch", stub)
    planner = RecordingPlanner({
        "restart nginx": _pc("services", "restart", {"unit": "nginx"}),
        "install vim": _pc("packages", "install", {"packages": ["vim"]}),
    })
    run = run_plan(
        "restart nginx and install vim", "snap", registry, CTX, log,
        planner=planner, proceed=lambda _t: False, confirmer=ApproveConfirmer(),
    )
    assert run.is_compound is True
    assert run.confirmed is False
    assert run.steps == []
    assert stub.calls == []  # nothing executed


def test_default_denies_when_no_proceed_supplied(audit, monkeypatch):
    log, _ = audit
    stub = DispatchStub({})
    monkeypatch.setattr(registry, "dispatch", stub)
    planner = RecordingPlanner({
        "restart nginx": _pc("services", "restart", {"unit": "nginx"}),
        "install vim": _pc("packages", "install", {"packages": ["vim"]}),
    })
    run = run_plan(
        "restart nginx and install vim", "snap", registry, CTX, log,
        planner=planner,  # no proceed / no confirmer -> deny by default
    )
    assert run.confirmed is False
    assert stub.calls == []


# --------------------------------------------------------------------------- #
# 3. Ordered multi-step execution through the spine + audit (I4)                #
# --------------------------------------------------------------------------- #

def test_multistep_executes_in_order_and_audits_each(audit, monkeypatch):
    log, path = audit
    stub = DispatchStub({
        ("services", "restart"): _ok(), ("services", "status"): _ok(),
        ("packages", "install"): _ok(), ("packages", "info"): _ok(),
    })
    monkeypatch.setattr(registry, "dispatch", stub)
    planner = RecordingPlanner({
        "restart nginx": _pc("services", "restart", {"unit": "nginx"}),
        "install vim": _pc("packages", "install", {"packages": ["vim"]}),
    })

    run = run_plan(
        "restart nginx and install vim", "snap", registry, CTX, log,
        planner=planner, proceed=_always_yes, confirmer=ApproveConfirmer(),
        context=FakeContext(), tier="t", retry_max=0,
    )

    assert run.completed is True and run.halted is False
    assert [r.command for r in run.steps] == [
        "systemctl restart nginx", "dnf install vim",
    ]
    # write ops ran in order (restart before install).
    write_ops = [(t, o) for (t, o, _) in stub.calls if o in ("restart", "install")]
    assert write_ops == [("services", "restart"), ("packages", "install")]
    # I4: the audit file holds exactly the number of records run_plan counted.
    assert len(list(iter_records(path))) == run.audit_records
    assert run.audit_records > 0


# --------------------------------------------------------------------------- #
# 4. Mid-plan verification failure -> bounded re-plan of the REMAINDER ONLY     #
# --------------------------------------------------------------------------- #

def test_midplan_verification_failure_replans_remainder(audit, monkeypatch):
    log, _ = audit
    # Step 2 (install vim) fails verification: the package still reads ABSENT
    # after install (info -> exit 1). With retry_max=0 that is an immediate
    # EXHAUSTED/escalation, which invalidates the REMAINDER (step 3).
    stub = DispatchStub({
        ("services", "restart"): _ok(), ("services", "status"): _ok(),
        ("packages", "install"): _ok(), ("packages", "info"): _fail(),
        ("services", "enable"): _ok(),
    })
    monkeypatch.setattr(registry, "dispatch", stub)
    planner = RecordingPlanner({
        "restart nginx": _pc("services", "restart", {"unit": "nginx"}),
        "install vim": _pc("packages", "install", {"packages": ["vim"]}),
        "enable nginx": _pc("services", "enable", {"unit": "nginx"}),
    })

    run = run_plan(
        "restart nginx and install vim and enable nginx", "snap", registry, CTX, log,
        planner=planner, proceed=_always_yes, confirmer=ApproveConfirmer(),
        context=FakeContext(), tier="t", retry_max=0, max_replans=1,
    )

    # Exactly one bounded re-plan happened.
    assert run.replans == 1
    # The planner was called twice: first with the FULL plan, then with the
    # REMAINDER ONLY (just the trailing clause) — not the whole request.
    assert planner.calls[0] == ["restart nginx", "install vim", "enable nginx"]
    assert planner.calls[1] == ["enable nginx"]
    # The already-run prefix is intact: step 1 verified, step 2 invalidated.
    assert run.steps[0].verify_status is VerifyStatus.VERIFIED
    assert run.steps[1].invalidated is True
    # After the re-plan, the remainder ran and the plan completed.
    assert run.steps[2].command == "systemctl enable nginx"
    assert run.steps[2].ran is True
    assert run.halted is False and run.completed is True


def test_replan_budget_is_bounded_and_halts(audit, monkeypatch):
    log, _ = audit
    # Same failing step-1 verification, but NO re-plan budget: execution must
    # HALT rather than silently auto-continuing into the remainder.
    stub = DispatchStub({
        ("packages", "install"): _ok(), ("packages", "info"): _fail(),
        ("services", "restart"): _ok(), ("services", "status"): _ok(),
    })
    monkeypatch.setattr(registry, "dispatch", stub)
    planner = RecordingPlanner({
        "install vim": _pc("packages", "install", {"packages": ["vim"]}),
        "restart nginx": _pc("services", "restart", {"unit": "nginx"}),
    })

    run = run_plan(
        "install vim and restart nginx", "snap", registry, CTX, log,
        planner=planner, proceed=_always_yes, confirmer=ApproveConfirmer(),
        context=FakeContext(), tier="t", retry_max=0, max_replans=0,
    )

    assert run.halted is True and run.completed is False
    assert run.replans == 0
    assert planner.calls == [["install vim", "restart nginx"]]  # never re-planned
    # Only the failing first step ran; the remainder was NOT auto-continued.
    assert len(run.steps) == 1
    assert stub.count("services", "restart") == 0


# --------------------------------------------------------------------------- #
# 5. Destructive steps gate INDIVIDUALLY                                        #
# --------------------------------------------------------------------------- #

def test_destructive_step_gates_individually_with_typed_confirmation(audit, monkeypatch):
    log, _ = audit
    stub = DispatchStub({
        ("services", "restart"): _ok(), ("services", "status"): _ok(),
        ("packages", "remove"): _ok(), ("packages", "info"): _fail(),  # absent => removed
    })
    monkeypatch.setattr(registry, "dispatch", stub)
    planner = RecordingPlanner({
        "restart nginx": _pc("services", "restart", {"unit": "nginx"}),
        "remove vim": _pc("packages", "remove", {"packages": ["vim"]}, OpClass.DESTRUCTIVE),
    })
    confirmer = ApproveConfirmer()

    run = run_plan(
        "restart nginx and remove vim", "snap", registry, CTX, log,
        planner=planner, proceed=_always_yes, confirmer=confirmer,
        context=FakeContext(), tier="t", retry_max=0,
    )

    # The write took a PLAIN confirm; the destructive step took its OWN typed
    # confirmation — the gate is resolved per step, keyed on the classifier.
    assert confirmer.confirms == ["systemctl restart nginx"]
    assert confirmer.typed == ["DESTROY"]
    assert stub.count("services", "restart") == 1
    assert stub.count("packages", "remove") == 1
    assert run.steps[1].op_class is OpClass.DESTRUCTIVE
    assert run.steps[1].gate == "confirm_typed"


def test_declining_one_destructive_step_does_not_stop_the_plan(audit, monkeypatch):
    log, _ = audit
    stub = DispatchStub({
        ("packages", "remove"): _ok(), ("packages", "info"): _fail(),
        ("services", "restart"): _ok(), ("services", "status"): _ok(),
    })
    monkeypatch.setattr(registry, "dispatch", stub)
    planner = RecordingPlanner({
        "remove vim": _pc("packages", "remove", {"packages": ["vim"]}, OpClass.DESTRUCTIVE),
        "restart nginx": _pc("services", "restart", {"unit": "nginx"}),
    })
    confirmer = SelectiveConfirmer()  # denies the typed (destructive) gate

    run = run_plan(
        "remove vim and restart nginx", "snap", registry, CTX, log,
        planner=planner, proceed=_always_yes, confirmer=confirmer,
        context=FakeContext(), tier="t", retry_max=0,
    )

    # Destructive step declined -> NOT run; the plan still continues to step 2.
    assert stub.count("packages", "remove") == 0
    assert run.steps[0].ran is False and run.steps[0].status == "not run"
    assert stub.count("services", "restart") == 1
    assert run.steps[1].ran is True
    assert run.halted is False


# --------------------------------------------------------------------------- #
# 6. Unresolved clause is audited as exactly one miss (I4)                      #
# --------------------------------------------------------------------------- #

def test_unresolved_step_is_audited_as_one_miss(audit, monkeypatch):
    log, path = audit
    stub = DispatchStub({("services", "restart"): _ok(), ("services", "status"): _ok()})
    monkeypatch.setattr(registry, "dispatch", stub)
    planner = RecordingPlanner({
        # first clause resolves to nothing -> a miss
        "do something vague": None,
        "restart nginx": _pc("services", "restart", {"unit": "nginx"}),
    })

    run = run_plan(
        "do something vague and restart nginx", "snap", registry, CTX, log,
        planner=planner, proceed=_always_yes, confirmer=ApproveConfirmer(),
        context=FakeContext(), tier="t", retry_max=0, max_replans=1,
    )

    assert run.steps[0].gate == "unresolved"
    assert run.steps[0].ran is False
    # I4: the file record count matches the counted total (miss included).
    assert len(list(iter_records(path))) == run.audit_records


# --------------------------------------------------------------------------- #
# render_plan is I2-clean                                                        #
# --------------------------------------------------------------------------- #

def test_render_plan_is_i2_clean():
    steps = [
        PlanStep(index=0, clause="restart nginx",
                 call=_pc("services", "restart", {"unit": "nginx"})),
        PlanStep(index=1, clause="do a thing", call=None,
                 reason="could not be turned into a single operation"),
    ]
    text = render_plan(steps)
    banned = ("ai", "llm", "model", "agent", "gpt", "language model")
    low = text.lower()
    for word in banned:
        assert word not in low
    assert "systemctl restart nginx" in text
    assert "1." in text and "2." in text
