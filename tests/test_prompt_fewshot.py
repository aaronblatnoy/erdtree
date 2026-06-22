"""
tests/test_prompt_fewshot.py

Phase 4 — Small-model tool-use discipline + few-shot tests.

Coverage:
  SC6  The assembled system message contains:
         - the tool-use discipline block
         - at least one tool-call few-shot example
         - at least one direct-answer few-shot example
  SC3  The WHOLE assembled prompt (with discipline + few-shot + context)
       passes _assert_no_ai_language (no I2-forbidden term anywhere).
  WIRE-SHAPE PARITY
       The structured tool-call example stored in _FEW_SHOT_TOOL_CALL_EXAMPLE
       passes router.validate_arguments against the matching ToolSpec with
       no ValueError — so a drifted example fails this test immediately.

Backward-compat checks:
  - assemble() and assemble_messages() signatures unchanged.
  - The new constants are I2-clean at import time (import itself proves it;
    _assert_no_ai_language is called on them at module load).

DEV-HOST HONESTY: no live Ollama round-trip is performed here.
The live-model FEEL test (does a real 7B pick tools correctly given
this prompt?) is DEFERRED-TO-MOSSAD: requires a provisioned Linux box
with Ollama running a 7B/14B.
"""

from __future__ import annotations

import pytest

# Importing prompt.py runs _assert_no_ai_language on all new constants
# at import time — if any constant contains a forbidden term the import
# fails, which is itself the strongest I2 test we can write.
from core.agent.prompt import (
    _AI_PATTERN,
    _FEW_SHOT,
    _FEW_SHOT_TOOL_CALL_EXAMPLE,
    _HOUSE_SYSTEM_PROMPT,
    _TOOL_USE_DISCIPLINE,
    _assert_no_ai_language,
    assemble,
    assemble_messages,
    PromptConfig,
)

# Register services so the router/registry can find it.
import core.tools.services  # noqa: F401
from core.tools import registry
from core.tools.services import SERVICES_SPEC
from core.agent.router import validate_arguments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assembled_system(snapshot: str = "kernel: 5.15", tier: str = "") -> str:
    """Return just the system-message content from assemble_messages."""
    cfg = PromptConfig(
        tier_prompt=tier,
        snapshot_text=snapshot,
        user_input="test",
        history=[],
        tools=[],
    )
    msgs = assemble_messages(cfg)
    # The first message is always the system message.
    assert msgs[0]["role"] == "system"
    return msgs[0]["content"]


# ---------------------------------------------------------------------------
# SC6 — discipline block present
# ---------------------------------------------------------------------------

class TestDisciplineBlockPresent:
    """SC6: the discipline block appears in the assembled system message."""

    def test_tool_use_rules_heading_present(self):
        content = _assembled_system()
        assert "Tool-use rules:" in content, (
            "assembled system message is missing the tool-use discipline heading"
        )

    def test_call_operation_rule_present(self):
        """The 'call a system operation' guidance is in the assembled message."""
        content = _assembled_system()
        assert "Call a system operation" in content

    def test_answer_directly_rule_present(self):
        """The 'answer directly' rule is present."""
        content = _assembled_system()
        assert "Answer directly in English" in content

    def test_no_narration_rule_present(self):
        """The 'never narrate' rule is present."""
        content = _assembled_system()
        assert "Never narrate" in content

    def test_terse_rule_present(self):
        """The terse / one-operation-at-a-time rule is present."""
        content = _assembled_system()
        assert "Be terse" in content


# ---------------------------------------------------------------------------
# SC6 — few-shot examples present
# ---------------------------------------------------------------------------

class TestFewShotPresent:
    """SC6: at least one tool-call example and one direct-answer example."""

    def test_few_shot_heading_present(self):
        content = _assembled_system()
        assert "DECIDING WHEN TO ACT" in content

    def test_tool_call_example_present(self):
        """Example 1 teaches the DECISION to act (services status on nginx),
        WITHOUT a copyable JSON-in-prose template — the small model echoed that
        template verbatim instead of emitting a real tool call. The example now
        describes the decision; the real call format comes from the tool schemas.
        """
        content = _assembled_system()
        assert "services status" in content
        assert "nginx.service" in content
        # The harmful copyable prose call-template must NOT be present.
        assert "call the services tool with" not in content
        assert '{"operation"' not in content

    def test_direct_answer_example_present(self):
        """Example 2 (direct English answer) is in the assembled message."""
        content = _assembled_system()
        # The direct-answer example mentions port 22.
        assert "Port 22" in content, (
            "direct-answer few-shot example not found in assembled system message"
        )

    def test_both_example_labels_present(self):
        content = _assembled_system()
        assert "Example 1" in content
        assert "Example 2" in content


# ---------------------------------------------------------------------------
# SC3 / I2 — full assembled prompt passes _assert_no_ai_language
# ---------------------------------------------------------------------------

