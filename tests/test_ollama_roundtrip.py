"""
tests/test_ollama_roundtrip.py

Phase 3 validation: mock round-trip for core/model/ollama.py
and prompt assembly smoke-test for core/agent/prompt.py.

Validation gates (plan §3 Phase 3):

  [ollama.py]
  1.  EgressViolation raised for any non-localhost base_url (I1).
  2.  localhost / 127.0.0.1 / ::1 accepted without error.
  3.  ':latest' tag rejected at construction (pinned-tag gotcha).
  4.  Mock round-trip: stream SSE carrying a well-formed tool call
      is assembled into a correct AssembledResponse (0002 §4).
  5.  Mock round-trip: English (stop) response assembled correctly.
  6.  Empty / partial / malformed SSE lines are tolerated (no crash).

  [prompt.py]
  7.  Assembled messages contain a system message, history, and user turn.
  8.  System snapshot text appears in the system message (I5).
  9.  I2: AI-language check fires on a forbidden term.
  10. build_tool_list() produces correct 0002 §1 wire format.
  11. assemble() convenience wrapper returns (messages, tools) correctly.
  12. Missing snapshot produces a graceful placeholder.

  [end-to-end mock]
  13. prompt.assemble() output fed into OllamaClient.chat() with a mock
      HTTP factory that returns tool-call SSE → AssembledResponse has
      finish_reason "tool_calls" and one well-formed tool call with
      parseable JSON arguments.  This is the Phase 3 round-trip gate.

All tests run on macOS / any host with standard Python >=3.9.
No Ollama, no Linux OS integration, no network calls.

DEFERRED-TO-MOSSAD: live base-Qwen round-trip on the Mossad server
  (Ollama + qwen2.5:7b-instruct-q4_K_M must be running).
"""

from __future__ import annotations

import json
import sys
import os

import pytest

# Ensure the repo root is on sys.path so imports work from the tests/ dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.model.ollama import (
    AssembledResponse,
    EgressViolation,
    OllamaClient,
    StreamChunk,
    TierConfig,
    _assert_localhost,
    _parse_chunk,
    _parse_sse_line,
)
from core.agent.prompt import (
    PromptConfig,
    _assert_no_ai_language,
    assemble,
    assemble_messages,
    build_tool_list,
)


# =========================================================================== #
# Helpers / fixtures                                                           #
# =========================================================================== #

def _make_config(
    base_url: str = "http://localhost:11434",
    model: str = "qwen2.5:7b-instruct-q4_K_M",
) -> TierConfig:
    return TierConfig(base_url, model)


def _sse_lines(*payloads: str) -> list[str]:
    """Wrap JSON payload strings in SSE data: framing."""
    lines = []
    for p in payloads:
        lines.append(f"data: {p}")
    lines.append("data: [DONE]")
    return lines


def _tool_call_sse(
    call_id: str = "call_abc123",
    tool_name: str = "services",
    arguments: str = '{"operation":"status","unit":"nginx.service"}',
) -> list[str]:
    """
    Minimal but complete SSE sequence for a tool call (0002 §4).
    Three deltas: role, id+name, arguments split in two.
    """
    mid = len(arguments) // 2
    args_a = arguments[:mid]
    args_b = arguments[mid:]

    chunks = [
        # delta 1: role
        {"choices": [{"delta": {"role": "assistant"}}]},
        # delta 2: id + name (index 0, first appearance)
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": call_id, "type": "function",
             "function": {"name": tool_name, "arguments": ""}}
        ]}}]},
        # delta 3: first half of arguments
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": args_a}}
        ]}}]},
        # delta 4: second half of arguments + finish_reason
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": args_b}}
        ]}, "finish_reason": "tool_calls"}]},
    ]
    return _sse_lines(*[json.dumps(c) for c in chunks])


def _english_sse(text: str = "nginx.service is active.") -> list[str]:
    """SSE for a plain English (stop) response."""
    chunks = [
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": text[:5]}}]},
        {"choices": [{"delta": {"content": text[5:]}, "finish_reason": "stop"}]},
    ]
    return _sse_lines(*[json.dumps(c) for c in chunks])


def _http_factory_from_lines(lines: list[str]):
    """Return a _http_factory that yields the given SSE lines."""
    def factory(endpoint: str, body: dict) -> list[str]:
        return lines
    return factory


