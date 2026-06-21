"""Tests for core/agent/main.py — the entrypoint wiring + graceful degradation.

Dev-host testable: we never reach a live model. We assert config resolution
from ERDTREE_TIER, the localhost egress guard surfaces as a clean message (not a
stack trace), and an unreachable model yields a clear line + non-zero exit.

Coverage:
  * AppConfig.from_env: default tier, ERDTREE_TIER override, model/base-url env.
  * A non-localhost ERDTREE_BASE_URL -> clean "Cannot start" message, exit 1
    (egress guard fired before any byte left the box).
  * A ':latest' model tag -> config rejected with exit 1, no crash.
  * One-shot against an unreachable local endpoint -> exit 3, clean message,
    no AI/LLM language leaked.
"""

from __future__ import annotations

import core.agent.main as main
from core.agent.main import AppConfig


def test_default_tier_is_radagon(monkeypatch):
    monkeypatch.delenv("ERDTREE_TIER", raising=False)
    monkeypatch.delenv("ERDTREE_MODEL", raising=False)
    cfg = AppConfig.from_env()
    assert cfg.tier == "radagon"
    assert "7b" in cfg.model  # radagon default model bucket


def test_tier_override(monkeypatch):
    monkeypatch.setenv("ERDTREE_TIER", "marika")
    monkeypatch.delenv("ERDTREE_MODEL", raising=False)
    cfg = AppConfig.from_env()
    assert cfg.tier == "marika"
    assert "3b" in cfg.model


def test_model_env_override(monkeypatch):
    monkeypatch.setenv("ERDTREE_MODEL", "qwen2.5:14b-instruct-q4_K_M")
    cfg = AppConfig.from_env()
    assert cfg.model == "qwen2.5:14b-instruct-q4_K_M"


def test_unknown_tier_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("ERDTREE_TIER", "no-such-tier")
    monkeypatch.delenv("ERDTREE_MODEL", raising=False)
    cfg = AppConfig.from_env()
    # Unknown tier label is kept (opaque), but the model bucket defaults safely.
    assert cfg.tier == "no-such-tier"
    assert cfg.model  # a sensible default, not empty


def test_non_localhost_endpoint_is_clean_message(monkeypatch, capsys):
    monkeypatch.setenv("ERDTREE_BASE_URL", "http://10.0.0.5:11434")
    rc = main.main(["restart", "nginx"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Cannot start" in err
    assert "Traceback" not in err


def test_latest_tag_rejected(monkeypatch, capsys):
    monkeypatch.setenv("ERDTREE_MODEL", "qwen2.5:latest")
    rc = main.main(["restart", "nginx"])
    # TierConfig rejects ':latest' -> surfaced as a clean message, not a crash.
    assert rc in (1,)
    out = capsys.readouterr()
    assert "Traceback" not in (out.err + out.out)


def test_unreachable_localhost_is_exit_3_clean(monkeypatch, capsys):
    # localhost endpoint passes the egress guard but nothing is listening ->
    # ConnectionError -> clean exit 3, no AI/LLM language, no stack trace.
    monkeypatch.setenv("ERDTREE_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.delenv("ERDTREE_TIER", raising=False)
    monkeypatch.delenv("ERDTREE_MODEL", raising=False)
    rc = main.main(["is", "sshd", "running"])
    assert rc == 3
    err = capsys.readouterr().err
    assert "not reachable" in err
    for forbidden in ("Traceback", "Ollama", "LLM", "model"):
        assert forbidden not in err
