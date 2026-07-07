"""finetune/simulate/dnf_modules.py — Rocky Linux 9 output simulator for the 'dnf_modules' tool.

Public API
----------
simulate_dnf_modules(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/dnf_modules.py
    args : dict of op arguments (may be {} for all-optional ops)
    ctx  : system context string from make_context(), OR a profile dict.

Realism model
-------------
* Exit codes mirror real 'dnf module' behaviour on Rocky Linux 9:
    0  — success
    1  — operation failed (module not found, conflict, permission error)
* stdout reflects real dnf module output tables and info blocks.
* Failure branches are deterministic: a module name containing "notfound",
  "missing", "broken", or "bogus" returns a not-found error; a hash-based
  ~15% scatter adds variety.

I2 compliance
-------------
All `summary` strings are I2-clean.  No forbidden terms (AI, LLM, model,
agent, agentic, neural, language model) appear in any summary.

INV-read-only-core: this module imports NOTHING from core/ directly.
No import of finetune.coreimports either (avoids circular deps).
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _module_not_found(module: str) -> bool:
    """Deterministically decide if a module name should trigger a not-found error."""
    lower = module.lower()
    for tok in ("notfound", "missing", "broken", "bogus", "noexist", "fail"):
        if tok in lower:
            return True
    # Hash-based deterministic scatter (~15%)
    h = int(hashlib.md5(module.encode()).hexdigest(), 16)
    return h % 20 == 0


def _module_is_enabled(module: str, ctx: Any) -> bool:
    """Return True if the module appears enabled in the context."""
    base = module.split(":")[0]
    if isinstance(ctx, dict):
        enabled: list[str] = ctx.get("enabled_modules", [])
        return base in enabled or any(base in m for m in enabled)
    if isinstance(ctx, str):
        return base in ctx
    return False


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

# Example of a realistic dnf module list table header
_LIST_HEADER = (
    "Rocky Linux 9 - AppStream\n"
    "Name             Stream         Profiles                    Summary\n"
)

_KNOWN_MODULES = [
    ("nodejs",          "18 [e][d]",   "common [d], development, minimal, s2i",
     "Javascript runtime"),
    ("nodejs",          "20",          "common [d], development, minimal, s2i",
     "Javascript runtime"),
    ("postgresql",      "15 [e][d]",   "client, server [d]",
     "PostgreSQL server and client module"),
    ("postgresql",      "16",          "client, server [d]",
     "PostgreSQL server and client module"),
    ("php",             "8.1 [e][d]",  "common [d], devel, minimal",
     "PHP scripting language"),
    ("php",             "8.2",         "common [d], devel, minimal",
     "PHP scripting language"),
    ("nginx",           "mainline",    "common [d]",
     "nginx webserver"),
    ("ruby",            "3.1 [e][d]",  "default [d]",
     "An interpreter of object-oriented scripting language"),
    ("ruby",            "3.3",         "default [d]",
     "An interpreter of object-oriented scripting language"),
    ("mariadb",         "10.11 [e][d]","client, galera, server [d]",
     "MariaDB Module"),
    ("container-tools", "rhel8 [e][d]","common [d]",
     "Most recent (rolling) versions of podman, buildah, skopeo, runc"),
    ("python39",        "3.9 [d]",     "build, default [d]",
     "Python programming language, version 3.9"),
]


def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module_filter: str = args.get("module") or ""
    base_filter = module_filter.split(":")[0].lower() if module_filter else ""

    if module_filter and _module_not_found(module_filter):
        stderr = (
            f"Error: No matching Modules to list\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"No modules found matching '{module_filter}'.",
        )

    rows = _KNOWN_MODULES
    if base_filter:
        rows = [(n, s, p, d) for n, s, p, d in rows if base_filter in n.lower()]
        if not rows:
            stderr = "Error: No matching Modules to list\n"
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=stderr,
                summary=f"No modules found matching '{module_filter}'.",
            )

    lines = [_LIST_HEADER]
    for name, stream, profiles, summary_text in rows:
        lines.append(f"{name:<16} {stream:<14} {profiles:<27} {summary_text}")
    lines.append("\nHint: [d]efault, [e]nabled, [x]disabled, [i]nstalled\n")
    stdout = "\n".join(lines) + "\n"

    suffix = f" for '{module_filter}'" if module_filter else ""
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Module listing retrieved{suffix}.",
    )


def _sim_info(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module: str = args.get("module", "nodejs")
    base = module.split(":")[0]
    stream = module.split(":")[1] if ":" in module else "18"

    if _module_not_found(module):
        stderr = f"Error: No matching Modules to show\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"No module info found for '{module}'.",
        )

    stdout = (
        f"Name             : {base}\n"
        f"Stream           : {stream}\n"
        f"Version          : 9020230203155141\n"
        f"Context          : 9edba152\n"
        f"Architecture     : x86_64\n"
        f"Profiles         : common [d], development, minimal\n"
        f"Default profiles : common\n"
        f"Repo             : appstream\n"
        f"Summary          : {base.capitalize()} module stream {stream}\n"
        f"Description      : Provides {base} packages for Rocky Linux 9.\n"
        f"Artifacts        : {base}-{stream}.0.0-1.module+el9.x86_64\n"
        f"\nHint: [d]efault, [e]nabled, [x]disabled, [i]nstalled\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Module info retrieved for '{module}'.",
    )


def _sim_enable(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module: str = args.get("module", "nodejs:18")
    base = module.split(":")[0]
    stream = module.split(":")[1] if ":" in module else ""

    if _module_not_found(module):
        stderr = (
            f"Error: Problems in request:\n"
            f"missing and available module streams: {module}\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to enable module stream '{module}' — not found.",
        )

    # Hash-based conflict scatter (~10%)
    h = int(hashlib.md5((module + "enable").encode()).hexdigest(), 16)
    if h % 10 == 0:
        stream_label = f":{stream}" if stream else ""
        stderr = (
            f"Error: It is not possible to switch enabled streams of a module.\n"
            f"It is recommended to remove all installed content from the module, "
            f"and reset the module using 'dnf module reset {base}' command. "
            f"After you reset the module, you can enable the {base}{stream_label} stream.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Cannot enable '{module}': another stream is already enabled. "
                f"Reset the module first with 'dnf module reset {base}'."
            ),
        )

    stdout = (
        f"Dependencies resolved.\n"
        f"Nothing to do.\n"
        f"Complete!\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Module stream '{module}' enabled.",
    )


def _sim_disable(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module: str = args.get("module", "nodejs")
    base = module.split(":")[0]

    if _module_not_found(module):
        stderr = (
            f"Error: Problems in request:\n"
            f"missing and available module streams: {module}\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to disable module stream '{module}' — not found.",
        )

    stdout = (
        f"Dependencies resolved.\n"
        f"Nothing to do.\n"
        f"Complete!\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Module stream '{module}' disabled.",
    )


def _sim_install(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module: str = args.get("module", "nodejs:18")
    base = module.split(":")[0]
    stream = module.split(":")[1].split("/")[0] if ":" in module else ""
    profile = module.split("/")[1] if "/" in module else "default"

    if _module_not_found(module):
        stderr = (
            f"Error: Problems in request:\n"
            f"missing and available module streams: {module}\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to install module '{module}' — not found.",
        )

    # Hash-based dependency conflict scatter (~8%)
    h = int(hashlib.md5((module + "install").encode()).hexdigest(), 16)
    if h % 12 == 0:
        stderr = (
            f"Error: Transaction test error:\n"
            f" installing package {base}-1.0.0-1.el9.x86_64 needs {base}-libs = 1.0.0, "
            f"this is provided by {base}-libs-0.9.0-1.el9.x86_64\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to install module '{module}' due to a dependency conflict (exit 1).",
        )

    pkg_version = "18.20.0" if "18" in module else "20.10.0" if "20" in module else "1.0.0"
    stdout = (
        f"Dependencies resolved.\n"
        f"================================================================================\n"
        f" Package                  Architecture  Version            Repository     Size\n"
        f"================================================================================\n"
        f"Installing group/module packages:\n"
        f" {base}                   x86_64        {pkg_version}-1.el9   @appstream     12 M\n"
        f"\n"
        f"Transaction Summary\n"
        f"================================================================================\n"
        f"Install  1 Package\n"
        f"\n"
        f"Total download size: 12 M\n"
        f"Installed size: 38 M\n"
        f"Downloading Packages:\n"
        f"Running transaction check\n"
        f"Transaction check succeeded.\n"
        f"Running transaction test\n"
        f"Transaction test succeeded.\n"
        f"Running transaction\n"
        f"  Installing  : {base}-{pkg_version}-1.el9.x86_64                         1/1\n"
        f"  Verifying   : {base}-{pkg_version}-1.el9.x86_64                         1/1\n"
        f"Installed products updated.\n"
        f"\n"
        f"Installed:\n"
        f"  {base}-{pkg_version}-1.el9.x86_64\n"
        f"\n"
        f"Complete!\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Module '{module}' installed.",
    )


def _sim_reset(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    module: str = args.get("module", "nodejs")
    base = module.split(":")[0]

    if _module_not_found(module):
        stderr = (
            f"Error: Problems in request:\n"
            f"missing and available module streams: {module}\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to reset module '{module}' — not found.",
        )

    stdout = (
        f"Dependencies resolved.\n"
        f"Nothing to do.\n"
        f"Complete!\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Module '{module}' reset to default state.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list":    _sim_list,
    "info":    _sim_info,
    "enable":  _sim_enable,
    "disable": _sim_disable,
    "install": _sim_install,
    "reset":   _sim_reset,
}


def simulate_dnf_modules(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'dnf_modules' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in the
           dnf_modules ToolSpec (list, info, enable, disable, install, reset).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_dnf_modules: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
