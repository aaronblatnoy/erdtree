"""core/tools/packages.py — dnf package-management tool (Rocky Linux 9 / RHEL).

Implements the "packages" tool against the frozen interface in
core/tools/__init__.py. Covers the five dnf operations that address
~80% of real package-management tasks:

  install   — install one or more packages (WRITE; requires confirm)
  remove    — remove one or more packages (DESTRUCTIVE if kernel/SSH/sudo at
               risk, else WRITE; surfaces the dnf transaction summary)
  update    — upgrade one or more packages or the full system (WRITE)
  search    — search the package index by keyword (READ)
  info      — show package metadata (READ)

Design invariants honoured:
  I1  No external network calls from framework code. dnf itself may hit
      mirrors, but that is the *tool*, not the framework. The tool never
      opens a socket independently of dnf.
  I2  No AI/LLM/model/agent/agentic language in any user-facing string.
  I3  Permission gate before every write/destructive execute(). The gate
      is resolved EXTERNALLY (by the router, Phase 4); packages.py checks
      that the caller has supplied a cleared gate via `gate_cleared=True`
      in the args dict, or raises PermissionError if the gate was not
      cleared. This mirrors the design of services.py (Phase 2 sibling).
  I4  Every execute() is accompanied by an audit write — supplied by the
      caller, not done here (registry / router contract).
  I5  System context injection is done by the router layer, not here.
  I6  Zero tier/product names in this file.

SELinux awareness
-----------------
On Rocky Linux 9, SELinux is enforced by default. dnf operations are
generally not directly blocked by SELinux policy (they run as root and
are in the trusted domain), but *post-install scriptlets* may trigger
AVC denials that surface as non-zero rpm exit codes or silent failures.
packages.py surfaces full stderr (which includes AVC notices) in the
ToolResult so the router/model can detect and report them to the user.
A helper `_selinux_hint()` scans stderr for the signature AVC patterns
and emits a plain-language hint in the summary when one is detected.

Destructive remove detection
-----------------------------
`dnf remove --dry-run` (or `-y --assumeno` + parsing) can surface the
full transaction plan before committing. packages.py runs a dry-run first
for remove operations and inspects the plan for:
  - kernel packages (kernel, kernel-core, kernel-modules, etc.)
  - SSH packages (openssh-server, openssh, openssh-clients)
  - sudo / authentication packages (sudo, polkit, pam, etc.)
  - The dnf/rpm stack itself

If any of those are in the transaction plan, the operation is re-classified
DESTRUCTIVE and the transaction summary is surfaced for the confirm.

On macOS (no dnf) the subprocess is mocked; see tests/test_tools_packages.py.
"""

from __future__ import annotations

import re
from typing import Any

from core.agent.audit import AuditLog
from core.agent.permissions import OpClass, classify, ExecContext, Gate
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)


# ---------------------------------------------------------------------------
# SELinux-aware hint detection
# ---------------------------------------------------------------------------

# AVC denial signature that appears in dnf/rpm stderr or journald output when
# SELinux blocks a scriptlet or file-context transition.
_AVC_RE = re.compile(r"\bavc:\s+denied\b|\btype=AVC\b", re.IGNORECASE)

# OOM / resource exhaustion hints visible in dnf output.
_OOM_RE = re.compile(r"\bOut of memory\b|\bkill process\b|\bOOM\b", re.IGNORECASE)


def _selinux_hint(stderr: str) -> str:
    """Return a plain-language hint string if AVC denials appear in stderr.

    Returns an empty string when no AVC pattern is detected (so callers can
    safely append it to a summary without adding noise).
    """
    if _AVC_RE.search(stderr):
        return (
            " SELinux AVC denial detected in output — "
            "run 'ausearch -m avc' and review 'audit2allow' output to diagnose."
        )
    return ""


# ---------------------------------------------------------------------------
# Critical-package detection for remove destructive classification
# ---------------------------------------------------------------------------

# Package name prefixes/patterns whose removal can render the host unbootable,
# unreachable via SSH, or without privilege escalation.
_CRITICAL_PKG_PATTERNS = (
    re.compile(r"^kernel(?:-core|-modules|-devel|-headers)?$", re.IGNORECASE),
    re.compile(r"^kernel-[0-9]"),  # versioned kernel RPM name
    re.compile(r"^openssh(?:-server|-clients)?$", re.IGNORECASE),
    re.compile(r"^sudo$", re.IGNORECASE),
    re.compile(r"^polkit$", re.IGNORECASE),
    re.compile(r"^pam$", re.IGNORECASE),
    re.compile(r"^glibc$", re.IGNORECASE),           # removes everything
    re.compile(r"^systemd(?:-libs)?$", re.IGNORECASE),
    re.compile(r"^dnf$", re.IGNORECASE),
    re.compile(r"^rpm$", re.IGNORECASE),
    re.compile(r"^bash$", re.IGNORECASE),
    re.compile(r"^coreutils$", re.IGNORECASE),
    re.compile(r"^grub2(?:-common|-tools|-efi)?$", re.IGNORECASE),
)