# Minimal tool registry schema for tests
_TOOL_SCHEMAS = [
    {
        "name": "services",
        "description": "Inspect and control systemd units.",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["status", "start", "stop", "restart", "enable", "disable", "logs"],
                },
                "unit": {"type": "string"},
            },
            "required": ["operation", "unit"],
            "additionalProperties": False,
        },
    }
]


# =========================================================================== #
# 1. Localhost / Egress guard (I1)                                            #
# =========================================================================== #

class TestEgressGuard:
    def test_localhost_name_accepted(self):
        _assert_localhost("http://localhost:11434")

    def test_127_accepted(self):
        _assert_localhost("http://127.0.0.1:11434")

    def test_ipv6_loopback_accepted(self):
        _assert_localhost("http://[::1]:11434")

    def test_public_ip_rejected(self):
        with pytest.raises(EgressViolation):
            _assert_localhost("http://8.8.8.8:11434")

    def test_private_ip_rejected(self):
        with pytest.raises(EgressViolation):
            _assert_localhost("http://192.168.1.100:11434")

    def test_remote_hostname_rejected(self):
        # "mossad" is a known internal host that is NOT loopback
        # Use a clearly non-loopback FQDN; use a domain that resolves but
        # is not loopback — or test that EgressViolation is raised on
        # unresolvable names (also an error).
        with pytest.raises(EgressViolation):
            _assert_localhost("http://example.com:11434")

    def test_client_construction_asserts_localhost(self):
        """OllamaClient.__init__ calls _assert_localhost."""
        with pytest.raises(EgressViolation):
            OllamaClient(_make_config(base_url="http://10.0.0.1:11434"))

    def test_client_construction_localhost_ok(self):
        client = OllamaClient(_make_config())
        assert client._model == "qwen2.5:7b-instruct-q4_K_M"


# =========================================================================== #
# 2. Pinned tag enforcement                                                   #
# =========================================================================== #

class TestPinnedTag:
    def test_latest_tag_rejected(self):
        with pytest.raises(ValueError, match="pinned"):
            TierConfig("http://localhost:11434", "qwen2.5:latest")

    def test_pinned_tag_accepted(self):
        cfg = TierConfig("http://localhost:11434", "qwen2.5:7b-instruct-q4_K_M")
        assert cfg.model == "qwen2.5:7b-instruct-q4_K_M"

    def test_untagged_name_accepted(self):
        # No ":latest" suffix — passes (e.g. bare model name in tests)
        cfg = TierConfig("http://localhost:11434", "qwen2.5")
        assert cfg.model == "qwen2.5"


# =========================================================================== #
# 3. SSE / chunk parsing                                                      #
# =========================================================================== #

class TestSSEParsing:
    def test_empty_line_returns_none(self):
        assert _parse_sse_line("") is None

    def test_comment_line_returns_none(self):
        assert _parse_sse_line(": keep-alive") is None

    def test_data_line_extracts_payload(self):
        payload = '{"choices":[]}'
        assert _parse_sse_line(f"data: {payload}") == payload

    def test_done_sentinel_returned_as_string(self):
        assert _parse_sse_line("data: [DONE]") == "[DONE]"

    def test_whitespace_stripped(self):
        assert _parse_sse_line("  data: hello  ") == "hello"

    def test_malformed_json_chunk_returns_empty(self):
        chunk = _parse_chunk("not json {{{")
        assert chunk.content_delta == ""
        assert chunk.tool_call_deltas == []

    def test_content_delta_parsed(self):
        raw = json.dumps({"choices": [{"delta": {"content": "hello"}}]})
        chunk = _parse_chunk(raw)
        assert chunk.content_delta == "hello"

    def test_finish_reason_parsed(self):
        raw = json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        chunk = _parse_chunk(raw)
        assert chunk.finish_reason == "stop"

    def test_tool_call_delta_parsed(self):
        raw = json.dumps({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "call_1", "type": "function",
             "function": {"name": "services", "arguments": "{\"op\":"}}
        ]}}]})
        chunk = _parse_chunk(raw)
        assert len(chunk.tool_call_deltas) == 1
        tc = chunk.tool_call_deltas[0]
        assert tc.index == 0
        assert tc.id == "call_1"
        assert tc.name == "services"
        assert tc.arguments == '{"op":'


# =========================================================================== #
# 4. Mock streaming round-trip — tool call path (PHASE 3 GATE)               #
# =========================================================================== #

