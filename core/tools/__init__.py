"""core/tools — Tool registry and uniform tool interface.

This module defines the FROZEN shared contract that router.py (Phase 4) and
every individual tool (services, packages, logs, ...) bind to. It is the
single source of truth for:

  * The structured result type every tool's execute() must return.
  * The ToolSpec descriptor every tool must provide.
  * The ToolRegistry that discovers and dispatches tools by name.

Design rules (load-bearing — see buildout invariants):

  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  Every tool declares a per-op permission class; the registry enforces that
      every execute() call has already been cleared by the permission seam before
      it runs (callers are responsible for calling permissions.classify() and
      resolving the gate; the registry validates, never by-passes, the gate).
  I4  Every execute() produces one AuditLog record (callers supply the log).
  I6  This module contains ZERO tier/product/model names.

Nothing in here talks to a network, a model, or a live Linux subsystem. It is
fully testable on any host (including macOS dev host) with stub tools.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.agent.permissions import OpClass


# ---------------------------------------------------------------------------
# Structured result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolResult:
    """The structured output that every tool's execute() must return.

    Fields mirror the audit schema (Phase 1 / audit.py) so the caller can
    transcribe the result into the audit log without extra transformation.

    exit_code:  The integer exit status of the underlying subprocess (or a
                synthetic code: 0 = success, 1 = general error, 2 = skipped
                by permission gate). None if execution was never attempted.
    stdout:     Raw captured stdout (may be empty).
    stderr:     Raw captured stderr (may be empty).
    summary:    A single human-readable sentence describing the outcome.
                No AI/LLM/model language (I2). This is what the model layer
                receives as the "tool output" to reason over.
    """

    exit_code: Optional[int]
    stdout: str
    stderr: str
    summary: str

    @property
    def ok(self) -> bool:
        """True iff the operation succeeded (exit_code == 0)."""
        return self.exit_code == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Tool spec
# ---------------------------------------------------------------------------

@dataclass
class ArgSpec:
    """Schema for a single argument a tool operation accepts.

    name:       Argument name as it appears in the tool-call JSON.
    type:       Python type (str, int, bool, list).  Used for validation.
    required:   Whether this argument must be present.
    description: One-line description (shown in error messages, never to users).
    default:    Default value when not required and absent.
    """

    name: str
    type: type
    required: bool = True
    description: str = ""
    default: Any = None


@dataclass
class OpSpec:
    """Declaration of one operation a tool supports.

    op_name:        Unique name within the tool (e.g. "status", "restart").
    permission_class: The risk class this operation falls into. The caller
                    MUST resolve the corresponding gate via permissions.classify()
                    before calling execute(). Declaring it here lets the registry
                    surface the class without executing anything — used by Phase 4
                    router.py to pre-classify before prompting the user.
    args:           The argument schema for this operation.
    description:    One-line description (internal / error messages).
    """

    op_name: str
    permission_class: OpClass
    args: list[ArgSpec] = field(default_factory=list)
    description: str = ""


@dataclass
class ToolSpec:
    """The complete descriptor for one registered tool.

    name:       Globally unique tool name (e.g. "services", "packages").
    ops:        All operations this tool supports, keyed by op_name.
    execute:    The callable that runs one operation.

                Signature::

                    execute(op: str, args: dict[str, Any]) -> ToolResult

                The callable must be side-effect-free until the permission gate
                has been resolved externally. It must never call permissions or
                audit itself — those are the registry's / caller's concern.
    description: One-line description of the tool (internal).
    """

    name: str
    ops: dict[str, OpSpec]
    execute: Callable[[str, dict[str, Any]], ToolResult]
    description: str = ""

    def get_op(self, op_name: str) -> Optional[OpSpec]:
        return self.ops.get(op_name)

    def permission_class_for(self, op_name: str) -> Optional[OpClass]:
        """Return the declared permission class for an op, or None if unknown."""
        op = self.ops.get(op_name)
        return op.permission_class if op else None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Central registry of all available tools.

    Tools register themselves with :meth:`register`. The Phase 4 router calls
    :meth:`dispatch` to execute a tool operation after the permission gate has
    been resolved.

    The registry is intentionally simple: a dict keyed on tool name. No
    dynamic loading, no plugin magic — just explicit registration. This keeps
    the contract auditable and the import graph clean.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, spec: ToolSpec) -> None:
        """Register a tool. Raises ValueError on duplicate names."""
        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' is already registered")
        self._tools[spec.name] = spec

    def unregister(self, name: str) -> None:
        """Remove a tool. Raises KeyError if not registered (for tests)."""
        del self._tools[name]

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[ToolSpec]:
        """Return a ToolSpec by name, or None if not found."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """Return sorted list of registered tool names."""
        return sorted(self._tools)

    def permission_class_for(self, tool_name: str, op_name: str) -> Optional[OpClass]:
        """Return the declared permission class for a (tool, op) pair.

        Returns None if the tool or op is not registered, so the caller can
        treat unknown as default-deny (WRITE at minimum).
        """
        spec = self._tools.get(tool_name)
        if spec is None:
            return None
        return spec.permission_class_for(op_name)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(
        self,
        tool_name: str,
        op: str,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute a (tool, op, args) triple and return a ToolResult.

        PRE-CONDITIONS (caller's responsibility — not enforced here):
          1. The permission gate for (tool_name, op) has been resolved and
             cleared (ALLOW or confirmed CONFIRM/CONFIRM_TYPED). The registry
             does NOT re-check the gate; it trusts the caller.
          2. The audit log has been (or will be) written by the caller.

        Raises:
          KeyError   — tool_name not registered.
          ValueError — op not declared in the tool's OpSpec map.
          TypeError  — args fail the declared arg schema.
        """
        spec = self._tools.get(tool_name)
        if spec is None:
            raise KeyError(f"Unknown tool: '{tool_name}'")

        op_spec = spec.get_op(op)
        if op_spec is None:
            raise ValueError(f"Tool '{tool_name}' has no operation '{op}'")

        # Validate args against the declared schema.
        _validate_args(args, op_spec)

        return spec.execute(op, args)

    def __repr__(self) -> str:  # pragma: no cover
        names = ", ".join(self.list_tools()) or "(empty)"
        return f"ToolRegistry([{names}])"


