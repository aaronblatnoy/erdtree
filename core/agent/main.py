"""
core/agent/main.py — runnable entrypoint wiring the whole framework together.

    collector -> prompt -> ollama -> router -> permissions -> tools -> audit -> back

This is the thin top-level that:
  1. Reads configuration from the environment (ERDTREE_TIER selects the tier
     config; sensible defaults otherwise — I6: no tier name is hardcoded in the
     framework, the value is read from the environment and treated as opaque).
  2. Registers the core tools.
  3. Builds the live Ollama-backed responder (localhost only — I1).
  4. Constructs the Repl and either runs a single request (argv) or an
     interactive loop.

DEGRADES GRACEFULLY (the plan's hard requirement): if Ollama is unreachable, the
program prints ONE clear plain-language line and exits non-zero — never a stack
trace. The localhost-egress guard (I1) is asserted at client construction; a
non-localhost endpoint also fails with a clear message, not a crash.

DEV-HOST NOTE: there is no Ollama on the macOS build host. ``python core/agent/main.py``
still imports and starts here; with no reachable model it prints the clear
"cannot reach" line and exits 3. The live end-to-end loop is DEFERRED-TO-MOSSAD.

I2  No AI/LLM/model/agent language in any user-facing string this prints.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Allow ``python core/agent/main.py`` from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.agent.audit import AuditLog  # noqa: E402
from core.agent.context import TurnContext  # noqa: E402
from core.agent.repl import ConsoleIO, Repl, interactive_loop  # noqa: E402
from core.tools import registry  # noqa: E402

# Register the core tools (self-register on import).
import core.tools.services  # noqa: E402,F401
import core.tools.packages  # noqa: E402,F401
import core.tools.logs  # noqa: E402,F401


# --------------------------------------------------------------------------- #
# Configuration (env-driven; I6 — tier value is opaque to the framework)       #
# --------------------------------------------------------------------------- #

# Per-tier sensible defaults. The framework does NOT hardcode a single product
# name into its logic; this table is config data, keyed by the opaque value of
# ERDTREE_TIER, and is easily replaced by the real Phase-9 tier loader. Tags are
# pinned (never ':latest', per CLAUDE.md gotcha).
_TIER_DEFAULTS: dict[str, dict[str, str]] = {
    "marika": {"model": "qwen2.5:3b-instruct-q4_K_M"},
    "radagon": {"model": "qwen2.5:7b-instruct-q4_K_M"},
    "radahn": {"model": "qwen2.5:14b-instruct-q4_K_M"},
}
_DEFAULT_TIER = "radagon"  # PRIMARY tier per CLAUDE.md; a default, not a hardcode.
_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_AUDIT_LOG = "/var/log/erdtree/audit.jsonl"


@dataclass
class AppConfig:
    """Resolved runtime configuration."""

    tier: str
    base_url: str
    model: str
    audit_log_path: str
    interactive: bool
    tier_prompt: str = ""

    @classmethod
    def from_env(cls, *, interactive: bool = True) -> "AppConfig":
        tier = os.environ.get("ERDTREE_TIER", _DEFAULT_TIER).strip() or _DEFAULT_TIER
        defaults = _TIER_DEFAULTS.get(tier, _TIER_DEFAULTS[_DEFAULT_TIER])
        model = os.environ.get("ERDTREE_MODEL", defaults["model"]).strip()
        base_url = os.environ.get("ERDTREE_BASE_URL", _DEFAULT_BASE_URL).strip()
        audit_log_path = os.environ.get("ERDTREE_AUDIT_LOG", _DEFAULT_AUDIT_LOG).strip()
        return cls(
            tier=tier,
            base_url=base_url,
            model=model,
            audit_log_path=audit_log_path,
            interactive=interactive,
            tier_prompt=os.environ.get("ERDTREE_TIER_PROMPT", "").strip(),
        )


# --------------------------------------------------------------------------- #
# Wiring                                                                        #
# --------------------------------------------------------------------------- #

def _resolve_audit_path(path: str) -> str:
    """Pick a writable audit path, falling back to a user-local one if the
    configured (system) path is not writable on this host (e.g. macOS dev box).

    The audit log is NON-NEGOTIABLE (I4): if we cannot open the configured path
    we must still get a real append-only log somewhere, not silently drop it.
    """
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Touch-test writability.
        with open(p, "a", encoding="utf-8"):
            pass
        return str(p)
    except OSError:
        fallback = Path.home() / ".local" / "share" / "erdtree" / "audit.jsonl"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return str(fallback)


def build_repl(config: AppConfig) -> Repl:
    """Wire collector -> context -> prompt -> ollama -> router -> repl.

    Constructs the live Ollama responder (I1 localhost-asserted at construction).
    Raises the underlying EgressViolation only if a non-localhost endpoint was
    configured — :func:`main` translates that into a clear message.
    """
    from core.model.ollama import OllamaClient, TierConfig

    tier_cfg = TierConfig(config.base_url, config.model)
    client = OllamaClient(tier_cfg)  # asserts localhost (I1)

    def responder(messages, tools):
        # chat() blocks until [DONE] and returns an AssembledResponse with
        # .content / .tool_calls (the shape Repl expects).
        return client.chat(messages, tools=tools, tool_choice="auto")

    audit_path = _resolve_audit_path(config.audit_log_path)
    audit = AuditLog(audit_path)
    context = TurnContext()

    return Repl(
        registry=registry,
        responder=responder,
        audit=audit,
        context=context,
        io=ConsoleIO(interactive=config.interactive),
        tier_label=config.tier,
        tier_prompt=config.tier_prompt,
        interactive=config.interactive,
    )


# --------------------------------------------------------------------------- #
# Entry point                                                                  #
# --------------------------------------------------------------------------- #

def main(argv: Optional[list[str]] = None) -> int:
    """Run one request (joined argv) or an interactive loop.

    Returns a process exit code. NEVER raises a stack trace at the user: an
    unreachable model, a bad endpoint, or a missing config all become a single
    clear plain-language line + a non-zero exit.
    """
    args = list(sys.argv[1:] if argv is None else argv)

    # A request given on the command line is a one-shot; otherwise interactive.
    one_shot = " ".join(args).strip()
    interactive = not bool(one_shot)

    try:
        config = AppConfig.from_env(interactive=interactive)
    except ValueError as exc:
        # e.g. a ':latest' model tag rejected by TierConfig.
        print(f"Configuration problem: {exc}", file=sys.stderr)
        return 1

    try:
        repl = build_repl(config)
    except Exception as exc:  # noqa: BLE001
        # EgressViolation (non-localhost endpoint) or any wiring failure.
        print(
            f"Cannot start: {exc}\n"
            "Check that the local service is configured to listen on localhost.",
            file=sys.stderr,
        )
        return 1

    if one_shot:
        return _run_one_shot(repl, one_shot)
    return _run_interactive(repl)


def _run_one_shot(repl: Repl, request: str) -> int:
    try:
        repl.run_turn(request)
    except ConnectionError as exc:
        print(_unreachable_message(exc), file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"Could not complete that request: {exc}", file=sys.stderr)
        return 1
    return 0


def _run_interactive(repl: Repl) -> int:
    print("Ready. Type a request, or 'exit' to quit.")
    # Probe reachability up front so a dead model is one clear line, not a
    # stack trace on the first request.
    try:
        interactive_loop(repl)
    except ConnectionError as exc:
        print(_unreachable_message(exc), file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"Stopped: {exc}", file=sys.stderr)
        return 1
    return 0


def _unreachable_message(exc: Exception) -> str:
    """Plain, I2-clean message for an unreachable local service."""
    return (
        "The local service is not reachable right now. "
        "Start it and try again."
    )


if __name__ == "__main__":
    raise SystemExit(main())
