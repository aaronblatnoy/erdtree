"""core/tools/selinux.py — SELinux policy and enforcement management tool.

Supported operations
--------------------
  sestatus               (READ)        — show overall SELinux status.
  getsebool              (READ)        — show the value of an SELinux boolean.
  getenforce             (READ)        — show the current enforcement mode.
  setenforce             (WRITE)       — set the enforcement mode (0=permissive, 1=enforcing).
  setsebool              (WRITE)       — set an SELinux boolean on/off, optionally persisting.
  semanage_fcontext_list  (READ)       — list all file context mappings.
  semanage_fcontext_add   (WRITE)      — add a file context mapping.
  semanage_fcontext_delete (DESTRUCTIVE) — delete a file context mapping.
  semanage_port_list      (READ)       — list port label mappings.
  semanage_port_add       (WRITE)      — add a port label mapping.
  semanage_port_delete    (DESTRUCTIVE) — delete a port label mapping.
  semanage_user_list      (READ)       — list SELinux user mappings.
  semanage_user_add       (WRITE)      — add an SELinux user mapping.
  semanage_user_delete    (DESTRUCTIVE) — delete an SELinux user mapping.
  restorecon             (WRITE)       — restore default file contexts on a path.
  chcon                  (WRITE)       — change the SELinux type on a file or directory.
  audit2allow            (READ)        — analyze AVC denial logs and generate policy suggestions.

Permission mapping
------------------
  READ        : sestatus, getsebool, getenforce, semanage_fcontext_list,
                semanage_port_list, semanage_user_list, audit2allow
  WRITE       : setenforce, setsebool, semanage_fcontext_add,
                semanage_port_add, semanage_user_add, restorecon, chcon
  DESTRUCTIVE : semanage_fcontext_delete, semanage_port_delete,
                semanage_user_delete

Note on setenforce
  setenforce 0 (disabling enforcement) is already classified DESTRUCTIVE by
  the permissions module (_DESTRUCTIVE_PATTERNS: setenforce\\s+0). The OpSpec
  advisory class is WRITE per the plan table; the classifier is authoritative.

Note on setsebool -P
  setsebool without -P changes only the runtime value. Adding -P persists the
  change across reboots and alters long-term security posture. Both forms are
  labeled WRITE per the plan table.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.
"""

from __future__ import annotations

import re
from typing import Any

from core.agent.permissions import OpClass
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)

# ---------------------------------------------------------------------------
# SELinux hint detection
# ---------------------------------------------------------------------------

_SELINUX_HINT_RE = re.compile(
    r"AVC\s+avc:|Permission\s+denied|dontaudit|type=AVC|selinux",
    re.IGNORECASE,
)

_SELINUX_HINT = (
    "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
    "or 'journalctl -t setroubleshoot' for denial details."
)


def _maybe_selinux_hint(stderr: str) -> str:
    """Return a SELinux hint suffix if stderr looks like an AVC denial."""
    if _SELINUX_HINT_RE.search(stderr):
        return f"  {_SELINUX_HINT}"
    return ""


# ---------------------------------------------------------------------------
# Shared ArgSpecs
# ---------------------------------------------------------------------------

_BOOLEAN_ARG = ArgSpec(
    name="boolean",
    type=str,
    required=True,
    description="The SELinux boolean name (e.g. 'httpd_can_network_connect').",
)

_PATH_ARG = ArgSpec(
    name="path",
    type=str,
    required=True,
    description="The filesystem path to operate on.",
)

# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------


