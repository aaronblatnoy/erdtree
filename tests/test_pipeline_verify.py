"""
tests/test_pipeline_verify.py — Phase 6 SAFETY proof for post-exec verification.

The load-bearing safety properties this file pins:

  1. A DESTRUCTIVE op whose verification read shows a mismatch NEVER retries and
     returns an ESCALATED outcome (the write is dispatched ZERO extra times).
  2. An idempotent failing write retries up to the cap (ERDTREE_RETRY_MAX) and
     STOPS (no unbounded loop).
  3. Every verification read (and every retried write) writes exactly one
     append-only audit record (I4).
  4. Verification only ever runs ops the registry DECLARES as READ, and each such
     read lands Gate.ALLOW through the SAME classifier (I3).
  5. Context is invalidated between idempotent retry attempts (I5).

Everything is driven with a real registry (so the REAL synthesize_command +
permissions.classify run) plus a controllable stand-in for registry.dispatch, so
no real command touches the host.
"""

from __future__ import annotations

import re

import pytest

# Register the tools the cases exercise (self-register on import).
import core.tools.services  # noqa: F401
import core.tools.packages  # noqa: F401
import core.tools.files  # noqa: F401
import core.tools.firewall  # noqa: F401
import core.tools.users  # noqa: F401
import core.tools.network  # noqa: F401
import core.tools.disk  # noqa: F401

from core.tools import registry, ToolResult
from core.agent import permissions as perm
from core.agent.permissions import ExecContext, Gate, OpClass
from core.agent.router import ParsedCall
from core.agent.audit import AuditLog, iter_records
from core.agent.pipeline import verify as verify_mod
from core.agent.pipeline.verify import (
    RetryPolicy,
    VerifyStatus,
    plan_verification,
    retry_policy_for,
    verify,
)


# --------------------------------------------------------------------------- #
# Test doubles                                                                  #
# --------------------------------------------------------------------------- #

class FakeContext:
    def __init__(self) -> None:
        self.invalidations = 0

    def invalidate(self) -> None:
        self.invalidations += 1


class DispatchStub:
    """Stand in for registry.dispatch. Returns a scripted ToolResult per
    (tool, op) and records every dispatch so we can prove what ran (and what
    did NOT re-run)."""

    def __init__(self, results: dict) -> None:
        # results maps (tool, op) -> ToolResult, or (tool, op) -> list[ToolResult]
        # (consumed in order, last value repeats).
        self._results = results
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, tool, op, args):
        self.calls.append((tool, op, dict(args)))
        r = self._results.get((tool, op))
        if isinstance(r, list):
            return r.pop(0) if len(r) > 1 else r[0]
        if r is None:
            return ToolResult(exit_code=0, stdout="", stderr="", summary="done")
        return r

    def count(self, tool, op) -> int:
        return sum(1 for (t, o, _) in self.calls if t == tool and o == op)


def _ok(stdout="ok"):
    return ToolResult(exit_code=0, stdout=stdout, stderr="", summary="completed successfully")


def _fail(stderr="nope"):
    return ToolResult(exit_code=1, stdout="", stderr=stderr, summary="exited 1")


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "audit.jsonl"), tmp_path / "audit.jsonl"


CTX = ExecContext(interactive=True)


# --------------------------------------------------------------------------- #
# Policy taxonomy                                                              #
# --------------------------------------------------------------------------- #

def test_policy_destructive_always_never_retries():
    # DESTRUCTIVE wins over any tool bucket.
    assert retry_policy_for("packages", OpClass.DESTRUCTIVE) is RetryPolicy.NEVER
    assert retry_policy_for("files", OpClass.DESTRUCTIVE) is RetryPolicy.NEVER
    assert retry_policy_for("disk", OpClass.DESTRUCTIVE) is RetryPolicy.NEVER
    assert retry_policy_for("network", OpClass.DESTRUCTIVE) is RetryPolicy.NEVER


def test_policy_idempotent_tools():
    for tool in ("services", "packages", "files", "firewall", "users"):
        assert retry_policy_for(tool, OpClass.WRITE) is RetryPolicy.IDEMPOTENT


def test_policy_network_is_partial():
    assert retry_policy_for("network", OpClass.WRITE) is RetryPolicy.PARTIAL


