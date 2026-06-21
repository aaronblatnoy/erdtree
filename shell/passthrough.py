"""
shell/passthrough.py — run a raw bash command and stream output to the terminal.

Used for:
  - `!cmd` single-shot escapes in NL mode
  - All input in BASH mode
  - The dead-man exec-into-bash path (exec variant)

Design:
  - Output is streamed line-by-line; the user sees it as it arrives.
  - Exit code is returned to the caller (for BASH mode prompt awareness).
  - We never filter or annotate stdout/stderr — the user asked for raw bash.
  - subprocess is the only dep (stdlib).

I1: this module opens no network connections.
I2: no AI/LLM/model/agent language anywhere.
"""

from __future__ import annotations

import os
import subprocess
import sys


def run_command(command: str) -> int:
    """Run *command* in a bash subshell, streaming output directly to the
    terminal. Returns the exit code.

    We use shell=True so the full shell syntax (pipes, redirects, etc.) works
    exactly as the user expects — this is the raw escape hatch, not the tool
    layer that runs curated commands.
    """
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            executable="/bin/bash",
            # Let stdin/stdout/stderr inherit from the parent — the user gets
            # the full interactive experience (pagers, editors, progress bars).
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        proc.wait()
        return proc.returncode
    except OSError as exc:
        print(f"Could not run command: {exc}", file=sys.stderr)
        return 127


def exec_bash(banner: str | None = None) -> None:
    """Replace the current process with bash (dead-man fallback path).

    Prints *banner* if given, then os.execs into bash so the user gets an
    interactive shell. Never returns — either exec succeeds or we print an
    error and fall through (the caller must handle that case if it matters).

    We use os.execvp so the new bash is the shell process (same PID, same
    session), which is the correct behavior for a login shell fallback.
    """
    if banner:
        print(banner, file=sys.stderr, flush=True)
    try:
        os.execvp("bash", ["bash"])
    except OSError as exc:
        # bash itself is missing — last-resort message.
        print(
            f"Critical: cannot start bash ({exc}). "
            "The system may be severely degraded.",
            file=sys.stderr,
        )