class TestMockRoundTripToolCall:
    def _client(self) -> OllamaClient:
        return OllamaClient(_make_config())

    def test_stream_yields_chunks_without_crash(self):
        lines = _tool_call_sse()
        client = self._client()
        chunks = list(client.stream(
            messages=[{"role": "user", "content": "check nginx"}],
            tools=build_tool_list(_TOOL_SCHEMAS),
            _http_factory=_http_factory_from_lines(lines),
        ))
        # Should get multiple StreamChunks including one with done=True
        assert any(c.done for c in chunks)

    def test_chat_assembles_tool_call(self):
        """Core Phase 3 gate: mock SSE → AssembledResponse with a tool call."""
        lines = _tool_call_sse(
            call_id="call_abc123",
            tool_name="services",
            arguments='{"operation":"status","unit":"nginx.service"}',
        )
        client = self._client()
        resp = client.chat(
            messages=[{"role": "user", "content": "check nginx"}],
            tools=build_tool_list(_TOOL_SCHEMAS),
            _http_factory=_http_factory_from_lines(lines),
        )

        assert isinstance(resp, AssembledResponse)
        assert resp.finish_reason == "tool_calls"
        assert len(resp.tool_calls) == 1

        tc = resp.tool_calls[0]
        assert tc["id"] == "call_abc123"
        assert tc["name"] == "services"

        # arguments must be a JSON string that parses correctly
        args = json.loads(tc["arguments"])
        assert args["operation"] == "status"
        assert args["unit"] == "nginx.service"

    def test_arguments_concatenated_across_deltas(self):
        """Arguments split across N deltas must be joined into a complete string."""
        full_args = '{"operation":"restart","unit":"postgresql.service"}'
        lines = _tool_call_sse(arguments=full_args)
        client = self._client()
        resp = client.chat(
            messages=[],
            _http_factory=_http_factory_from_lines(lines),
        )
        assert resp.tool_calls[0]["arguments"] == full_args

    def test_multiple_tool_calls_assembled(self):
        """Parallel tool calls (two indices) each get their own entry."""
        two_call_chunks = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_A", "type": "function",
                 "function": {"name": "services", "arguments": '{"operation":"status","unit":"nginx.service"}'}},
                {"index": 1, "id": "call_B", "type": "function",
                 "function": {"name": "services", "arguments": '{"operation":"status","unit":"sshd.service"}'}},
            ]}, "finish_reason": "tool_calls"}]},
        ]
        lines = _sse_lines(*[json.dumps(c) for c in two_call_chunks])
        client = self._client()
        resp = client.chat(
            messages=[],
            _http_factory=_http_factory_from_lines(lines),
        )
        assert len(resp.tool_calls) == 2
        names = {tc["name"] for tc in resp.tool_calls}
        assert names == {"services"}
        ids = {tc["id"] for tc in resp.tool_calls}
        assert ids == {"call_A", "call_B"}


# =========================================================================== #
# 5. Mock streaming round-trip — English (stop) path                         #
# =========================================================================== #

class TestMockRoundTripEnglish:
    def test_chat_assembles_english_answer(self):
        lines = _english_sse("nginx.service is active.")
        client = OllamaClient(_make_config())
        resp = client.chat(
            messages=[{"role": "user", "content": "is nginx running"}],
            _http_factory=_http_factory_from_lines(lines),
        )
        assert resp.finish_reason == "stop"
        assert resp.content == "nginx.service is active."
        assert resp.tool_calls == []

    def test_partial_content_accumulated(self):
        """Content split across deltas is joined."""
        chunks = [
            {"choices": [{"delta": {"content": "nginx"}}]},
            {"choices": [{"delta": {"content": ".service "}}]},
            {"choices": [{"delta": {"content": "active"}, "finish_reason": "stop"}]},
        ]
        lines = _sse_lines(*[json.dumps(c) for c in chunks])
        resp = OllamaClient(_make_config()).chat(
            messages=[],
            _http_factory=_http_factory_from_lines(lines),
        )
        assert resp.content == "nginx.service active"


# =========================================================================== #
# 6. Resilience: malformed / empty stream                                     #
# =========================================================================== #