def test_policy_unknown_write_default_denies():
    assert retry_policy_for("disk", OpClass.WRITE) is RetryPolicy.NEVER
    assert retry_policy_for("mystery", OpClass.WRITE) is RetryPolicy.NEVER


# --------------------------------------------------------------------------- #
# Verifying-read mapping only ever selects registry-declared READ ops           #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "tool, op, args, read_op",
    [
        ("services", "start", {"unit": "nginx"}, "status"),
        ("packages", "install", {"packages": ["vim"]}, "info"),
        ("files", "mkdir", {"path": "/tmp/x"}, "stat"),
        ("firewall", "add_service", {"service": "http", "zone": "public"}, "query"),
        ("users", "add", {"user": "bob"}, "info"),
        ("network", "bring_up", {"interface": "eth0"}, "show"),
    ],
)
def test_plan_selects_declared_read_op(tool, op, args, read_op):
    call = ParsedCall(call_id="c1", tool=tool, operation=op, args=args,
                      permission_class=OpClass.WRITE)
    plan = plan_verification(call, registry)
    assert plan is not None
    read_call, _present = plan
    assert read_call.operation == read_op
    # HARD GUARD: the chosen op is declared READ in the registry.
    assert registry.permission_class_for(tool, read_op) is OpClass.READ


# --------------------------------------------------------------------------- #
# 1. DESTRUCTIVE mismatch -> ESCALATE, ZERO retries                            #
# --------------------------------------------------------------------------- #

def test_destructive_failing_op_never_retries(audit, monkeypatch):
    log, path = audit
    # packages.remove is DESTRUCTIVE. Verifying read = packages.info; we script
    # it to still show the package PRESENT (exit 0) => the removal did NOT take
    # => a mismatch. A destructive mismatch must ESCALATE, never repeat the op.
    stub = DispatchStub({
        ("packages", "info"): _ok("vim-9.0 present"),  # still present => mismatch
    })
    monkeypatch.setattr(registry, "dispatch", stub)

    call = ParsedCall(call_id="c1", tool="packages", operation="remove",
                      args={"packages": ["vim"]}, permission_class=OpClass.DESTRUCTIVE)
    ctx = FakeContext()

    outcome = verify(call, _ok(), registry, CTX, log, context=ctx,
                     tier="t", nl_input="remove vim")

    assert outcome.op_class is OpClass.DESTRUCTIVE
    assert outcome.policy is RetryPolicy.NEVER
    assert outcome.status is VerifyStatus.ESCALATED
    assert outcome.escalated is True
    assert outcome.verified is False
    assert outcome.attempts == 0                      # NO write retry, ever
    # The write (packages.remove) was dispatched ZERO times by verify — only the
    # verifying read ran.
    assert stub.count("packages", "remove") == 0
    assert stub.count("packages", "info") == 1
    assert ctx.invalidations == 0                     # no retry => no invalidation
    # concrete, I2-clean error mentions the op, no forbidden words (I2: no
    # AI/LLM/model/agent language — matched as whole words, not substrings).
    assert "dnf remove vim" in outcome.message
    for banned in ("ai", "llm", "model", "agent"):
        assert not re.search(rf"\b{banned}\b", outcome.message.lower())
    # Exactly one audit record (the verification read).
    records = list(iter_records(path))
    assert len(records) == 1
    assert records[0]["tool"] == "packages"
    assert records[0]["args"]["operation"] == "info"


def test_disk_format_mismatch_escalates_without_retry(audit, monkeypatch):
    log, path = audit
    # disk.format is DESTRUCTIVE with no per-target READ verifier -> unverifiable
    # + destructive => ESCALATE, and NO write is ever dispatched by verify.
    stub = DispatchStub({})
    monkeypatch.setattr(registry, "dispatch", stub)
    call = ParsedCall(call_id="c1", tool="disk", operation="format",
                      args={"device": "/dev/sdb", "fstype": "ext4"},
                      permission_class=OpClass.DESTRUCTIVE)
    outcome = verify(call, _ok(), registry, CTX, log)
    assert outcome.status is VerifyStatus.ESCALATED
    assert outcome.op_class is OpClass.DESTRUCTIVE
    assert outcome.attempts == 0
    assert stub.calls == []                           # nothing re-run at all


