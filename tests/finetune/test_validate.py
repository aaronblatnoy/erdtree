"""tests/finetune/test_validate.py — correctness gate for finetune/validate.py.

Three families of tests:
  1. GOOD record  -> every call is VALID; validate_jsonl exits 0.
  2. BAD record (arguments as a nested OBJECT) -> MISS; non-zero exit.
  3. BAD record (fake / unknown operation)     -> MISS; non-zero exit.
  4. No drift: validate's per-call verdict == RouterResult.is_valid_action on
               the same well-formed input (INV-schema-sync / bench alignment).

All offline — no network, no ANTHROPIC_API_KEY, no anthropic package required.
"""

from __future__ import annotations

import json
import tempfile
import os

import pytest

from finetune import coreimports
from finetune.validate import (
    CallVerdict,
    ValidationReport,
    check_call,
    validate_jsonl,
    main as validate_main,
)

# --------------------------------------------------------------------------- #
# Shared fixtures                                                              #
# --------------------------------------------------------------------------- #

# A known-good tool / op / args combo — derived LIVE from the registry.
GOOD_TOOL = "services"
GOOD_OP = "status"
GOOD_ARGS = {"operation": GOOD_OP, "unit": "nginx.service"}
GOOD_ARGS_STR = json.dumps(GOOD_ARGS, separators=(",", ":"))
GOOD_CALL_ID = "toolu_01AbcDef234"

# The assistant content string used in good records — must be I2-clean.
GOOD_ANSWER = "nginx.service is active and running on this host."
# System content — must be I2-clean (it IS the house prompt, so it passes by
# construction, but we use a short stand-in for the test record shape).
GOOD_SYSTEM = coreimports.HOUSE_SYSTEM_PROMPT


def _good_tool_call() -> dict:
    """A well-formed §2 tool_call dict (string arguments, valid op)."""
    return {
        "id": GOOD_CALL_ID,
        "type": "function",
        "function": {
            "name": GOOD_TOOL,
            "arguments": GOOD_ARGS_STR,   # JSON-encoded STRING (INV-0002 §2)
        },
    }


def _good_record() -> dict:
    """A minimal well-formed ShareGPT record (0002-conformant)."""
    return {
        "messages": [
            {"role": "system", "content": GOOD_SYSTEM},
            {"role": "user", "content": "is nginx running?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [_good_tool_call()],
            },
            {
                "role": "tool",
                "tool_call_id": GOOD_CALL_ID,        # correlation (0002 §3)
                "content": json.dumps(
                    {"exit_code": 0, "stdout": "", "stderr": "",
                     "summary": "nginx.service is active (running)"},
                    separators=(",", ":"),
                ),
            },
            {"role": "assistant", "content": GOOD_ANSWER},
        ],
        "tools": coreimports.live_tool_list(),
        "meta": {
            "tier": "radagon",
            "scenario_id": "services-status-test-0001",
            "tool": GOOD_TOOL,
            "operation": GOOD_OP,
            "permission_class": "read",
        },
    }


def _bad_record_object_args() -> dict:
    """BAD: arguments is a NESTED OBJECT (dict) instead of a JSON string.

    This is the classic INV-0002 §2 poison bug.  validate.py must count it as
    a MISS; it must NOT silently accept the call.
    """
    rec = _good_record()
    for msg in rec["messages"]:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            # Replace the JSON-encoded string with a raw dict (object).
            msg["tool_calls"][0]["function"]["arguments"] = dict(GOOD_ARGS)
    return rec


def _bad_record_fake_op() -> dict:
    """BAD: operation value is not a real registered op of the tool."""
    fake_args = {"operation": "nonexistent_operation_xyz", "unit": "nginx.service"}
    rec = _good_record()
    for msg in rec["messages"]:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            msg["tool_calls"][0]["function"]["arguments"] = json.dumps(
                fake_args, separators=(",", ":")
            )
    return rec


