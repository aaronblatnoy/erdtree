"""
core/agent/repl.py — the read-eval-print loop (one-turn engine + interactive loop).

This is the integration spine that drives a single turn end to end:

    collect context (TurnContext)  ->  assemble prompt (prompt.py)
      ->  ask the model (injected responder)  ->  classify (router.py)
      ->  for each call: permission gate (permissions.py)  ->  dispatch (registry)
      ->  audit EVERY op (audit.py)  ->  feed tool results back  ->  repeat
      ->  English answer terminates the turn.

Design contract (load-bearing invariants):

  I1  No egress here. The model is reached only through the injected
      ``responder`` (which, in production, is core.model.ollama — itself
      localhost-asserted). The REPL never opens a socket itself.
  I2  No AI/LLM/model/agent language in any user-facing string. Prompts the user
      sees ("Run this change? [y/N]", "Type DESTROY to proceed") speak plain
      Linux-operator language.
  I3  The permission gate is resolved BEFORE every write/destructive dispatch.
      A read runs immediately (Gate.ALLOW). A write needs a yes/no. A
      destructive needs the literal typed word. A non-interactive write or
      destructive is REFUSED, never auto-run. This module imports and USES
      core.agent.permissions; it never re-implements or weakens it.
  I4  EVERY attempted op writes exactly one append-only JSONL audit record —
      including ops that were refused or declined at the gate, and including
      MISS turns (recorded so the validity story is auditable).
  I5  Fresh system context is injected every turn via TurnContext. After any
      mutating op the context cache is invalidated so the next turn sees reality.
  I6  No tier/product names. The tier label + tier prompt are passed in.
  I8  Reads run with no confirmation so simple ops feel instant.

THE MODEL IS INJECTED. ``Repl`` takes a ``responder`` callable:

    responder(messages, tools) -> object with .content (str) and
                                   .tool_calls (list[{"id","name","arguments"}])

i.e. the core.model.ollama.AssembledResponse shape. This makes the WHOLE loop
unit-testable on the dev host (tests inject a scripted responder); the live
Ollama-backed responder is wired in main.py.

The confirm / typed-word prompts and the rendering are also injected
(``io``) so tests drive them deterministically; the default IO uses stdin/stdout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

from core.agent import permissions as perm
from core.agent.audit import AuditLog
from core.agent.context import TurnContext
from core.agent.permissions import ExecContext, Gate, OpClass
from core.agent.prompt import assemble
from core.agent.router import ParsedCall, Router, RouterResult, TurnKind
from core.tools import ToolRegistry, ToolResult


# --------------------------------------------------------------------------- #
# IO seam (so tests drive prompts/rendering deterministically)                 #
# --------------------------------------------------------------------------- #

class ReplIO(Protocol):
    """Everything the loop needs from the terminal. Injected for tests."""

    def render(self, text: str) -> None: ...
    def confirm(self, prompt: str) -> bool: ...
    def confirm_typed(self, prompt: str, word: str) -> bool: ...


class ConsoleIO:
    """Default IO: plain stdin/stdout. No AI/LLM language anywhere (I2)."""

    def __init__(self, *, interactive: bool = True) -> None:
        self.interactive = interactive

    def render(self, text: str) -> None:
        if text:
            print(text)

    def confirm(self, prompt: str) -> bool:
        if not self.interactive:
            return False
        try:
            ans = input(f"{prompt} [y/N] ").strip().lower()
        except EOFError:
            return False
        return ans in ("y", "yes")

    def confirm_typed(self, prompt: str, word: str) -> bool:
        if not self.interactive:
            return False
        try:
            ans = input(f"{prompt} (type {word} to proceed) ")
        except EOFError:
            return False
        return perm.confirms_destructive(ans)


# A responder turns (messages, tools) into an assembled model response.
class _AssembledLike(Protocol):
    content: str
    tool_calls: list[dict]


Responder = Callable[[list[dict], list[dict]], _AssembledLike]


# --------------------------------------------------------------------------- #
# Turn outcome                                                                  #
# --------------------------------------------------------------------------- #

@dataclass
class TurnOutcome:
    """Structured result of running one user turn (for tests + callers)."""

    final_text: str = ""
    tool_calls_made: int = 0           # calls actually dispatched (gate cleared)
    misses: int = 0                    # MISS turns encountered (validity signal)
    refused: int = 0                   # ops blocked at the permission gate
    rounds: int = 0                    # model<->tool round trips taken
    ended_in_english: bool = False
    audit_records: int = 0             # ops recorded (I4)
    history: list[dict] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# The REPL engine                                                              #
# --------------------------------------------------------------------------- #

# A human-readable command string per (tool, op) for the permission classifier.
# permissions.classify() works on a literal command line; we synthesize a
# faithful one from the validated call so the SAME hardened classifier decides
# the gate. (We never trust the model's self-declared class.)
def synthesize_command(call: ParsedCall) -> str:
    """Build the literal shell command a (tool, op, args) maps to, for the gate.

    This drives core.agent.permissions.classify — the single, hardened gate.
    The mapping is conservative: anything we cannot render precisely falls
    through to permissions' default-deny (>= WRITE).
    """
    args = call.args
    if call.tool == "services":
        unit = args.get("unit", "")
        op = call.operation
        if op in ("status", "logs"):
            return f"systemctl {op} {unit}".strip()
        return f"systemctl {op} {unit}".strip()
    if call.tool == "packages":
        op = call.operation
        pkgs = args.get("packages") or []
        pkg_str = " ".join(pkgs) if isinstance(pkgs, list) else str(pkgs)
        if op == "search":
            return f"dnf search {args.get('keyword', '')}".strip()
        if op == "info":
            return f"dnf info {args.get('package', '')}".strip()
        if op == "remove":
            return f"dnf remove {pkg_str}".strip()
        if op == "install":
            return f"dnf install {pkg_str}".strip()
        if op == "update":
            return f"dnf update {pkg_str}".strip()
        return f"dnf {op} {pkg_str}".strip()
    if call.tool == "logs":
        # All log operations are read-only journal/dmesg queries.
        return "journalctl"
    # Unknown tool shape -> default-deny floor at the classifier.
    return f"{call.tool} {call.operation}"


class Repl:
    """Drives the agent loop. Model + IO + audit are injected (dev-host testable).

    Parameters
    ----------
    registry:    the tool registry (tools already registered).
    responder:   callable(messages, tools) -> AssembledResponse-like.
    audit:       an AuditLog (I4 — every op recorded).
    context:     a TurnContext (I5 — fresh context every turn).
    io:          a ReplIO (defaults to ConsoleIO).
    tier_label:  opaque label written into audit records (I6 — not interpreted).
    tier_prompt: tier personality addendum for the system prompt (I6).
    interactive: whether a human is present (drives the permission gate via
                 ExecContext); non-interactive writes/destructives are REFUSED.
    max_rounds:  safety cap on model<->tool round trips per turn.
    """

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        responder: Responder,
        audit: AuditLog,
        context: Optional[TurnContext] = None,
        io: Optional[ReplIO] = None,
        router: Optional[Router] = None,
        tier_label: str = "",
        tier_prompt: str = "",
        interactive: bool = True,
        max_rounds: int = 6,
    ) -> None:
        self._registry = registry
        self._responder = responder
        self._audit = audit
        self._context = context if context is not None else TurnContext()
        self._io = io if io is not None else ConsoleIO(interactive=interactive)
        self._router = router if router is not None else Router(registry)
        self._tier_label = tier_label
        self._tier_prompt = tier_prompt
        self._interactive = interactive
        self._exec_ctx = ExecContext(interactive=interactive)
        self._max_rounds = max(1, max_rounds)

    # ------------------------------------------------------------------ #
    # One full turn                                                       #
    # ------------------------------------------------------------------ #

    def run_turn(self, user_input: str) -> TurnOutcome:
        """Drive one user request to completion (English answer or exhaustion).

        Loops model -> router -> (gate -> dispatch -> audit) -> tool results ->
        model, until the model answers in English, all calls miss, or the round
        cap is hit. Never raises on a malformed model turn (router counts it a
        MISS and we re-ask).
        """
        outcome = TurnOutcome()

        snapshot_text = self._context.snapshot_text()
        tools = self._advertised_tools()
        messages, _ = assemble(
            user_input=user_input,
            snapshot_text=snapshot_text,
            history=[],
            tier_prompt=self._tier_prompt,
            tools=[],
        )

        for _round in range(self._max_rounds):
            outcome.rounds += 1
            response = self._responder(messages, tools)
            content = getattr(response, "content", "") or ""
            raw_calls = list(getattr(response, "tool_calls", []) or [])

            verdict: RouterResult = self._router.route(
                content=content, tool_calls=raw_calls
            )

            # Record the assistant turn into history (OpenAI shape).
            messages.append(self._assistant_message(content, raw_calls))

            if verdict.kind is TurnKind.ENGLISH:
                outcome.final_text = verdict.content
                outcome.ended_in_english = True
                self._io.render(verdict.content)
                break

            if verdict.kind is TurnKind.MISS:
                outcome.misses += 1
                # Audit the miss (I4 — every op, including failed parses).
                for miss in verdict.misses:
                    self._audit.write(
                        tier=self._tier_label,
                        nl_input=user_input,
                        result=f"miss:{miss.reason}",
                        permission_decision="n/a",
                    )
                    outcome.audit_records += 1
                # Re-ask: feed the verbatim 0002 §5 messages back and loop.
                # If the model ALSO produced some valid calls, dispatch those.
                self._dispatch_calls(
                    verdict.calls, user_input, messages, outcome
                )
                for reask in verdict.reask_messages:
                    messages.append(reask)
                continue

            # TOOL_CALL: dispatch every (already-validated) call through the gate.
            self._dispatch_calls(verdict.calls, user_input, messages, outcome)

        outcome.history = messages
        return outcome

    # ------------------------------------------------------------------ #
    # Dispatch one batch of validated calls through the permission gate    #
    # ------------------------------------------------------------------ #

    def _dispatch_calls(
        self,
        calls: list[ParsedCall],
        user_input: str,
        messages: list[dict],
        outcome: TurnOutcome,
    ) -> None:
        for call in calls:
            command = synthesize_command(call)
            decision = perm.classify(command, self._exec_ctx)

            cleared, gate_note = self._resolve_gate(decision, command)

            if not cleared:
                outcome.refused += 1
                # I4: record the refused/declined op.
                self._audit.write(
                    tier=self._tier_label,
                    nl_input=user_input,
                    translated_command=command,
                    tool=call.tool,
                    args=self._safe_args(call),
                    permission_decision=f"{decision.gate.value}:{gate_note}",
                    exit_code=2,  # conventional "skipped by gate" code
                    result=gate_note,
                )
                outcome.audit_records += 1
                # Tell the model the op was not performed so it can adapt.
                messages.append(self._router.tool_result_message(
                    call.call_id,
                    ToolResult(exit_code=2, stdout="", stderr="", summary=gate_note),
                ))
                continue

            # Gate cleared -> execute and audit the real op.
            result = self._safe_dispatch(call)
            outcome.tool_calls_made += 1
            self._audit.write(
                tier=self._tier_label,
                nl_input=user_input,
                translated_command=command,
                tool=call.tool,
                args=self._safe_args(call),
                permission_decision=decision.gate.value,
                exit_code=result.exit_code,
                stdout_summary=result.stdout,
                stderr_summary=result.stderr,
                result=result.summary,
            )
            outcome.audit_records += 1

            # I5: a successful mutation changes the box — invalidate context.
            if decision.op_class is not OpClass.READ and result.ok:
                self._context.invalidate()

            messages.append(self._router.tool_result_message(call.call_id, result))

    # ------------------------------------------------------------------ #
    # Permission gate resolution (I3 — uses the hardened classifier)       #
    # ------------------------------------------------------------------ #

    def _resolve_gate(self, decision, command: str) -> tuple[bool, str]:
        """Resolve one permission decision into (cleared, human_note).

        ALLOW           -> clears immediately (I8: reads feel instant).
        CONFIRM         -> plain yes/no.
        CONFIRM_TYPED   -> the literal word, typed in full.
        REFUSE          -> never clears (non-interactive write/destructive).
        """
        if decision.gate is Gate.ALLOW:
            return True, "read — allowed"

        if decision.gate is Gate.REFUSE:
            return False, decision.reason

        if decision.gate is Gate.CONFIRM:
            ok = self._io.confirm(f"Run this change? {decision.reason}.")
            return ok, ("confirmed" if ok else "declined")

        if decision.gate is Gate.CONFIRM_TYPED:
            word = decision.confirm_word or perm.DESTRUCTIVE_CONFIRM_WORD
            ok = self._io.confirm_typed(
                f"This cannot be undone: {decision.reason}.", word
            )
            return ok, ("confirmed (typed)" if ok else "declined")

        # Unknown gate -> default-deny.
        return False, "blocked for safety"

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _advertised_tools(self) -> list[dict]:
        from core.agent.prompt import build_tool_list

        return build_tool_list(self._router.advertised_schemas())

    def _safe_dispatch(self, call: ParsedCall) -> ToolResult:
        """Dispatch a validated call; turn any execution error into a ToolResult.

        The registry validated args already (router did the schema check), but a
        tool's execute() could still raise on a live box — we never let that
        crash the loop.
        """
        try:
            return self._router.dispatch(call)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                exit_code=1, stdout="", stderr=str(exc),
                summary=f"operation could not be completed: {exc}",
            )

    @staticmethod
    def _safe_args(call: ParsedCall) -> dict:
        out = dict(call.args)
        out["operation"] = call.operation
        return out

    @staticmethod
    def _assistant_message(content: str, raw_calls: list[dict]) -> dict:
        """Build the OpenAI assistant message to append to history (0002 §2)."""
        msg: dict[str, Any] = {"role": "assistant", "content": content or None}
        if raw_calls:
            tcs = []
            for rc in raw_calls:
                name = rc.get("name") or (rc.get("function") or {}).get("name", "")
                args = rc.get("arguments")
                if args is None:
                    args = (rc.get("function") or {}).get("arguments", "")
                if not isinstance(args, str):
                    args = json.dumps(args, separators=(",", ":"))
                tcs.append({
                    "id": rc.get("id", ""),
                    "type": "function",
                    "function": {"name": name, "arguments": args},
                })
            msg["tool_calls"] = tcs
        return msg


# --------------------------------------------------------------------------- #
# Interactive loop driver                                                      #
# --------------------------------------------------------------------------- #

def interactive_loop(
    repl: Repl,
    *,
    prompt: str = "> ",
    read_line: Optional[Callable[[str], str]] = None,
) -> None:
    """Read user lines and run each as a turn until EOF / 'exit' / 'quit'.

    ``read_line`` is injectable for tests; defaults to builtin input(). The loop
    swallows nothing important: a per-turn exception is reported as a plain line
    and the loop continues (one bad turn never kills the session).
    """
    reader = read_line if read_line is not None else input
    while True:
        try:
            line = reader(prompt)
        except (EOFError, KeyboardInterrupt):
            break
        if line is None:
            break
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in ("exit", "quit"):
            break
        try:
            repl.run_turn(stripped)
        except ConnectionError:
            # The local service is unreachable. One clean, I2-safe line; the
            # raw error (which may name the engine) is never surfaced.
            print("The local service is not reachable right now. Start it and try again.")
        except Exception:  # noqa: BLE001 — one bad turn never kills the loop
            print("Could not complete that request.")
