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

# Register the Phase 6 tools (self-register on import). Each import is a pure
# side-effect: the module calls registry.register(...) at import time.
import core.tools.network  # noqa: E402,F401
import core.tools.firewall  # noqa: E402,F401
import core.tools.users  # noqa: E402,F401
import core.tools.disk  # noqa: E402,F401
import core.tools.processes  # noqa: E402,F401
import core.tools.hardware  # noqa: E402,F401
import core.tools.files  # noqa: E402,F401

# Register the docs (reference-lookup) tool. GUARDED: a missing/unreadable
# corpus index must NOT crash build_repl — the tool degrades to empty-but-valid
# results at call time, and even an import-time failure here is swallowed so the
# loop still starts without the reference tool (I9).
try:
    import core.tools.docs  # noqa: E402,F401
except Exception:  # noqa: BLE001 — docs is optional; absence must never crash startup.
    pass


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
}
# Only these tiers are operational. The larger tiers (radahn = massive /
# dedicated-infra, starscourge) run on models that are NOT built — they must be
# entirely unreachable, never silently resolved to a smaller model. Requesting a
# non-operational or unknown tier is REFUSED outright (no fallback).
_OPERATIONAL_TIERS = frozenset(_TIER_DEFAULTS)  # {"marika", "radagon"}
_DEFAULT_TIER = "radagon"  # PRIMARY tier per CLAUDE.md; a default, not a hardcode.
_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_AUDIT_LOG = "/var/log/erdtree/audit.jsonl"