def _op_sestatus(args: dict[str, Any]) -> ToolResult:
    """sestatus — display SELinux status."""
    result = run_subprocess(["sestatus"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "SELinux status retrieved."
    else:
        summary = f"Failed to retrieve SELinux status (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_getsebool(args: dict[str, Any]) -> ToolResult:
    """getsebool <boolean> — show a boolean value."""
    boolean: str = args["boolean"]
    result = run_subprocess(["getsebool", boolean])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Boolean '{boolean}' value retrieved."
    else:
        summary = f"Failed to get boolean '{boolean}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_getenforce(args: dict[str, Any]) -> ToolResult:
    """getenforce — show the current enforcement mode."""
    result = run_subprocess(["getenforce"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Enforcement mode retrieved."
    else:
        summary = f"Failed to retrieve enforcement mode (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_setenforce(args: dict[str, Any]) -> ToolResult:
    """setenforce <mode> — set enforcement mode (0=permissive, 1=enforcing)."""
    mode: str = args["mode"]
    result = run_subprocess(["setenforce", mode])
    selinux = _maybe_selinux_hint(result.stderr)
    mode_label = "permissive" if mode == "0" else "enforcing"
    if result.ok:
        summary = f"Enforcement set to {mode_label}."
    else:
        summary = f"Failed to set enforcement to {mode_label} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_setsebool(args: dict[str, Any]) -> ToolResult:
    """setsebool [-P] <boolean> <on|off> — set a boolean, optionally persisting."""
    boolean: str = args["boolean"]
    value: str = args["value"]
    persist: bool = bool(args.get("persist", False))
    if persist:
        cmd = ["setsebool", "-P", boolean, value]
    else:
        cmd = ["setsebool", boolean, value]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    persist_note = " (persistent)" if persist else " (runtime only)"
    if result.ok:
        summary = f"Boolean '{boolean}' set to {value}{persist_note}."
    else:
        summary = f"Failed to set boolean '{boolean}' to {value} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_semanage_fcontext_list(args: dict[str, Any]) -> ToolResult:
    """semanage fcontext -l — list all file context mappings."""
    result = run_subprocess(["semanage", "fcontext", "-l"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "File context mappings listed."
    else:
        summary = f"Failed to list file context mappings (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_semanage_fcontext_add(args: dict[str, Any]) -> ToolResult:
    """semanage fcontext -a -t <type> <spec> — add a file context mapping."""
    fcontext_type: str = args["fcontext_type"]
    fcontext_spec: str = args["fcontext_spec"]
    result = run_subprocess(
        ["semanage", "fcontext", "-a", "-t", fcontext_type, fcontext_spec]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"File context '{fcontext_spec}' mapped to type '{fcontext_type}'."
    else:
        summary = (
            f"Failed to add file context mapping '{fcontext_spec}' -> '{fcontext_type}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_semanage_fcontext_delete(args: dict[str, Any]) -> ToolResult:
    """semanage fcontext -d <spec> — delete a file context mapping."""
    fcontext_spec: str = args["fcontext_spec"]
    result = run_subprocess(["semanage", "fcontext", "-d", fcontext_spec])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"File context mapping '{fcontext_spec}' deleted."
    else:
        summary = (
            f"Failed to delete file context mapping '{fcontext_spec}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_semanage_port_list(args: dict[str, Any]) -> ToolResult:
    """semanage port -l — list all port label mappings."""
    result = run_subprocess(["semanage", "port", "-l"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Port label mappings listed."
    else:
        summary = f"Failed to list port label mappings (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_semanage_port_add(args: dict[str, Any]) -> ToolResult:
    """semanage port -a -t <type> -p <proto> <port> — add a port label."""
    port_type: str = args["port_type"]
    protocol: str = args["protocol"]
    port: str = args["port"]
    result = run_subprocess(
        ["semanage", "port", "-a", "-t", port_type, "-p", protocol, port]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Port {port}/{protocol} labeled as '{port_type}'."
    else:
        summary = (
            f"Failed to add port label {port}/{protocol} as '{port_type}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_semanage_port_delete(args: dict[str, Any]) -> ToolResult:
    """semanage port -d -p <proto> <port> — delete a port label."""
    protocol: str = args["protocol"]
    port: str = args["port"]
    result = run_subprocess(["semanage", "port", "-d", "-p", protocol, port])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Port label for {port}/{protocol} deleted."
    else:
        summary = f"Failed to delete port label for {port}/{protocol} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_semanage_user_list(args: dict[str, Any]) -> ToolResult:
    """semanage user -l — list all SELinux user mappings."""
    result = run_subprocess(["semanage", "user", "-l"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "User mappings listed."
    else:
        summary = f"Failed to list user mappings (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_semanage_user_add(args: dict[str, Any]) -> ToolResult:
    """semanage user -a -R <roles> <seuser> — add a user mapping."""
    seuser: str = args["seuser"]
    roles: str = args["roles"]
    result = run_subprocess(["semanage", "user", "-a", "-R", roles, seuser])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"User '{seuser}' added with roles '{roles}'."
    else:
        summary = f"Failed to add user '{seuser}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_semanage_user_delete(args: dict[str, Any]) -> ToolResult:
    """semanage user -d <seuser> — delete a user mapping."""
    seuser: str = args["seuser"]
    result = run_subprocess(["semanage", "user", "-d", seuser])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"User mapping '{seuser}' deleted."
    else:
        summary = f"Failed to delete user mapping '{seuser}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_restorecon(args: dict[str, Any]) -> ToolResult:
    """restorecon -Rv <path> — restore default file contexts recursively."""
    path: str = args["path"]
    result = run_subprocess(["restorecon", "-Rv", path])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"File contexts restored on '{path}'."
    else:
        summary = f"Failed to restore contexts on '{path}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_chcon(args: dict[str, Any]) -> ToolResult:
    """chcon -t <type> <path> — change the type component of a file context."""
    context_type: str = args["context_type"]
    path: str = args["path"]
    result = run_subprocess(["chcon", "-t", context_type, path])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Context type on '{path}' set to '{context_type}'."
    else:
        summary = (
            f"Failed to change context on '{path}' to '{context_type}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_audit2allow(args: dict[str, Any]) -> ToolResult:
    """audit2allow -a — read audit log and generate policy suggestions."""
    result = run_subprocess(["audit2allow", "-a"], timeout=60)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Denial log analyzed; policy suggestions generated."
    else:
        summary = f"audit2allow completed with warnings (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "sestatus": _op_sestatus,
    "getsebool": _op_getsebool,
    "getenforce": _op_getenforce,
    "setenforce": _op_setenforce,
    "setsebool": _op_setsebool,
    "semanage_fcontext_list": _op_semanage_fcontext_list,
    "semanage_fcontext_add": _op_semanage_fcontext_add,
    "semanage_fcontext_delete": _op_semanage_fcontext_delete,
    "semanage_port_list": _op_semanage_port_list,
    "semanage_port_add": _op_semanage_port_add,
    "semanage_port_delete": _op_semanage_port_delete,
    "semanage_user_list": _op_semanage_user_list,
    "semanage_user_add": _op_semanage_user_add,
    "semanage_user_delete": _op_semanage_user_delete,
    "restorecon": _op_restorecon,
    "chcon": _op_chcon,
    "audit2allow": _op_audit2allow,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------


def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a selinux operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    the audit record (I3, I4). This function never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for selinux tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

SELINUX_SPEC = ToolSpec(
    name="selinux",
    description="Manage enforcement mode, booleans, file/port/user contexts, and policy analysis.",
    ops={
        "sestatus": OpSpec(
            op_name="sestatus",
            permission_class=OpClass.READ,
            args=[],
            description="Show overall enforcement status and policy type.",
        ),
        "getsebool": OpSpec(
            op_name="getsebool",
            permission_class=OpClass.READ,
            args=[_BOOLEAN_ARG],
            description="Show the current value of a policy boolean.",
        ),
        "getenforce": OpSpec(
            op_name="getenforce",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current enforcement mode (Enforcing/Permissive/Disabled).",
        ),
        "setenforce": OpSpec(
            op_name="setenforce",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="mode",
                    type=str,
                    required=True,
                    description="Enforcement mode: '1' for Enforcing, '0' for Permissive.",
                ),
            ],
            description=(
                "Set the enforcement mode at runtime. "
                "setenforce 0 (permissive) escalates to DESTRUCTIVE via the classifier."
            ),
        ),
        "setsebool": OpSpec(
            op_name="setsebool",
            permission_class=OpClass.WRITE,
            args=[
                _BOOLEAN_ARG,
                ArgSpec(
                    name="value",
                    type=str,
                    required=True,
                    description="Value to set: 'on' or 'off'.",
                ),
                ArgSpec(
                    name="persist",
                    type=bool,
                    required=False,
                    description="If true, pass -P to persist the change across reboots.",
                    default=False,
                ),
            ],
            description="Set a policy boolean, optionally persisting with -P.",
        ),
        "semanage_fcontext_list": OpSpec(
            op_name="semanage_fcontext_list",
            permission_class=OpClass.READ,
            args=[],
            description="List all file context mappings.",
        ),
        "semanage_fcontext_add": OpSpec(
            op_name="semanage_fcontext_add",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="fcontext_type",
                    type=str,
                    required=True,
                    description="The type to assign (e.g. 'httpd_sys_content_t').",
                ),
                ArgSpec(
                    name="fcontext_spec",
                    type=str,
                    required=True,
                    description="The file path specification (e.g. '/srv/www(/.*)?').",
                ),
            ],
            description="Add a file context mapping.",
        ),
        "semanage_fcontext_delete": OpSpec(
            op_name="semanage_fcontext_delete",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="fcontext_spec",
                    type=str,
                    required=True,
                    description="The file path specification to remove.",
                ),
            ],
            description=(
                "Delete a file context mapping. "
                "Removing a mapping can break file labeling for confined services."
            ),
        ),
        "semanage_port_list": OpSpec(
            op_name="semanage_port_list",
            permission_class=OpClass.READ,
            args=[],
            description="List all port label mappings.",
        ),
        "semanage_port_add": OpSpec(
            op_name="semanage_port_add",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="port_type",
                    type=str,
                    required=True,
                    description="The port type to assign (e.g. 'http_port_t').",
                ),
                ArgSpec(
                    name="protocol",
                    type=str,
                    required=True,
                    description="Protocol: 'tcp' or 'udp'.",
                ),
                ArgSpec(
                    name="port",
                    type=str,
                    required=True,
                    description="The port number (e.g. '8080').",
                ),
            ],
            description="Add a port label mapping.",
        ),
        "semanage_port_delete": OpSpec(
            op_name="semanage_port_delete",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="protocol",
                    type=str,
                    required=True,
                    description="Protocol: 'tcp' or 'udp'.",
                ),
                ArgSpec(
                    name="port",
                    type=str,
                    required=True,
                    description="The port number.",
                ),
            ],
            description=(
                "Delete a port label mapping. "
                "Removing a label can prevent confined services from binding the port."
            ),
        ),
        "semanage_user_list": OpSpec(
            op_name="semanage_user_list",
            permission_class=OpClass.READ,
            args=[],
            description="List all user mappings.",
        ),
        "semanage_user_add": OpSpec(
            op_name="semanage_user_add",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="seuser",
                    type=str,
                    required=True,
                    description="The user name to add.",
                ),
                ArgSpec(
                    name="roles",
                    type=str,
                    required=True,
                    description="Space-separated roles (e.g. 'staff_r sysadm_r').",
                ),
            ],
            description="Add a user mapping with associated roles.",
        ),
        "semanage_user_delete": OpSpec(
            op_name="semanage_user_delete",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="seuser",
                    type=str,
                    required=True,
                    description="The user name to delete.",
                ),
            ],
            description=(
                "Delete a user mapping. "
                "Removing a mapping can break confined user access."
            ),
        ),
        "restorecon": OpSpec(
            op_name="restorecon",
            permission_class=OpClass.WRITE,
            args=[_PATH_ARG],
            description="Restore default file contexts on a path (recursive with -Rv).",
        ),
        "chcon": OpSpec(
            op_name="chcon",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="context_type",
                    type=str,
                    required=True,
                    description="The type component to apply (e.g. 'httpd_sys_content_t').",
                ),
                _PATH_ARG,
            ],
            description="Change the type component of a file or directory context.",
        ),
        "audit2allow": OpSpec(
            op_name="audit2allow",
            permission_class=OpClass.READ,
            args=[],
            description="Read the audit log and generate policy suggestions from denial entries.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(SELINUX_SPEC)
