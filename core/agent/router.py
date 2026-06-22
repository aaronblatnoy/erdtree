"""
core/agent/router.py

Tool-call router: the strict parser/validator that sits between the model's
assembled response and the tool-dispatch layer.  It implements the FROZEN
tool-call contract in docs/decisions/0002-tool-call-protocol.md (§2 parse
rules, §5 malformed-call / re-ask contract).  It is the single place that
decides whether a model turn is a VALID tool call or a MISS.

Design contract (load-bearing):

  * 0002 §2  A tool call is an entry in ``tool_calls[]`` with ``type ==
             "function"``; ``function.name`` MUST match a registered tool id;
             ``function.arguments`` is a JSON-encoded STRING (not a nested
             object) that must parse AND validate against that tool's
             parameter schema.
  * 0002 §5  Anything else (prose where a tool was required, unknown tool,
             unparseable / schema-invalid args) is a MISS.  On a MISS the
             router NEVER crashes: it counts the miss and produces the
             verbatim re-ask message so the loop can re-prompt.
  * I2       No AI/LLM/model/agent language in any user-facing string.  The
             re-ask wording is the plain OpenCode-grounded contract text from
             0002 §5; it speaks about "the <tool> tool" and "the input", never
             about a model.

This module derives each tool's §1 JSON-Schema and validates parsed arguments
WITHOUT importing or mutating core/tools (the registry stays the single source
of truth for the op/arg descriptors).  The wire shape (§1) presents each tool
as a single function whose ``operation`` argument is an enum over the tool's
op names, plus the union of all per-op arguments; validation then enforces the
selected operation's required-arg set.  Dispatch maps the wire
``{operation, ...rest}`` form onto the registry's ``dispatch(tool, op, args)``
internal API.

Nothing here talks to a network, a model, or a live Linux subsystem.  It is
fully unit-testable on any host (including the macOS dev host).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.agent.permissions import OpClass
from core.tools import ArgSpec, OpSpec, ToolRegistry, ToolResult, ToolSpec


# --------------------------------------------------------------------------- #
# Re-ask wording (0002 §5 — I2-clean, instructive for self-correction)        #
# --------------------------------------------------------------------------- #
#
# These three strings are the FROZEN MISS signals from 0002 §5.  They are
# surfaced back to the loop as a ``role:"tool"`` message so the next turn can
# rewrite its call.  None of them contain AI/LLM/model/agent language.
#
# Design: lead with the CONCRETE FIX — echo the exact detail the validator
# produced (valid operation list, missing arg name, offending token) so a
# small 7B/3B has the precise correction in front of it.  Keep each message
# to one or two sentences; over-verbose re-asks confuse small bases.

def reask_invalid_arguments(tool: str, detail: str) -> str:
    """0002 §5 — invalid-arguments re-ask; threads the exact validator detail.

    ``detail`` is the precise message from :func:`validate_arguments`
    (e.g. ``"'operation' must be one of [install, remove, ...], got 'instal'"``
    or ``"operation 'restart' requires argument 'unit'"``).
    Leading with the concrete fix helps a small base self-correct.
    """
    return (
        f"The `{tool}` tool was called with invalid input: {detail}. "
        "Rewrite the input so it matches the required schema and try again."
    )


def reask_unknown_tool(name: str, valid_tools: Optional[list[str]] = None) -> str:
    """0002 §5 — unknown-tool MISS signal; names the offending tool.

    When ``valid_tools`` is supplied (a sorted list of registered tool names)
    it is appended so the next call can pick a correct name.
    """
    if valid_tools:
        names = ", ".join(valid_tools)
        return (
            f"'{name}' is not a recognised tool. "
            f"Use one of the available tools: {names}."
        )
    return f"'{name}' is not a recognised tool."


def reask_invalid_input(detail: str) -> str:
    """0002 §5 — low-level decode-failure MISS signal; surfaces offending token."""
    return (
        f"The tool input could not be parsed: {detail}. "
        "Check that the input is valid JSON and try again."
    )


# --------------------------------------------------------------------------- #
# Outcome classification                                                       #
# --------------------------------------------------------------------------- #

class TurnKind(str, Enum):
    """How the router classified one assistant turn."""

    TOOL_CALL = "tool_call"   # ≥1 valid, dispatchable tool call (VALID)
    ENGLISH = "english"       # plain English answer, no tool_calls (not a miss)
    MISS = "miss"             # malformed / unknown / invalid — counts against validity


@dataclass
class ParsedCall:
    """One successfully parsed + validated tool call, ready to dispatch."""

    call_id: str            # the §2 correlation id, echoed in the tool result
    tool: str               # registered tool name
    operation: str          # the selected op_name within the tool
    args: dict[str, Any]    # the per-op arguments (operation key stripped out)
    permission_class: OpClass  # declared class for (tool, op) — pre-classify aid


@dataclass
class MissDetail:
    """One MISS, carrying the verbatim re-ask message to feed back to the model."""

    call_id: str            # may be "" when the model gave no id
    reason: str             # short machine reason (unknown_tool / bad_json / schema)
    reask: str              # verbatim 0002 §5 re-ask text (I2-clean)


@dataclass
class RouterResult:
    """The router's verdict for one assembled assistant turn.

    ``kind`` is the top-level classification.  ``calls`` holds every VALID call
    (parallel calls each get an entry; 0002 §2).  ``misses`` holds every MISS
    with its re-ask text.  ``content`` carries the English text for an
    ENGLISH turn.

    For benchmark scoring (bench/run_bench.py): a turn is VALID iff
    ``kind is TurnKind.TOOL_CALL`` AND there are no misses (every emitted
    call parsed and validated).  ``is_valid_action`` encodes exactly that.
    """

    kind: TurnKind
    calls: list[ParsedCall] = field(default_factory=list)
    misses: list[MissDetail] = field(default_factory=list)
    content: str = ""

    @property
    def is_valid_action(self) -> bool:
        """True iff this turn is a clean, fully-parseable tool-call turn.

        This is the bench validity predicate (0002 §5): ≥1 tool call, every
        one with a registered name and schema-valid arguments, zero misses.
        """
        return self.kind is TurnKind.TOOL_CALL and not self.misses and bool(self.calls)

    @property
    def reask_messages(self) -> list[dict]:
        """0002 §3-shaped ``role:"tool"`` messages re-asking each MISS.

        The loop appends these to the conversation and re-prompts.  Each
        message correlates by ``tool_call_id`` when the model supplied an id.
        """
        out: list[dict] = []
        for miss in self.misses:
            out.append({
                "role": "tool",
                "tool_call_id": miss.call_id or "",
                "content": miss.reask,
            })
        return out


# --------------------------------------------------------------------------- #
# Schema derivation (0002 §1) from the registry's ToolSpec descriptors        #
# --------------------------------------------------------------------------- #
#
# The registry keys operations by op_name and gives each op its own ArgSpec
# list.  The wire shape (§1) is ONE function per tool whose ``operation`` arg
# is an enum over the op names, plus the union of every op's arguments.  We
# build that here without touching core/tools.

_PY_TYPE_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _arg_to_json_schema(arg: ArgSpec) -> dict[str, Any]:
    json_type = _PY_TYPE_TO_JSON.get(arg.type, "string")
    prop: dict[str, Any] = {"type": json_type}
    if arg.description:
        prop["description"] = arg.description
    if json_type == "array":
        # Conservative: list-of-strings is the only list shape any core tool
        # uses (e.g. packages.packages).  Items typed as string keeps the
        # schema strict without over-specifying.
        prop["items"] = {"type": "string"}
    return prop


def tool_to_function_schema(spec: ToolSpec) -> dict[str, Any]:
    """Build the 0002 §1 ``{"name","description","parameters"}`` schema dict.

    ``parameters`` is a JSON-Schema (draft-07 subset) object whose required
    set is the minimal cross-op floor: ``operation`` is always required; an
    argument is listed as required at the top level only if EVERY op that
    declares it marks it required (so the schema never demands an arg that some
    selected op does not need).  Per-op required enforcement happens in
    :func:`validate_arguments` once the operation is known.
    """
    properties: dict[str, Any] = {
        "operation": {
            "type": "string",
            "enum": sorted(spec.ops.keys()),
            "description": "The operation to perform.",
        }
    }
    # Union every op's args into the property set.
    seen: dict[str, ArgSpec] = {}
    for op in spec.ops.values():
        for arg in op.args:
            if arg.name not in seen:
                seen[arg.name] = arg
                properties[arg.name] = _arg_to_json_schema(arg)

    parameters: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        # Only ``operation`` is unconditionally required at the wire level;
        # per-op required args are enforced after the op is resolved.
        "required": ["operation"],
        "additionalProperties": False,
    }
    return {
        "name": spec.name,
        "description": spec.description,
        "parameters": parameters,
    }


def registry_schemas(registry: ToolRegistry, tool_names: Optional[list[str]] = None) -> list[dict]:
    """Return §1 schema dicts for the named tools (or all registered tools).

    Output is the ``[{"name","description","parameters"}]`` shape that
    ``core.agent.prompt.build_tool_list`` consumes.  Unknown names are skipped
    silently (the prompt layer only advertises what exists).
    """
    names = tool_names if tool_names is not None else registry.list_tools()
    out: list[dict] = []
    for name in names:
        spec = registry.get(name)
        if spec is None:
            continue
        out.append(tool_to_function_schema(spec))
    return out


# --------------------------------------------------------------------------- #
# Argument validation (0002 §2/§5)                                            #
# --------------------------------------------------------------------------- #

def _json_type_ok(value: Any, py_type: type) -> bool:
    # bool is a subclass of int in Python; keep them distinct for the schema.
    if py_type is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if py_type is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, py_type)


def validate_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate a parsed arguments dict against ``spec`` (0002 §5).

    Enforces: ``operation`` present and a known op; every required arg of the
    SELECTED op present; declared args correctly typed; no unknown keys (the
    wire schema is ``additionalProperties:false``).

    Returns ``(operation, per_op_args)`` on success — the operation key is
    stripped from the returned args so it maps onto the registry's
    ``dispatch(tool, op, args)`` API.

    Raises ValueError with a human ``detail`` string on the first violation
    (the caller turns it into the §5 re-ask message; the string is I2-clean —
    it talks about arguments and operations, never a model).
    """
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be a JSON object")

    operation = arguments.get("operation")
    if operation is None:
        raise ValueError("missing required argument 'operation'")
    if not isinstance(operation, str):
        raise ValueError("'operation' must be a string")
    op_spec: Optional[OpSpec] = spec.get_op(operation)
    if op_spec is None:
        valid = ", ".join(sorted(spec.ops.keys()))
        raise ValueError(
            f"'operation' must be one of [{valid}], got {operation!r}"
        )

    declared = {a.name: a for a in op_spec.args}
    rest = {k: v for k, v in arguments.items() if k != "operation"}

    # No unknown keys (additionalProperties:false at the per-op level too).
    for key in rest:
        if key not in declared:
            raise ValueError(
                f"unexpected argument {key!r} for operation {operation!r}"
            )

    # Required args of the selected op must be present and typed.
    for arg in op_spec.args:
        if arg.name not in rest or rest[arg.name] is None:
            if arg.required:
                raise ValueError(
                    f"operation {operation!r} requires argument {arg.name!r}"
                )
            continue
        if not _json_type_ok(rest[arg.name], arg.type):
            raise ValueError(
                f"argument {arg.name!r} must be {arg.type.__name__}, "
                f"got {type(rest[arg.name]).__name__}"
            )

    return operation, rest


