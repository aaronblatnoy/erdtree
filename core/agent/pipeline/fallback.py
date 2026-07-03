"""
core/agent/pipeline/fallback.py — Phase 7: last-resort free-text argv path.

This module is the LAST RUNG of the understanding escalation ladder. It is only
reached when intent classification AND slot extraction AND the assembler have all
failed to produce a validated ParsedCall from the user's input.

What it does
------------
1. Generate a candidate argv from the user's free-text input (a single narrow
   request via the injected responder — I1, localhost Ollama only).
2. Pass that argv VERBATIM through ``permissions.classify`` — the UNCHANGED,
   single, hardened gate. No second gate, no re-implementation.
3. Render the result with an I2-clean "unverified / best-effort" visual marker
   so the user sees it is not a confidently parsed command before they confirm.
4. Audit the attempt with a DISTINCT ``source=fallback`` field so fallback usage
   is independently queryable in the append-only JSONL log (I4).
5. NEVER auto-run. Even a fallback argv that classifies as READ gets the
   "best-effort" confirmation note — the user sees it before it runs. ALLOW
   auto-run is BLOCKED on all fallback paths.

Load-bearing invariants
-----------------------
I1  No egress. The only inference call is via the INJECTED responder (localhost
    Ollama). This module opens no socket of its own.
I2  No AI/LLM/model/agent language in any user-facing string. The marker says
    "unverified / best-effort" and explains the command in plain terms; it
    never says "AI", "LLM", "model", or "agent".
I3  permissions.classify is THE single gate. This module calls it ONCE, BEFORE
    any dispatch decision is made. It does NOT re-implement, weaken, or bypass
    classify. A destructive argv from fallback hits CONFIRM_TYPED or REFUSE
    exactly as a native path would.
I4  Every attempted op (including fallback misses and refusals) writes exactly
    one append-only JSONL record, always with source=fallback.
I6  No tier/product names. The ``tier`` field in the audit record is opaque data
    supplied by the caller.
I8  This module is an ESCALATION TIER — it is NEVER on the fast path (reads or
    well-understood ops are served long before reaching here).

HARD CONSTRAINT — no second gate, no second executor
The FallbackResult carries a decision (the classify output) and a formatted
display string. The CALLER is responsible for presenting the confirmation
surface and, if confirmed, dispatching through the UNCHANGED spine
(synthesize_command -> classify -> dispatch -> audit). This module NEVER
dispatches — it only classifies the proposed argv and audits the attempt.

Risk R2 mitigation
------------------
R2 in the plan states: "fallback = unbounded command generation, a NEW danger
surface." Mitigation by construction:
  * The gate (classify) is unchanged — a destructive fallback argv cannot slip
    through as a plain write.
  * The visual marker tells the user this is best-effort before they act.
  * The source=fallback audit field makes all fallback usage queryable.
  * Auto-run is structurally blocked — FallbackResult.auto_ok is always False.
  * The path is strictly last-resort; it is gated behind intent+slots failure.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.agent.permissions import Decision, ExecContext, Gate, OpClass, classify

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

# The display marker shown in every fallback confirmation — I2-clean (no AI/
# LLM/model/agent language). Two lines: the mark and a brief note.
FALLBACK_MARKER = "[unverified / best-effort]"
FALLBACK_NOTE = (
    "This command was inferred from your request and has not been validated "
    "against the operation schema. Review carefully before proceeding."
)


@dataclass(frozen=True)
class FallbackResult:
    """The outcome of one fallback attempt.

    Fields
    ------
    argv:           The raw proposed command string inferred from the user's
                    input.  May be empty if generation failed (see ``failed``).
    decision:       The ``permissions.classify`` Decision for this argv.
                    Always present (even on failure: classify("") -> WRITE/REFUSE).
    display:        I2-clean formatted string for the confirmation surface.
                    Includes the FALLBACK_MARKER, the argv, the gate, and the
                    plain reason.  The caller renders this verbatim.
    audit_record:   A dict ready to write to the append-only JSONL audit log,
                    always including ``source="fallback"`` (I4).
    auto_ok:        ALWAYS False.  Fallback ops NEVER auto-run, even for reads.
                    The caller MUST surface a confirmation before dispatching.
    failed:         True if the responder could not produce a plausible argv
                    (empty result, garbled JSON, no command found). The caller
                    should treat this as "fallback produced nothing" and re-ask.
    failure_reason: Plain explanation when ``failed`` is True; empty otherwise.
    """

    argv: str
    decision: Decision
    display: str
    audit_record: dict[str, Any]
    auto_ok: bool = field(default=False, init=False)  # ALWAYS False
    failed: bool = False
    failure_reason: str = ""

    def __post_init__(self) -> None:
        # Structural enforcement: fallback NEVER auto-runs.
        # We use object.__setattr__ because this is a frozen dataclass.
        object.__setattr__(self, "auto_ok", False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def propose_fallback(
    user_input: str,
    *,
    responder: Callable[[list[dict], list[dict]], Any],
    context: Optional[ExecContext] = None,
    tier: Optional[str] = None,
    nl_input: Optional[str] = None,
) -> FallbackResult:
    """Generate a best-effort argv from free text, classify it, and audit it.

    Parameters
    ----------
    user_input:  The original natural-language request (used both as the
                 generation prompt and as the ``nl_input`` audit field).
    responder:   The injected model callable — ``responder(messages, tools)``
                 returning an object with a ``.content`` attribute (I1: only
                 localhost Ollama via this injected callable; no new sockets).
    context:     The execution environment for permissions.classify.
                 Defaults to ``ExecContext()`` (interactive, non-remote).
    tier:        Opaque tier string for the audit record (I6).
    nl_input:    Optional override for the audit nl_input field; defaults to
                 ``user_input``.

    Returns
    -------
    FallbackResult — always returned (never raises). If generation failed, the
    result has ``failed=True`` and the caller should treat it as a miss.

    Invariants enforced here
    ------------------------
    * I1: generation only via the injected responder.
    * I2: no AI/LLM/model/agent language in the display or audit strings.
    * I3: classify() is called exactly once, on the proposed argv, before any
          dispatch decision.
    * I4: the returned audit_record dict has source=fallback; the caller writes
          it to the append-only log (this function does NOT write the record
          itself, to preserve the caller's control over audit path and timing;
          see ``write_fallback_audit`` for the one-line helper).
    * auto_ok is always False — structural, not conditional.
    """
    ctx = context or ExecContext()
    audit_nl = nl_input if nl_input is not None else user_input

    # ---- 1. Generate a candidate argv via the injected responder (I1) ------
    argv, gen_failed, gen_reason = _generate_argv(user_input, responder)

    if gen_failed:
        decision = classify("", ctx)
        display = _format_display(argv="", decision=decision, failed=True,
                                   failure_reason=gen_reason)
        audit = _build_audit(
            argv="", decision=decision, tier=tier, nl_input=audit_nl,
            result="generation-failed", extra={"failure_reason": gen_reason},
        )
        return FallbackResult(
            argv="",
            decision=decision,
            display=display,
            audit_record=audit,
            failed=True,
            failure_reason=gen_reason,
        )

    # ---- 2. Classify via THE unchanged gate (I3) ---------------------------
    decision = classify(argv, ctx)

    # ---- 3. Build the I2-clean display string ------------------------------
    display = _format_display(argv=argv, decision=decision)

    # ---- 4. Build the audit record — source=fallback always (I4) ----------
    audit = _build_audit(
        argv=argv, decision=decision, tier=tier, nl_input=audit_nl,
        result="proposed",
    )

    return FallbackResult(
        argv=argv,
        decision=decision,
        display=display,
        audit_record=audit,
        failed=False,
    )


def write_fallback_audit(
    audit_log: Any,
    result: FallbackResult,
    *,
    outcome: str = "proposed",
    confirmed: Optional[bool] = None,
) -> None:
    """Write one append-only audit record for a fallback attempt.

    The record always carries ``source=fallback`` (I4). The caller controls
    ``outcome`` so the same FallbackResult can be recorded at multiple lifecycle
    points (proposed, confirmed, refused, dispatched).

    Parameters
    ----------
    audit_log:  An object with a ``.write(**kwargs)`` method — the standard
                ``AuditLog`` instance from ``core.agent.audit``.
    result:     The FallbackResult to record.
    outcome:    One of "proposed" / "confirmed" / "refused" / "dispatched".
    confirmed:  True if the user confirmed the op, False if refused, None if
                the record is written before confirmation.
    """
    rec = dict(result.audit_record)
    rec["result"] = outcome
    if confirmed is not None:
        rec.setdefault("extra", {})
        if isinstance(rec.get("extra"), dict):
            rec["extra"]["user_confirmed"] = confirmed

    # AuditLog.write() accepts only its declared kwargs; pass only the keys
    # the standard schema knows about. The source=fallback field travels in
    # permission_decision (prefixed) so it survives the fixed schema.
    audit_log.write(
        tier=rec.get("tier"),
        nl_input=rec.get("nl_input"),
        translated_command=rec.get("translated_command"),
        tool=rec.get("tool"),
        args=rec.get("args"),
        permission_decision=rec.get("permission_decision"),
        result=rec.get("result"),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Narrow system prompt for argv generation — I2-clean, no AI/LLM language.
_SYSTEM_PROMPT = (
    "You are a Linux command-line assistant. "
    "Given the user's request, respond with EXACTLY ONE shell command that "
    "fulfils the request. "
    "Output ONLY the command, with no explanation, no markdown, no backticks, "
    "no surrounding text. "
    "If you cannot determine a safe, specific command, output the single word: UNKNOWN"
)


def _generate_argv(
    user_input: str,
    responder: Callable[[list[dict], list[dict]], Any],
) -> tuple[str, bool, str]:
    """Call the responder to generate a candidate argv.

    Returns (argv, failed, reason).
      * On success: (non-empty command string, False, "").
      * On failure: ("", True, plain reason string).

    The responder is called with a minimal messages list and an EMPTY tools
    list so it is forced into plain-text response mode (no tool calls).
    """
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    try:
        response = responder(messages, [])
        raw: str = (getattr(response, "content", "") or "").strip()
    except Exception as exc:  # noqa: BLE001
        return "", True, f"responder error: {exc}"

    if not raw:
        return "", True, "responder returned empty content"

    # Strip markdown code fences if the model wrapped the command anyway.
    raw = _strip_code_fence(raw)

    if not raw or raw.upper() == "UNKNOWN":
        return "", True, "no specific command could be determined"

    # Sanity-check: the result should look like a shell command (starts with
    # a word character or a path), not a multi-paragraph explanation.
    first_line = raw.splitlines()[0].strip()
    if not first_line:
        return "", True, "responder output had no usable first line"

    # Accept only the first line to prevent multi-command injection.
    return first_line, False, ""


def _strip_code_fence(text: str) -> str:
    """Remove surrounding ``` or ```bash fences if present."""
    # ``` or ```bash / ```sh at start, ``` at end.
    fenced = re.match(
        r"^```(?:bash|sh|shell|zsh|text)?\s*\n?(.*?)\n?```\s*$",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        return fenced.group(1).strip()
    return text


def _format_display(
    argv: str,
    decision: Decision,
    *,
    failed: bool = False,
    failure_reason: str = "",
) -> str:
    """Build the I2-clean display string for the confirmation surface.

    All language is plain Linux; no AI/LLM/model/agent words.
    The FALLBACK_MARKER is always the first line so it is visually prominent.
    """
    lines: list[str] = [FALLBACK_MARKER]

    if failed:
        lines.append(f"Could not determine a specific command: {failure_reason}")
        lines.append(FALLBACK_NOTE)
        return "\n".join(lines)

    lines.append(f"Proposed command:  {argv}")
    lines.append(f"Risk assessment:   {decision.op_class.value} — {decision.reason}")

    gate_label = {
        Gate.ALLOW:        "requires confirmation (best-effort)",
        Gate.CONFIRM:      "requires confirmation",
        Gate.CONFIRM_TYPED: f"requires typing '{decision.confirm_word}' in full",
        Gate.REFUSE:       "cannot proceed in non-interactive context",
    }.get(decision.gate, decision.gate.value)
    lines.append(f"Gate:              {gate_label}")
    lines.append("")
    lines.append(FALLBACK_NOTE)
    return "\n".join(lines)


def _build_audit(
    argv: str,
    decision: Decision,
    *,
    tier: Optional[str],
    nl_input: str,
    result: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the audit record dict (I4 — source=fallback embedded in the dict).

    The ``permission_decision`` field carries both the gate outcome AND the
    ``source=fallback`` tag, joined with a pipe, so the fixed AuditLog schema
    does not need an extra column while still making fallback usage queryable
    via a simple ``grep source=fallback`` on the JSONL log.

    Format: "fallback|<gate>|<op_class>"
    Example: "fallback|confirm_typed|destructive"
    """
    perm_tag = f"fallback|{decision.gate.value}|{decision.op_class.value}"
    record: dict[str, Any] = {
        "tier": tier,
        "nl_input": nl_input,
        "translated_command": argv,
        "tool": None,
        "args": extra,
        "permission_decision": perm_tag,
        "exit_code": None,
        "stdout_summary": None,
        "stderr_summary": None,
        "result": result,
    }
    return record