# --------------------------------------------------------------------------- #
# 2. Idempotent failing write retries up to the cap and STOPS                  #
# --------------------------------------------------------------------------- #

def test_idempotent_failing_write_retries_to_cap_and_stops(audit, monkeypatch):
    log, path = audit
    # services.start (WRITE, idempotent tool). Verifying read (status) always
    # reports the unit INACTIVE (exit 1) => the start never "takes" => the retry
    # loop runs to the cap and stops.
    stub = DispatchStub({
        ("services", "status"): _fail(),      # always inactive => never matches
        ("services", "start"): _ok(),         # each retry "succeeds" but doesn't stick
    })
    monkeypatch.setattr(registry, "dispatch", stub)
    monkeypatch.setenv("ERDTREE_RETRY_MAX", "2")

    call = ParsedCall(call_id="c1", tool="services", operation="start",
                      args={"unit": "nginx"}, permission_class=OpClass.WRITE)
    ctx = FakeContext()

    outcome = verify(call, _ok(), registry, CTX, log, context=ctx,
                     tier="t", nl_input="start nginx")

    assert outcome.policy is RetryPolicy.IDEMPOTENT
    assert outcome.status is VerifyStatus.EXHAUSTED
    assert outcome.escalated is True
    assert outcome.verified is False
    assert outcome.attempts == 2                       # capped at ERDTREE_RETRY_MAX
    # The write was re-run EXACTLY cap times (not more — it STOPPED).
    assert stub.count("services", "start") == 2
    # Reads: initial + one after each retry = 3.
    assert stub.count("services", "status") == 3
    assert outcome.reads == 3
    # I5: context invalidated once before each retry.
    assert ctx.invalidations == 2


def test_idempotent_retry_succeeds_before_cap(audit, monkeypatch):
    log, path = audit
    # First status read fails, then after one retry the read reports ACTIVE.
    stub = DispatchStub({
        ("services", "status"): [_fail(), _ok("active")],  # fail once, then active
        ("services", "start"): _ok(),
    })
    monkeypatch.setattr(registry, "dispatch", stub)
    monkeypatch.setenv("ERDTREE_RETRY_MAX", "3")

    call = ParsedCall(call_id="c1", tool="services", operation="start",
                      args={"unit": "nginx"}, permission_class=OpClass.WRITE)
    ctx = FakeContext()
    outcome = verify(call, _ok(), registry, CTX, log, context=ctx)

    assert outcome.status is VerifyStatus.RETRIED_OK
    assert outcome.verified is True
    assert outcome.attempts == 1                        # stopped as soon as it stuck
    assert stub.count("services", "start") == 1
    assert ctx.invalidations == 1


def test_retry_max_zero_disables_retry(audit, monkeypatch):
    log, _ = audit
    stub = DispatchStub({("services", "status"): _fail(), ("services", "start"): _ok()})
    monkeypatch.setattr(registry, "dispatch", stub)
    call = ParsedCall(call_id="c1", tool="services", operation="start",
                      args={"unit": "nginx"}, permission_class=OpClass.WRITE)
    outcome = verify(call, _ok(), registry, CTX, log, retry_max=0)
    assert outcome.attempts == 0
    assert stub.count("services", "start") == 0
    assert outcome.status is VerifyStatus.EXHAUSTED


# --------------------------------------------------------------------------- #
# 3. Happy path + audit-every-read                                             #
# --------------------------------------------------------------------------- #

def test_first_read_confirms_no_retry(audit, monkeypatch):
    log, path = audit
    stub = DispatchStub({("users", "info"): _ok("uid=1001(bob)")})
    monkeypatch.setattr(registry, "dispatch", stub)
    call = ParsedCall(call_id="c1", tool="users", operation="add",
                      args={"user": "bob"}, permission_class=OpClass.WRITE)
    ctx = FakeContext()
    outcome = verify(call, _ok(), registry, CTX, log, context=ctx, nl_input="add bob")

    assert outcome.status is VerifyStatus.VERIFIED
    assert outcome.verified is True
    assert outcome.attempts == 0
    assert ctx.invalidations == 0
    assert stub.count("users", "info") == 1
    assert stub.count("users", "add") == 0
    records = list(iter_records(path))
    assert len(records) == 1                            # exactly one read audited