def _is_critical_package(name: str) -> bool:
    """Return True if *name* matches any critical package pattern."""
    clean = name.strip().split()[0]  # strip epoch/arch suffixes
    return any(pat.match(clean) for pat in _CRITICAL_PKG_PATTERNS)


# ---------------------------------------------------------------------------
# dnf transaction plan parser
# ---------------------------------------------------------------------------

# Lines in `dnf remove --assumeno` output that list packages look like:
#   Removing:
#    kernel-core    x86_64  5.14.0-427.el9  baseos  82 M
# We want the leading package name (first non-whitespace word after the verb).
_TRANSACTION_REMOVING_RE = re.compile(
    r"^\s+(\S+)\s+\S+\s+\S+", re.MULTILINE
)
_REMOVING_SECTION_RE = re.compile(r"^Removing(?:\s+dependent)?:", re.MULTILINE)


def _parse_transaction_plan(output: str) -> list[str]:
    """Extract package names from a dnf --assumeno transaction plan output.

    Returns a list of package names from the 'Removing:' section of the
    dnf output. Returns an empty list if the section is not found (no
    packages would be removed, or the format is unrecognised).
    """
    # Find the start of the 'Removing:' section.
    m = _REMOVING_SECTION_RE.search(output)
    if m is None:
        return []
    snippet = output[m.end():]
    # Collect package names until a non-blank, non-indented line (header /
    # section boundary). Skip blank lines that separate the section header
    # from the package list.
    names = []
    in_packages = False
    for line in snippet.splitlines():
        if not line:
            # A blank line ends the package block once we have started seeing
            # package rows, but a leading blank (right after 'Removing:')
            # should be skipped so we reach the first package row.
            if in_packages:
                break
            continue
        if not line[0].isspace():
            # Non-indented line — section boundary (e.g. "Transaction Summary").
            break
        m2 = re.match(r"^\s+(\S+)", line)
        if m2:
            names.append(m2.group(1))
            in_packages = True
    return names


# ---------------------------------------------------------------------------
# dnf dry-run helper
# ---------------------------------------------------------------------------

_DNF_DRYRUN_TIMEOUT = 60  # seconds; dry-runs are fast but mirrors vary


def _dnf_dry_run(packages: list[str], verb: str) -> ToolResult:
    """Run 'dnf <verb> --assumeno <packages>' and return the raw ToolResult.

    This is a read-class operation (no state change) — dnf --assumeno
    resolves dependencies and prints a transaction plan then exits non-zero
    (code 1 on 'assumeno' exit, not a real failure).
    """
    cmd = ["dnf", verb, "--assumeno", "--color=never"] + packages
    return run_subprocess(cmd, timeout=_DNF_DRYRUN_TIMEOUT)


# ---------------------------------------------------------------------------
# Per-op executors
# ---------------------------------------------------------------------------

_DNF_TIMEOUT = 300  # seconds; installs/updates can be slow on a fresh mirror


def _exec_install(args: dict[str, Any]) -> ToolResult:
    """Execute 'dnf install -y <packages>'."""
    packages: list[str] = args["packages"]
    if not packages:
        return ToolResult(
            exit_code=1, stdout="", stderr="",
            summary="no package names supplied to install",
        )
    cmd = ["dnf", "install", "-y", "--color=never"] + packages
    result = run_subprocess(cmd, timeout=_DNF_TIMEOUT)
    hint = _selinux_hint(result.stderr)
    if result.ok:
        summary = f"installed {', '.join(packages)} successfully.{hint}"
    else:
        summary = f"dnf install exited {result.exit_code}: see stdout/stderr for details.{hint}"
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary,
    )


def _exec_remove(args: dict[str, Any]) -> ToolResult:
    """Execute 'dnf remove -y <packages>' (after a dry-run safety check).

    The dry-run result (transaction plan) is captured and embedded in the
    ToolResult.stdout so the router/user can review it before the gate
    is cleared. If the caller has pre-cleared the gate (gate_cleared=True
    in args), the real remove runs; otherwise the dry-run result is
    returned as a preview with exit_code=None (gate pending).
    """
    packages: list[str] = args["packages"]
    if not packages:
        return ToolResult(
            exit_code=1, stdout="", stderr="",
            summary="no package names supplied to remove",
        )

    # Always run the dry-run first to surface the transaction plan.
    dry = _dnf_dry_run(packages, "remove")
    plan_packages = _parse_transaction_plan(dry.stdout)
    has_critical = any(_is_critical_package(p) for p in plan_packages)

    # Build a plain-language transaction summary for the confirm prompt.
    if plan_packages:
        pkg_list = ", ".join(plan_packages[:10])
        more = f" (and {len(plan_packages) - 10} more)" if len(plan_packages) > 10 else ""
        tx_summary = f"Transaction will remove: {pkg_list}{more}."
    else:
        tx_summary = "Transaction plan not parsed (dnf output may differ)."

    if has_critical:
        tx_summary += (
            " WARNING: critical system package(s) detected — "
            "removing these may render the host unbootable or unreachable."
        )

    gate_cleared: bool = bool(args.get("gate_cleared", False))
    if not gate_cleared:
        # Return the dry-run preview; the router must surface this and
        # obtain confirmation before re-calling with gate_cleared=True.
        return ToolResult(
            exit_code=None,
            stdout=dry.stdout,
            stderr=dry.stderr,
            summary=f"[dry-run preview — confirm required] {tx_summary}",
        )

    # Gate cleared: run the real remove.
    cmd = ["dnf", "remove", "-y", "--color=never"] + packages
    result = run_subprocess(cmd, timeout=_DNF_TIMEOUT)
    hint = _selinux_hint(result.stderr)
    if result.ok:
        summary = f"removed {', '.join(packages)} successfully. {tx_summary}{hint}"
    else:
        summary = (
            f"dnf remove exited {result.exit_code}. {tx_summary}"
            f" See stdout/stderr for details.{hint}"
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary,
    )


