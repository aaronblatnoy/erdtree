"""
core/agent/pipeline/verify.py — Phase 6: deterministic post-exec verification
with op-class-keyed bounded retry.

After a write/destructive op has run through the spine (synthesize_command ->
permissions.classify -> registry.dispatch -> AuditLog), this module CONFIRMS the
change actually landed by running the tool's OWN READ op through the SAME spine
(classify -> ALLOW -> dispatch -> audit) and comparing the observed state to the
intended state. If the state does not match, the RETRY POLICY — keyed on the
operation's risk class (the class the SAME hardened classifier assigns, never the
model's self-declared class) — decides what happens next:

    idempotent (services / packages / files / firewall / users, non-destructive)
        -> auto-retry the write, bounded by ERDTREE_RETRY_MAX (default 2), then stop.
    partial (network)
        -> verify once; NEVER auto-retry (re-running an interface change can sever
           remote access); escalate to a person on mismatch.
    destructive (disk format/partition/wipe/dd, package removal, user lockout/
    delete, firewall panic, interface teardown, and ANYTHING the classifier calls
    DESTRUCTIVE)
        -> verify once; NEVER auto-retry — there is NO retry branch on this path at
           all (auto-repeating mkfs / dd / userdel is catastrophic, R3). Escalate
           to a person with a concrete error.

Load-bearing invariants (identical to the spine this converges on):

  I1  No egress. This module opens no socket; it only calls the injected
      registry's dispatch (the SAME executor) and the injected AuditLog.
  I2  No AI/LLM/model/agent language in any human-facing string.
  I3  permissions.classify is THE single gate. Every op this module runs — every
      verification read AND every idempotent write retry — is classified by the
      SAME classifier before it runs. A verification read that does not land
      Gate.ALLOW is NOT run. This module never re-implements or weakens classify.
  I4  Every attempted op writes exactly one append-only JSONL audit record —
      verification reads, write retries, and refusals all recorded.
  I5  Between idempotent retry attempts the system context is invalidated so the
      next read/write sees reality, not a stale snapshot.
  I6  No tier/product names in this module; the audit `tier` field is opaque.
  I8  Reads are Gate.ALLOW and run with no confirmation, so verification is fast.

HARD SAFETY LINE (R1/R3): this module builds NO second executor and NO second
gate. It reuses ``core.agent.repl.synthesize_command`` (one renderer),
``core.agent.permissions.classify`` (one gate), and the injected registry's
``dispatch`` (one executor). Verification only ever runs ops the registry
DECLARES as READ; the classifier independently confirms Gate.ALLOW before any
such read runs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol

from core.agent import permissions as perm
from core.agent.permissions import Decision, ExecContext, Gate, OpClass
from core.agent.router import ParsedCall
from core.tools import ToolRegistry, ToolResult


# --------------------------------------------------------------------------- #
# Configuration                                                                 #
# --------------------------------------------------------------------------- #

#: Environment knob capping idempotent auto-retries. Read OPAQUELY (never raises);
#: a missing / malformed value degrades to the safe default.
ENV_RETRY_MAX = "ERDTREE_RETRY_MAX"
DEFAULT_RETRY_MAX = 2

#: Tools whose non-destructive writes are safe to repeat (idempotent) — the
#: brainstorm verification table. A destructive op in ANY of these tools is still
#: routed to the NEVER-retry path by the op-class check, which wins.
_IDEMPOTENT_TOOLS = frozenset({"services", "packages", "files", "firewall", "users"})


def _retry_cap(override: Optional[int]) -> int:
    """Resolve the idempotent retry cap: explicit override, else env, else default.

    Read opaquely — a non-integer / negative env value falls back to the default
    rather than raising (a typo must never change safety behavior). The cap is
    floored at 0 (0 => verify only, never retry).
    """
    if override is not None:
        return max(0, override)
    raw = os.environ.get(ENV_RETRY_MAX, "").strip()
    if not raw:
        return DEFAULT_RETRY_MAX
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_RETRY_MAX


# --------------------------------------------------------------------------- #
# Outcome taxonomy                                                              #
# --------------------------------------------------------------------------- #

class RetryPolicy(str, Enum):
    """How a failed verification may be recovered — keyed on op class + tool."""

    IDEMPOTENT = "idempotent"   # safe to repeat -> bounded auto-retry
    PARTIAL = "partial"         # verify only, never auto-retry (network)
    NEVER = "never"             # destructive / default-deny -> NEVER retry, escalate


class VerifyStatus(str, Enum):
    """Final disposition of a verification pass."""

    VERIFIED = "verified"           # first read confirmed the intended state
    RETRIED_OK = "retried_ok"       # confirmed after one or more idempotent retries
    EXHAUSTED = "exhausted"         # idempotent retries hit the cap, still mismatched
    ESCALATED = "escalated"         # destructive/partial mismatch -> a person must act
    UNVERIFIABLE = "unverifiable"   # no READ op exists to check this write against
    READ_ONLY = "read_only"         # the op itself was a read — nothing to verify


class ContextLike(Protocol):
    """The one thing verification needs from the per-turn context (I5)."""

    def invalidate(self) -> None: ...


@dataclass(frozen=True)
class VerifyOutcome:
    """Structured result of one verification pass (for the caller + tests)."""

    status: VerifyStatus
    policy: RetryPolicy
    op_class: OpClass
    verified: bool = False        # True iff the intended state was confirmed
    escalated: bool = False       # True iff a person must intervene
    attempts: int = 0             # write RE-RUNS this pass performed (0 on destructive)
    reads: int = 0                # verification reads this pass performed
    audit_records: int = 0        # total audit records written this pass (I4)
    message: str = ""             # I2-clean, concrete status / error


# --------------------------------------------------------------------------- #
# Retry-policy resolution (keyed on OpClass, then tool)                         #
# --------------------------------------------------------------------------- #

def retry_policy_for(tool: str, op_class: OpClass) -> RetryPolicy:
    """Map (tool, op_class) to a retry policy.

    DESTRUCTIVE wins over everything: a destructive op is NEVER auto-retried,
    regardless of which tool it lives in (R3). Only then do we key on the tool:
    network is PARTIAL (verify, never auto-retry an access-affecting change); the
    idempotent tool set auto-retries; anything else default-denies to NEVER.
    """
    if op_class is OpClass.DESTRUCTIVE:
        return RetryPolicy.NEVER
    if tool == "network":
        return RetryPolicy.PARTIAL
    if tool in _IDEMPOTENT_TOOLS:
        return RetryPolicy.IDEMPOTENT
    # Default-deny: an unrecognised write (e.g. disk mount/unmount, an unknown
    # tool) is not proven safe to repeat -> never auto-retry.
    return RetryPolicy.NEVER


# --------------------------------------------------------------------------- #
# Verifying-read mapping (each write op -> the tool's OWN read op)              #
# --------------------------------------------------------------------------- #
#
# Returns (read_call, expected_present) or None when no READ op can confirm this
# write. `expected_present` is the intended post-state: True  => the read should
# SUCCEED (exit 0) — the resource is present / active; False => the read should
# FAIL (nonzero) — the resource is absent / inactive. This maps exactly onto the
# real Linux read ops: `systemctl is-active`, `rpm -q`, `stat`/`test -e`,
# `firewall-cmd --query-service`, `id <user>`, `ip addr show`.

def _read_call(
    registry: ToolRegistry,
    call_id: str,
    tool: str,
    read_op: str,
    read_args: dict[str, Any],
) -> Optional[ParsedCall]:
    """Build a verifying-read ParsedCall — ONLY if the registry DECLARES read_op
    as READ. This is the hard guard behind "only use ops declared READ in the
    registry for verification": a mis-declared op can never be used to verify.
    """
    if registry.permission_class_for(tool, read_op) is not OpClass.READ:
        return None
    clean = {k: v for k, v in read_args.items() if v is not None and v != ""}
    return ParsedCall(
        call_id=f"verify-{call_id}",
        tool=tool,
        operation=read_op,
        args=clean,
        permission_class=OpClass.READ,
    )


def plan_verification(
    call: ParsedCall, registry: ToolRegistry
) -> Optional[tuple[ParsedCall, bool]]:
    """Choose the verifying read for a write ``call`` (or None if unverifiable)."""
    tool, op, a = call.tool, call.operation, call.args
    cid = call.call_id

    if tool == "services":
        if op in ("start", "restart", "enable", "stop", "disable", "mask"):
            present = op in ("start", "restart", "enable")
            rc = _read_call(registry, cid, tool, "status", {"unit": a.get("unit")})
            return (rc, present) if rc else None

    elif tool == "packages":
        # install/update -> package should be present (rpm -q). remove is
        # DESTRUCTIVE (never retried) but we still confirm absence + escalate.
        if op in ("install", "update", "remove"):
            pkgs = a.get("packages")
            pkg = ""
            if isinstance(pkgs, list) and pkgs:
                pkg = str(pkgs[0])
            elif isinstance(pkgs, str):
                pkg = pkgs
            present = op != "remove"
            rc = _read_call(registry, cid, tool, "info", {"package": pkg})
            return (rc, present) if rc else None

    elif tool == "files":
        if op in ("copy", "move", "mkdir", "write", "chmod", "chown", "remove"):
            path = a.get("dst") if op in ("copy", "move") else a.get("path")
            present = op != "remove"
            rc = _read_call(registry, cid, tool, "stat", {"path": path})
            return (rc, present) if rc else None

    elif tool == "firewall":
        # Only the service ops have a clean READ verifier (--query-service).
        if op in ("add_service", "remove_service"):
            present = op == "add_service"
            rc = _read_call(
                registry, cid, tool, "query",
                {"service": a.get("service"), "zone": a.get("zone")},
            )
            return (rc, present) if rc else None

    elif tool == "users":
        # add/set_shell/add_to_group -> user should exist (id). delete is
        # DESTRUCTIVE (never retried) but we confirm absence + escalate.
        if op in ("add", "set_shell", "add_to_group", "delete"):
            present = op != "delete"
            rc = _read_call(registry, cid, tool, "info", {"user": a.get("user")})
            return (rc, present) if rc else None

    elif tool == "network":
        # ip addr show — best-effort confirmation (PARTIAL). bring_down is
        # DESTRUCTIVE (never retried) but we still read + escalate.
        if op in ("bring_up", "set_ip", "bring_down"):
            present = op != "bring_down"
            rc = _read_call(registry, cid, tool, "show", {})
            return (rc, present) if rc else None

    # disk destructive ops and everything else: no per-target READ verifier.
    return None


def _matches(result: ToolResult, expected_present: bool) -> bool:
    """Does the read's outcome match the intended post-state?

    Presence is read exit 0 (`is-active` / `rpm -q` / `stat` / `--query-service`
    / `id` all return 0 iff the resource is present/active). Absence is the
    inverse. Kept exit-code based so it is deterministic and mirrors the real
    read ops one-for-one.
    """
    ok = result.exit_code == 0
    return ok if expected_present else (not ok)


# --------------------------------------------------------------------------- #
# Spine helpers — reuse synthesize_command + classify + dispatch + audit        #
# --------------------------------------------------------------------------- #

def _synthesize(call: ParsedCall) -> str:
    # Imported lazily so this module never participates in repl.py's import.
    from core.agent.repl import synthesize_command

    return synthesize_command(call)


def _audit(audit, *, tier, nl_input, command, call, decision_note, result) -> None:
    """Write exactly one audit record for one attempted op (I4)."""
    args = dict(call.args)
    args["operation"] = call.operation
    audit.write(
        tier=tier,
        nl_input=nl_input,
        translated_command=command,
        tool=call.tool,
        args=args,
        permission_decision=decision_note,
        exit_code=result.exit_code if result is not None else 2,
        stdout_summary=result.stdout if result is not None else "",
        stderr_summary=result.stderr if result is not None else "",
        result=result.summary if result is not None else decision_note,
    )


def _run_read(
    read_call: ParsedCall,
    exec_ctx: ExecContext,
    registry: ToolRegistry,
    audit,
    *,
    tier: str,
    nl_input: str,
) -> Optional[ToolResult]:
    """Run ONE verifying read through the spine (classify -> ALLOW -> dispatch ->
    audit). Returns the ToolResult, or None if the classifier did NOT land
    Gate.ALLOW (in which case the read is refused and audited, never run — I3).
    Writes exactly one audit record either way (I4).
    """
    command = _synthesize(read_call)
    decision: Decision = perm.classify(command, exec_ctx)
    # A verifying read MUST be a pure read. If the SAME hardened classifier does
    # not agree this is Gate.ALLOW, we refuse it rather than run it (I3).
    if decision.gate is not Gate.ALLOW:
        _audit(
            audit, tier=tier, nl_input=nl_input, command=command, call=read_call,
            decision_note=f"{decision.gate.value}:verify-read-not-allowed",
            result=None,
        )
        return None
    try:
        result = registry.dispatch(read_call.tool, read_call.operation, read_call.args)
    except Exception as exc:  # noqa: BLE001 — a read fault becomes a failed read.
        result = ToolResult(exit_code=1, stdout="", stderr=str(exc),
                            summary="verification read could not be completed")
    _audit(
        audit, tier=tier, nl_input=nl_input, command=command, call=read_call,
        decision_note=decision.gate.value, result=result,
    )
    return result


def _rerun_write(
    call: ParsedCall,
    exec_ctx: ExecContext,
    registry: ToolRegistry,
    audit,
    *,
    tier: str,
    nl_input: str,
) -> Optional[ToolResult]:
    """Re-run an IDEMPOTENT write through the spine and audit it (I4).

    The classifier runs again first (I3): this is a defense-in-depth check that
    the op is STILL not destructive before it repeats. If re-classification comes
    back DESTRUCTIVE (it cannot on unchanged args, but we never assume), the
    retry is REFUSED and audited — verify never dispatches a destructive op.
    Returns the ToolResult, or None if the retry was refused.
    """
    command = _synthesize(call)
    decision: Decision = perm.classify(command, exec_ctx)
    if decision.op_class is OpClass.DESTRUCTIVE:
        _audit(
            audit, tier=tier, nl_input=nl_input, command=command, call=call,
            decision_note=f"{decision.gate.value}:verify-retry-refused-destructive",
            result=None,
        )
        return None
    try:
        result = registry.dispatch(call.tool, call.operation, call.args)
    except Exception as exc:  # noqa: BLE001
        result = ToolResult(exit_code=1, stdout="", stderr=str(exc),
                            summary="operation could not be completed")
    _audit(
        audit, tier=tier, nl_input=nl_input, command=command, call=call,
        decision_note=f"{decision.gate.value}:verify-retry", result=result,
    )
    return result


# --------------------------------------------------------------------------- #
# I2-clean, concrete escalation messages                                        #
# --------------------------------------------------------------------------- #

def _escalation_message(command: str) -> str:
    return (
        f"'{command}' did not reach the expected state and cannot be safely "
        f"repeated. Check the system before acting again."
    )


def _partial_message(command: str) -> str:
    return (
        f"Could not confirm '{command}' took effect. Re-running it could disrupt "
        f"connectivity, so it was left alone. Check the system."
    )


def _exhausted_message(command: str, attempts: int) -> str:
    return (
        f"'{command}' did not take effect after {attempts} more "
        f"{'attempt' if attempts == 1 else 'attempts'}. Check the system."
    )


# --------------------------------------------------------------------------- #
# The entry point                                                              #
# --------------------------------------------------------------------------- #

def verify(
    call: ParsedCall,
    result: ToolResult,
    registry: ToolRegistry,
    exec_ctx: ExecContext,
    audit,
    *,
    context: Optional[ContextLike] = None,
    tier: str = "",
    nl_input: str = "",
    retry_max: Optional[int] = None,
) -> VerifyOutcome:
    """Confirm ``call`` (already executed, producing ``result``) took effect, and
    recover per the op-class-keyed retry policy.

    Runs the tool's OWN read op through the SAME spine (classify -> ALLOW ->
    dispatch -> audit) and compares to the intended state. On a mismatch:

      * idempotent (services/packages/files/firewall/users, non-destructive):
        auto-retry the write, bounded by ERDTREE_RETRY_MAX (default 2),
        invalidating context between attempts (I5), then stop.
      * partial (network): verify only, never auto-retry; escalate on mismatch.
      * destructive (ANY op the classifier calls DESTRUCTIVE): verify only —
        there is NO retry branch on this path — escalate with a concrete error.

    ``context``, ``tier``, ``nl_input`` and ``retry_max`` are optional keyword
    extras that keep the required positional signature intact while letting the
    caller wire context invalidation (I5), the opaque audit tier (I6), the
    originating request text, and a test override for the cap.
    """
    write_command = _synthesize(call)
    # The SAME hardened classifier decides the op class the policy is keyed on —
    # never the model's self-declared class (I3).
    decision: Decision = perm.classify(write_command, exec_ctx)
    op_class = decision.op_class
    policy = retry_policy_for(call.tool, op_class)

    # A read has nothing to verify (I8: reads already returned their own output).
    if op_class is OpClass.READ:
        return VerifyOutcome(
            status=VerifyStatus.READ_ONLY, policy=policy, op_class=op_class,
            verified=True, message="",
        )

    plan = plan_verification(call, registry)
    if plan is None:
        # No READ op can confirm this write. A destructive op we cannot confirm
        # MUST go to a person; a non-destructive one is simply marked unverified.
        if op_class is OpClass.DESTRUCTIVE:
            return VerifyOutcome(
                status=VerifyStatus.ESCALATED, policy=policy, op_class=op_class,
                escalated=True,
                message=(
                    f"Could not confirm '{write_command}' and it cannot be safely "
                    f"repeated. Check the system."
                ),
            )
        return VerifyOutcome(
            status=VerifyStatus.UNVERIFIABLE, policy=policy, op_class=op_class,
            message=f"No read is available to confirm '{write_command}'.",
        )

    read_call, expected_present = plan
    audit_records = 0

    # --- Attempt 0: verify the state the write was supposed to produce. --------
    read = _run_read(read_call, exec_ctx, registry, audit, tier=tier, nl_input=nl_input)
    audit_records += 1  # exactly one record per verification read (I4)
    if read is not None and _matches(read, expected_present):
        return VerifyOutcome(
            status=VerifyStatus.VERIFIED, policy=policy, op_class=op_class,
            verified=True, reads=1, audit_records=audit_records,
            message="Confirmed the change took effect.",
        )

    # --- Mismatch. Branch STRICTLY on policy. ---------------------------------
    if policy is RetryPolicy.NEVER:
        # DESTRUCTIVE (or default-deny). There is NO retry branch here by
        # construction: a destructive op is never re-run automatically (R3).
        return VerifyOutcome(
            status=VerifyStatus.ESCALATED, policy=policy, op_class=op_class,
            escalated=True, reads=1, audit_records=audit_records,
            message=_escalation_message(write_command),
        )

    if policy is RetryPolicy.PARTIAL:
        # network: a re-run could sever access — verify only, escalate, never retry.
        return VerifyOutcome(
            status=VerifyStatus.ESCALATED, policy=policy, op_class=op_class,
            escalated=True, reads=1, audit_records=audit_records,
            message=_partial_message(write_command),
        )

    # --- IDEMPOTENT: bounded auto-retry, then stop. --------------------------
    cap = _retry_cap(retry_max)
    attempts = 0
    reads = 1
    while attempts < cap:
        # I5: invalidate context so the retried write + re-read see reality.
        if context is not None:
            try:
                context.invalidate()
            except Exception:  # noqa: BLE001 — invalidation never breaks verify.
                pass

        rerun = _rerun_write(call, exec_ctx, registry, audit, tier=tier, nl_input=nl_input)
        attempts += 1
        audit_records += 1  # the retried write is audited (I4)
        if rerun is None:
            # Re-classification refused the retry (would be destructive) -> stop.
            return VerifyOutcome(
                status=VerifyStatus.ESCALATED, policy=policy, op_class=op_class,
                escalated=True, attempts=attempts, reads=reads,
                audit_records=audit_records,
                message=_escalation_message(write_command),
            )

        read = _run_read(read_call, exec_ctx, registry, audit, tier=tier, nl_input=nl_input)
        reads += 1
        audit_records += 1  # each re-verification read is audited (I4)
        if read is not None and _matches(read, expected_present):
            return VerifyOutcome(
                status=VerifyStatus.RETRIED_OK, policy=policy, op_class=op_class,
                verified=True, attempts=attempts, reads=reads,
                audit_records=audit_records,
                message="Confirmed the change took effect after retrying.",
            )

    # Cap reached, still mismatched -> hand off to a person.
    return VerifyOutcome(
        status=VerifyStatus.EXHAUSTED, policy=policy, op_class=op_class,
        escalated=True, attempts=attempts, reads=reads,
        audit_records=audit_records,
        message=_exhausted_message(write_command, attempts),
    )
