"""finetune/llm.py — the LLM seam (Fake default / Anthropic real).

The generation driver (Phase 5) never touches an SDK directly; it talks to an
:class:`LLMBackend`.  This keeps INV-offline true: the whole build/validate/smoke
path runs with the FakeBackend — NO network, NO ``anthropic`` installed, NO
``ANTHROPIC_API_KEY``.  The real Anthropic client is behind a LAZY import inside
:class:`AnthropicBackend` so this module imports cleanly on a bare machine.

Normalized backend contract (Anthropic-shaped)
----------------------------------------------
``await backend.complete(messages, tools, tool_choice)`` returns::

    {"stop_reason": "tool_use" | "end_turn",
     "content_blocks": [ <block>, ... ]}

where each block is either a tool_use block ({type:"tool_use", id, name,
input(dict)}) or a text block ({type:"text", text}).  Blocks expose their fields
as ATTRIBUTES (``block.id`` / ``block.input`` / ``block.text``) — the real SDK
blocks already do, and :class:`ToolUseBlock` / :class:`TextBlock` mirror that —
so ``finetune.convert`` consumes either interchangeably.

Real backend uses model ``claude-sonnet-4-6`` (exact id, no date suffix).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

# Import the seam, NOT core/ directly (INV-read-only-core routes through here).
from finetune import coreimports

# Real backend's model id — the exact string, no date suffix (plan A2 / brief).
CLAUDE_MODEL = "claude-sonnet-4-6"


# --------------------------------------------------------------------------- #
# Normalized content blocks (Anthropic-shaped, attribute-accessible)           #
# --------------------------------------------------------------------------- #

@dataclass
class ToolUseBlock:
    """A normalized Anthropic ``tool_use`` block.

    ``input`` is a DICT (Claude's parsed tool input); convert.py JSON-encodes it
    into the §2 ``arguments`` STRING.
    """

    id: str
    name: str
    input: dict = field(default_factory=dict)
    type: str = "tool_use"


@dataclass
class TextBlock:
    """A normalized Anthropic ``text`` block (a plain English answer/narration)."""

    text: str
    type: str = "text"


# --------------------------------------------------------------------------- #
# The seam Protocol                                                            #
# --------------------------------------------------------------------------- #

@runtime_checkable
class LLMBackend(Protocol):
    """The single seam every generation call goes through.

    Implementations return the normalized {stop_reason, content_blocks} shape
    above so Phase-5 generate.py is identical regardless of backend.
    """

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: Any = "auto",
    ) -> dict:
        ...


# --------------------------------------------------------------------------- #
# Helpers shared by backends                                                   #
# --------------------------------------------------------------------------- #

def _scenario_field(scenario: Any, name: str) -> Any:
    if scenario is None:
        return None
    if isinstance(scenario, dict):
        return scenario.get(name)
    return getattr(scenario, name, None)


def _has_tool_result(messages: Sequence[dict]) -> bool:
    """True once a ``role:"tool"`` message is present — i.e. we are on the
    follow-up call, where the model would produce its final English answer."""
    return any(m.get("role") == "tool" for m in messages)


def _placeholder_for(arg_type: type, arg_name: str) -> Any:
    """A type-correct, plausible value for one required arg.

    Validity (0002 §5) only checks the TYPE, so a type-correct value always
    passes the live router.  We add a few name-based niceties so canned traces
    read realistically (e.g. a ``unit`` looks like a systemd unit).
    """
    if arg_type is bool:
        return True
    if arg_type is int:
        return 10
    if arg_type is float:
        return 1.0
    if arg_type is list:
        return ["nginx"]
    if arg_type is dict:
        return {}
    # str (default): light name-based realism, else a safe generic token.
    name = (arg_name or "").lower()
    if "unit" in name:
        return "nginx.service"
    if "package" in name or name in ("name", "pkg"):
        return "nginx"
    if "path" in name or "file" in name or name in ("dir", "directory"):
        return "/etc/nginx/nginx.conf"
    if "user" in name or name in ("username", "login"):
        return "deploy"
    if "port" in name:
        return "443/tcp"
    if "zone" in name:
        return "public"
    if "interface" in name or name in ("iface", "dev"):
        return "eth0"
    if "host" in name:
        return "localhost"
    return "nginx"


def plausible_args(tool: str, operation: str) -> dict:
    """Build a canned, schema-valid arguments dict for (tool, operation).

    Derived LIVE from the registry (INV-schema-sync — never hardcoded): the
    result is ``{"operation": operation, <each REQUIRED arg>: <typed value>}``
    so it validates through ``coreimports.validate_arguments`` unchanged.
    """
    args: dict[str, Any] = {"operation": operation}
    spec = coreimports.registry.get(tool)
    if spec is None:
        return args
    op_spec = spec.get_op(operation)
    if op_spec is None:
        return args
    for arg in op_spec.args:
        if arg.required:
            args[arg.name] = _placeholder_for(arg.type, arg.name)
    return args


# --------------------------------------------------------------------------- #
# FakeBackend (DEFAULT) — deterministic, offline                              #
# --------------------------------------------------------------------------- #

# A canned, I2-clean final answer.  It must pass core's _assert_no_ai_language
# (no "AI"/"LLM"/"model"/"agent"/"ollama"/"inference"/...).  Kept generic so it
# reads plausibly after any tool result.
_FAKE_ANSWER = "Done. The requested operation completed and the system is in the expected state."


class FakeBackend:
    """Deterministic, offline backend (the DEFAULT — INV-offline).

    Bound to ONE scenario (cheap to construct per scenario in generate.py).
    Statelessly decides its reply from the conversation, so it is safe under
    concurrency:

      * first call (no ``role:"tool"`` message yet) -> a ``tool_use`` block for
        the scenario's (tool, operation) with canned, schema-valid args, and
        ``stop_reason == "tool_use"``.
      * follow-up call (a tool result is present) -> a canned I2-clean English
        answer as a ``text`` block, ``stop_reason == "end_turn"``.

    The canned answer is asserted I2-clean at construction so a future edit that
    slips a forbidden term fails loudly here, not deep in the corpus.
    """

    def __init__(self, scenario: Any = None, answer: str = _FAKE_ANSWER) -> None:
        self.scenario = scenario
        self.answer = answer
        # Fail loud if the canned answer ever violates I2.
        coreimports.assert_no_ai_language(self.answer, "FakeBackend.answer")

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: Any = "auto",
    ) -> dict:
        if _has_tool_result(messages):
            return {
                "stop_reason": "end_turn",
                "content_blocks": [TextBlock(text=self.answer)],
            }

        tool = _scenario_field(self.scenario, "tool")
        operation = _scenario_field(self.scenario, "operation")
        if tool is None:
            # No scenario bound: fall back to the first advertised tool + its
            # first operation so the Fake still emits a valid, dispatchable call.
            tool, operation = self._first_tool_and_op(tools)

        block = ToolUseBlock(
            id=self._call_id(tool, operation),
            name=tool,
            input=plausible_args(tool, operation),
        )
        return {"stop_reason": "tool_use", "content_blocks": [block]}

    # -- helpers ----------------------------------------------------------- #

    def _call_id(self, tool: str, operation: str) -> str:
        """A deterministic ``toolu_``-prefixed id (matches Anthropic's prefix so
        the same code path exercises id-correlation offline; plan A5)."""
        sid = _scenario_field(self.scenario, "id") or f"{tool}-{operation}"
        return f"toolu_fake_{sid}"

    @staticmethod
    def _first_tool_and_op(tools: list[dict]) -> tuple[str, str]:
        for t in tools:
            fn = t.get("function", {})
            name = fn.get("name")
            enum = (
                fn.get("parameters", {})
                .get("properties", {})
                .get("operation", {})
                .get("enum", [])
            )
            if name and enum:
                return name, enum[0]
        raise ValueError("FakeBackend: no scenario bound and no usable tool advertised")


# --------------------------------------------------------------------------- #
# AnthropicBackend (real) — lazy import, never at module top                   #
# --------------------------------------------------------------------------- #

class AnthropicBackend:
    """Real backend wrapping ``anthropic.AsyncAnthropic`` (LAZY import).

    The ``anthropic`` package is imported INSIDE ``__init__`` — never at module
    top — so ``import finetune.llm`` succeeds with no SDK installed and no API
    key (INV-offline).  Relies on the SDK's built-in retry for 429/5xx.
    """

    def __init__(self, model: str = CLAUDE_MODEL, max_tokens: int = 1024) -> None:
        # LAZY import — do NOT hoist to module scope (INV-offline).
        import anthropic  # noqa: PLC0415

        self._anthropic = anthropic
        self._client = anthropic.AsyncAnthropic()
        self.model = model
        self.max_tokens = max_tokens

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: Any = None,
    ) -> dict:
        """Call the Messages API and normalize the response.

        ``messages`` here are the Anthropic-shaped conversation turns (the
        system prompt is passed via ``system=``, NOT as a role in the array).
        The caller (generate.py) is responsible for splitting the composed
        system string out of the assembled messages before calling this.
        """
        system, convo = self._split_system(messages)
        if tool_choice is None:
            tool_choice = {"type": "auto"}

        resp = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=convo,
            tools=self._to_anthropic_tools(tools),
            tool_choice=tool_choice,
        )
        return self._normalize(resp)

    # -- helpers ----------------------------------------------------------- #

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[Optional[str], list[dict]]:
        system: Optional[str] = None
        convo: list[dict] = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content")
            else:
                convo.append(m)
        return system, convo

    @staticmethod
    def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
        """Map 0002 §1 OpenAI tool schemas -> Anthropic tool schemas.

        OpenAI: {"type":"function","function":{"name","description","parameters"}}
        Anthropic: {"name","description","input_schema"}
        The parameters/input_schema JSON-Schema body is identical.
        """
        out: list[dict] = []
        for t in tools:
            fn = t.get("function", t)
            out.append({
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return out

    def _normalize(self, resp: Any) -> dict:
        """Parse ``response.content`` into normalized {stop_reason, content_blocks}.

        Parses tool inputs with json (the SDK already delivers ``.input`` as a
        parsed dict) — never string-match (claude-api pitfall).
        """
        blocks: list[Any] = []
        for block in getattr(resp, "content", []) or []:
            btype = getattr(block, "type", None)
            if btype == "tool_use":
                blocks.append(ToolUseBlock(
                    id=getattr(block, "id", ""),
                    name=getattr(block, "name", ""),
                    input=getattr(block, "input", {}) or {},
                ))
            elif btype == "text":
                blocks.append(TextBlock(text=getattr(block, "text", "")))
        return {
            "stop_reason": getattr(resp, "stop_reason", None),
            "content_blocks": blocks,
        }


# --------------------------------------------------------------------------- #
# Factory                                                                     #
# --------------------------------------------------------------------------- #

def make_backend(name: str = "fake", *, scenario: Any = None, model: str = CLAUDE_MODEL):
    """Construct a backend by name.

    ``"fake"`` (DEFAULT) -> a scenario-bound :class:`FakeBackend` (offline).
    ``"anthropic"``      -> a real :class:`AnthropicBackend` (lazy SDK import).
    """
    if name == "fake":
        return FakeBackend(scenario=scenario)
    if name == "anthropic":
        return AnthropicBackend(model=model)
    raise ValueError(f"unknown backend {name!r} (expected 'fake' or 'anthropic')")
