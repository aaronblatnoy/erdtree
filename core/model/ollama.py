"""
core/model/ollama.py

Streaming client to LOCAL Ollama via the OpenAI-compatible endpoint.

Design contract (load-bearing — see plan invariants I1, I6, I8):

  I1  This client ONLY talks to localhost.  At construction time it asserts that
      the configured base_url resolves to a loopback address.  Any attempt to
      point it at a non-localhost host raises EgressViolation before a single
      byte leaves the machine.

  I6  No tier/product names are hardcoded here.  The caller passes a TierConfig
      (or any object with .base_url and .model fields) obtained from the tier
      loader (Phase 9).  This module is tier-agnostic.

  I8  Responses are streamed; callers receive chunks as they arrive so the
      terminal feels instant.

Wire format: OpenAI Chat Completions (Ollama /v1/chat/completions).
Frozen contract: docs/decisions/0002-tool-call-protocol.md.

DEV-HOST NOTE: there is no Ollama on the macOS build host.  This module is
unit-tested against a mock HTTP server (tests/test_ollama_roundtrip.py).
Any live round-trip is DEFERRED-TO-MOSSAD.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from typing import Generator, Iterable, Optional
from urllib.parse import urlparse


# --------------------------------------------------------------------------- #
# Invariant guard                                                              #
# --------------------------------------------------------------------------- #

class EgressViolation(RuntimeError):
    """Raised when the configured endpoint is not a localhost address (I1)."""


def _assert_localhost(base_url: str) -> None:
    """
    Parse *base_url* and assert that the host resolves to a loopback address.

    Raises EgressViolation on any non-loopback host.
    Accepts: 127.0.0.1, ::1, localhost, and any name that resolves to a
    loopback address.  Rejects everything else — including 0.0.0.0 and any
    public/private routable address.
    """
    parsed = urlparse(base_url)
    host = parsed.hostname or ""

    if not host:
        raise EgressViolation(
            f"Cannot determine host from base_url={base_url!r}"
        )

    # Fast path: literal loopback
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_loopback:
            return
        raise EgressViolation(
            f"Endpoint host {host!r} is not a loopback address (I1 violation)."
        )
    except ValueError:
        pass  # not a bare IP — fall through to name resolution

    # Named host: "localhost" and any alias that resolves to loopback
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise EgressViolation(
            f"Cannot resolve endpoint host {host!r}: {exc}"
        ) from exc

    for _family, _type, _proto, _canon, sockaddr in infos:
        raw_addr = sockaddr[0]
        try:
            if ipaddress.ip_address(raw_addr).is_loopback:
                return
        except ValueError:
            continue

    raise EgressViolation(
        f"Endpoint host {host!r} resolves to no loopback address (I1 violation). "
        f"All inference must run on localhost."
    )


# --------------------------------------------------------------------------- #
# Data structures (mirrors 0002 streaming shape)                              #
# --------------------------------------------------------------------------- #

@dataclass
class ToolCallDelta:
    """Partial tool-call accumulator (0002 §4)."""
    index: int
    id: str = ""
    name: str = ""
    arguments: str = ""   # raw JSON string, concatenated across deltas


@dataclass
class StreamChunk:
    """
    A parsed SSE chunk from /v1/chat/completions.

    Only the fields Erdtree cares about are populated; unrecognised fields
    are silently ignored (forward-compat).
    """
    # Content delta (plain-text / English answer path)
    content_delta: str = ""

    # Tool call deltas accumulating this chunk (0002 §4)
    tool_call_deltas: list[ToolCallDelta] = field(default_factory=list)

    # Set on the finish chunk; "tool_calls" or "stop" are the two live values
    finish_reason: Optional[str] = None

    # Set to True on the [DONE] sentinel line
    done: bool = False


@dataclass
class AssembledResponse:
    """
    Fully assembled model response after the stream closes.

    Callers that want a single structured result rather than incremental chunks
    call OllamaClient.chat() which blocks until [DONE].
    """
    # English text answer (finish_reason == "stop")
    content: str = ""

    # Assembled tool calls (finish_reason == "tool_calls")
    # Each entry: {"id": str, "name": str, "arguments": str (JSON)}
    tool_calls: list[dict] = field(default_factory=list)

    finish_reason: str = ""


# --------------------------------------------------------------------------- #
# Tier config protocol (structural typing — no import from Phase 9)           #
# --------------------------------------------------------------------------- #

class TierConfig:
    """
    Minimal interface this client requires from tier config (Phase 9).

    Phase 9 will provide a real TierConfig dataclass; until then tests can
    pass any object with these two attributes.
    """
    base_url: str   # e.g. "http://localhost:11434"
    model: str      # e.g. "qwen2.5:14b-instruct-q4_K_M"  (never :latest)

    def __init__(self, base_url: str, model: str) -> None:
        if model.endswith(":latest"):
            raise ValueError(
                f"Model tag must be pinned, never ':latest' — got {model!r}. "
                "Pin a specific quantization tag in tier config (CLAUDE.md gotcha)."
            )
        self.base_url = base_url.rstrip("/")
        self.model = model


# --------------------------------------------------------------------------- #
# SSE parsing                                                                  #
# --------------------------------------------------------------------------- #

def _parse_sse_line(line: str) -> Optional[str]:
    """
    Extract the JSON payload from a single SSE data line.

    Returns None for comment lines, empty lines, or the [DONE] sentinel
    (callers check for "[DONE]" themselves).
    """
    line = line.strip()
    if not line or line.startswith(":"):
        return None
    if line.startswith("data:"):
        payload = line[5:].strip()
        return payload  # may be "[DONE]" or JSON
    return None


def _parse_chunk(payload: str) -> StreamChunk:
    """Parse one JSON payload into a StreamChunk (0002 §4)."""
    chunk = StreamChunk()
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        return chunk  # malformed chunk — return empty, caller continues

    choices = obj.get("choices") or []
    if not choices:
        return chunk

    choice = choices[0]
    finish_reason = choice.get("finish_reason")
    if finish_reason:
        chunk.finish_reason = finish_reason

    delta = choice.get("delta") or {}

    # Plain content delta
    content = delta.get("content")
    if content:
        chunk.content_delta = content

    # Tool call deltas (0002 §4: accumulate by index)
    raw_tcs = delta.get("tool_calls") or []
    for raw_tc in raw_tcs:
        idx = raw_tc.get("index", 0)
        tc_delta = ToolCallDelta(index=idx)
        tc_delta.id = raw_tc.get("id", "")
        func = raw_tc.get("function") or {}
        tc_delta.name = func.get("name", "")
        tc_delta.arguments = func.get("arguments", "")
        chunk.tool_call_deltas.append(tc_delta)

    return chunk


# --------------------------------------------------------------------------- #
# Core client                                                                  #
# --------------------------------------------------------------------------- #

class OllamaClient:
    """
    Streaming client to the LOCAL Ollama OpenAI-compatible endpoint.

    Usage
    -----
    config = TierConfig("http://localhost:11434", "qwen2.5:7b-instruct-q4_K_M")
    client = OllamaClient(config)
    response = client.chat(messages, tools=tools)
    # or consume the raw stream:
    for chunk in client.stream(messages, tools=tools):
        ...

    The client asserts I1 at construction time (EgressViolation raised if
    base_url is not localhost).  It does not need a live Ollama to be
    constructed; it only connects when .stream() / .chat() is called.
    """

    def __init__(self, config: TierConfig) -> None:
        _assert_localhost(config.base_url)
        self._base_url = config.base_url
        self._model = config.model
        self._endpoint = f"{self._base_url}/v1/chat/completions"

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: str = "auto",
        *,
        _http_factory=None,
    ) -> Generator[StreamChunk, None, None]:
        """
        Open a streaming request to Ollama and yield StreamChunks as they
        arrive, terminating after the [DONE] sentinel.

        Parameters
        ----------
        messages:       OpenAI-format message list.
        tools:          Optional list of tool schemas (0002 §1).
        tool_choice:    "auto" (default) per 0002.
        _http_factory:  Injection seam for tests (replaces the real HTTP call
                        with a mock that returns an iterable of SSE lines).
                        Production callers leave this as None.
        """
        body: dict = {
            "model": self._model,
            "stream": True,
            "messages": messages,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice

        lines: Iterable[str] = self._make_request(body, _http_factory)
        yield from self._parse_stream(lines)

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: str = "auto",
        *,
        _http_factory=None,
    ) -> AssembledResponse:
        """
        Blocking convenience wrapper: streams and assembles the full response.
        """
        content_parts: list[str] = []
        # Accumulator dict: index -> ToolCallDelta
        tc_accum: dict[int, ToolCallDelta] = {}
        finish_reason = ""

        for chunk in self.stream(
            messages, tools=tools, tool_choice=tool_choice,
            _http_factory=_http_factory
        ):
            if chunk.content_delta:
                content_parts.append(chunk.content_delta)

            for delta in chunk.tool_call_deltas:
                if delta.index not in tc_accum:
                    tc_accum[delta.index] = ToolCallDelta(index=delta.index)
                acc = tc_accum[delta.index]
                if delta.id:
                    acc.id = delta.id
                if delta.name:
                    acc.name = delta.name
                acc.arguments += delta.arguments

            if chunk.finish_reason:
                finish_reason = chunk.finish_reason

        assembled_tcs = []
        for idx in sorted(tc_accum):
            acc = tc_accum[idx]
            assembled_tcs.append({
                "id": acc.id,
                "name": acc.name,
                "arguments": acc.arguments,
            })

        return AssembledResponse(
            content="".join(content_parts),
            tool_calls=assembled_tcs,
            finish_reason=finish_reason,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _make_request(
        self,
        body: dict,
        _http_factory,
    ) -> Iterable[str]:
        """
        Send the POST request and return an iterable of raw SSE lines.

        When _http_factory is provided (test seam), it is called with
        (endpoint, body) and must return an iterable of SSE line strings.
        In production, we use the stdlib urllib (zero extra dependencies).
        """
        if _http_factory is not None:
            return _http_factory(self._endpoint, body)

        # Production path: urllib (stdlib, no extra deps, sync)
        import urllib.request
        import urllib.error

        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self._endpoint,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Cannot reach Ollama at {self._endpoint}: {exc}"
            ) from exc

        # Return a generator over the response lines
        return (line.decode("utf-8") for line in resp)

    @staticmethod
    def _parse_stream(lines: Iterable[str]) -> Generator[StreamChunk, None, None]:
        """Parse SSE lines into StreamChunks (0002 §4)."""
        for line in lines:
            payload = _parse_sse_line(line)
            if payload is None:
                continue
            if payload == "[DONE]":
                done = StreamChunk()
                done.done = True
                yield done
                return
            chunk = _parse_chunk(payload)
            yield chunk