def test_every_read_and_retry_writes_one_audit_record(audit, monkeypatch):
    log, path = audit
    # firewall.add_service, verify read (query) fails twice then we exhaust.
    stub = DispatchStub({
        ("firewall", "query"): _fail(),   # never present => never matches
        ("firewall", "add_service"): _ok(),
    })
    monkeypatch.setattr(registry, "dispatch", stub)
    monkeypatch.setenv("ERDTREE_RETRY_MAX", "2")
    call = ParsedCall(call_id="c1", tool="firewall", operation="add_service",
                      args={"service": "http", "zone": "public"},
                      permission_class=OpClass.WRITE)
    outcome = verify(call, _ok(), registry, CTX, log, nl_input="open http")

    # 3 reads (initial + 2 after retries) + 2 write retries = 5 audited ops.
    records = list(iter_records(path))
    assert len(records) == 5
    assert outcome.audit_records == 5
    # Every record is append-only JSONL with the schema fields present.
    for rec in records:
        assert "permission_decision" in rec and "translated_command" in rec
    # The reads were classified ALLOW; the retries were the verify-retry note.
    decisions = [r["permission_decision"] for r in records]
    assert decisions.count("allow") == 3
    assert sum(1 for d in decisions if "verify-retry" in d) == 2


# --------------------------------------------------------------------------- #
# 4. Verification reads land Gate.ALLOW through the SAME classifier (I3)        #
# --------------------------------------------------------------------------- #

def test_verification_reads_are_classified_allow(audit, monkeypatch):
    log, _ = audit
    stub = DispatchStub({("files", "stat"): _ok("exists")})
    monkeypatch.setattr(registry, "dispatch", stub)

    seen: list[tuple[str, Gate]] = []
    real = perm.classify

    def spy(command, context=None):
        d = real(command, context)
        seen.append((command, d.gate))
        return d

    monkeypatch.setattr("core.agent.pipeline.verify.perm.classify", spy)

    call = ParsedCall(call_id="c1", tool="files", operation="mkdir",
                      args={"path": "/tmp/newdir"}, permission_class=OpClass.WRITE)
    outcome = verify(call, _ok(), registry, CTX, log)
    assert outcome.status is VerifyStatus.VERIFIED
    # The verifying read (stat) was classified and landed ALLOW.
    stat_gates = [g for (cmd, g) in seen if cmd.startswith("stat ")]
    assert stat_gates and all(g is Gate.ALLOW for g in stat_gates)


# --------------------------------------------------------------------------- #
# 5. network is PARTIAL: verify only, never auto-retry                          #
# --------------------------------------------------------------------------- #

def test_network_partial_never_auto_retries(audit, monkeypatch):
    log, _ = audit
    # network.set_ip is WRITE; policy PARTIAL. `show` read exit 0 => our exit-code
    # match reports present, so force a mismatch by making the read FAIL.
    stub = DispatchStub({("network", "show"): _fail()})
    monkeypatch.setattr(registry, "dispatch", stub)
    call = ParsedCall(call_id="c1", tool="network", operation="set_ip",
                      args={"interface": "eth0", "address": "10.0.0.5/24"},
                      permission_class=OpClass.WRITE)
    ctx = FakeContext()
    outcome = verify(call, _ok(), registry, CTX, log, context=ctx)

    assert outcome.policy is RetryPolicy.PARTIAL
    assert outcome.status is VerifyStatus.ESCALATED
    assert outcome.attempts == 0
    assert stub.count("network", "set_ip") == 0        # never re-run
    assert ctx.invalidations == 0


# --------------------------------------------------------------------------- #
# 6. A read op input has nothing to verify                                     #
# --------------------------------------------------------------------------- #

def test_read_op_is_read_only(audit, monkeypatch):
    log, path = audit
    stub = DispatchStub({})
    monkeypatch.setattr(registry, "dispatch", stub)
    call = ParsedCall(call_id="c1", tool="services", operation="status",
                      args={"unit": "nginx"}, permission_class=OpClass.READ)
    outcome = verify(call, _ok(), registry, CTX, log)
    assert outcome.status is VerifyStatus.READ_ONLY
    assert stub.calls == []                             # nothing dispatched
    assert list(iter_records(path)) == []               # nothing audited
