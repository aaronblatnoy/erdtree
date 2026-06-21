"""Tests for bench/run_bench.py — the tool-call validity benchmark runner.

Dev-host testable: the runner takes an injected responder, so we feed it
recorded / mock outputs and assert it scores them with the SAME VALID/MISS
predicate the Router enforces. No model, no network, no Linux.

Coverage:
  * load_cases() reads the seed cases.
  * All-valid mock recordings -> 100% validity, english controls held.
  * A deliberately malformed recording -> counted as a MISS (never crashes).
  * English negative controls are NOT in the validity denominator.
  * validity_rate is None (not a fabricated 0.0) when there are no action turns.
  * A missing recording for a case is a MISS, not a crash.
  * The shipped bench/fixtures/mock_outputs.json scores 100% (fixtures are valid
    against the real Phase-2 schemas).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import bench.run_bench as rb
from bench.run_bench import (
    BenchCase,
    BenchRunner,
    load_cases,
    recorded_responder,
)

_FIXTURES = Path(rb.__file__).resolve().parent / "fixtures" / "mock_outputs.json"


@pytest.fixture
def cases():
    return load_cases()


@pytest.fixture
def runner():
    return BenchRunner()


def test_load_cases_nonempty(cases):
    assert len(cases) >= 10
    ids = {c.id for c in cases}
    assert "svc-restart-001" in ids
    assert any(c.turn_type == "english" for c in cases)


def test_shipped_fixtures_score_full_validity(cases, runner):
    with _FIXTURES.open() as fh:
        recordings = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    responder = recorded_responder(recordings)
    report = runner.run(cases, responder, label="mock")
    # Every action turn in the hand-authored fixtures is a valid call.
    assert report.validity_rate == 1.0
    assert report.valid_action_turns == report.total_action_turns
    # Both english negative controls correctly stayed English.
    assert report.english_held == len(report.english_results)
    assert len(report.english_results) == 2


def test_english_turns_excluded_from_denominator(cases, runner):
    with _FIXTURES.open() as fh:
        recordings = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    report = runner.run(cases, recorded_responder(recordings), label="mock")
    # 10 cases, 2 of which are english -> 8 action turns counted.
    assert report.total_action_turns == 8
    assert len(report.english_results) == 2


def test_malformed_recording_counts_as_miss(runner):
    case = BenchCase.from_dict({
        "id": "x", "domain": "services", "turn_type": "action",
        "system_context": "", "user": "restart nginx", "tools": ["services"],
        "expect": {"tool": "services"},
    })
    # Unparseable JSON arguments -> the router calls this a MISS, the runner
    # must record it as such and NOT crash.
    bad = recorded_responder({"x": {"content": "", "tool_calls": [
        {"id": "c1", "name": "services", "arguments": "{broken"}
    ]}})
    report = runner.run([case], bad, label="bad")
    assert report.validity_rate == 0.0
    assert report.valid_action_turns == 0
    assert report.total_action_turns == 1
    assert report.results[0].miss_reasons == ["bad_json"]


def test_prose_where_tool_required_is_miss(runner):
    case = BenchCase.from_dict({
        "id": "x", "domain": "services", "turn_type": "action",
        "system_context": "", "user": "restart nginx", "tools": ["services"],
        "expect": {"tool": "services"},
    })
    # The dominant 3B failure mode: prose instead of a tool call on an action turn.
    prose = recorded_responder({"x": {"content": "I would restart nginx.", "tool_calls": []}})
    report = runner.run([case], prose, label="prose")
    assert report.validity_rate == 0.0
    assert report.results[0].kind == "english"  # stayed English where a call was required


def test_missing_recording_is_miss_not_crash(runner):
    case = BenchCase.from_dict({
        "id": "absent", "domain": "services", "turn_type": "action",
        "system_context": "", "user": "x", "tools": ["services"], "expect": {},
    })
    report = runner.run([case], recorded_responder({}), label="empty")
    assert report.validity_rate == 0.0
    assert report.total_action_turns == 1


def test_validity_rate_none_when_no_action_turns(runner):
    eng = BenchCase.from_dict({
        "id": "e", "domain": "dispatch", "turn_type": "english",
        "system_context": "", "user": "hi", "tools": ["services"], "expect": {},
    })
    report = runner.run([eng], recorded_responder({"e": {"content": "hello", "tool_calls": []}}), label="x")
    # No action turns -> we must NOT fabricate a 0.0; it is None ("no data").
    assert report.validity_rate is None


def test_intent_match_is_informational(cases, runner):
    with _FIXTURES.open() as fh:
        recordings = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    report = runner.run(cases, recorded_responder(recordings), label="mock")
    by_id = {r.case_id: r for r in report.results}
    # svc-restart-001 hits the expected operation+unit subset.
    assert by_id["svc-restart-001"].intent_match is True


def test_cli_refuses_to_fabricate_without_responder(capsys):
    rc = rb.main([])
    assert rc == 2
    err = capsys.readouterr().err
    assert "No responder" in err


def test_cli_recorded_run(tmp_path, capsys):
    with _FIXTURES.open() as fh:
        recordings = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    rec_path = tmp_path / "rec.json"
    rec_path.write_text(json.dumps(recordings))
    rc = rb.main(["--recordings", str(rec_path), "--label", "t"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "validity: 100.0%" in out
    assert "MEETS TARGET" in out