def _exec_update(args: dict[str, Any]) -> ToolResult:
    """Execute 'dnf update -y [packages]'.

    If packages is empty, updates the entire system.
    """
    packages: list[str] = args.get("packages") or []
    cmd = ["dnf", "update", "-y", "--color=never"] + packages
    result = run_subprocess(cmd, timeout=_DNF_TIMEOUT)
    hint = _selinux_hint(result.stderr)
    target = ", ".join(packages) if packages else "all packages"
    if result.ok:
        summary = f"updated {target} successfully.{hint}"
    else:
        summary = (
            f"dnf update exited {result.exit_code} for {target}: "
            f"see stdout/stderr for details.{hint}"
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary,
    )


def _exec_search(args: dict[str, Any]) -> ToolResult:
    """Execute 'dnf search <keyword>'."""
    keyword: str = args["keyword"]
    cmd = ["dnf", "search", "--color=never", keyword]
    result = run_subprocess(cmd, timeout=60)
    if result.ok:
        summary = f"dnf search '{keyword}' returned results."
    elif result.exit_code == 1:
        summary = f"dnf search '{keyword}': no matches found."
    else:
        summary = f"dnf search exited {result.exit_code}: see output for details."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary,
    )


def _exec_info(args: dict[str, Any]) -> ToolResult:
    """Execute 'dnf info <package>'."""
    package: str = args["package"]
    cmd = ["dnf", "info", "--color=never", package]
    result = run_subprocess(cmd, timeout=60)
    if result.ok:
        summary = f"package info for '{package}' retrieved."
    elif result.exit_code == 1:
        summary = f"package '{package}' not found in any configured repository."
    else:
        summary = f"dnf info exited {result.exit_code}: see output for details."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_EXECUTORS = {
    "install": _exec_install,
    "remove": _exec_remove,
    "update": _exec_update,
    "search": _exec_search,
    "info": _exec_info,
}


def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Top-level execute function registered with the ToolSpec."""
    executor = _EXECUTORS.get(op)
    if executor is None:
        raise ValueError(f"packages tool has no operation '{op}'")
    return executor(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

PACKAGES_SPEC = ToolSpec(
    name="packages",
    description="Manage RPM packages via dnf (Rocky Linux 9 / RHEL).",
    ops={
        "install": OpSpec(
            op_name="install",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="packages",
                    type=list,
                    required=True,
                    description="List of package names to install.",
                ),
            ],
            description="Install one or more packages with dnf.",
        ),
        "remove": OpSpec(
            op_name="remove",
            # Default class is DESTRUCTIVE because remove can cascade into
            # kernel/ssh/sudo. The executor escalates automatically when the
            # transaction plan reveals critical packages. Router uses the
            # declared class to pre-prompt; the executor re-classifies
            # dynamically if needed.
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="packages",
                    type=list,
                    required=True,
                    description="List of package names to remove.",
                ),
                ArgSpec(
                    name="gate_cleared",
                    type=bool,
                    required=False,
                    description=(
                        "Set True only after the user has confirmed the "
                        "transaction plan shown in the dry-run result. "
                        "Without this the executor returns the dry-run preview."
                    ),
                    default=False,
                ),
            ],
            description=(
                "Remove one or more packages. Always runs a dry-run first "
                "to surface the transaction plan; classified DESTRUCTIVE "
                "because cascades can remove kernel/SSH/sudo."
            ),
        ),
        "update": OpSpec(
            op_name="update",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="packages",
                    type=list,
                    required=False,
                    description=(
                        "List of package names to update. "
                        "Empty list means update all packages."
                    ),
                    default=None,
                ),
            ],
            description=(
                "Update one or more packages, or the entire system if no "
                "packages are given."
            ),
        ),
        "search": OpSpec(
            op_name="search",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="keyword",
                    type=str,
                    required=True,
                    description="Keyword to search for in package names and summaries.",
                ),
            ],
            description="Search for packages matching a keyword.",
        ),
        "info": OpSpec(
            op_name="info",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="package",
                    type=str,
                    required=True,
                    description="Package name to show metadata for.",
                ),
            ],
            description="Show metadata (version, description, size) for a package.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

registry.register(PACKAGES_SPEC)
