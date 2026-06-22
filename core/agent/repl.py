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
import re
import sys
import threading
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

# Strip ANSI/VT escape sequences from captured command output before display
# (OpenCode does the same via stripAnsi — raw stdout may carry color codes).
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# Cap raw command output so a `cat` of a huge file does not flood the screen.
_MAX_OUTPUT_LINES = 60

# --- Tool-block presentation (ports OpenCode's BlockTool: a left-gutter panel
#     with a muted title line = the command, a spinner while it runs, then the
#     real output below the same gutter). Plain ANSI so it works in any tty. ---
_DIM = "\x1b[2m"
_GRAY = "\x1b[90m"
_GREEN = "\x1b[32m"
_RED = "\x1b[31m"
_AMBER = "\x1b[33m"
_RESET = "\x1b[0m"
_CLEAR_LINE = "\r\x1b[2K"
_GUTTER = "\x1b[90m│\x1b[0m"            # dim vertical bar, the block's left edge
# Braille spinner frames (same family OpenCode/Claude Code use).
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SPINNER_DELAY = 0.15                    # don't paint for fast ops (no flash)
_SPINNER_INTERVAL = 0.08


# A trailing offer of MORE interaction ("Would you like more detail?", "Let me
# know if...", "Want me to..."). Narrow on purpose: it must NOT eat genuine
# sysadmin advice like "If you need to change it, edit sshd_config." — only
# clauses that offer further help/output from the system itself.
_CHATBOT_TRAILER = re.compile(
    r"(?:\n+|(?<=[.!?])\s+)"
    r"(?:would you like|do you want|did you want|let me know|feel free|"
    r"if you(?:'d| would) (?:like|prefer|want)|"
    r"want me to|shall i|should i (?:provide|show|give|list|summarize|elaborate)|"
    r"is there (?:anything|something)(?:\s+else)?)"
    r"\b[^\n]*?[?.]?\s*$",
    re.IGNORECASE,
)


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting from terminal output.

    The model may emit markdown regardless of instructions.  Strip it at
    render time so the terminal always sees plain text (I2-adjacent: no
    document-renderer artifacts in a raw terminal).
    """
    # Triple-backtick fences: drop the fence line, keep content inside
    text = re.sub(r"```[^\n]*\n?", "", text)
    # Inline backticks: keep the content, drop the backticks
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    # Bullet / list markers at the start of a line
    text = re.sub(r"(?m)^[ \t]*[-*]\s+", "", text)
    # Markdown headers
    text = re.sub(r"(?m)^#+\s+", "", text)
    # Bold and italic markers
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
    # Chatbot closings ("let me know", "feel free", etc.)
    text = _CHATBOT_TRAILER.sub("", text)
    # Collapse 3+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class ReplIO(Protocol):
    """Everything the loop needs from the terminal. Injected for tests.

    The three methods below are the BASE contract every IO implements.

    OPTIONAL incremental-render hooks (feature-detected by the loop via the
    responder's delta sink — run_turn itself never calls them directly):

      render_delta(token)      -> stream one content token live (no newline)
      tool_step(text)          -> announce a step about to run        (P3)
      tool_step_result(text)   -> report a step's outcome             (P3)

    Any IO implementing only render()/confirm()/confirm_typed() (today's
    contract) still works: the streaming responder owns the delta sink, and a
    buffered responder never produces deltas, so behavior is byte-identical to
    the pre-streaming path when these hooks are absent.
    """

    def render(self, text: str) -> None: ...
    def confirm(self, prompt: str) -> bool: ...
    def confirm_typed(self, prompt: str, word: str) -> bool: ...

    # Optional (no-op default in callers; ConsoleIO implements render_delta).
    def begin_turn(self) -> None: ...               # reset per-turn display state
    def render_delta(self, token: str) -> None: ...
    def tool_step(self, text: str) -> None: ...
    def tool_step_result(self, text: str) -> None: ...
    def tool_output(self, text: str) -> None: ...   # raw read stdout, verbatim


class ConsoleIO:
    """Default IO: plain stdin/stdout. No AI/LLM language anywhere (I2).

    Incremental rendering: when a streaming responder is wired, each content
    token arrives via render_delta() and is written with NO trailing newline +
    an explicit flush so the answer appears live. render() then closes the
    streamed line WITHOUT re-printing it (NO DOUBLE-RENDER). When no token was
    streamed (the buffered path), render() prints the full English answer
    exactly as it does today — byte-identical.
    """

    def __init__(self, *, interactive: bool = True) -> None:
        self.interactive = interactive
        # Accumulates content already emitted token-by-token this turn so
        # render() knows not to re-print it.  Empty -> buffered path.
        self._streamed = ""
        # Presentation state for tool steps (reset each turn).
        self._pending_cmd = ""           # command for the in-flight step
        self._had_tool_step = False      # a step ran this turn -> breathe before answer
        self._answer_open = False        # the streamed answer has begun this turn
        self._pending_confirmed = False  # True after a granted confirm (write op)
        self._header_open = False        # an unterminated block-title line is on screen
        self._block_shown = False        # a tool block was already rendered this turn
        self._spin_stop: Optional[threading.Event] = None
        self._spin_thread: Optional[threading.Thread] = None

    def begin_turn(self) -> None:
        """Reset per-turn display state. Called once at the top of each turn so
        block separation and answer spacing never leak across turns (robust even
        when the final answer is suppressed and render() is not called)."""
        self._had_tool_step = False
        self._answer_open = False
        self._block_shown = False
        self._streamed = ""

    @staticmethod
    def _isatty() -> bool:
        try:
            return sys.stdout.isatty()
        except Exception:  # noqa: BLE001 — rendering must never crash the loop
            return False

    def render_delta(self, token: str) -> None:
        # Buffer the token; render() prints the full stripped response once
        # streaming completes.  This defers display until we can strip markdown
        # from the whole response rather than printing raw tokens as they arrive.
        if not token:
            return
        self._answer_open = True
        self._streamed += token

    def tool_step(self, text: str) -> None:
        """Open a tool block: a left-gutter title line carrying the command.

        Ports OpenCode's BlockTool title (a muted line, the command) plus its
        running-spinner. On a tty the line is left OPEN so the spinner can
        animate in place and the result resolves it cleanly; off a tty it is a
        plain one-shot line.
        """
        if not text:
            return
        cmd = text[len("running: "):] if text.startswith("running: ") else text
        self._pending_cmd = cmd
        self._had_tool_step = True
        # Write ops (gate already confirmed): no block; the ✓ line stands alone.
        if self._pending_confirmed:
            return
        # Separate consecutive tool blocks with a blank line (BlockTool margin).
        if self._block_shown:
            print()
        self._block_shown = True
        # Read ops: open the block with its title = the command.
        if self._isatty():
            sys.stdout.write(f"{_GUTTER} {_DIM}{cmd}{_RESET}")
            sys.stdout.flush()
            self._header_open = True
            self._start_spinner(cmd)
        else:
            print(f"{_GUTTER} {cmd}", flush=True)

    def tool_step_result(self, text: str) -> None:
        status = (text or "").strip()
        self._stop_spinner()
        cmd = self._pending_cmd
        self._pending_cmd = ""
        confirmed = self._pending_confirmed
        self._pending_confirmed = False
        low = status.lower()

        # Resolve any open block-title line to a clean, spinner-free state.
        if self._header_open:
            sys.stdout.write(f"{_CLEAR_LINE}{_GUTTER} {_DIM}{cmd}{_RESET}\n")
            sys.stdout.flush()
            self._header_open = False

        # Declined / not run: nothing — the user already saw the [y/N] prompt.
        if low in ("not run", ""):
            return

        # Error: red, inside the block for a read; standalone for a write.
        if (low.startswith("exit") and low != "exit 0") or "error" in low or "could not" in low:
            if cmd and confirmed:
                print(f"{_RED}✗ {cmd} · {status}{_RESET}", flush=True)
            elif cmd:
                print(f"{_GUTTER} {_RED}✗ {status}{_RESET}", flush=True)
            return

        # Success: a confirmed write gets a green ✓ line (no block, matches the
        # marketing demo). A read's success is shown by its output block below.
        if confirmed and cmd:
            print(f"{_GREEN}✓ {cmd}{_RESET}", flush=True)

    def tool_output(self, text: str) -> None:
        """Render a read op's RAW stdout verbatim under the block gutter — the
        way Claude Code and OpenCode show command output: the real bytes, never
        a re-typed summary.

        ANSI escapes are stripped (OpenCode does the same via stripAnsi). Very
        long output is capped with a trailing note so a `cat` of a huge file
        does not flood the terminal.
        """
        if not text:
            return
        clean = _ANSI_ESCAPE.sub("", text).rstrip("\n")
        if not clean:
            return
        lines = clean.split("\n")
        shown, hidden = lines[:_MAX_OUTPUT_LINES], len(lines) - _MAX_OUTPUT_LINES
        # Blank gutter row separates the title from the output (BlockTool gap).
        out = [_GUTTER]
        out += [f"{_GUTTER} {line}" for line in shown]
        if hidden > 0:
            plural = "s" if hidden != 1 else ""
            out.append(f"{_GUTTER} {_GRAY}… {hidden} more line{plural}{_RESET}")
        print("\n".join(out), flush=True)

    # ---- running spinner (ports OpenCode's BlockTool spinner) -------------- #

    def _start_spinner(self, cmd: str) -> None:
        """Animate a spinner on the open title line, after a short delay so a
        fast read never flashes. Runs in a daemon thread; only the thread writes
        to stdout between tool_step and tool_step_result (which joins it)."""
        if not self._isatty():
            return
        stop = threading.Event()
        self._spin_stop = stop

        def _run() -> None:
            # Delay first paint: if the op finishes within the delay, the spinner
            # never appears (no flash on instant reads).
            if stop.wait(_SPINNER_DELAY):
                return
            i = 0
            while not stop.is_set():
                frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
                try:
                    sys.stdout.write(f"{_CLEAR_LINE}{_GUTTER} {_GRAY}{frame}{_RESET} {_DIM}{cmd}{_RESET}")
                    sys.stdout.flush()
                except Exception:  # noqa: BLE001 — a write race never breaks a turn
                    return
                i += 1
                if stop.wait(_SPINNER_INTERVAL):
                    return

        self._spin_thread = threading.Thread(target=_run, daemon=True)
        self._spin_thread.start()

    def _stop_spinner(self) -> None:
        if self._spin_stop is not None:
            self._spin_stop.set()
        if self._spin_thread is not None:
            self._spin_thread.join(timeout=0.3)
        self._spin_stop = None
        self._spin_thread = None

    def render(self, text: str) -> None:
        had_step = self._had_tool_step
        self._had_tool_step = False
        self._answer_open = False
        # Streaming path: _streamed holds buffered tokens; use the authoritative
        # assembled text when available, fall back to the buffer otherwise.
        if self._streamed:
            to_print = text if text else self._streamed
            self._streamed = ""
        else:
            to_print = text
        if not to_print:
            print()
            return
        stripped = _strip_markdown(to_print)
        if stripped:
            if had_step:
                print()  # breathing room between tool steps and the answer
            print(stripped)
        else:
            print()

    def confirm(self, prompt: str) -> bool:
        if not self.interactive:
            return False
        try:
            ans = input(f"{prompt} [y/N] ").strip().lower()
        except EOFError:
            return False
        ok = ans in ("y", "yes")
        if ok:
            self._pending_confirmed = True
        return ok

    def confirm_typed(self, prompt: str, word: str) -> bool:
        if not self.interactive:
            return False
        print(f"\x1b[33m⚠  {prompt}\x1b[0m")
        try:
            ans = input(f"Type {word} to proceed: ")
        except EOFError:
            return False
        ok = perm.confirms_destructive(ans)
        if ok:
            self._pending_confirmed = True
        return ok


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
    read_output_shown: bool = False    # a read op's raw stdout was displayed
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
    op = call.operation
    if call.tool == "services":
        unit = args.get("unit", "")
        if op in ("status", "logs"):
            return f"systemctl {op} {unit}".strip()
        return f"systemctl {op} {unit}".strip()
    if call.tool == "packages":
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

    # ------------------------------------------------------------------ #
    # P6 tools — render the FAITHFUL command line so the SAME hardened     #
    # classifier (permissions.classify) assigns the gate. For destructive #
    # ops we emit the REAL dangerous argv so the classifier ESCALATES.     #
    # CONSERVATISM RULE: any op we cannot render precisely (and EVERY      #
    # write op whose precise render is not needed to reach its class)      #
    # falls through to the `f"{tool} {op}"` default-deny WRITE floor —     #
    # we NEVER emit a string that UNDER-states the blast radius.           #
    # ------------------------------------------------------------------ #

    # docs.retrieve — a pure READ. Render a clearly-read shape so the
    # classifier returns Gate.ALLOW with no gate friction (I8).
    if call.tool == "docs":
        if op == "retrieve":
            # A pure READ. Use a FIXED read sentinel (`man -k`, an apropos
            # reference lookup) and DELIBERATELY do NOT splice the user's query
            # into it: arbitrary query text (e.g. a word like "mount" or
            # "nmcli") would trip the classifier's write-shape patterns and
            # wrongly gate a pure read. The gate only needs to see that this is
            # a read; the real retrieval text never reaches the shell.
            return "man -k"
        return f"{call.tool} {op}"

    # hardware.* — every op is a pure READ lister; emit the real read argv.
    if call.tool == "hardware":
        _HW = {
            "cpu": "lscpu", "memory": "free -h", "pci": "lspci",
            "usb": "lsusb", "block": "lsblk", "sensors": "sensors",
            "summary": "uname -a",
        }
        return _HW.get(op, f"{call.tool} {op}")

    if call.tool == "disk":
        device = str(args.get("device", "") or "")
        if op == "usage":
            return f"df -h {args.get('path', '') or ''}".strip()
        if op == "list":
            return f"lsblk {device}".strip()
        if op == "smart":
            return f"smartctl -a {device}".strip()
        if op == "mount":
            return f"mount {device} {args.get('mount_point', '') or ''}".strip()
        if op == "unmount":
            return f"umount {args.get('target', '') or ''}".strip()
        # --- DESTRUCTIVE: emit the real dangerous form so the classifier
        #     escalates to DESTRUCTIVE -> CONFIRM_TYPED (REFUSE non-interactive).
        if op == "format":
            fstype = str(args.get("fstype") or "ext4")
            return f"mkfs.{fstype} {device}".strip()
        if op == "partition":
            raw = args.get("command")
            if isinstance(raw, list):
                cmd_str = " ".join(str(c) for c in raw)
            elif raw:
                cmd_str = str(raw)
            else:
                cmd_str = ""
            return f"parted {device} {cmd_str}".strip()
        if op == "wipe":
            return f"wipefs -a {device}".strip()
        if op == "dd_write":
            source = str(args.get("source", "") or "")
            bs = str(args.get("bs") or "4M")
            return f"dd if={source} of={device} bs={bs}".strip()
        return f"{call.tool} {op}"

    if call.tool == "users":
        user = str(args.get("user", "") or "")
        if op == "list":
            return "cat /etc/passwd"
        if op == "info":
            return f"id {user}".strip()
        if op == "add":
            return f"useradd {user}".strip()
        if op == "set_shell":
            return f"usermod -s {args.get('shell', '') or ''} {user}".strip()
        if op == "add_to_group":
            return f"usermod -aG {args.get('group', '') or ''} {user}".strip()
        # --- DESTRUCTIVE lockout set: emit the real argv.
        if op == "lock":
            return f"usermod -L {user}".strip()
        if op == "delete":
            return f"userdel {user}".strip()
        if op == "remove_from_privgroup":
            # The tool removes from the privileged group "wheel"; the classifier
            # recognises `gpasswd -d <user> wheel` as a sudo-lockout DESTRUCTIVE.
            return f"gpasswd -d {user} wheel".strip()
        return f"{call.tool} {op}"

    if call.tool == "firewall":
        # Mirror the tool's real argv EXACTLY: space-separated flags and a
        # `--zone <zone>` operand (the classifier's firewall READ sub-verb map
        # keys on the bare `--query-service` token, so the `=` form would
        # mis-classify a read as a write).
        zone = args.get("zone")
        zone_part = f"--zone {zone} " if zone else ""
        if op == "list":
            return f"firewall-cmd {zone_part}--list-all".strip()
        if op == "get_zones":
            return "firewall-cmd --get-zones"
        if op == "query":
            return f"firewall-cmd {zone_part}--query-service {args.get('service', '') or ''}".strip()
        if op == "add_service":
            return f"firewall-cmd {zone_part}--add-service {args.get('service', '') or ''}".strip()
        if op == "add_port":
            return f"firewall-cmd {zone_part}--add-port {args.get('port', '') or ''}".strip()
        if op == "remove_service":
            return f"firewall-cmd {zone_part}--remove-service {args.get('service', '') or ''}".strip()
        if op == "remove_port":
            return f"firewall-cmd {zone_part}--remove-port {args.get('port', '') or ''}".strip()
        if op == "reload":
            return "firewall-cmd --reload"
        if op == "set_default_zone":
            return f"firewall-cmd --set-default-zone {zone or ''}".strip()
        # --- DESTRUCTIVE: panic mode drops all traffic (lockout).
        if op == "panic_on":
            return "firewall-cmd --panic-on"
        return f"{call.tool} {op}"

    if call.tool == "network":
        iface = str(args.get("interface", "") or "")
        if op == "show":
            return "ip addr show"
        if op == "status":
            return "ip -brief addr"
        if op == "connections":
            # The tool runs `nmcli con show` (a read), but the classifier flags
            # ANY bare `nmcli` invocation as write-capable. Render the read
            # faithfully as a listing of the connection profiles so a pure read
            # stays ALLOW (no gate friction — I8) without weakening the gate.
            return "ls /etc/NetworkManager/system-connections"
        if op == "interfaces":
            return "ip link show"
        if op == "bring_up":
            return f"ip link set {iface} up".strip()
        if op == "set_ip":
            return f"ip addr add {args.get('address', '') or ''} dev {iface}".strip()
        # NOTE (network.bring_down): the faithful argv is `ip link set <if>
        # down`. The frozen classifier (permissions.py — which P6 must NOT
        # weaken or modify, I3) classifies that string as WRITE -> CONFIRM
        # (REFUSE non-interactive): it has no destructive rule for an
        # interface teardown. We emit the faithful form; it is still GATED
        # and never auto-run, satisfying the CONSERVATISM RULE (no
        # under-running). It does NOT reach CONFIRM_TYPED because the
        # classifier — not synthesize — owns that escalation, and editing
        # permissions.py is out of scope for this pass.
        if op == "bring_down":
            return f"ip link set {iface} down".strip()
        return f"{call.tool} {op}"

    if call.tool == "processes":
        pid = args.get("pid")
        pid_str = str(pid) if pid is not None else ""
        if op == "list":
            return "ps aux"
        if op == "tree":
            return "ps -ejH"
        if op == "top":
            return "ps aux --sort=-%cpu"
        if op == "info":
            return f"ps -p {pid_str}".strip()
        if op == "renice":
            prio = args.get("priority")
            prio_str = str(prio) if prio is not None else ""
            return f"renice -n {prio_str} -p {pid_str}".strip()
        if op == "signal":
            sig = args.get("signal_num")
            if sig is None:
                # plain TERM -> WRITE
                return f"kill {pid_str}".strip()
            # Emit the real `kill -<n> <pid>` argv. A kill-all / init signal
            # (-1) trips the classifier's `kill ... -1` DESTRUCTIVE rule.
            try:
                sig_int = int(sig)
            except (TypeError, ValueError):
                # Unparseable signal -> default-deny floor (WRITE at minimum).
                return f"{call.tool} {op}"
            sig_flag = str(sig_int) if sig_int < 0 else f"-{sig_int}"
            return f"kill {sig_flag} {pid_str}".strip()
        return f"{call.tool} {op}"

    if call.tool == "files":
        path = str(args.get("path", "") or "")
        if op == "list":
            return f"tree -L 2 {path}".strip()
        if op == "read":
            return f"cat {path}".strip()
        if op == "stat":
            return f"stat {path}".strip()
        if op == "find":
            return f"find {path}".strip()
        if op == "copy":
            rec = " -r" if args.get("recursive") else ""
            return f"cp{rec} {args.get('src', '') or ''} {args.get('dst', '') or ''}".strip()
        if op == "move":
            return f"mv {args.get('src', '') or ''} {args.get('dst', '') or ''}".strip()
        if op == "mkdir":
            par = " -p" if args.get("parents", True) else ""
            return f"mkdir{par} {path}".strip()
        if op == "chmod":
            rec = " -R" if args.get("recursive") else ""
            return f"chmod{rec} {args.get('mode', '') or ''} {path}".strip()
        if op == "chown":
            rec = " -R" if args.get("recursive") else ""
            return f"chown{rec} {args.get('owner', '') or ''} {path}".strip()
        if op == "write":
            return f"tee {path}".strip()
        if op == "remove":
            # Mirror the tool's real argv: `rm [-r] [-f] <path>`. Recursive /
            # forced / system-path removals trip the classifier's DESTRUCTIVE
            # rm rules; a plain `rm <path>` stays WRITE.
            flags = ""
            if args.get("recursive"):
                flags += " -r"
            if args.get("force"):
                flags += " -f"
            return f"rm{flags} {path}".strip()
        return f"{call.tool} {op}"

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
        memory: Optional[Any] = None,
        episodic: Optional[Any] = None,
        compaction_threshold: int = 0,
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
        # P8 invisible memory (all OPTIONAL — absence preserves pre-P8 behavior
        # byte-for-byte, I9).
        #   memory:    a TranscriptMemory. None -> history stays [] (today's
        #              behavior EXACTLY); existing repl/router/loop tests stay green.
        #   episodic:  an EpisodicMemory. Reserved for past-operation recall; the
        #              loop PREFERS routing recall through the docs-tool engine
        #              (the loop CALLS it like any other read — keeps the
        #              "loop decides" property), so the loop does not inject it
        #              here.  Stored so callers/tests can reach it; never auto-run.
        #   compaction_threshold: the opaque per-tier char budget handed to
        #              TranscriptMemory.compacted_history(); <=0 means "no budget
        #              cap" (compaction policy still applies — see memory.py).
        self._memory = memory
        self._episodic = episodic
        self._compaction_threshold = compaction_threshold

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

        # Reset per-turn display state (block separation, answer spacing). Hook
        # is optional + feature-detected, so non-ConsoleIO IOs are unaffected.
        begin = getattr(self._io, "begin_turn", None)
        if begin is not None:
            try:
                begin()
            except Exception:  # noqa: BLE001 — display never breaks a turn
                pass

        snapshot_text = self._context.snapshot_text()
        tools = self._advertised_tools()
        # P8 invisible memory: when a TranscriptMemory is wired, the `history`
        # arg is the silently-compacted prior-turn window (recent turns verbatim
        # so deixis resolves; older turns keep only outcomes).  With memory=None
        # this is [] — TODAY's behavior EXACTLY (I9, backward-compatible).
        history = (
            self._memory.compacted_history(self._compaction_threshold)
            if self._memory is not None
            else []
        )
        # Index into `messages` where THIS turn's new messages begin: everything
        # appended below (the assistant turns + tool-result messages for this
        # request) is what we hand to memory.record() once the turn completes.
        messages, _ = assemble(
            user_input=user_input,
            snapshot_text=snapshot_text,
            history=history,
            tier_prompt=self._tier_prompt,
            tools=[],
        )
        new_msgs_start = len(messages)

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
                # Presentation only. A faulting render (e.g. a broken streaming
                # sink that raised partway and left render() in a bad state)
                # must NEVER kill the turn or skip the memory/audit bookkeeping
                # below (mirrors the _safe_emit wrap on the delta sink, P1).
                #
                # When we already showed the real command output for a read,
                # a SMALL model tends to re-type that data as prose (lossily).
                # Suppress that re-typing: keep only a TERSE insight (the way a
                # diagnosis like "port conflict on :80" is kept, but a 16-line
                # re-listing of `ls` is dropped — the user already has the real
                # output above). Length is the discriminator: synthesis is
                # short, a data echo is bulky.
                if outcome.read_output_shown and self._is_data_echo(verdict.content):
                    pass  # the real output above IS the answer
                else:
                    self._safe_render(verdict.content)
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

        # Fallback: the turn produced nothing the user could see — no English
        # answer, no read output, no op ran, no gate prompt. (E.g. the model
        # only emitted malformed tool-call attempts until the round cap.) Show
        # one clean, honest line instead of a silent void. I2-clean.
        if (
            not outcome.ended_in_english
            and not outcome.read_output_shown
            and outcome.tool_calls_made == 0
            and outcome.refused == 0
        ):
            self._safe_render("Could not turn that into an operation. Try rephrasing it.")

        # P8: fold THIS turn's new messages into the transcript memory so the
        # NEXT turn's compacted_history() carries them.  Walk the appended slice
        # grouping each assistant message with the role:"tool" results that
        # follow it (the TranscriptMemory.record() shape).  memory=None -> no-op,
        # so the loop is byte-compatible with the pre-P8 path (I9).  Recording
        # never raises out of run_turn (I9): any failure is swallowed.
        if self._memory is not None:
            try:
                self._record_turn(messages[new_msgs_start:])
            except Exception:  # noqa: BLE001 — memory bookkeeping never breaks a turn
                pass

        outcome.history = messages
        return outcome

    def _record_turn(self, new_messages: list[dict]) -> None:
        """Group this turn's appended messages into TranscriptMemory records.

        ``new_messages`` is the ordered slice appended during this turn: zero or
        more assistant messages, each optionally followed by its role:"tool"
        result messages.  Each assistant message becomes one recorded Turn with
        its trailing tool results.  Any leading non-assistant message (should not
        occur) is ignored defensively.
        """
        current_assistant: Optional[dict] = None
        tool_results: list[dict] = []
        for msg in new_messages:
            role = msg.get("role")
            if role == "assistant":
                if current_assistant is not None:
                    self._memory.record(current_assistant, tool_results)
                current_assistant = msg
                tool_results = []
            elif role == "tool" and current_assistant is not None:
                tool_results.append(msg)
        if current_assistant is not None:
            self._memory.record(current_assistant, tool_results)

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
                # Display ONLY (SC4): a refused/declined op NEVER gets a
                # "running:" line (I3 honesty — we never imply an unconfirmed
                # write ran). Report a neutral "not run" status instead.
                self._emit_tool_step_result("not run")
                # Tell the model the op was not performed so it can adapt.
                messages.append(self._router.tool_result_message(
                    call.call_id,
                    ToolResult(exit_code=2, stdout="", stderr="", summary=gate_note),
                ))
                continue

            # Gate cleared -> the op is ACTUALLY going to run. Announce it now
            # (display ONLY, SC4 — zero audit, no gate change). synthesize_command
            # is already an I2-clean shell argv.
            self._emit_tool_step("running: " + command)

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

            # Display ONLY (SC4): terse status AFTER dispatch + audit. This adds
            # zero audit records and does not alter audit ordering.
            self._emit_tool_step_result(self._step_status(result))

            # Show the REAL command output for a successful read, verbatim —
            # the harness displays it, the model never re-types it (the Claude
            # Code / OpenCode pattern). Reads only: a write's stdout is noise,
            # and the ✓ line already reports the write. Display ONLY (SC4).
            if decision.op_class is OpClass.READ and result.ok and result.stdout.strip():
                if self._emit_tool_output(result.stdout):
                    outcome.read_output_shown = True

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
            ok = self._io.confirm(command)
            return ok, ("confirmed" if ok else "declined")

        if decision.gate is Gate.CONFIRM_TYPED:
            word = decision.confirm_word or perm.DESTRUCTIVE_CONFIRM_WORD
            ok = self._io.confirm_typed(decision.reason, word)
            return ok, ("confirmed (typed)" if ok else "declined")

        # Unknown gate -> default-deny.
        return False, "blocked for safety"

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _safe_render(self, text: str) -> None:
        """Render the final English answer; a presentation fault never aborts.

        Rendering is presentation ONLY (SC4). If the IO's render() raises — for
        instance a streaming sink that faulted mid-stream — the turn must still
        complete and record its memory/audit bookkeeping. We swallow the fault
        here exactly as the delta sink is wrapped (P1), never the audit path.
        """
        try:
            self._io.render(text)
        except Exception:  # noqa: BLE001 — presentation never breaks a turn
            pass

    def _advertised_tools(self) -> list[dict]:
        from core.agent.prompt import build_tool_list

        return build_tool_list(self._router.advertised_schemas())

    # ------------------------------------------------------------------ #
    # Live tool-step display (P3) — PRESENTATION ONLY (SC4).               #
    # These NEVER write audit, NEVER touch the gate, and degrade to a      #
    # no-op when the IO does not implement the optional hook (BACK-COMPAT  #
    # with today's render()/confirm()/confirm_typed()-only IOs).           #
    # ------------------------------------------------------------------ #
    def _emit_tool_step(self, text: str) -> None:
        hook = getattr(self._io, "tool_step", None)
        if hook is None:
            return
        try:
            hook(text)
        except Exception:  # noqa: BLE001 — display never breaks a turn
            pass

    def _emit_tool_step_result(self, text: str) -> None:
        hook = getattr(self._io, "tool_step_result", None)
        if hook is None:
            return
        try:
            hook(text)
        except Exception:  # noqa: BLE001 — display never breaks a turn
            pass

    def _emit_tool_output(self, text: str) -> bool:
        """Show raw read output. Returns True iff it was ACTUALLY displayed.

        The return value gates answer-suppression: we only drop the model's
        re-typing when the real output was genuinely shown. An IO without the
        hook (or one that raised) returns False, so the model's answer is kept
        and the user is never left with nothing.
        """
        hook = getattr(self._io, "tool_output", None)
        if hook is None:
            return False
        try:
            hook(text)
            return True
        except Exception:  # noqa: BLE001 — display never breaks a turn
            return False

    @staticmethod
    def _is_data_echo(text: str) -> bool:
        """True if the model's answer is a bulky re-typing of data already shown.

        We display real read output ourselves; a frontier model would add a
        terse insight, but a small model re-lists the data. Discriminate by
        bulk: a genuine insight is short (a sentence or two); a data echo is
        long or many-lined. Conservative — when in doubt, KEEP the answer
        (only clearly-bulky text is suppressed).
        """
        stripped = (text or "").strip()
        if not stripped:
            return True  # nothing to add — the real output stands alone
        lines = [ln for ln in stripped.splitlines() if ln.strip()]
        return len(lines) > 3 or len(stripped) > 240

    @staticmethod
    def _step_status(result: ToolResult) -> str:
        """Terse, I2-clean status for a dispatched op, derived from ToolResult.

        Speaks as a command interface ("done", "exit 0", "exit 1") — never as
        an actor. No AI/LLM/model/agent language (I2).
        """
        code = result.exit_code
        if code is None:
            return "not run"
        if code == 0:
            return "done"
        return f"exit {code}"

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
