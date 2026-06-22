"""test_compaction — Phase 8 immortality / amnesia integration keystone.

This is THE invisible-memory gate (SC-P8.1 .. SC-P8.4).  It drives the REAL
``core.agent.repl.Repl`` loop — wired with a real ``TranscriptMemory``, a real
``EpisodicMemory`` over a real on-disk ``AuditLog``, and the real permission
classifier — across a corpus of multi-task sessions that EXCEED the prompt
window, then asserts the session is *immortal*:

  (a) AMNESIA SILENCE (SC-P8.4): no user-visible reset / limit / "context" /
      "forgot" / "earlier session" / "no longer have" language EVER appears in
      anything rendered to the operator, and no I2-forbidden term leaks either.
      Enforced with core/agent/prompt.py's canonical ``_FORBIDDEN_AI_TERMS``
      PLUS a dedicated amnesia-phrase blocklist.

  (b) DEEP RECALL (SC-P8.3): a fact established ~50 tasks ago — far past the
      compacted window — is recalled via EpisodicMemory and answered AS KNOWN:
      no re-ask, no "out of context".  Recall runs over the audit log the loop
      itself wrote, through the reused rag engine (episodic index_path, NOT the
      docs corpus index).

  (c) RECENT DEIXIS (SC-P8.1): "restart it" still resolves to the right unit
      because the recent turns survive VERBATIM in compacted_history — the
      deictic referent is byte-identical to what was recorded.

No network, no model, no live Linux: a scripted responder + fake IO + tmp
audit log.  Run: python3 -m unittest tests.test_compaction
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is importable when run directly.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Real tools (self-register on import) so the loop dispatches genuine ops.
import core.tools.services  # noqa: E402,F401
import core.tools.packages  # noqa: E402,F401

from core.tools import registry, ToolResult  # noqa: E402
from core.agent.audit import AuditLog  # noqa: E402
from core.agent.memory import TranscriptMemory  # noqa: E402
from core.agent.episodic import EpisodicMemory  # noqa: E402
from core.agent.repl import Repl  # noqa: E402

# The canonical I2 filter — IMPORTED, never re-listed (per the invariants).
from core.agent.prompt import _FORBIDDEN_AI_TERMS  # noqa: E402

# The docs corpus index fixture path — used to PROVE the episodic index differs.
_DOCS_FIXTURE_INDEX = str(_ROOT / "rag" / "fixtures" / "mini_index.db")


# --------------------------------------------------------------------------- #
# The amnesia-phrase blocklist (the cardinal-UX-sin filter).                   #
# These are phrases that, if surfaced to the operator, would BETRAY a window   #
# limit / reset — the very "amnesia moment" P8 exists to abolish (SC-P8.4).    #
# --------------------------------------------------------------------------- #
_AMNESIA_PHRASES = (
    "context",
    "limit",
    "reset",
    "forgot",
    "forget",
    "earlier session",
    "no longer have",
    "out of context",
    "i don't recall",
    "i do not recall",
    "don't remember",
    "do not remember",
    "as we discussed before but i",
)

# Whole-word pattern for the I2 forbidden terms (mirrors prompt._AI_PATTERN, but
# rebuilt locally from the IMPORTED set so this test owns no copy of the list).
_AI_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _FORBIDDEN_AI_TERMS) + r")\b",
    re.IGNORECASE,
)


def _assert_operator_clean(testcase: unittest.TestCase, text: str) -> None:
    """Fail if *text* leaks an I2 term or any amnesia phrase."""
    lowered = text.lower()
    ai = _AI_PATTERN.search(text)
    testcase.assertIsNone(
        ai, f"I2-forbidden term leaked to the operator: {ai!r} in {text!r}"
    )
    for phrase in _AMNESIA_PHRASES:
        testcase.assertNotIn(
            phrase,
            lowered,
            f"amnesia phrase {phrase!r} leaked to the operator: {text!r}",
        )


# --------------------------------------------------------------------------- #
# Test doubles (match the shapes test_repl.py uses).                           #
# --------------------------------------------------------------------------- #

class FakeContext:
    """Fixed snapshot text + invalidation counter (a TurnContext stand-in)."""

    def __init__(self, text: str = "Host: testbox") -> None:
        self.text = text
        self.invalidations = 0

    def snapshot_text(self, *, force: bool = False) -> str:
        return self.text

    def invalidate(self) -> None:
        self.invalidations += 1


class CapturingIO:
    """Captures everything rendered; auto-confirms gates (so writes proceed)."""

    def __init__(self) -> None:
        self.rendered: list[str] = []

    def render(self, text: str) -> None:
        self.rendered.append(text)

    def confirm(self, prompt: str) -> bool:
        # Capture the gate PROMPT too — it is operator-facing and must stay clean.
        self.rendered.append(prompt)
        return True

    def confirm_typed(self, prompt: str, word: str) -> bool:
        self.rendered.append(prompt)
        return True


class QueuedResponder:
    """Plays a queue of (content, tool_calls) responses; '' when exhausted.

    Each call pops one scripted response.  A turn that needs a tool call then an
    English answer queues two responses; a plain-answer turn queues one.
    """

    def __init__(self) -> None:
        self._queue: list[tuple[str, list[dict]]] = []

    def push(self, content: str, tool_calls: list[dict] | None = None) -> None:
        self._queue.append((content, list(tool_calls or [])))

    def __call__(self, messages, tools):
        if self._queue:
            content, calls = self._queue.pop(0)
        else:
            content, calls = "", []

        class _R:
            pass

        r = _R()
        r.content = content
        r.tool_calls = calls
        # Stash the messages the loop assembled so a test can inspect the
        # history window the model would have seen (deixis / recall checks).
        self.last_messages = messages
        return r


def _tool_call(call_id: str, name: str, arguments: dict) -> dict:
    """Build one assembled-shape tool call (the ollama AssembledResponse shape)."""
    return {
        "id": call_id,
        "name": name,
        "arguments": json.dumps(arguments, separators=(",", ":")),
    }


# --------------------------------------------------------------------------- #
# The keystone tests.                                                          #
# --------------------------------------------------------------------------- #

class TestImmortalSession(unittest.TestCase):
    """An over-window multi-task session stays silent, deep-recalls, resolves
    recent deixis — the four SC-P8 sub-criteria, end to end."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._audit_path = os.path.join(self._tmp, "audit.jsonl")
        self._index_path = os.path.join(self._tmp, "episodic.db")

        self._audit = AuditLog(self._audit_path)
        self._io = CapturingIO()
        self._responder = QueuedResponder()
        # A SMALL compaction budget so the multi-task session genuinely EXCEEDS
        # the window and compaction must evict — this is the immortal-session
        # condition, not a no-op.
        self._memory = TranscriptMemory(keep_recent=2)
        self._episodic = EpisodicMemory(
            self._audit_path, self._index_path, k=3
        )
        self._repl = Repl(
            registry=registry,
            responder=self._responder,
            audit=self._audit,
            context=FakeContext(),
            io=self._io,
            tier_label="test-tier",
            interactive=True,
            memory=self._memory,
            episodic=self._episodic,
            compaction_threshold=800,  # opaque small char budget -> eviction fires
        )

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self._tmp, ignore_errors=True)

    # ------------------------------------------------------------------ #
    # Drivers                                                            #
    # ------------------------------------------------------------------ #

    def _run_service_task(self, request: str, unit: str, op: str = "status") -> None:
        """One task: the model issues a services op, then answers in English."""
        self._responder.push(
            "", [_tool_call(f"c-{unit}-{op}", "services", {"operation": op, "unit": unit})]
        )
        self._responder.push(f"Done with {unit}.")
        self._repl.run_turn(request)

    # ------------------------------------------------------------------ #
    # (a) AMNESIA SILENCE across an over-window session (SC-P8.4)         #
    # ------------------------------------------------------------------ #

    def test_no_amnesia_language_across_overwindow_session(self) -> None:
        """50+ tasks that blow the window -> nothing operator-facing betrays a
        reset/limit, and the compacted window is genuinely bounded (eviction)."""
        units = [f"svc{i}.service" for i in range(55)]
        for i, unit in enumerate(units):
            self._run_service_task(f"check {unit}", unit)

        # The history actually exceeded the window: more turns recorded than the
        # compacted window carries (eviction happened) — i.e. this is a real
        # immortal session, not a session that fit trivially.
        self.assertGreater(len(self._memory.turns), self._memory._keep_recent)
        compacted = self._memory.compacted_history(800)
        self.assertLessEqual(
            self._memory.size(800), 800 + 256,
            "compacted window not bounded by the budget — eviction did not fire",
        )
        # Eviction must have dropped at least one early turn's content.
        flat = json.dumps(compacted)
        self.assertNotIn("svc0.service", flat,
                         "oldest task survived in the window — no eviction occurred")

        # SC-P8.4: every operator-facing string stays clean.
        for line in self._io.rendered:
            _assert_operator_clean(self, line)

    # ------------------------------------------------------------------ #
    # (b) DEEP RECALL of a ~50-tasks-ago fact, answered AS KNOWN (SC-P8.3)#
    # ------------------------------------------------------------------ #

    def test_old_fact_recalled_via_episodic_and_answered_as_known(self) -> None:
        """A distinctive op established at task 1, then 50+ unrelated tasks, is
        still recalled via episodic and answered without re-asking."""
        # Task 1: the distinctive, memorable operation.
        self._run_service_task(
            "restart the billing database service", "postgresql-billing.service",
            op="status",
        )
        # 50+ unrelated tasks bury it far past the compacted window.
        for i in range(52):
            self._run_service_task(f"check filler {i}", f"filler{i}.service")

        # The buried fact is GONE from the compacted window (it must be recalled,
        # not merely still-in-window).
        window = json.dumps(self._memory.compacted_history(800))
        self.assertNotIn("postgresql-billing", window,
                         "the old fact is still in-window; this isn't a deep-recall test")

        # Episodic recall (the reused rag engine over the audit log the loop
        # wrote) surfaces the buried op AS KNOWN — no re-ask needed.
        hits = self._episodic.recall("billing database service restart")
        self.assertTrue(hits, "episodic failed to recall the ~50-tasks-ago fact")
        joined = " ".join(h.text for h in hits).lower()
        self.assertIn("postgresql-billing", joined,
                      "the recalled snippet does not reference the billing service")

        # The recall path itself is operator-clean (no AI/amnesia leakage).
        for h in hits:
            _assert_operator_clean(self, h.text)

        # Reuse-not-fork: the episodic index path differs from the docs corpus.
        self.assertNotEqual(self._episodic.index_path, _DOCS_FIXTURE_INDEX)

    # ------------------------------------------------------------------ #
    # (c) RECENT DEIXIS: "restart it" resolves to the right unit (SC-P8.1)#
    # ------------------------------------------------------------------ #

    def test_recent_deixis_resolves_to_right_unit(self) -> None:
        """After many tasks, the just-touched unit survives verbatim in the
        recent window, so a deictic 'restart it' has a concrete referent."""
        for i in range(40):
            self._run_service_task(f"check {i}", f"early{i}.service")

        # The most-recent concrete unit the operator touched.
        self._run_service_task("look at the cache layer", "redis-cache.service")

        # 'restart it' — the deictic turn.  The loop assembles history from the
        # compacted window; assert the referent (redis-cache.service) is present
        # VERBATIM in what the model would see (recent window kept byte-identical).
        self._responder.push(
            "",
            [_tool_call("c-deixis", "services",
                        {"operation": "status", "unit": "redis-cache.service"})],
        )
        self._responder.push("Restarted it.")
        self._repl.run_turn("restart it")

        seen = json.dumps(self._responder.last_messages)
        self.assertIn(
            "redis-cache.service", seen,
            "the recent-turn referent for 'it' was not preserved verbatim — "
            "deixis would not resolve",
        )
        # And nothing operator-facing leaked amnesia/AI language.
        for line in self._io.rendered:
            _assert_operator_clean(self, line)


class TestBackwardCompatibleDefault(unittest.TestCase):
    """memory=None preserves TODAY's behavior EXACTLY: history stays []."""

    def test_memory_none_keeps_history_empty(self) -> None:
        responder = QueuedResponder()
        responder.push("All good.")
        repl = Repl(
            registry=registry,
            responder=responder,
            audit=AuditLog(os.path.join(tempfile.mkdtemp(), "audit.jsonl")),
            context=FakeContext(),
            io=CapturingIO(),
            tier_label="test-tier",
            interactive=True,
            # memory omitted -> None.
        )
        outcome = repl.run_turn("hello")
        # With memory=None the loop must assemble with history=[]: there is no
        # prior-session content, so the ONLY assistant message in the final
        # history is THIS turn's own English answer, and there are NO tool
        # messages carried over from a (nonexistent) prior session.
        roles = [m.get("role") for m in outcome.history]
        self.assertNotIn(
            "tool", roles,
            "tool history leaked with memory=None (backward-compat broken)",
        )
        self.assertEqual(
            roles.count("assistant"), 1,
            "more than this turn's own assistant message present with "
            "memory=None (history was not empty — backward-compat broken)",
        )


if __name__ == "__main__":
    unittest.main()
