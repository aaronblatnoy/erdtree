"""Invisible transcript memory: rolling compaction + window management.

This is the P8 "invisible memory" core.  The Repl loop builds an ever-growing
list of OpenAI-shaped messages (assistant turns + ``role:"tool"`` result
messages produced by ``Router.tool_result_message``).  Left unmanaged that list
grows without bound and eventually blows the prompt window — which a user would
experience as a reset / "amnesia" moment.  ``TranscriptMemory`` removes that
moment entirely by compacting the history *silently*:

  * The **recent K turns** are kept **byte-identical** (verbatim).  This is what
    lets deixis resolve — "restart it", "the one we just did" still point at the
    same concrete unit because the recent turns are unchanged.

  * **Older turns** keep the tool-call **OUTCOMES** — the ``{exit_code, summary}``
    the router already shaped in ``tool_result_message`` — and **drop** the
    verbose ``stdout``/``stderr`` summaries once they have been reasoned over.
    The model still knows *what happened* (a service restarted, a package
    installed, exit code 0) without re-carrying every byte of output.

The compaction threshold is an **opaque per-tier knob** (a character budget):
the larger tier simply carries a bigger budget.  No tier/product name appears
here (I6).  The accounting is **pure stdlib** — no model/network calls of any
kind (I8) — it is plain byte counting over the JSON message shapes.

Nothing in this module is user-facing, so it emits no strings at all; there is
no AI/limit/reset language to leak (I2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = ["Turn", "TranscriptMemory"]

# Keys in a ``role:"tool"`` content payload (the router's tool_result_message
# shape, router.py ~line 466).  These are the *verbose* fields dropped from
# older turns once they have been reasoned over.
_VERBOSE_RESULT_KEYS = ("stdout_summary", "stderr_summary")

# The OUTCOME fields older turns retain.  ``exit_code`` + ``summary`` are the
# durable record of what an operation did.
_OUTCOME_RESULT_KEYS = ("exit_code", "summary")


@dataclass
class Turn:
    """One accumulated turn: an assistant message + its tool result messages.

    ``assistant`` is the OpenAI assistant message (``role:"assistant"``).
    ``tool_results`` are the zero-or-more ``role:"tool"`` messages produced for
    that turn's tool calls.  A turn with no tool calls (a plain English answer)
    simply carries an empty ``tool_results`` list.
    """

    assistant: dict
    tool_results: list[dict] = field(default_factory=list)

    def messages(self) -> list[dict]:
        """Flatten this turn back into ordered OpenAI messages."""
        return [self.assistant, *self.tool_results]


def _byte_len(messages: list[dict]) -> int:
    """Opaque size accounting: bytes of the compact JSON encoding.

    Pure stdlib, deterministic, no model call.  We measure the *serialized*
    history because that is what actually consumes the prompt budget.
    """
    total = 0
    for m in messages:
        total += len(json.dumps(m, ensure_ascii=False, separators=(",", ":")))
    return total


def _compact_tool_result(msg: dict) -> dict:
    """Drop the verbose stdout/stderr from one ``role:"tool"`` message.

    Keeps the OUTCOME (``exit_code`` + ``summary``) and re-encodes the content.
    A message whose content is not the expected JSON object is passed through
    unchanged (defensive — never raise, I9).
    """
    if msg.get("role") != "tool":
        return msg
    raw = msg.get("content")
    if not isinstance(raw, str):
        return msg
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return msg
    if not isinstance(payload, dict):
        return msg
    # Nothing verbose to drop -> already compact; leave the object identical.
    if not any(k in payload for k in _VERBOSE_RESULT_KEYS):
        return msg

    compact_payload: dict[str, Any] = {}
    for k in _OUTCOME_RESULT_KEYS:
        if k in payload:
            compact_payload[k] = payload[k]
    # Preserve any unexpected non-verbose keys so we never silently lose data
    # the router may add later (forward-compatible), except the verbose ones.
    for k, v in payload.items():
        if k in _OUTCOME_RESULT_KEYS or k in _VERBOSE_RESULT_KEYS:
            continue
        compact_payload[k] = v

    out = dict(msg)
    out["content"] = json.dumps(
        compact_payload, ensure_ascii=False, separators=(",", ":")
    )
    return out


def _compact_turn(turn: Turn) -> Turn:
    """Return a turn with its tool results compacted (assistant kept as-is)."""
    return Turn(
        assistant=turn.assistant,
        tool_results=[_compact_tool_result(m) for m in turn.tool_results],
    )


class TranscriptMemory:
    """Owns the message-history window the Repl loop feeds to ``assemble``.

    Usage mirrors the loop: call :meth:`record` once per completed turn with the
    assistant message and the list of tool result messages, then ask
    :meth:`compacted_history` for the budget-bounded message list to pass as the
    ``history`` argument.

    ``keep_recent`` is how many trailing turns are preserved verbatim (default
    2 — enough that "the one we just did" / "restart it" resolves while the turn
    before it is still intact).  It is an ordinary parameter, not a tier name.
    """

    def __init__(self, *, keep_recent: int = 2) -> None:
        if keep_recent < 0:
            raise ValueError("keep_recent must be >= 0")
        self._keep_recent = keep_recent
        self._turns: list[Turn] = []

    # ------------------------------------------------------------------ #
    # Accumulation                                                        #
    # ------------------------------------------------------------------ #

    def record(
        self,
        assistant_msg: dict,
        tool_result_msgs: Optional[list[dict]] = None,
    ) -> None:
        """Accumulate one completed turn.

        ``assistant_msg`` is the OpenAI assistant message; ``tool_result_msgs``
        are the ``role:"tool"`` messages for that turn (empty/None for a plain
        English answer).
        """
        self._turns.append(
            Turn(
                assistant=assistant_msg,
                tool_results=list(tool_result_msgs or []),
            )
        )

    @property
    def turns(self) -> list[Turn]:
        """The accumulated turns (read view)."""
        return self._turns

    # ------------------------------------------------------------------ #
    # Compaction                                                          #
    # ------------------------------------------------------------------ #

    def compacted_history(self, threshold: int) -> list[dict]:
        """Return the budget-bounded message history.

        Policy:
          * The most-recent ``keep_recent`` turns are emitted **verbatim**
            (byte-identical message objects) — preserving deixis.
          * Older turns have their tool-result stdout/stderr **dropped**,
            keeping only the ``{exit_code, summary}`` outcome.
          * If still over ``threshold`` (an opaque char budget), the oldest
            compacted turns are evicted whole, oldest-first, until the
            serialized history fits — the recent verbatim window is never
            evicted to make budget (deixis survives).

        ``threshold <= 0`` is treated as "no budget cap" (compaction policy
        still applies, but nothing is evicted) — a safe degrade (I9).
        """
        n = len(self._turns)
        if n == 0:
            return []

        keep = min(self._keep_recent, n)
        recent = self._turns[n - keep:] if keep else []
        older = self._turns[: n - keep]

        compacted_older = [_compact_turn(t) for t in older]

        # Evict oldest compacted turns until under budget.  Never touch the
        # recent verbatim window.
        if threshold > 0:
            recent_msgs = [m for t in recent for m in t.messages()]
            recent_size = _byte_len(recent_msgs)
            # Drop oldest-first while the total still exceeds the budget AND
            # there is something evictable left.
            while compacted_older:
                older_msgs = [
                    m for t in compacted_older for m in t.messages()
                ]
                if recent_size + _byte_len(older_msgs) <= threshold:
                    break
                compacted_older.pop(0)

        out: list[dict] = []
        for t in compacted_older:
            out.extend(t.messages())
        for t in recent:
            out.extend(t.messages())
        return out

    # ------------------------------------------------------------------ #
    # Introspection (test/diagnostic helpers — not user-facing)           #
    # ------------------------------------------------------------------ #

    def size(self, threshold: int) -> int:
        """Serialized byte size of the compacted history for ``threshold``."""
        return _byte_len(self.compacted_history(threshold))
