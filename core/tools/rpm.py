"""core/tools/rpm.py — RPM package query, verification, and installation via rpm/rpm2cpio.

Supported operations
--------------------
  query_info  (READ)  — show metadata for an installed package (rpm -qi).
  query_files (READ)  — list files owned by an installed package (rpm -ql).
  query_file  (READ)  — identify which package owns a given file path (rpm -qf).
  verify      (READ)  — verify integrity of installed package files (rpm -V / rpm -Va).
  checksig    (READ)  — verify the GPG/PGP signature of an RPM file (rpm --checksig).
  install     (WRITE) — install an RPM package file (rpm -ivh).
  rpm2cpio    (READ)  — extract the cpio payload of an RPM file (rpm2cpio).

Permission mapping (advisory; authoritative gate is permissions.classify()):
  READ  : query_info, query_files, query_file, verify, checksig, rpm2cpio
  WRITE : install

Note on removal
  rpm removal (rpm -e / --erase) is DELIBERATELY ABSENT.  Package removal is
  owned by the 'packages' tool (dnf remove) which already carries DESTRUCTIVE
  permission labeling.  Adding rpm -e here would create ambiguity in the gate.

Note on verify timeout
  rpm -Va audits every file in every installed package.  On a typical Rocky 9
  host this can take 30–120 seconds.  run_subprocess is called with timeout=180
  for the verify op to avoid a premature timeout.

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
# SELinux hint detection (copy VERBATIM from services.py)
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
# Shared ArgSpec constants
# ---------------------------------------------------------------------------

_PKG_ARG = ArgSpec(
    name="package",
    type=str,
    required=True,
    description="The installed package name (e.g. 'bash', 'openssl-libs').",
)

_FILE_ARG = ArgSpec(
    name="file",
    type=str,
    required=True,
    description="The absolute path to the file to query (e.g. '/usr/bin/bash').",
)

_RPM_FILE_ARG = ArgSpec(
    name="rpm_file",
    type=str,
    required=True,
    description="Path to the RPM package file (e.g. '/tmp/mypkg-1.0.x86_64.rpm').",
)


# ---------------------------------------------------------------------------
# Operation implementations
# ---------------------------------------------------------------------------

def _op_query_info(args: dict[str, Any]) -> ToolResult:
    """rpm -qi <package> — show package metadata."""
    package: str = args["package"]
    result = run_subprocess(["rpm", "-qi", package])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Package '{package}' metadata retrieved."
    else:
        summary = f"Package '{package}' not found or query failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_query_files(args: dict[str, Any]) -> ToolResult:
    """rpm -ql <package> — list files owned by the package."""
    package: str = args["package"]
    result = run_subprocess(["rpm", "-ql", package])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        file_count = result.stdout.count("\n")
        summary = f"Package '{package}' owns {file_count} file(s)."
    else:
        summary = f"Could not list files for package '{package}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_query_file(args: dict[str, Any]) -> ToolResult:
    """rpm -qf <file> — identify which package owns a file."""
    file: str = args["file"]
    result = run_subprocess(["rpm", "-qf", file])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        owner = result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unknown"
        summary = f"File '{file}' is owned by package '{owner}'."
    else:
        summary = f"File '{file}' is not owned by any installed package (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_verify(args: dict[str, Any]) -> ToolResult:
    """rpm -Va (all) or rpm -V <package> — verify package integrity.

    Uses a generous timeout because rpm -Va audits every file on the system
    and can take over a minute on a fully-loaded Rocky 9 host.
    """
    package: str = args.get("package", "")
    if package:
        cmd = ["rpm", "-V", package]
        target = f"package '{package}'"
    else:
        cmd = ["rpm", "-Va"]
        target = "all installed packages"
    result = run_subprocess(cmd, timeout=180)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Integrity verification of {target} passed; no discrepancies found."
    else:
        discrepancy_count = result.stdout.count("\n") if result.stdout else 0
        summary = (
            f"Integrity verification of {target} found {discrepancy_count} discrepancy(ies) "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_checksig(args: dict[str, Any]) -> ToolResult:
    """rpm --checksig <rpm_file> — verify the GPG signature of an RPM file."""
    rpm_file: str = args["rpm_file"]
    result = run_subprocess(["rpm", "--checksig", rpm_file])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Signature check for '{rpm_file}' passed."
    else:
        summary = f"Signature check for '{rpm_file}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_install(args: dict[str, Any]) -> ToolResult:
    """rpm -ivh <rpm_file> — install an RPM package file."""
    rpm_file: str = args["rpm_file"]
    result = run_subprocess(["rpm", "-ivh", rpm_file])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Package file '{rpm_file}' installed successfully."
    else:
        summary = f"Installation of '{rpm_file}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_rpm2cpio(args: dict[str, Any]) -> ToolResult:
    """rpm2cpio <rpm_file> — extract the cpio archive payload of an RPM file."""
    rpm_file: str = args["rpm_file"]
    result = run_subprocess(["rpm2cpio", rpm_file])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Extracted cpio payload from '{rpm_file}'."
    else:
        summary = f"Failed to extract cpio payload from '{rpm_file}' (exit {result.exit_code})."
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
    "query_info":   _op_query_info,
    "query_files":  _op_query_files,
    "query_file":   _op_query_file,
    "verify":       _op_verify,
    "checksig":     _op_checksig,
    "install":      _op_install,
    "rpm2cpio":     _op_rpm2cpio,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an rpm operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function NEVER raises (I9): unknown ops and all subprocess failures
    degrade to a well-formed ToolResult with a non-zero exit code.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for rpm tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

RPM_SPEC = ToolSpec(
    name="rpm",
    description="Query, verify, and install RPM packages via rpm and rpm2cpio.",
    ops={
        "query_info": OpSpec(
            op_name="query_info",
            permission_class=OpClass.READ,
            args=[_PKG_ARG],
            description="Show metadata for an installed package (rpm -qi).",
        ),
        "query_files": OpSpec(
            op_name="query_files",
            permission_class=OpClass.READ,
            args=[_PKG_ARG],
            description="List files owned by an installed package (rpm -ql).",
        ),
        "query_file": OpSpec(
            op_name="query_file",
            permission_class=OpClass.READ,
            args=[_FILE_ARG],
            description="Identify which installed package owns a given file path (rpm -qf).",
        ),
        "verify": OpSpec(
            op_name="verify",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="package",
                    type=str,
                    required=False,
                    description=(
                        "Package name to verify. Omit to verify all installed packages "
                        "(rpm -Va); warning: can be slow."
                    ),
                    default="",
                ),
            ],
            description=(
                "Verify integrity of installed package files against the RPM database "
                "(rpm -V <pkg> or rpm -Va for all packages)."
            ),
        ),
        "checksig": OpSpec(
            op_name="checksig",
            permission_class=OpClass.READ,
            args=[_RPM_FILE_ARG],
            description="Verify the GPG/PGP signature of an RPM file (rpm --checksig).",
        ),
        "install": OpSpec(
            op_name="install",
            permission_class=OpClass.WRITE,
            args=[_RPM_FILE_ARG],
            description="Install an RPM package file directly via rpm -ivh.",
        ),
        "rpm2cpio": OpSpec(
            op_name="rpm2cpio",
            permission_class=OpClass.READ,
            args=[_RPM_FILE_ARG],
            description="Extract the cpio archive payload from an RPM file (rpm2cpio).",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(RPM_SPEC)
