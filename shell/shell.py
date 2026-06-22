"""
shell/shell.py — the product login shell.

This is the OUTERMOST layer. It wraps the agent loop (core.agent.repl.Repl,
built by core.agent.main.build_repl) and turns it into a real login shell that
a user lands in. It does NOT reinvent the loop — it drives a single turn at a
time via Repl.run_turn and handles mode toggling, raw-bash dispatch, and the
dead-man bash fallback around it.

MODE STATE
  - NL mode is the default. The prompt is "[user@host dir] NATURAL LANGUAGE ❯ "
    with the tier-colored tail.
  - "!!" toggles PERMANENTLY into BASH mode (and back). The prompt becomes the
    plain Linux "[user@host dir]$ ".
  - "!cmd" runs a SINGLE bash command without leaving NL mode.
  - A bare "cd" is handled in-process (in either mode) so the working
    directory — and the prompt — actually changes.
  - In BASH mode, every line runs as raw bash (except "!!", which toggles back).

NL-MODE DISPATCH (shell/dispatch.py, conservative — SC4):
  - TOGGLE  -> flip the mode flag.
  - RAW     -> run one bash command, stay in NL mode.
  - ENGLISH -> hand the text to the wrapped loop (Repl.run_turn).

DEAD-MAN FALLBACK (I9 — NON-NEGOTIABLE):
  - On STARTUP: a guarded agent-start. If the local service is unreachable /
    times out / not ready, OR build_repl raises for any reason -> exec into
    bash with a LOUD plain banner. Never an unbounded wait.
  - MID-SESSION: if a turn raises ConnectionError (the local service died mid
    session) -> exec into bash with a plain banner. Never leave the user
    shell-less.
  Because of this, shell.py drives Repl.run_turn DIRECTLY rather than using
  core.agent.repl.interactive_loop (which swallows ConnectionError); the
  fallback must be the OUTERMOST guard around BOTH start and each turn.

INVARIANTS
  I1  This module opens no network connections itself. Only the wrapped loop
      talks to localhost. The startup health check (shell/hooks/startup.py)
      touches localhost only.
  I2  No "AI"/"LLM"/"model"/"agent"/"agentic" in ANY user-facing string here.
  I6  The tier label + its color are passed IN from outside (env/config), opaque.
      No tier name is branched on or hardcoded in this logic. The color lookup
      lives in shell/prompt.py, keyed by the opaque label.
  I7  No "Rocky" in any user-facing string.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from shell import dispatch as dispatch_mod
from shell import passthrough
from shell import prompt as prompt_mod
from shell.dispatch import DispatchKind
from shell.hooks import startup


# --------------------------------------------------------------------------- #
# Loud, I2-clean banners (no AI/LLM/model/agent/agentic language)              #
# --------------------------------------------------------------------------- #

_BANNER_RULE = "=" * 70

_STARTUP_FALLBACK_BANNER = (
    "\n" + _BANNER_RULE + "\n"
    "  PLAIN BASH MODE — the English command service is not available.\n"
    "  {detail}\n"
    "  You have a normal bash shell. All standard Linux commands work.\n"
    + _BANNER_RULE + "\n"
)

_MIDSESSION_FALLBACK_BANNER = (
    "\n" + _BANNER_RULE + "\n"
    "  PLAIN BASH MODE — the English command service stopped responding.\n"
    "  Dropping you into a normal bash shell so you are never stuck.\n"
    "  All standard Linux commands work.\n"
    + _BANNER_RULE + "\n"
)

_TIER_UNAVAILABLE_BANNER = (
    "\n" + _BANNER_RULE + "\n"
    "  PLAIN BASH MODE — this edition is not available on this host.\n"
    "  {detail}\n"
    "  You have a normal bash shell. All standard Linux commands work.\n"
    + _BANNER_RULE + "\n"
)


# --------------------------------------------------------------------------- #
# Mode state                                                                   #
# --------------------------------------------------------------------------- #

class Mode:
    NL = "NL"
    BASH = "BASH"


@dataclass
class ShellState:
    mode: str = Mode.NL

    def toggle(self) -> None:
        self.mode = Mode.BASH if self.mode is Mode.NL else Mode.NL


# --------------------------------------------------------------------------- #
# Dependency seams (injected so the shell is fully testable on this host)      #
# --------------------------------------------------------------------------- #

# A factory that performs the GUARDED agent start and returns a Repl-like object
# exposing run_turn(str). Injectable so tests can supply a fake that raises or a
# fake that succeeds without touching Ollama.
ReplFactory = Callable[[], object]


def _default_repl_factory() -> object:
    """Build the wrapped loop via core.agent.main.build_repl (live path).

    Raises on any wiring failure (unreachable / misconfigured endpoint); the
    caller's dead-man guard turns that into a bash fallback.
    """
    from core.agent.main import AppConfig, build_repl

    config = AppConfig.from_env(interactive=True)
    return build_repl(config)


def _exec_bash(banner: str) -> None:
    """Print *banner* loudly then exec into bash. Never returns on success."""
    passthrough.exec_bash(banner)


# --------------------------------------------------------------------------- #
# The shell                                                                    #
# --------------------------------------------------------------------------- #

class ProductShell:
    """The login shell: mode state + dispatch + dead-man fallback around Repl.

    Parameters
    ----------
    tier_label:    opaque label selecting the NL prompt color (I6). Never branched
                   on; passed straight to shell.prompt.
    repl_factory:  builds the wrapped loop (the guarded agent start). Injectable.
    health_check:  pre-shell reachability probe -> startup.HealthResult. Injectable.
    read_line:     line reader (prompt) -> str. Injectable for tests; default input().
    exec_bash:     the dead-man exec path. Injectable so tests don't replace the
                   test runner; default execs real bash.
    run_command:   raw-bash single-command runner. Injectable; default streams bash.
    """

    def __init__(
        self,
        *,
        tier_label: str = "",
        repl_factory: ReplFactory = _default_repl_factory,
        health_check: Callable[[], startup.HealthResult] = startup.check,
        read_line: Optional[Callable[[str], str]] = None,
        exec_bash: Callable[[str], None] = _exec_bash,
        run_command: Callable[[str], int] = passthrough.run_command,
    ) -> None:
        self._tier_label = tier_label
        self._repl_factory = repl_factory
        self._health_check = health_check
        self._read_line = read_line if read_line is not None else input
        self._exec_bash = exec_bash
        self._run_command = run_command
        self._state = ShellState()
        self._repl: Optional[object] = None
        self._oldpwd: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Entry point — the OUTERMOST dead-man guard lives here.              #
    # ------------------------------------------------------------------ #

    def run(self) -> int:
        """Start the shell. The very first action is a GUARDED agent start;
        any failure execs into bash with a loud banner (I9). Then the input
        loop runs, also under the dead-man guard for mid-session failures.

        Returns a process exit code (only reached if the loop ends cleanly via
        EOF/exit and the dead-man path never fired).
        """
        # --- STARTUP dead-man guard (outermost) ------------------------- #
        if not self._guarded_start():
            # _guarded_start execs into bash on failure and does not return;
            # if exec itself failed we fall through to here with no shell.
            return 1

        # --- Input loop, with the mid-session dead-man guard ------------ #
        return self._loop()

    def _guarded_start(self) -> bool:
        """Probe reachability, then build the wrapped loop. ANY failure ->
        exec bash loudly and (normally) never return. Returns True only if the
        loop is up and ready.
        """
        try:
            health = self._health_check()
        except Exception:  # noqa: BLE001 — a crashing probe must still fall back
            self._exec_bash(
                _STARTUP_FALLBACK_BANNER.format(
                    detail="The service could not be reached during startup."
                )
            )
            return False

        if not health.ok:
            self._exec_bash(
                _STARTUP_FALLBACK_BANNER.format(
                    detail=health.message or "The service is not ready right now."
                )
            )
            return False

        # Lazy import so shell.py stays importable for the dead-man path even if
        # the core stack cannot import. If core is unavailable, () matches nothing
        # and the generic handler below covers the resulting ImportError.
        try:
            from core.agent.main import TierUnavailableError as _TierUnavailable
        except Exception:  # noqa: BLE001
            _TierUnavailable = ()  # type: ignore[assignment]

        try:
            self._repl = self._repl_factory()
        except _TierUnavailable as exc:  # type: ignore[misc]
            # An unbuilt / non-operational edition was requested. Refuse clearly,
            # but never leave the box shell-less (I9): drop to plain bash.
            self._exec_bash(_TIER_UNAVAILABLE_BANNER.format(detail=str(exc)))
            return False
        except Exception:  # noqa: BLE001 — build failure must fall back, never crash
            self._exec_bash(
                _STARTUP_FALLBACK_BANNER.format(
                    detail="The service could not be started."
                )
            )
            return False

        return True

    # ------------------------------------------------------------------ #
    # The input loop                                                      #
    # ------------------------------------------------------------------ #

    def _loop(self) -> int:
        while True:
            prompt = self._current_prompt()
            try:
                line = self._read_line(prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if line is None:
                return 0

            stripped = line.strip()
            if not stripped:
                continue
            if self._state.mode is Mode.NL and stripped in ("exit", "quit"):
                return 0

            if self._state.mode is Mode.BASH:
                self._handle_bash_mode(stripped)
            else:
                self._handle_nl_mode(stripped)

    def _current_prompt(self) -> str:
        if self._state.mode is Mode.BASH:
            return prompt_mod.bash_prompt()
        return prompt_mod.nl_prompt(self._tier_label)

    # ------------------------------------------------------------------ #
    # BASH mode: every line is raw bash; "!!" toggles back to NL.         #
    # ------------------------------------------------------------------ #

    def _handle_bash_mode(self, line: str) -> None:
        if line == "!!":
            self._state.toggle()
            return
        self._exec_raw(line)

    # ------------------------------------------------------------------ #
    # NL mode: dispatch -> toggle / raw / English.                        #
    # ------------------------------------------------------------------ #

    def _handle_nl_mode(self, line: str) -> None:
        result = dispatch_mod.dispatch(line)

        if result.kind is DispatchKind.TOGGLE:
            self._state.toggle()
            return

        if result.kind is DispatchKind.RAW:
            # "!cmd" single escape OR a heuristically-recognized raw command.
            # Stays in NL mode.
            self._exec_raw(result.command)
            return

        # ENGLISH -> hand to the wrapped loop, ONE turn, under the mid-session
        # dead-man guard. A ConnectionError here means the local service died
        # mid-session: exec into bash loudly (I9) and never return.
        self._run_english_turn(result.text)

    def _exec_raw(self, command: str) -> None:
        """Run a raw command, but handle `cd` IN-PROCESS so the shell's working
        directory (and thus the prompt) actually changes — a subprocess `cd`
        would not persist. Everything else goes to the raw bash runner.
        """
        if self._maybe_cd(command):
            return
        self._run_command(command)

    def _maybe_cd(self, command: str) -> bool:
        """If *command* is a bare `cd [dir]`, change directory here and return
        True. Compound commands (cd containing ;, |, &&, etc.) fall through to
        bash. Returns False when it is not a standalone cd.
        """
        stripped = command.strip()
        if stripped != "cd" and not stripped.startswith("cd "):
            return False
        if any(ch in stripped for ch in (";", "|", "&", "\n", "`", "$(")):
            return False  # let bash handle a compound/expanded command

        arg = stripped[2:].strip()
        if arg == "-":
            target = self._oldpwd or os.environ.get("OLDPWD") or ""
            if not target:
                print("cd: OLDPWD not set", file=sys.stderr)
                return True
        elif arg == "" or arg == "~":
            target = os.path.expanduser("~")
        else:
            target = os.path.expanduser(arg)

        try:
            prev = os.getcwd()
        except OSError:
            prev = None
        try:
            os.chdir(target)
        except OSError as exc:
            print(f"cd: {exc.strerror}: {target}", file=sys.stderr)
            return True
        if prev is not None:
            self._oldpwd = prev
            os.environ["OLDPWD"] = prev
        os.environ["PWD"] = os.getcwd()
        return True

    def _run_english_turn(self, text: str) -> None:
        try:
            self._repl.run_turn(text)  # type: ignore[union-attr]
        except ConnectionError:
            self._exec_bash(_MIDSESSION_FALLBACK_BANNER)
            # exec replaces the process; if it somehow returned, stop cleanly.
            return
        except Exception:  # noqa: BLE001 — one bad turn never kills the session
            print("Could not complete that request.", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Module entry point                                                          #
# --------------------------------------------------------------------------- #

def main() -> int:
    """Construct and run the product shell.

    The tier label (which selects the NL prompt color) comes from OUTSIDE — the
    environment — and is treated as opaque (I6). No tier name is hardcoded here.
    """
    tier_label = os.environ.get("ERDTREE_TIER", "").strip()
    shell = ProductShell(tier_label=tier_label)
    return shell.run()


if __name__ == "__main__":
    raise SystemExit(main())