def _int_env(name: str, default: int) -> int:
    """Read an integer env knob OPAQUELY; any non-integer value -> default.

    Never raises (I9): a malformed ERDTREE_* integer degrades to the safe
    default rather than crashing config resolution / build_repl.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class TierUnavailableError(RuntimeError):
    """Raised when ERDTREE_TIER names a tier that is not available on this host —
    an unbuilt tier (radahn/starscourge) or an unknown value. The config layer
    refuses it outright rather than silently falling back to another tier."""


@dataclass
class AppConfig:
    """Resolved runtime configuration."""

    tier: str
    base_url: str
    model: str
    audit_log_path: str
    interactive: bool
    tier_prompt: str = ""
    # P8 invisible-memory knobs (read OPAQUELY, exactly like ERDTREE_MODEL —
    # I6).  All have safe defaults; absence -> the feature degrades OFF and
    # build_repl never crashes (I9).
    facts_path: str = ""             # ERDTREE_FACTS_PATH — "" -> no preamble.
    corpus_index: str = ""           # ERDTREE_CORPUS_INDEX — "" -> docs/episodic off.
    retrieval_k: int = 3             # ERDTREE_RETRIEVAL_K — per-tier recall budget.
    compaction_threshold: int = 0    # ERDTREE_COMPACTION_THRESHOLD — 0 -> no cap.

    @classmethod
    def from_env(cls, *, interactive: bool = True) -> "AppConfig":
        tier = os.environ.get("ERDTREE_TIER", _DEFAULT_TIER).strip() or _DEFAULT_TIER
        if tier not in _OPERATIONAL_TIERS:
            # A non-operational tier (radahn/starscourge) or an unknown value is
            # refused — never silently resolved to a different tier's model.
            raise TierUnavailableError(
                f"Tier {tier!r} is not available on this host."
            )
        defaults = _TIER_DEFAULTS[tier]
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
            facts_path=os.environ.get("ERDTREE_FACTS_PATH", "").strip(),
            corpus_index=os.environ.get("ERDTREE_CORPUS_INDEX", "").strip(),
            retrieval_k=_int_env("ERDTREE_RETRIEVAL_K", 3),
            compaction_threshold=_int_env("ERDTREE_COMPACTION_THRESHOLD", 0),
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


def _stream_enabled() -> bool:
    """Decide whether the live path streams tokens incrementally.

    Default ON (P6): the live ConsoleIO path renders the answer live, token by
    token, so simple requests feel instant (I8). Setting ERDTREE_STREAM to a
    falsey value ("0"/"off"/"false"/"no") forces the BUFFERED path — the same
    full-answer-at-once behavior the loop had before streaming landed. Read
    OPAQUELY and never raises (I9): any unrecognized value -> the default.
    """
    raw = os.environ.get("ERDTREE_STREAM", "").strip().lower()
    if not raw:
        return True  # default ON for the live path
    return raw not in ("0", "off", "false", "no")


def build_repl(config: AppConfig) -> Repl:
    """Wire collector -> context -> prompt -> ollama -> router -> repl.

    Constructs the live Ollama responder (I1 localhost-asserted at construction).
    Raises the underlying EgressViolation only if a non-localhost endpoint was
    configured — :func:`main` translates that into a clear message.

    LIVE PATH STREAMING (P6): the default responder is the streaming responder
    (core.model.ollama.stream_responder) whose on_delta sink is the ConsoleIO's
    render_delta, so the English answer appears live. It returns the SAME
    AssembledResponse chat() would assemble from the same chunks (parity proven
    in tests/test_streaming.py), so the router/gate/audit see the identical
    assembled turn (SC4 — streaming is PRESENTATION ONLY). It opens NO new
    socket and names NO new host: it drains client.stream(), loopback-asserted
    at the client's construction (I1). ERDTREE_STREAM=0 falls back to the
    buffered chat() closure (SC5/back-compat).
    """
    from core.model.ollama import OllamaClient, TierConfig, stream_responder

    tier_cfg = TierConfig(config.base_url, config.model)
    client = OllamaClient(tier_cfg)  # asserts localhost (I1)

    # Build the IO first so its render_delta can be the streaming sink.
    io = ConsoleIO(interactive=config.interactive)

    if _stream_enabled():
        # The streaming responder OWNS the delta sink (the seam): run_turn stays
        # unaware of streaming. on_delta -> io.render_delta renders each content
        # token live; _safe_emit (in stream_responder) wraps the sink so a
        # rendering fault degrades to no-stream and never aborts assembly (SC4).
        _stream = stream_responder(client, on_delta=io.render_delta)

        def responder(messages, tools):
            # Same shape Repl expects: returns an AssembledResponse with
            # .content / .tool_calls, identical to chat() over the same chunks.
            return _stream(messages, tools=tools, tool_choice="auto")
    else:
        def responder(messages, tools):
            # Buffered path (ERDTREE_STREAM=0): chat() blocks until [DONE] and
            # returns the same AssembledResponse the streaming responder does.
            return client.chat(messages, tools=tools, tool_choice="auto")

    audit_path = _resolve_audit_path(config.audit_log_path)
    audit = AuditLog(audit_path)

    # P8 invisible memory.  EVERY piece below is OPTIONAL and degrades OFF on
    # absence/error — build_repl must never crash on a missing facts file,
    # absent corpus index, or unbuildable episodic index (I9).
    #   * facts preamble  -> threaded through TurnContext.snapshot_text (I5).
    #   * TranscriptMemory -> silent rolling compaction of the prior-turn window.
    #   * EpisodicMemory   -> past-operation recall (reuses the P7 rag engine
    #                         pointed at an index DERIVED from the audit log; a
    #                         DIFFERENT path from the docs corpus index).
    context = _build_context(config)
    memory = _build_memory()
    episodic = _build_episodic(config, audit_path)

    return Repl(
        registry=registry,
        responder=responder,
        audit=audit,
        context=context,
        io=io,
        tier_label=config.tier,
        tier_prompt=config.tier_prompt,
        interactive=config.interactive,
        memory=memory,
        episodic=episodic,
        compaction_threshold=config.compaction_threshold,
    )


def _build_context(config: AppConfig) -> TurnContext:
    """Build the TurnContext, wiring the per-host facts preamble when configured.

    Absent/empty ERDTREE_FACTS_PATH -> no FactsLoader -> snapshot_text output is
    byte-identical to the pre-P8 path (I9 backward-compatible default).  A
    construction failure degrades to a plain TurnContext (no preamble).
    """
    try:
        if config.facts_path:
            from core.context.facts import FactsLoader

            return TurnContext(facts=FactsLoader(config.facts_path))
    except Exception:  # noqa: BLE001 — facts are optional; never crash startup.
        pass
    return TurnContext()


def _build_memory():
    """Construct the TranscriptMemory (invisible rolling compaction).

    Always-on once available, since it is pure stdlib byte-counting with no
    external dependency and an empty transcript is a harmless no-op.  Any import
    failure degrades to None -> the loop keeps history=[] (pre-P8 behavior, I9).
    """
    try:
        from core.agent.memory import TranscriptMemory

        return TranscriptMemory()
    except Exception:  # noqa: BLE001
        return None


def _build_episodic(config: AppConfig, audit_path: str):
    """Construct the EpisodicMemory over the audit log, when usable.

    The episodic index path is DERIVED from the audit log path (a sibling file)
    and is DIFFERENT from the docs corpus index (ERDTREE_CORPUS_INDEX) — that
    difference is the reuse-not-fork property.  Any failure -> None (I9); the
    loop simply has no past-operation recall and continues.
    """
    try:
        from pathlib import Path as _Path

        from core.agent.episodic import EpisodicMemory

        index_path = str(_Path(audit_path).with_name("episodic.db"))
        return EpisodicMemory(
            audit_path=audit_path,
            index_path=index_path,
            k=config.retrieval_k,
        )
    except Exception:  # noqa: BLE001
        return None


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
