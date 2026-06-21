"""
shell/dispatch.py — command-vs-English dispatch heuristic.

When in NL mode, the user types something without a `!` prefix. We must
decide: is this a raw Linux command, or English intent to send to the agent?

The rule set is CONSERVATIVE. A mis-dispatched raw command on a live box is
catastrophic; sending an ambiguous input to the agent is a minor annoyance
(the agent will still handle it correctly). So the default is English.

Rules (applied in order):
  R1  `!!`         — toggle signal (not a command; caller handles it)
  R2  `!cmd`       — always raw bash (explicit escape prefix)
  R3  First token starts with `/`, `./`, `../`  — raw (path invocation)
  R4  First token NOT on PATH (shutil.which returns None) — English intent
  R5  First token IS on PATH AND input has flag tokens (tokens starting with `-`)
                   — raw command
  R6  First token IS on PATH AND input has path-like args (tokens containing `/`)
                   — raw command
  R7  Otherwise    — English intent (conservative safe default)

Rationale for R7 being the fallback to English:
  - "systemctl status nginx" → R5 fires (flag-less but single-word second arg,
    no `/`) → falls to R7 → English; the agent translates and executes it
    correctly. That is fine.
  - A genuinely unknown English sentence whose first word happens to be on PATH
    (e.g. "find me a solution") → R7 → English. Correct.
  - `df -h` → R5 fires → raw. Correct.
  - `cat /etc/fstab` → R6 fires (arg contains `/`) → raw. Correct.
  - The ONLY risky case is R5/R6 not firing when they should. We prefer a
    false-English over a false-raw at the dispatch layer; the agent handles
    English fallthrough gracefully.

Return values (DispatchResult):
  .kind == TOGGLE   — user typed `!!`
  .kind == RAW      — run as raw bash; .command is the command string to run
  .kind == ENGLISH  — send to the agent; .text is what to send

I1: no network calls.
I2: no AI/LLM/model/agent language in user-facing strings.
"""

from __future__ import annotations

import shlex
import shutil
from dataclasses import dataclass
from enum import Enum, auto


class DispatchKind(Enum):
    TOGGLE  = auto()   # `!!` — mode toggle
    RAW     = auto()   # run as bash
    ENGLISH = auto()   # send to agent loop


@dataclass(frozen=True)
class DispatchResult:
    kind: DispatchKind
    # For RAW: the command string (stripped of leading `!` if present).
    command: str = ""
    # For ENGLISH: the text to send to the agent.
    text: str = ""


TOGGLE = DispatchResult(kind=DispatchKind.TOGGLE)

import re as _re
_REAL_FLAG_RE = _re.compile(
    r'^--[a-zA-Z0-9][a-zA-Z0-9-]*$'   # --word  /  --no-color
    r'|^-[a-zA-Z0-9]{1,2}$'            # -h  -v  -la  -rf  (≤2 chars: safe ceiling)
    # 3+ char single-dash tokens (-aux, -ing, -alyze) are excluded: 3-char chained
    # flags like -aux go to ENGLISH (AI handles them correctly), while English
    # word-fragments like -ing or -alyze never incorrectly dispatch as RAW.
)

def _is_real_flag(token: str) -> bool:
    """True only for tokens that structurally resemble real shell flags."""
    return bool(_REAL_FLAG_RE.match(token))


def dispatch(user_input: str) -> DispatchResult:
    """Classify *user_input* from NL-mode into a DispatchResult.

    All classification is pure Python — no subprocess, no network.
    """
    stripped = user_input.strip()

    # R1 — mode toggle
    if stripped == "!!":
        return TOGGLE

    # R2 — explicit raw-bash escape
    if stripped.startswith("!"):
        return DispatchResult(kind=DispatchKind.RAW, command=stripped[1:].lstrip())

    # Tokenize for subsequent rules.  shlex is used so quoted tokens stay
    # together; on parse failure we treat input as English (conservative).
    try:
        tokens = shlex.split(stripped)
    except ValueError:
        return DispatchResult(kind=DispatchKind.ENGLISH, text=stripped)

    if not tokens:
        return DispatchResult(kind=DispatchKind.ENGLISH, text=stripped)

    first = tokens[0]

    # R3 — absolute or relative path invocation
    if first.startswith("/") or first.startswith("./") or first.startswith("../"):
        return DispatchResult(kind=DispatchKind.RAW, command=stripped)

    # R4 — first token not on PATH → English (not a known command)
    if shutil.which(first) is None:
        return DispatchResult(kind=DispatchKind.ENGLISH, text=stripped)

    # First token IS on PATH — check for structural indicators of raw commands.
    rest = tokens[1:]

    # R5 — a token that structurally looks like a real shell flag → raw.
    # Accepted: --word  or  -X  where X is 1–4 alphanumeric chars (-h, -la, -rf, -aux).
    # Rejected: -alyze, -arefully, -ing-like-suffixes — English word fragments with a
    # leading dash are not shell flags and must not trigger raw dispatch.
    if any(_is_real_flag(t) for t in rest):
        return DispatchResult(kind=DispatchKind.RAW, command=stripped)

    # R6 — any argument that looks path-like (contains `/`) → raw
    if any("/" in t for t in rest):
        return DispatchResult(kind=DispatchKind.RAW, command=stripped)

    # R7 — conservative default: treat as English
    # Rationale: "systemctl status nginx", "find me something", "show uptime"
    # are all better handled by the agent than by a mis-dispatch heuristic.
    return DispatchResult(kind=DispatchKind.ENGLISH, text=stripped)
