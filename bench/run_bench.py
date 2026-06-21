"""
bench/run_bench.py — Tool-call validity benchmark runner.

WHAT THIS MEASURES (decision #2, the #1 technical bet)
-----------------------------------------------------
The **tool-call validity rate**: across the action turns in ``bench/cases/``,
what fraction of model turns emit a VALID, parseable tool call in the frozen
protocol (docs/decisions/0002-tool-call-protocol.md §2/§5). See bench/README.md
for the frozen VALID/MISS definition — this runner is the executable form of it.

The VALID/MISS predicate is NOT re-derived here: it is delegated to
``core.agent.router.Router`` (the single source of truth for the contract). A
turn is VALID iff ``RouterResult.is_valid_action`` is True. A MISS is anything
else — including prose where a tool was required (the dominant 3B failure mode),
unknown tool name, or unparseable / schema-invalid arguments. A bad call is a
MISS, never a crash.

ENGLISH negative-control turns (``turn_type == "english"``) are scored
separately and are NOT part of the validity denominator (bench/README.md: "Only
action turns count toward the denominator"). The runner reports whether each
negative control correctly stayed English.

THE MODEL IS INJECTED (the dev-host seam)
-----------------------------------------
This runner never imports a live model. It takes a ``responder`` callable:

    responder(case, messages, tools) -> AssembledResponse-like

where the returned object exposes ``.content`` (str) and ``.tool_calls``
(list of ``{"id","name","arguments"}`` dicts), exactly the
``core.model.ollama.AssembledResponse`` shape. This is what makes the runner
UNIT-TESTABLE on the macOS dev host: tests pass a ``responder`` backed by
recorded / mock outputs (see tests/test_run_bench.py and
bench/fixtures/mock_outputs.json).

The LIVE measurement (a ``responder`` backed by a real local Ollama across base
Qwen 14B / 7B / 3B) is **DEFERRED-TO-MOSSAD** — :func:`ollama_responder` builds
that responder but it requires a running model. This module NEVER fabricates a
rate; with no responder it refuses to invent numbers.

I1  No egress here. The runner only talks to whatever ``responder`` it is given;
    the live responder routes through ``core.model.ollama`` which itself asserts
    localhost (I1).
I2  No AI/LLM/model/agent language in any user-facing string the runner prints
    about the SYSTEM under test. (Benchmark-internal field names like "model
    size" describe the thing being measured, not user-facing product copy.)
I6  No tier/product names hardcoded: model-size buckets are whatever the caller
    labels its responder runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Protocol

# Make ``core`` importable when run as ``python bench/run_bench.py`` from repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.agent.router import Router, TurnKind  # noqa: E402
from core.tools import registry as default_registry  # noqa: E402

# Import the tool modules so they self-register on the default registry.
import core.tools.services  # noqa: E402,F401
import core.tools.packages  # noqa: E402,F401
import core.tools.logs  # noqa: E402,F401


CASES_DIR = Path(__file__).resolve().parent / "cases"


# --------------------------------------------------------------------------- #
# Case + result types                                                          #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BenchCase:
    """One scenario loaded from cases/*.json (schema in bench/README.md)."""

    id: str
    domain: str
    turn_type: str            # "action" (tool expected) | "english" (neg control)
    system_context: str
    user: str
    tools: list[str]
    expect: dict[str, Any]
    notes: str = ""

    @property
    def is_action(self) -> bool:
        return self.turn_type == "action"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BenchCase":
        return cls(
            id=d["id"],
            domain=d.get("domain", ""),
            turn_type=d.get("turn_type", "action"),
            system_context=d.get("system_context", ""),
            user=d.get("user", ""),
            tools=list(d.get("tools", [])),
            expect=dict(d.get("expect", {})),
            notes=d.get("notes", ""),
        )


@dataclass
class CaseResult:
    """The scored outcome of running one case once."""

    case_id: str
    turn_type: str
    kind: str                 # TurnKind value the router returned
    valid: bool               # is_valid_action (action turns only meaningful)
    stayed_english: bool      # for english turns: did it correctly stay English
    miss_reasons: list[str] = field(default_factory=list)
    # Whether the emitted call (if any) matched the case's expected tool +
    # arguments_contains subset. Informational only — NOT part of validity.
    intent_match: Optional[bool] = None


@dataclass
class BenchReport:
    """Aggregate over a full run of all cases (one model-size bucket)."""

    label: str                # e.g. "mock", "qwen-7b" — caller-supplied
    results: list[CaseResult] = field(default_factory=list)

    # ---- action-turn validity (the headline number) ----
    @property
    def action_results(self) -> list[CaseResult]:
        return [r for r in self.results if r.turn_type == "action"]

    @property
    def total_action_turns(self) -> int:
        return len(self.action_results)

    @property
    def valid_action_turns(self) -> int:
        return sum(1 for r in self.action_results if r.valid)

    @property
    def validity_rate(self) -> Optional[float]:
        """valid_turns / total_action_turns, or None if no action turns.

        Returns None (NOT 0.0, NOT a fabricated number) when there is nothing
        to measure, so the caller never mistakes "no data" for "0% valid".
        """
        n = self.total_action_turns
        if n == 0:
            return None
        return self.valid_action_turns / n

    # ---- english negative controls ----
    @property
    def english_results(self) -> list[CaseResult]:
        return [r for r in self.results if r.turn_type == "english"]

    @property
    def english_held(self) -> int:
        return sum(1 for r in self.english_results if r.stayed_english)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "validity_rate": self.validity_rate,
            "valid_action_turns": self.valid_action_turns,
            "total_action_turns": self.total_action_turns,
            "english_held": self.english_held,
            "english_total": len(self.english_results),
            "results": [
                {
                    "case_id": r.case_id,
                    "turn_type": r.turn_type,
                    "kind": r.kind,
                    "valid": r.valid,
                    "stayed_english": r.stayed_english,
                    "intent_match": r.intent_match,
                    "miss_reasons": r.miss_reasons,
                }
                for r in self.results
            ],
        }


# --------------------------------------------------------------------------- #
# Responder protocol (the injection seam)                                      #
# --------------------------------------------------------------------------- #

class _AssembledLike(Protocol):
    content: str
    tool_calls: list[dict]


# A responder turns (case, messages, tools) into an assembled model response.
Responder = Callable[[BenchCase, list[dict], list[dict]], _AssembledLike]


# --------------------------------------------------------------------------- #
# Case loading                                                                 #
# --------------------------------------------------------------------------- #

def load_cases(cases_dir: Path = CASES_DIR) -> list[BenchCase]:
    """Load every cases/*.json into a sorted list of BenchCase."""
    cases: list[BenchCase] = []
    for path in sorted(cases_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as fh:
            cases.append(BenchCase.from_dict(json.load(fh)))
    return cases


# --------------------------------------------------------------------------- #
# The runner                                                                   #
# --------------------------------------------------------------------------- #

class BenchRunner:
    """Runs the validity benchmark against an injected responder.

    The runner owns the prompt assembly (advertise the case's tools per 0002 §1)
    and the scoring (delegate VALID/MISS to the Router). It does NOT own the
    model — that is the responder's job — which keeps the whole pipeline
    unit-testable on the dev host.
    """

    def __init__(self, registry=None, router: Optional[Router] = None) -> None:
        reg = registry if registry is not None else default_registry
        self._registry = reg
        self._router = router if router is not None else Router(reg)

    # ------------------------------------------------------------------ #
    # Prompt assembly (advertise the case's tools, 0002 §1)               #
    # ------------------------------------------------------------------ #

    def _tools_for(self, case: BenchCase) -> list[dict]:
        """0002 §1 wire-format tool list for the tools the case advertises.

        Unknown tool names in a case are skipped (the prompt advertises only
        what the registry actually has). This mirrors the REPL/main path.
        """
        from core.agent.prompt import build_tool_list

        schemas = self._router.advertised_schemas(case.tools)
        return build_tool_list(schemas)

    def _messages_for(self, case: BenchCase) -> list[dict]:
        """Assemble the OpenAI messages array for one case (0002 §1).

        Uses the prompt layer so the live responder sees exactly what the REPL
        would send. The case's ``system_context`` is the injected I5 snapshot
        stub.
        """
        from core.agent.prompt import assemble

        messages, _ = assemble(
            user_input=case.user,
            snapshot_text=case.system_context,
            history=[],
            tier_prompt="",
            tools=[],
        )
        return messages

    # ------------------------------------------------------------------ #
    # Scoring one case                                                    #
    # ------------------------------------------------------------------ #

    def score_one(self, case: BenchCase, response: _AssembledLike) -> CaseResult:
        """Apply the frozen VALID/MISS predicate to one model response.

        VALID/MISS is decided ENTIRELY by the Router (single source of truth).
        ``response`` is any object with ``.content`` and ``.tool_calls``
        (AssembledResponse shape).
        """
        verdict = self._router.route(
            content=getattr(response, "content", "") or "",
            tool_calls=list(getattr(response, "tool_calls", []) or []),
        )

        kind = verdict.kind.value
        valid = verdict.is_valid_action
        stayed_english = verdict.kind is TurnKind.ENGLISH
        miss_reasons = [m.reason for m in verdict.misses]

        intent_match: Optional[bool] = None
        if valid and case.is_action:
            intent_match = _intent_matches(case, verdict.calls[0])

        return CaseResult(
            case_id=case.id,
            turn_type=case.turn_type,
            kind=kind,
            valid=valid,
            stayed_english=stayed_english,
            miss_reasons=miss_reasons,
            intent_match=intent_match,
        )

    # ------------------------------------------------------------------ #
    # Full run                                                            #
    # ------------------------------------------------------------------ #

    def run(
        self,
        cases: Iterable[BenchCase],
        responder: Responder,
        *,
        label: str = "run",
        repeats: int = 1,
    ) -> BenchReport:
        """Run every case ``repeats`` times through ``responder`` and score.

        ``repeats`` > 1 supports the README's "run each case M times
        (temperature-varied) to get a stable rate" — every repeat is an
        independent scored turn in the report.
        """
        report = BenchReport(label=label)
        for case in cases:
            tools = self._tools_for(case)
            messages = self._messages_for(case)
            for _ in range(max(1, repeats)):
                response = responder(case, messages, tools)
                report.results.append(self.score_one(case, response))
        return report


# --------------------------------------------------------------------------- #
# Intent subset check (informational; NOT part of validity)                    #
# --------------------------------------------------------------------------- #

def _intent_matches(case: BenchCase, call) -> bool:
    """True iff the parsed call hits the case's expected tool + args subset.

    ``arguments_contains`` is a SUBSET check (bench/README.md). It does not
    change the validity score; it only sanity-confirms the model targeted the
    right thing.
    """
    exp = case.expect or {}
    exp_tool = exp.get("tool")
    if exp_tool is not None and call.tool != exp_tool:
        return False
    contains = exp.get("arguments_contains") or {}
    merged = dict(call.args)
    merged["operation"] = call.operation
    for key, want in contains.items():
        if merged.get(key) != want:
            return False
    return True


# --------------------------------------------------------------------------- #
# Responders                                                                   #
# --------------------------------------------------------------------------- #

def recorded_responder(recordings: dict[str, dict]) -> Responder:
    """Build a responder over a dict of recorded outputs keyed by case id.

    Each recording is ``{"content": str, "tool_calls": [...] }`` — the
    AssembledResponse shape. This is the dev-host / unit-test responder: feed it
    recorded model outputs and the runner scores them exactly as it would score
    a live stream.

    A case id missing from ``recordings`` yields an empty English response (a
    MISS for an action turn) rather than raising — so a partial recording set
    still produces an honest (lower) number instead of crashing.
    """

    class _Recorded:
        def __init__(self, content: str, tool_calls: list[dict]) -> None:
            self.content = content
            self.tool_calls = tool_calls

    def _respond(case: BenchCase, messages: list[dict], tools: list[dict]) -> _Recorded:
        rec = recordings.get(case.id)
        if rec is None:
            return _Recorded("", [])
        return _Recorded(rec.get("content", "") or "", list(rec.get("tool_calls", []) or []))

    return _respond


def ollama_responder(config) -> Responder:
    """Build a responder backed by a LIVE local Ollama client (I1).

    DEFERRED-TO-MOSSAD: this requires a running Ollama with the pinned model.
    It is provided so the live measurement is a one-liner on the GPU box; it is
    NOT exercised on the dev host and this module never fabricates the resulting
    rate. ``config`` is any object with ``.base_url`` / ``.model``
    (core.model.ollama.TierConfig); the client asserts localhost on construction.
    """
    from core.model.ollama import OllamaClient

    client = OllamaClient(config)

    def _respond(case: BenchCase, messages: list[dict], tools: list[dict]):
        # chat() returns an AssembledResponse with .content / .tool_calls.
        return client.chat(messages, tools=tools, tool_choice="auto")

    return _respond


# --------------------------------------------------------------------------- #
# Reporting                                                                    #
# --------------------------------------------------------------------------- #

def format_report(report: BenchReport, *, target: float = 0.995) -> str:
    """Render a human-readable summary. No AI/LLM language in the copy.

    The headline is the validity rate over action turns; ``target`` is the SC2
    ship gate (>= 99.5%). For a recorded/mock run the number is real for that
    recording set — it is honestly labelled as such by the caller's ``label``.
    """
    lines: list[str] = []
    lines.append(f"Tool-call validity benchmark — run '{report.label}'")
    rate = report.validity_rate
    if rate is None:
        lines.append("  validity: n/a (no action turns measured)")
    else:
        verdict = "MEETS TARGET" if rate >= target else "BELOW TARGET"
        lines.append(
            f"  validity: {rate * 100:.1f}%  "
            f"({report.valid_action_turns}/{report.total_action_turns} action turns)  "
            f"[target {target * 100:.1f}% — {verdict}]"
        )
    lines.append(
        f"  english controls held: {report.english_held}/{len(report.english_results)}"
    )
    # Per-miss detail so failures are loud, not hidden.
    for r in report.results:
        if r.turn_type == "action" and not r.valid:
            reasons = ", ".join(r.miss_reasons) or "no-tool-call"
            lines.append(f"    MISS  {r.case_id}: {r.kind} ({reasons})")
        elif r.turn_type == "english" and not r.stayed_english:
            lines.append(f"    LEAK  {r.case_id}: expected English, got {r.kind}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_bench",
        description="Tool-call validity benchmark (docs/decisions/0002).",
    )
    parser.add_argument(
        "--recordings",
        type=str,
        default=None,
        help="Path to a JSON file of recorded outputs keyed by case id "
             "(the dev-host / offline path). Without this AND without --live, "
             "the runner refuses to invent a rate.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use a LIVE local Ollama responder (DEFERRED-TO-MOSSAD; needs a "
             "running model on the GPU box).",
    )
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument(
        "--model",
        default=None,
        help="Pinned model tag for --live (never ':latest').",
    )
    parser.add_argument("--label", default=None)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args(argv)

    cases = load_cases()
    runner = BenchRunner()

    if args.recordings:
        with open(args.recordings, "r", encoding="utf-8") as fh:
            recordings = json.load(fh)
        responder = recorded_responder(recordings)
        label = args.label or "recorded"
    elif args.live:
        if not args.model:
            parser.error("--live requires --model (a pinned tag, never ':latest').")
        from core.model.ollama import TierConfig

        config = TierConfig(args.base_url, args.model)
        responder = ollama_responder(config)
        label = args.label or args.model
    else:
        # HONESTY GATE: with neither a recording set nor a live model there is
        # nothing real to measure. We refuse to print a fabricated rate.
        print(
            "No responder selected. Pass --recordings <file> for an offline run, "
            "or --live --model <tag> for a live run. "
            "(The live run is deferred to the GPU box; this host has no model.)",
            file=sys.stderr,
        )
        return 2

    report = runner.run(cases, responder, label=label, repeats=args.repeats)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
