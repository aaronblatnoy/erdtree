"""Unit tests for the P8 invisible-memory core (core/agent/memory.py).

Policy under test (plan §3 P8, Step 1):
  (a) the recent K turns are kept BYTE-IDENTICAL (deixis survives),
  (b) OLDER turns retain {exit_code, summary} but NOT raw stdout/stderr,
  (c) total serialized size stays under the opaque char budget.

Pure stdlib unittest.  No model/network calls — the module is plain byte
accounting, so these tests launch nothing and patch nothing.

Run:  python3 -m unittest tests.test_memory
"""

import copy
import json
import unittest

from core.agent.memory import TranscriptMemory, Turn
from core.agent.router import Router
from core.tools import ToolResult


def _assistant_msg(i: int) -> dict:
    """An OpenAI assistant message that emits one tool call (turn ``i``)."""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {
                    "name": "services",
                    "arguments": json.dumps({"unit": f"svc{i}.service"}),
                },
            }
        ],
    }


def _tool_result_msg(i: int, *, stdout_kb: int = 4) -> dict:
    """A ``role:"tool"`` message via the REAL router shaper.

    The stdout is deliberately large so a few turns blow any small budget; the
    summary + exit_code are the compact outcome that must survive.
    """
    big_stdout = ("x" * 1024) * stdout_kb  # ~stdout_kb KiB of verbose output
    result = ToolResult(
        exit_code=0,
        stdout=big_stdout,
        stderr="",
        summary=f"Restarted svc{i}.service.",
    )
    return Router.tool_result_message(f"call_{i}", result)


def _make_turns(n: int, *, stdout_kb: int = 4) -> list[tuple[dict, list[dict]]]:
    return [
        (_assistant_msg(i), [_tool_result_msg(i, stdout_kb=stdout_kb)])
        for i in range(n)
    ]


class TestCompactionPolicy(unittest.TestCase):
    def setUp(self):
        self.keep_recent = 2
        self.n = 12
        self.threshold = 4000  # opaque char budget (well under raw history)
        self.raw_turns = _make_turns(self.n)
        # Deep-copy what we feed in so we can later compare against pristine
        # inputs (record must not mutate the recent window).
        self.mem = TranscriptMemory(keep_recent=self.keep_recent)
        for assistant, results in self.raw_turns:
            self.mem.record(copy.deepcopy(assistant), copy.deepcopy(results))

    def test_a_recent_turns_byte_identical(self):
        """(a) The recent K turns are byte-identical to what was recorded."""
        history = self.mem.compacted_history(self.threshold)

        # Rebuild the verbatim tail from the pristine inputs.
        expected_tail: list[dict] = []
        for assistant, results in self.raw_turns[self.n - self.keep_recent:]:
            expected_tail.append(assistant)
            expected_tail.extend(results)

        # The compacted history must END with exactly those messages, byte-for
        # byte (same dicts AND same serialized JSON).
        tail = history[-len(expected_tail):]
        self.assertEqual(tail, expected_tail)
        self.assertEqual(
            [json.dumps(m, sort_keys=True) for m in tail],
            [json.dumps(m, sort_keys=True) for m in expected_tail],
        )

    def test_b_older_turns_keep_outcome_drop_stdout(self):
        """(b) Older turns retain {exit_code, summary} but not raw stdout."""
        history = self.mem.compacted_history(self.threshold)

        # Identify which call ids are in the recent (verbatim) window.
        recent_ids = {
            f"call_{i}" for i in range(self.n - self.keep_recent, self.n)
        }

        saw_older_tool = False
        for m in history:
            if m.get("role") != "tool":
                continue
            cid = m.get("tool_call_id")
            payload = json.loads(m["content"])
            if cid in recent_ids:
                # Recent: untouched, still carries the verbose stdout_summary.
                self.assertIn("stdout_summary", payload)
                continue
            saw_older_tool = True
            # Older: outcome kept ...
            self.assertIn("exit_code", payload)
            self.assertIn("summary", payload)
            self.assertEqual(payload["exit_code"], 0)
            self.assertTrue(payload["summary"].startswith("Restarted"))
            # ... raw verbose fields dropped.
            self.assertNotIn("stdout_summary", payload)
            self.assertNotIn("stderr_summary", payload)
            # And the giant stdout content must be gone from the wire bytes.
            self.assertNotIn("xxxx", m["content"])

        self.assertTrue(saw_older_tool, "expected at least one compacted older turn")

    def test_c_total_size_under_budget(self):
        """(c) Total serialized size is under the opaque budget."""
        history = self.mem.compacted_history(self.threshold)
        size = sum(
            len(json.dumps(m, ensure_ascii=False, separators=(",", ":")))
            for m in history
        )
        self.assertLessEqual(size, self.threshold)
        # Sanity: the RAW (uncompacted) history would have blown the budget,
        # proving compaction actually did work.
        raw_msgs = [
            m
            for assistant, results in self.raw_turns
            for m in (assistant, *results)
        ]
        raw_size = sum(
            len(json.dumps(m, ensure_ascii=False, separators=(",", ":")))
            for m in raw_msgs
        )
        self.assertGreater(raw_size, self.threshold)

    def test_recent_window_survives_even_when_over_budget(self):
        """The verbatim window is never evicted to make budget (deixis lives)."""
        # A budget smaller than even the recent window alone.
        history = self.mem.compacted_history(threshold=10)
        ids = {
            m.get("tool_call_id")
            for m in history
            if m.get("role") == "tool"
        }
        for i in range(self.n - self.keep_recent, self.n):
            self.assertIn(f"call_{i}", ids)


class TestEdgeCases(unittest.TestCase):
    def test_empty_history(self):
        mem = TranscriptMemory()
        self.assertEqual(mem.compacted_history(1000), [])

    def test_no_cap_when_threshold_nonpositive(self):
        """threshold<=0 => no eviction (still applies compaction policy)."""
        mem = TranscriptMemory(keep_recent=1)
        for assistant, results in _make_turns(5):
            mem.record(assistant, results)
        history = mem.compacted_history(0)
        # All five turns present (nothing evicted), but older ones compacted.
        ids = {m.get("tool_call_id") for m in history if m.get("role") == "tool"}
        self.assertEqual(ids, {f"call_{i}" for i in range(5)})

    def test_plain_english_turn_no_tool_results(self):
        mem = TranscriptMemory(keep_recent=1)
        mem.record({"role": "assistant", "content": "Done."}, None)
        history = mem.compacted_history(1000)
        self.assertEqual(history, [{"role": "assistant", "content": "Done."}])

    def test_record_does_not_mutate_inputs(self):
        """compacted_history must not mutate the recorded messages in place."""
        mem = TranscriptMemory(keep_recent=1)
        turns = _make_turns(4)
        snapshot = copy.deepcopy(turns)
        for assistant, results in turns:
            mem.record(assistant, results)
        mem.compacted_history(2000)
        self.assertEqual(turns, snapshot)

    def test_keep_recent_negative_rejected(self):
        with self.assertRaises(ValueError):
            TranscriptMemory(keep_recent=-1)

    def test_turn_messages_flatten_order(self):
        t = Turn(assistant={"role": "assistant", "content": "x"},
                 tool_results=[{"role": "tool", "tool_call_id": "a", "content": "{}"}])
        self.assertEqual(
            t.messages(),
            [{"role": "assistant", "content": "x"},
             {"role": "tool", "tool_call_id": "a", "content": "{}"}],
        )


if __name__ == "__main__":
    unittest.main()