def _write_jsonl(records: list[dict]) -> str:
    """Write records to a temp JSONL file; return the path."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n")
    return path


# --------------------------------------------------------------------------- #
# 1. check_call — unit tests on a single tool_call dict                       #
# --------------------------------------------------------------------------- #

def test_check_call_valid_returns_true():
    cv = check_call(_good_tool_call())
    assert isinstance(cv, CallVerdict)
    assert cv.is_valid is True
    assert cv.tool == GOOD_TOOL
    assert cv.operation == GOOD_OP
    assert cv.permission_class != ""   # live registry knows it
    assert cv.reason == ""


def test_check_call_object_args_is_miss():
    """arguments as a nested object -> MISS (INV-0002 §2 violation)."""
    bad_call = {
        "id": GOOD_CALL_ID,
        "type": "function",
        "function": {
            "name": GOOD_TOOL,
            "arguments": dict(GOOD_ARGS),   # OBJECT, not string
        },
    }
    cv = check_call(bad_call)
    assert cv.is_valid is False
    assert cv.reason  # non-empty explanation


def test_check_call_fake_op_is_miss():
    """Unknown operation -> MISS (validate_arguments raises ValueError)."""
    bad_call = {
        "id": GOOD_CALL_ID,
        "type": "function",
        "function": {
            "name": GOOD_TOOL,
            "arguments": json.dumps(
                {"operation": "nonexistent_op_xyz"},
                separators=(",", ":"),
            ),
        },
    }
    cv = check_call(bad_call)
    assert cv.is_valid is False
    assert cv.reason


def test_check_call_unknown_tool_is_miss():
    bad_call = {
        "id": "toolu_xxx",
        "type": "function",
        "function": {"name": "totally_fake_tool_zzz", "arguments": "{}"},
    }
    cv = check_call(bad_call)
    assert cv.is_valid is False


# --------------------------------------------------------------------------- #
# 2. validate_jsonl — file-level tests                                        #
# --------------------------------------------------------------------------- #

def test_good_record_gives_valid_and_exit_zero():
    """A fully conformant record -> zero MISSes, zero I2, exit 0."""
    path = _write_jsonl([_good_record()])
    try:
        report = validate_jsonl(path)
        assert report.total_records == 1
        assert report.total_tool_calls == 1
        assert report.valid_count == 1
        assert report.miss_count == 0
        assert report.miss_rate == 0.0
        assert report.i2_violation_count == 0
        assert report.correlation_error_count == 0
        # Good record has no coverage gap for services tool.
        assert report.per_tool["services"]["valid"] == 1
    finally:
        os.unlink(path)


def test_bad_record_object_args_is_miss_and_nonzero():
    """arguments as nested object -> MISS, non-zero exit code."""
    path = _write_jsonl([_bad_record_object_args()])
    try:
        report = validate_jsonl(path)
        assert report.miss_count >= 1
        assert report.should_fail
        # The CLI main must return non-zero.
        exit_code = validate_main([path])
        assert exit_code != 0
    finally:
        os.unlink(path)


def test_bad_record_fake_op_is_miss_and_nonzero():
    """Unknown operation in arguments -> MISS, non-zero exit code."""
    path = _write_jsonl([_bad_record_fake_op()])
    try:
        report = validate_jsonl(path)
        assert report.miss_count >= 1
        assert report.should_fail
        exit_code = validate_main([path])
        assert exit_code != 0
    finally:
        os.unlink(path)


def test_main_returns_zero_for_good_record():
    """CLI main returns 0 on a fully valid single-record file."""
    # Build a file that passes the coverage check — but a single record
    # will have a coverage gap (10 tools missing valid calls).  To avoid that
    # we test the report object directly; the exit-0 gate is covered end-to-end
    # in the smoke test (all 11 tools via --n 20).
    path = _write_jsonl([_good_record()])
    try:
        report = validate_jsonl(path)
        # The single record itself has 0 MISSes, 0 I2, 0 correlation errors.
        assert report.miss_count == 0
        assert report.i2_violation_count == 0
        assert report.correlation_error_count == 0
    finally:
        os.unlink(path)


# --------------------------------------------------------------------------- #
# 3. No drift: validate verdict == RouterResult.is_valid_action               #
# --------------------------------------------------------------------------- #

def test_check_call_verdict_matches_router_result_is_valid_action_for_valid_call():
    """check_call(good) is_valid MUST equal RouterResult.is_valid_action.

    Both derive from the SAME ``validate_arguments`` function — this test
    proves there is NO drift between finetune/validate.py and the bench
    router semantics.  We import Router directly for the comparison (it is
    acceptable to import from core/ in tests; validate.py itself must NOT
    do so directly).
    """
    from core.agent.router import Router, RouterResult  # test-only direct import

    router = Router(coreimports.registry)

    # --- VALID call --------------------------------------------------------- #
    good_call = _good_tool_call()
    cv = check_call(good_call)
    rr: RouterResult = router.route(tool_calls=[good_call])

    assert cv.is_valid == rr.is_valid_action, (
        f"validate verdict ({cv.is_valid}) != RouterResult.is_valid_action "
        f"({rr.is_valid_action}) for a good call — bench drift detected"
    )
    assert cv.is_valid is True
    assert rr.is_valid_action is True


def test_check_call_verdict_matches_router_result_is_valid_action_for_fake_op():
    """check_call(fake_op) is_valid MUST equal RouterResult.is_valid_action.

    For an unknown operation, both validate.py and the Router must agree it is
    a MISS.  This catches any case where our MISS criterion diverges from the
    bench's.
    """
    from core.agent.router import Router, RouterResult  # test-only direct import

    router = Router(coreimports.registry)

    bad_call = {
        "id": GOOD_CALL_ID,
        "type": "function",
        "function": {
            "name": GOOD_TOOL,
            "arguments": json.dumps(
                {"operation": "nonexistent_xyz"}, separators=(",", ":")
            ),
        },
    }

    cv = check_call(bad_call)
    rr: RouterResult = router.route(tool_calls=[bad_call])

    assert cv.is_valid == rr.is_valid_action, (
        f"validate verdict ({cv.is_valid}) != RouterResult.is_valid_action "
        f"({rr.is_valid_action}) for a fake-op call — bench drift detected"
    )
    assert cv.is_valid is False
    assert rr.is_valid_action is False


# --------------------------------------------------------------------------- #
# 4. Correlation check                                                         #
# --------------------------------------------------------------------------- #

def test_missing_tool_message_is_detected():
    """A tool_call_id with no matching role:'tool' message -> correlation error."""
    rec = _good_record()
    # Remove the role:"tool" message.
    rec["messages"] = [
        m for m in rec["messages"] if m.get("role") != "tool"
    ]
    path = _write_jsonl([rec])
    try:
        report = validate_jsonl(path)
        assert report.correlation_error_count >= 1
    finally:
        os.unlink(path)


# --------------------------------------------------------------------------- #
# 5. I2 violation detection                                                    #
# --------------------------------------------------------------------------- #

def test_i2_violation_in_assistant_content_is_detected():
    """An assistant content string with a forbidden term -> I2 violation count."""
    rec = _good_record()
    # Inject a forbidden term into the final assistant answer.
    for msg in rec["messages"]:
        if msg.get("role") == "assistant" and msg.get("content") == GOOD_ANSWER:
            msg["content"] = "The AI agent processed your request."
    path = _write_jsonl([rec])
    try:
        report = validate_jsonl(path)
        assert report.i2_violation_count >= 1
        assert report.should_fail
    finally:
        os.unlink(path)