class TestStreamResilience:
    def test_empty_stream_does_not_crash(self):
        resp = OllamaClient(_make_config()).chat(
            messages=[],
            _http_factory=_http_factory_from_lines(["data: [DONE]"]),
        )
        assert resp.content == ""
        assert resp.tool_calls == []

    def test_interspersed_empty_lines_tolerated(self):
        lines = ["", "  ", "data: [DONE]"]
        resp = OllamaClient(_make_config()).chat(
            messages=[],
            _http_factory=_http_factory_from_lines(lines),
        )
        assert resp.content == ""

    def test_malformed_json_lines_skipped(self):
        lines = ["data: {bad json", "data: [DONE]"]
        resp = OllamaClient(_make_config()).chat(
            messages=[],
            _http_factory=_http_factory_from_lines(lines),
        )
        assert resp.content == ""


# =========================================================================== #
# 7–12. Prompt assembly                                                       #
# =========================================================================== #

class TestPromptAssembly:
    def _config(self, **kwargs) -> PromptConfig:
        defaults = dict(
            tier_prompt="",
            snapshot_text="Host: testbox\nOS: Rocky Linux 9.3  kernel: 5.14.0",
            user_input="show me all failing services",
            history=[],
            tools=[],
        )
        defaults.update(kwargs)
        return PromptConfig(**defaults)

    # 7. Structure
    def test_messages_have_system_user(self):
        msgs = assemble_messages(self._config())
        roles = [m["role"] for m in msgs]
        assert roles[0] == "system"
        assert roles[-1] == "user"

    def test_history_between_system_and_user(self):
        history = [
            {"role": "user", "content": "restart nginx"},
            {"role": "assistant", "content": "Done."},
        ]
        msgs = assemble_messages(self._config(history=history))
        roles = [m["role"] for m in msgs]
        assert roles == ["system", "user", "assistant", "user"]

    # 8. System context (I5)
    def test_snapshot_text_in_system_message(self):
        msgs = assemble_messages(self._config(
            snapshot_text="Host: mybox\nOS: Rocky Linux 9.3"
        ))
        system_content = msgs[0]["content"]
        assert "Host: mybox" in system_content
        assert "SYSTEM CONTEXT" in system_content

    def test_missing_snapshot_produces_placeholder(self):
        msgs = assemble_messages(self._config(snapshot_text=""))
        system_content = msgs[0]["content"]
        assert "unavailable" in system_content.lower()

    # 9. I2 check
    def test_ai_language_check_fires_on_forbidden_term(self):
        with pytest.raises(ValueError, match="I2 violation"):
            _assert_no_ai_language("This is an AI assistant.", "test")

    def test_ai_language_check_passes_clean_text(self):
        _assert_no_ai_language("nginx.service is active (running).", "test")

    def test_tier_prompt_with_ai_language_rejected(self):
        with pytest.raises(ValueError, match="I2 violation"):
            assemble_messages(self._config(
                tier_prompt="You are an AI that helps sysadmins."
            ))

    def test_tier_prompt_clean_accepted(self):
        msgs = assemble_messages(self._config(
            tier_prompt="Prefer concise output. Radagon tier context depth."
        ))
        # Should not raise; tier_prompt text present in system message
        system_content = msgs[0]["content"]
        assert "Radagon tier context depth" in system_content

    # 10. build_tool_list wire format
    def test_build_tool_list_format(self):
        wire = build_tool_list(_TOOL_SCHEMAS)
        assert len(wire) == 1
        entry = wire[0]
        assert entry["type"] == "function"
        func = entry["function"]
        assert func["name"] == "services"
        assert "description" in func
        assert "parameters" in func
        assert func["parameters"]["type"] == "object"

    def test_build_tool_list_empty(self):
        assert build_tool_list([]) == []

    # 11. assemble() convenience
    def test_assemble_returns_messages_and_tools(self):
        tools = build_tool_list(_TOOL_SCHEMAS)
        msgs, ret_tools = assemble(
            user_input="check nginx",
            snapshot_text="Host: box",
            history=[],
            tier_prompt="",
            tools=tools,
        )
        assert isinstance(msgs, list)
        assert isinstance(ret_tools, list)
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "check nginx"
        assert ret_tools == tools

    # 12. User input whitespace stripped
    def test_user_input_whitespace_stripped(self):
        msgs = assemble_messages(self._config(user_input="  check nginx  "))
        assert msgs[-1]["content"] == "check nginx"


# =========================================================================== #
# 13. End-to-end mock round-trip: prompt → chat → AssembledResponse          #
# =========================================================================== #

