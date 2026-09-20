"""No-call guard — never show the operator a result that was not obtained.

A fine-tuned model that was trained only on single-turn records will, on a
follow-up, WRITE a plausible result ("crond.service started; active (running);
PID 1420") instead of calling a tool.  Nothing ran.  For a system interface
that is the most dangerous possible failure, so the runtime refuses to display
such a reply: when no operation was dispatched this turn and the reply looks
like command output, or the request plainly asked for an action or a live
fact, the loop re-asks once for a tool call and otherwise reports that
nothing was run.

Pure stdlib, deterministic.  Strings here are user-facing and I2-clean.
"""
from __future__ import annotations

import re

# Text that reads like the output of an operation.
_RESULT_SHAPES = re.compile(
    r"(\bPID\b\s*:?\s*\d+|\bMain PID\b|active \((running|exited)\)|inactive \(dead\)|"
    r"\bexit(ed)? (code|status)\b|\bexit code \d+|\b(started|stopped|restarted|reloaded|enabled|disabled|"
    r"installed|removed|deleted|created|mounted|unmounted|added|applied)\b[.;,]|"
    r"\b\d+\.\d+(\.\d+)?-\d+[\w.]*\.el\d|\blistening on\b|\bsince (Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b|"
    r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})",
    re.I,
)
_ACTION_LEAD = re.compile(
    r"^\s*(please\s+|ok[,.]?\s+|okay[,.]?\s+|now\s+|and\s+|then\s+|yes[,.]?\s+|also\s+)*"
    r"(restart|start|stop|reload|enable|disable|mask|install|remove|uninstall|update|upgrade|delete|add|set|"
    r"create|make|show|list|check|get|run|open|close|allow|deny|block|mount|unmount|format|wipe|kill|"
    r"signal|rename|move|copy|extract|archive|back ?up|restore|sync|schedule|undo|revert|retry|do|"
    r"bring|take|give|tell me (the|what|which|how many)|find|search|look|view|tail|flush|rotate|lock|unlock)\b",
    re.I,
)
_FOLLOWUP_ACTION = re.compile(r"\b(same|again|get it running|do it|do that|go ahead|for the other|the other one)\b", re.I)
_PLAIN_QUESTION = re.compile(r"^\s*(what (is|are|does|do)|how (do|does|can|to)|why (is|are|does|do)|explain|difference between|meaning of)\b", re.I)

REASK_TEXT = (
    "No operation was run for that request. Call the appropriate tool now. "
    "Do not describe a result that you have not obtained."
)
NOTHING_RAN_TEXT = "Nothing was run. Rephrase the request or name the unit, file, or target."


def looks_like_result(text: str) -> bool:
    return bool(_RESULT_SHAPES.search(text or ""))


def wants_operation(user_input: str) -> bool:
    text = user_input or ""
    if _PLAIN_QUESTION.search(text):
        return False
    return bool(_ACTION_LEAD.search(text) or _FOLLOWUP_ACTION.search(text))


def should_block(user_input: str, reply_text: str, calls_this_turn: int) -> bool:
    """True when a prose reply must NOT be shown because nothing was executed."""
    if calls_this_turn > 0:
        return False
    return looks_like_result(reply_text) or wants_operation(user_input)