# --------------------------------------------------------------------------- #
# The router                                                                   #
# --------------------------------------------------------------------------- #

class Router:
    """Strict tool-call router (0002 §2/§5).

    Construct with the tool registry.  Call :meth:`route` with the assembled
    assistant turn (the shape produced by
    ``core.model.ollama.AssembledResponse`` — i.e. ``content`` plus a list of
    ``{"id","name","arguments"}`` tool-call dicts) and receive a
    :class:`RouterResult`.

    The router NEVER raises on malformed input.  A bad call is recorded as a
    MISS (with its verbatim re-ask), never a crash (plan: "count a bad call as
    a MISS, never crash").
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    # ------------------------------------------------------------------ #
    # Schema advertisement (feeds prompt.build_tool_list)                  #
    # ------------------------------------------------------------------ #

    def advertised_schemas(self, tool_names: Optional[list[str]] = None) -> list[dict]:
        """§1 schema dicts for the prompt layer (see :func:`registry_schemas`)."""
        return registry_schemas(self._registry, tool_names)

    # ------------------------------------------------------------------ #
    # Routing                                                             #
    # ------------------------------------------------------------------ #

    def route(
        self,
        *,
        content: str = "",
        tool_calls: Optional[list[dict]] = None,
        finish_reason: str = "",
    ) -> RouterResult:
        """Classify one assistant turn.

        Parameters mirror ``AssembledResponse``:
          content:       English text the model produced (may be "").
          tool_calls:    list of ``{"id","name","arguments"}`` dicts, where
                         ``arguments`` is a JSON-ENCODED STRING (0002 §2).  An
                         entry may also carry ``type`` / ``function`` in the
                         raw OpenAI shape; both shapes are accepted.
          finish_reason: the stream's finish reason (informational).
        """
        calls = tool_calls or []

        # No tool calls at all -> English turn (0002 §2: content non-null, no
        # tool_calls = a plain answer).  Not a miss.
        if not calls:
            return RouterResult(kind=TurnKind.ENGLISH, content=content)

        parsed: list[ParsedCall] = []
        misses: list[MissDetail] = []

        for raw in calls:
            call_id, name, arg_str = _extract_call_fields(raw)

            # type must be "function" when present (0002 §2).
            raw_type = raw.get("type")
            if raw_type is not None and raw_type != "function":
                misses.append(MissDetail(
                    call_id=call_id,
                    reason="bad_type",
                    reask=reask_invalid_input(
                        f"tool call type must be 'function', got {raw_type!r}"
                    ),
                ))
                continue

            # Unknown / missing tool name (0002 §2 -> §5 "Unknown tool").
            if not name:
                misses.append(MissDetail(
                    call_id=call_id,
                    reason="missing_name",
                    reask=reask_unknown_tool("(none)"),
                ))
                continue
            spec = self._registry.get(name)
            if spec is None:
                misses.append(MissDetail(
                    call_id=call_id,
                    reason="unknown_tool",
                    reask=reask_unknown_tool(name, self._registry.list_tools()),
                ))
                continue

            # arguments must be a JSON-encoded STRING that parses (0002 §2).
            parsed_args, parse_err = _parse_arguments(arg_str)
            if parse_err is not None:
                misses.append(MissDetail(
                    call_id=call_id,
                    reason="bad_json",
                    reask=reask_invalid_arguments(name, parse_err),
                ))
                continue

            # Schema validation against the selected op (0002 §5).
            try:
                operation, op_args = validate_arguments(spec, parsed_args)
            except ValueError as exc:
                misses.append(MissDetail(
                    call_id=call_id,
                    reason="schema",
                    reask=reask_invalid_arguments(name, str(exc)),
                ))
                continue

            perm = spec.permission_class_for(operation) or OpClass.WRITE
            parsed.append(ParsedCall(
                call_id=call_id,
                tool=name,
                operation=operation,
                args=op_args,
                permission_class=perm,
            ))

        # Verdict: any miss makes the whole turn a MISS for validity scoring
        # (0002 §5 — a turn is VALID iff every emitted call parses+validates).
        if misses:
            return RouterResult(
                kind=TurnKind.MISS,
                calls=parsed,
                misses=misses,
                content=content,
            )
        return RouterResult(kind=TurnKind.TOOL_CALL, calls=parsed, content=content)

    # ------------------------------------------------------------------ #
    # Dispatch (post-permission-gate execution; 0002 §3 result shaping)   #
    # ------------------------------------------------------------------ #

    def dispatch(self, call: ParsedCall) -> ToolResult:
        """Execute one already-gated, already-validated call.

        PRE-CONDITION (caller's responsibility, mirrors registry.dispatch):
        the permission gate for ``(call.tool, call.operation)`` has been
        resolved and cleared, and the audit record is written by the caller.
        This method only maps the wire form onto the registry API and runs it.
        """
        return self._registry.dispatch(call.tool, call.operation, call.args)

    @staticmethod
    def tool_result_message(call_id: str, result: ToolResult) -> dict:
        """Build the 0002 §3 ``role:"tool"`` result message for one call.

        ``content`` is the compact JSON of the structured result so the model
        can reason over exit code + summaries (0002 §3).
        """
        payload = {
            "exit_code": result.exit_code,
            "stdout_summary": _clip(result.stdout, 512),
            "stderr_summary": _clip(result.stderr, 512),
            "summary": result.summary,
        }
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        }


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _extract_call_fields(raw: dict) -> tuple[str, str, Any]:
    """Pull (id, name, arguments) from either the assembled or raw §2 shape.

    Assembled (ollama.AssembledResponse): ``{"id","name","arguments"}``.
    Raw OpenAI (§2): ``{"id","type","function":{"name","arguments"}}``.
    Both are accepted so the router works directly on either representation.
    """
    call_id = raw.get("id") or ""
    if "function" in raw and isinstance(raw["function"], dict):
        fn = raw["function"]
        return call_id, fn.get("name") or "", fn.get("arguments")
    return call_id, raw.get("name") or "", raw.get("arguments")


def _parse_arguments(arg_str: Any) -> tuple[dict[str, Any], Optional[str]]:
    """Parse the §2 JSON-encoded arguments STRING.

    0002 §2 says ``arguments`` is a JSON-encoded string, NOT a nested object.
    We accept a dict too (some intermediaries pre-decode it) for robustness,
    but a string that fails to parse is a MISS.  Returns ``(parsed, None)`` on
    success or ``({}, detail)`` on failure.
    """
    if isinstance(arg_str, dict):
        return arg_str, None
    if arg_str is None:
        return {}, "arguments are missing"
    if not isinstance(arg_str, str):
        return {}, f"arguments must be a JSON string, got {type(arg_str).__name__}"
    s = arg_str.strip()
    if s == "":
        # Empty string is a common 3B failure; treat as empty object so the
        # schema layer reports the precise missing 'operation' instead.
        return {}, None
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as exc:
        return {}, f"arguments are not valid JSON ({exc.msg})"
    if not isinstance(obj, dict):
        return {}, "arguments must decode to a JSON object"
    return obj, None


def _clip(text: str, limit: int) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "…[truncated]"