class TestE2EMockRoundTrip:
    """
    Phase 3 integration gate.

    assemble() output is fed directly into OllamaClient.chat() with a mock
    HTTP factory returning tool-call SSE.  The response must have:
      - finish_reason == "tool_calls"
      - one tool call with name "services"
      - arguments that JSON-parse into a dict with "operation" and "unit"
    """

    def test_e2e_tool_call_round_trip(self):
        # 1. Assemble prompt
        tools = build_tool_list(_TOOL_SCHEMAS)
        messages, ret_tools = assemble(
            user_input="show me all failing services",
            snapshot_text=(
                "Host: testbox\n"
                "OS: Rocky Linux 9.3  kernel: 5.14.0\n"
                "Failed services (1): postgresql.service\n"
                "Listening ports: 22/tcp, 80/tcp"
            ),
            history=[],
            tier_prompt="",
            tools=tools,
        )

        # 2. Mock SSE the "model" returns
        sse_lines = _tool_call_sse(
            call_id="call_xyz",
            tool_name="services",
            arguments='{"operation":"status","unit":"postgresql.service"}',
        )

        # 3. Chat
        client = OllamaClient(_make_config())
        resp = client.chat(
            messages=messages,
            tools=ret_tools,
            _http_factory=_http_factory_from_lines(sse_lines),
        )

        # 4. Assert
        assert resp.finish_reason == "tool_calls", (
            f"Expected finish_reason='tool_calls', got {resp.finish_reason!r}"
        )
        assert len(resp.tool_calls) == 1, (
            f"Expected 1 tool call, got {len(resp.tool_calls)}"
        )
        tc = resp.tool_calls[0]
        assert tc["name"] == "services", f"Tool name mismatch: {tc['name']!r}"

        args = json.loads(tc["arguments"])
        assert "operation" in args, "Missing 'operation' in args"
        assert "unit" in args, "Missing 'unit' in args"

        # arguments are well-formed JSON with expected values
        assert args["operation"] == "status"
        assert args["unit"] == "postgresql.service"

    def test_e2e_english_answer_round_trip(self):
        """English answer (stop) path: no tool calls, content populated."""
        messages, _ = assemble(
            user_input="how much disk space is left on /",
            snapshot_text="Host: testbox\nDisks: / (45% used)",
        )
        sse_lines = _english_sse("/ has 55% free (200 GB available).")
        client = OllamaClient(_make_config())
        resp = client.chat(
            messages=messages,
            _http_factory=_http_factory_from_lines(sse_lines),
        )
        assert resp.finish_reason == "stop"
        assert "55%" in resp.content
        assert resp.tool_calls == []


# =========================================================================== #
# DEFERRED-TO-MOSSAD marker                                                   #
# =========================================================================== #
# The following test is skipped on the macOS dev host.  It requires:
#   - Ollama running at http://localhost:11434
#   - qwen2.5:7b-instruct-q4_K_M pulled
# Run on the Mossad server (Arch Linux, 2x RTX 3060 Ti) after pull:
#   pytest tests/test_ollama_roundtrip.py::TestDeferredToMossad -v

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires live Ollama + pulled model")
class TestDeferredToMossad:
    """Live base-Qwen round-trip.  Run on Mossad, not the macOS dev host."""

    def test_live_tool_call_round_trip(self):
        """
        Full live round-trip: real Ollama + qwen2.5:7b-instruct-q4_K_M.

        Asserts:
          - Response has finish_reason "tool_calls" OR "stop" (either is
            valid; the bench in Phase 4 measures tool-call validity rate).
          - If tool_calls, arguments parse as JSON.
          - Egress: the client never contacts any non-localhost endpoint
            (enforced by construction; additionally verified by running
             this test inside the mossad egress monitor).
        """
        from core.model.ollama import OllamaClient, TierConfig
        from core.agent.prompt import assemble, build_tool_list

        config = TierConfig(
            base_url="http://localhost:11434",
            model="qwen2.5:7b-instruct-q4_K_M",
        )
        client = OllamaClient(config)
        tools = build_tool_list(_TOOL_SCHEMAS)
        messages, ret_tools = assemble(
            user_input="show me the status of nginx",
            snapshot_text="Host: mossad\nOS: Arch Linux  kernel: 6.x",
            tools=tools,
        )
        resp = client.chat(messages=messages, tools=ret_tools)
        assert resp.finish_reason in ("tool_calls", "stop")
        for tc in resp.tool_calls:
            json.loads(tc["arguments"])  # must be valid JSON