# ---------------------------------------------------------------------------
# Argument validation helper
# ---------------------------------------------------------------------------

def _validate_args(args: dict[str, Any], op_spec: OpSpec) -> None:
    """Validate args dict against an OpSpec's declared ArgSpec list.

    Raises TypeError with a descriptive message on the first violation. Does
    not raise for extra keys (permissive on forward-compat extras).
    """
    for arg_spec in op_spec.args:
        if arg_spec.required and arg_spec.name not in args:
            raise TypeError(
                f"Operation '{op_spec.op_name}' requires argument '{arg_spec.name}'"
            )
        if arg_spec.name in args and args[arg_spec.name] is not None:
            value = args[arg_spec.name]
            if not isinstance(value, arg_spec.type):
                raise TypeError(
                    f"Argument '{arg_spec.name}' for '{op_spec.op_name}' must be "
                    f"{arg_spec.type.__name__}, got {type(value).__name__}"
                )


# ---------------------------------------------------------------------------
# Subprocess helper (shared by tool implementations)
# ---------------------------------------------------------------------------

def run_subprocess(
    cmd: list[str],
    *,
    timeout: int = 30,
    input: Optional[str] = None,  # noqa: A002
) -> ToolResult:
    """Run a subprocess and return a ToolResult.

    This is the ONLY sanctioned way for tool implementations to shell out. It
    captures stdout and stderr, never raises on non-zero exit (the exit_code in
    the result communicates failure), and enforces a timeout.

    Args:
        cmd:      The command vector to execute (never passed to a shell).
        timeout:  Maximum wall-clock seconds before the process is killed.
        input:    Optional stdin to feed the process.

    Returns:
        A ToolResult with exit_code, stdout, stderr, and a brief summary line.
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input,
        )
        summary = (
            f"exited {proc.returncode}"
            if proc.returncode != 0
            else "completed successfully"
        )
        return ToolResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            summary=summary,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            exit_code=124,  # conventional timeout exit code
            stdout="",
            stderr="",
            summary=f"timed out after {timeout}s",
        )
    except FileNotFoundError:
        return ToolResult(
            exit_code=127,  # command not found
            stdout="",
            stderr="",
            summary=f"command not found: {cmd[0]}",
        )
    except OSError as exc:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr=str(exc),
            summary=f"OS error: {exc}",
        )


# ---------------------------------------------------------------------------
# Module-level default registry (convenience singleton)
# ---------------------------------------------------------------------------

#: The global tool registry. Individual tool modules call
#: ``from core.tools import registry; registry.register(...)`` at import time.
registry: ToolRegistry = ToolRegistry()
