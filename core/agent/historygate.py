"""History gate — decide whether prior turns belong in this turn's prompt.

The fine-tuned models were trained on single-turn records: system prompt,
one request, one call, one result, one answer.  Feeding them a transcript of
earlier turns is out of distribution and measurably degrades them (they drift
into prose and stop calling tools).  So history is included ONLY when the
request cannot be understood without it: it refers back to something
("it", "that one", "the same for nginx", "do it", "again", "undo"), or it is so
short that it is plainly a continuation ("yes", "ok", "the second").

Everything else is treated as a fresh, self-contained request and gets no
history at all.  Pure stdlib, deterministic, unit-tested.
"""
from __future__ import annotations

import re

# Words that only make sense with an antecedent.
_ANAPHORA = {
    "it", "its", "that", "those", "these", "them", "this", "one", "ones",
    "same", "again", "instead", "too", "also", "previous", "last", "earlier",
    "above", "before", "other", "another", "rest", "remaining", "both",
    "undo", "revert", "retry", "redo", "continue", "proceed", "confirm",
    "yes", "yeah", "yep", "no", "nope", "ok", "okay", "sure", "go", "do",
    "first", "second", "third", "next", "former", "latter",
}
# Phrases that signal a follow-up even when the words above are absent.
_PHRASES = re.compile(
    r"\b(do it|go ahead|use (these|those|that)|the (same|other) (one|thing|way)|"
    r"as (before|above|earlier)|like (before|last time)|what about|and (then|now)|"
    r"which (one|ones)|why (did|didn't|not)|what (happened|went wrong)|"
    r"try (again|once more)|one more time|show me more|more (detail|details|info))\b",
    re.I,
)
_WORD = re.compile(r"[a-z']+")
SHORT_TURN_WORDS = 3  # "yes", "the second", "ok do it"


def needs_history(user_input: str) -> bool:
    """True when the request refers back to earlier turns and needs them."""
    text = (user_input or "").strip()
    if not text:
        return False
    words = _WORD.findall(text.lower())
    if not words:
        return False
    if _PHRASES.search(text):
        return True
    if len(words) <= SHORT_TURN_WORDS:
        # "yes", "do it", "the second one" refer back; "restart nginx" does not.
        return any(w in _ANAPHORA for w in words)
    # Anaphora anywhere in the first clause is the strongest signal; a lone
    # "this" deep in a long self-contained request ("check this server's
    # disks") should not drag history in, so weigh position.
    head = words[:6]
    if any(w in _ANAPHORA for w in head if w not in ("this", "do", "go", "no")):
        return True
    return False
