"""
core/agent/pipeline/assembler.py

Deterministic assembly of (tool, operation, slot_values) into a validated
ParsedCall (the frozen router shape) or a structured Unresolved.

Public API
----------
    assemble(tool, operation, slot_values, registry) -> AssembleResult

AssembleResult is either:
  * a ParsedCall  — validated, ready to flow into
                    synthesize_command -> permissions.classify ->
                    registry.dispatch -> AuditLog (the unchanged spine).
  * an Unresolved — carries the list of missing required slot names and a
                    plain reason string; the slot layer or escalation path
                    uses this to fill the gaps before retrying.

Design invariants (load-bearing)
---------------------------------
A1  ArgSpec.default is applied here for absent non-required args; this is a
    USE of the frozen contract, not a change to it.
A5  Argv rendering stays in repl.synthesize_command.  The assembler NEVER
    emits a shell string.
I2  No AI/LLM/model/agent language in any user-facing string.  Reason
    strings in Unresolved speak about operations and arguments, never a
    model.
I3  permissions.classify is THE single gate.  The assembler NEVER calls it
    and NEVER re-implements it; it only constructs the ParsedCall shape so
    the UNCHANGED spine can pass it through the gate.

Validation: we call router.validate_arguments — the SAME predicate the
native path uses — so the assembler and the native path produce IDENTICAL
validation verdicts.  One validator, not two.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Union

from core.agent.permissions import OpClass
from core.agent.router import ParsedCall, validate_arguments
from core.tools import ToolRegistry


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Unresolved:
    """One or more required slots could not be filled, or the spec is invalid.

    missing: the list of ArgSpec.name strings that are required but absent.
             Empty when the failure is not about missing slots (e.g. unknown
             tool/op or a type mismatch after defaults were applied).
    reason:  a concise, I2-clean explanation (no AI/LLM/model language).
    """

    missing: list[str] = field(default_factory=list)
    reason: str = ""


# The assembler returns one of these two types.
AssembleResult = Union[ParsedCall, Unresolved]


# ---------------------------------------------------------------------------
# assemble()
# ---------------------------------------------------------------------------

def assemble(
    tool: str,
    operation: str,
    slot_values: dict[str, Any],
    registry: ToolRegistry,
) -> AssembleResult:
    """Turn (tool, operation, slot_values) into a validated ParsedCall or Unresolved.

    Steps
    -----
    1. Look up the tool in the registry; Unresolved if not found.
    2. Look up the operation in the tool spec; Unresolved if not found.
    3. Apply ArgSpec.default for absent non-required args (A1).
    4. Collect missing required slots; return Unresolved if any.
    5. Call router.validate_arguments (same predicate as the native path) to
       produce the IDENTICAL validation verdict.  On failure: Unresolved.
    6. Set permission_class via spec.permission_class_for(operation), exactly
       as Router.route does.
    7. Return ParsedCall (frozen router shape, ready for the spine).

    Parameters
    ----------
    tool:        Registered tool name (e.g. "disk", "services").
    operation:   Op name within the tool (e.g. "format", "restart").
    slot_values: The filled slot dict from the extraction layer.  Should NOT
                 contain an "operation" key; the assembler injects it when
                 calling the shared validator.
    registry:    The ToolRegistry to look up specs and permission classes from.

    Returns
    -------
    ParsedCall on full validation success; Unresolved otherwise.
    """
    # 1. Tool lookup.
    spec = registry.get(tool)
    if spec is None:
        return Unresolved(
            missing=[],
            reason=f"tool {tool!r} is not registered",
        )

    # 2. Operation lookup.
    op_spec = spec.get_op(operation)
    if op_spec is None:
        valid_ops = ", ".join(sorted(spec.ops.keys()))
        return Unresolved(
            missing=[],
            reason=(
                f"operation {operation!r} is not declared for tool {tool!r}; "
                f"valid operations: [{valid_ops}]"
            ),
        )

    # 3. Apply ArgSpec.default for absent non-required args (A1).
    #    Build the working args dict (no "operation" key — injected in step 5).
    args: dict[str, Any] = {}
    for arg_spec in op_spec.args:
        supplied = slot_values.get(arg_spec.name)
        if supplied is not None:
            args[arg_spec.name] = supplied
        elif not arg_spec.required and arg_spec.default is not None:
            # Apply the declared default; this is a USE of the frozen ArgSpec
            # contract, not a change to it.
            args[arg_spec.name] = arg_spec.default
        # Required absent slots are collected in step 4.

    # 4. Collect missing required slots.
    missing: list[str] = [
        arg_spec.name
        for arg_spec in op_spec.args
        if arg_spec.required and arg_spec.name not in args
    ]
    if missing:
        return Unresolved(
            missing=missing,
            reason=(
                f"operation {operation!r} requires: {', '.join(missing)}"
            ),
        )

    # 5. Validate via the SAME predicate the native path uses (one validator,
    #    not two).  Inject "operation" so validate_arguments sees the full dict
    #    — this mirrors exactly what Router.route does after JSON-parsing the
    #    model's arguments string.
    full_args: dict[str, Any] = {"operation": operation, **args}
    try:
        _, validated_args = validate_arguments(spec, full_args)
    except ValueError as exc:
        # The validator surfaces a specific detail string (type mismatches,
        # unexpected keys, etc.).  Map to Unresolved so the slot layer can
        # act on it.
        return Unresolved(
            missing=[],
            reason=str(exc),
        )

    # 6. Permission class — identical to Router.route:
    #    spec.permission_class_for(operation) or OpClass.WRITE.
    perm: OpClass = spec.permission_class_for(operation) or OpClass.WRITE

    # 7. Return ParsedCall (the frozen router shape).
    #    call_id is a fresh correlation id; the spine's AuditLog and the
    #    tool-result message correlate by this id.
    return ParsedCall(
        call_id=_fresh_call_id(),
        tool=tool,
        operation=operation,
        args=validated_args,
        permission_class=perm,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_call_id() -> str:
    """Generate a unique correlation id for an assembled call.

    The id space is disjoint from model-issued ids (which may be empty strings
    or model-specific tokens); the "asm-" prefix makes the source visible in
    audit records without using AI/LLM language (I2).
    """
    return f"asm-{uuid.uuid4().hex[:12]}"