class TestAssembledPromptI2Clean:
    """SC3: no forbidden term anywhere in the assembled system message."""

    def test_assembled_system_no_forbidden_terms(self):
        content = _assembled_system()
        # _assert_no_ai_language raises ValueError if any forbidden term found.
        # We call it directly so a failure gives a clear error message.
        try:
            _assert_no_ai_language(content, "assembled system message")
        except ValueError as exc:
            pytest.fail(str(exc))

    def test_assembled_system_with_tier_prompt_no_forbidden_terms(self):
        """Even with a tier_prompt the assembled message stays I2-clean."""
        tier = "Terse. Direct. No hedging."
        content = _assembled_system(tier=tier)
        try:
            _assert_no_ai_language(content, "assembled system message (with tier)")
        except ValueError as exc:
            pytest.fail(str(exc))

    def test_discipline_constant_no_forbidden_terms(self):
        """_TOOL_USE_DISCIPLINE constant is I2-clean (belt-and-suspenders)."""
        match = _AI_PATTERN.search(_TOOL_USE_DISCIPLINE)
        assert match is None, (
            f"I2 violation in _TOOL_USE_DISCIPLINE: {match.group()!r}"
        )

    def test_fewshot_constant_no_forbidden_terms(self):
        """_FEW_SHOT constant is I2-clean."""
        match = _AI_PATTERN.search(_FEW_SHOT)
        assert match is None, (
            f"I2 violation in _FEW_SHOT: {match.group()!r}"
        )

    def test_house_prompt_no_forbidden_terms(self):
        """_HOUSE_SYSTEM_PROMPT constant is I2-clean (regression guard)."""
        match = _AI_PATTERN.search(_HOUSE_SYSTEM_PROMPT)
        assert match is None, (
            f"I2 violation in _HOUSE_SYSTEM_PROMPT: {match.group()!r}"
        )


# ---------------------------------------------------------------------------
# Wire-shape parity — the tool-call example must pass validate_arguments
# ---------------------------------------------------------------------------

class TestFewShotWireShapeParity:
    """Parity: the structured tool-call example validates against the real spec.

    If the example drifts from the actual ToolSpec (e.g. operation renamed,
    required arg changed) this test fails immediately, preventing the harness
    from teaching the wrong wire shape.

    DEV-HOST HONESTY: this is a pure static/structural check — no subprocess,
    no live Ollama, no network.  A live round-trip to verify the 7B actually
    produces this format is DEFERRED-TO-MOSSAD.
    """

    def test_tool_name_registered(self):
        """The example's tool name is in the live registry."""
        tool_name = _FEW_SHOT_TOOL_CALL_EXAMPLE["tool"]
        spec = registry.get(tool_name)
        assert spec is not None, (
            f"_FEW_SHOT_TOOL_CALL_EXAMPLE references tool {tool_name!r} "
            "which is not registered; update the example or register the tool"
        )

    def test_arguments_validate_against_spec(self):
        """The example arguments pass validate_arguments with no exception.

        This is the wire-shape parity assertion: if 'operation' is wrong,
        a required arg is missing, or an arg type is wrong, validate_arguments
        raises ValueError and this test fails loudly.
        """
        tool_name = _FEW_SHOT_TOOL_CALL_EXAMPLE["tool"]
        args = _FEW_SHOT_TOOL_CALL_EXAMPLE["arguments"]
        # Use the canonical SERVICES_SPEC (the spec the example is based on).
        try:
            operation, op_args = validate_arguments(SERVICES_SPEC, args)
        except ValueError as exc:
            pytest.fail(
                f"_FEW_SHOT_TOOL_CALL_EXAMPLE failed validate_arguments "
                f"against {tool_name!r} spec: {exc}"
            )
        assert operation == args["operation"], (
            f"validate_arguments returned operation {operation!r} "
            f"but example says {args['operation']!r}"
        )

    def test_arguments_validate_against_registry_spec(self):
        """Also validate against the registry's live spec (belt-and-suspenders)."""
        tool_name = _FEW_SHOT_TOOL_CALL_EXAMPLE["tool"]
        args = _FEW_SHOT_TOOL_CALL_EXAMPLE["arguments"]
        spec = registry.get(tool_name)
        assert spec is not None
        try:
            operation, _ = validate_arguments(spec, args)
        except ValueError as exc:
            pytest.fail(
                f"_FEW_SHOT_TOOL_CALL_EXAMPLE failed validate_arguments "
                f"against registry spec for {tool_name!r}: {exc}"
            )
        assert operation == args["operation"]

    def test_example_operation_is_read(self):
        """The tool-call example uses a READ operation (no gate confirmation needed)."""
        from core.agent.permissions import OpClass
        tool_name = _FEW_SHOT_TOOL_CALL_EXAMPLE["tool"]
        args = _FEW_SHOT_TOOL_CALL_EXAMPLE["arguments"]
        operation = args["operation"]
        spec = registry.get(tool_name)
        assert spec is not None
        perm = spec.permission_class_for(operation)
        assert perm is OpClass.READ, (
            f"few-shot tool-call example uses {operation!r} which is "
            f"{perm}; prefer a READ operation for the illustrative example"
        )


# ---------------------------------------------------------------------------
# Backward-compat — assemble() / assemble_messages() signatures unchanged
# ---------------------------------------------------------------------------

class TestSignaturesUnchanged:
    """assemble() and assemble_messages() still work with existing call sites."""

    def test_assemble_returns_tuple(self):
        msgs, tools = assemble("show disk usage", "kernel: 5.15")
        assert isinstance(msgs, list)
        assert isinstance(tools, list)

    def test_assemble_messages_returns_list(self):
        cfg = PromptConfig(user_input="show disk usage", snapshot_text="kernel: 5.15")
        msgs = assemble_messages(cfg)
        assert isinstance(msgs, list)
        assert msgs[0]["role"] == "system"

    def test_assemble_with_all_kwargs(self):
        msgs, tools = assemble(
            "show disk usage",
            "kernel: 5.15",
            history=[{"role": "user", "content": "hello"}],
            tier_prompt="Terse.",
            tools=[],
        )
        assert len(msgs) >= 3  # system + history + user

    def test_user_input_in_messages(self):
        msgs, _ = assemble("what services are failing?", "kernel: 5.15")
        user_msgs = [m for m in msgs if m["role"] == "user"]
        assert any("failing" in m["content"] for m in user_msgs)

    def test_system_message_always_first(self):
        msgs, _ = assemble("test", "ctx")
        assert msgs[0]["role"] == "system"
