"""finetune/simulate/sosreport.py — Rocky Linux 9 output simulator for 'sosreport'.

Public API
----------
simulate_sosreport(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the real operations declared in core/tools/sosreport.py
           ('generate', 'info')
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string from make_context(), OR a profile dict.

Realism model
-------------
* 'sos report' output mirrors Rocky Linux 9's sos-4.x output: plugin load
  progress, a final archive path under /var/tmp, and an md5 checksum file.
* 'sos info' output mirrors the plugin table produced by 'sos info'.
* Failure branches (exit 127 / permission denied) are deterministic via a
  hash-based scatter so traces teach error handling.

I2 compliance
-------------
All 'summary' strings are I2-clean; no AI/LLM/agent/model language anywhere.

INV-read-only-core: imports NOTHING from core/ and nothing from finetune.coreimports.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx (dict or snapshot-text string)."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


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


def _should_fail(seed: str) -> bool:
    """Hash-based deterministic ~12% failure scatter."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return h % 17 == 0


def _sos_not_installed(ctx: Any) -> bool:
    """Return True if context hints that sos is not installed."""
    if isinstance(ctx, dict):
        missing = ctx.get("missing_binaries", [])
        return "sos" in missing
    if isinstance(ctx, str):
        return "sos: command not found" in ctx
    return False


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_generate(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate 'sos report --batch [--label <l>] [--output-dir <d>]'."""
    label: str = args.get("label") or ""
    output_dir: str = args.get("output_dir") or "/var/tmp"
    host = _hostname(ctx)

    if _sos_not_installed(ctx):
        stderr = "bash: sos: command not found\n"
        return _make_result(
            exit_code=127,
            stdout="",
            stderr=stderr,
            summary="sos is not installed; the diagnostics collection utility was not found.",
        )

    if _should_fail(host + label + "generate"):
        stderr = (
            "Please run this as root.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="sos report failed; elevated privileges are required to collect diagnostics.",
        )

    label_suffix = f"-{label}" if label else ""
    archive_name = f"sosreport-{host}{label_suffix}-2026-07-04-abcdef1.tar.xz"
    archive_path = f"{output_dir.rstrip('/')}/{archive_name}"
    md5_path = f"{archive_path}.md5"

    stdout = (
        "sosreport (version 4.6.1)\n"
        "\n"
        "This command will collect diagnostic and configuration information from\n"
        "this Rocky Linux system and installed applications.\n"
        "\n"
        "An archive containing the collected information will be generated in\n"
        f" {output_dir}\n"
        "\n"
        "Setting up archive ...\n"
        "Setting up plugins ...\n"
        " Running 152 plugins\n"
        "\n"
        "  Running plugins. Please wait ...\n"
        "\n"
        "    Finishing plugins              [Running: kernel memory rpm uname]\n"
        "    Finished running plugins\n"
        "\n"
        "Creating compressed archive...\n"
        "\n"
        "Your sosreport has been generated and saved in:\n"
        f"\t{archive_path}\n"
        "\n"
        f"Size\t{archive_path}\t38.7MiB\n"
        "\n"
        "The checksum is: d41d8cd98f00b204e9800998ecf8427e\n"
        "\n"
        f"Please send this file to your support representative.\n"
    )

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Diagnostics archive generated: {archive_path}.",
    )


def _sim_info(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate 'sos info [<plugin>]'."""
    plugin: str = args.get("plugin") or ""
    host = _hostname(ctx)

    if _sos_not_installed(ctx):
        stderr = "bash: sos: command not found\n"
        return _make_result(
            exit_code=127,
            stdout="",
            stderr=stderr,
            summary="sos is not installed; the diagnostics collection utility was not found.",
        )

    if plugin:
        # Check for a plausible plugin name
        known_plugins = {
            "kernel", "memory", "rpm", "uname", "networking", "hardware",
            "block", "filesys", "logs", "process", "boot", "systemd",
            "selinux", "auditd", "cgroups", "container", "podman",
            "dnf", "yum", "subscription", "pacemaker", "iscsi",
        }
        if plugin.lower() not in known_plugins:
            stderr = f"No plugin named '{plugin}' found.\n"
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=stderr,
                summary=f"Failed to retrieve info for plugin '{plugin}' (exit 1).",
            )

        stdout = (
            f"Plugin: {plugin}\n"
            f"  Version    : 1.0\n"
            f"  Description: Collects {plugin}-related diagnostics\n"
            f"  Status     : enabled\n"
            f"  Options    :\n"
            f"    all   : Collect all available {plugin} data [off]\n"
            f"    log   : Include recent log output [on]\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Plugin information for '{plugin}' retrieved.",
        )

    # Full plugin listing
    stdout = (
        "The following plugins are currently enabled:\n"
        "\n"
        " Plugin      | Description\n"
        "-------------|-----------------------------------------------------------\n"
        " auditd      | Audit subsystem data\n"
        " block       | Block device and filesystem information\n"
        " boot        | Boot loader and initrd configuration\n"
        " cgroups     | Control group hierarchy and resource limits\n"
        " container   | Container runtime and image data\n"
        " dnf         | Package manager logs and configuration\n"
        " filesys     | Filesystem metadata and mount information\n"
        " hardware    | Hardware inventory (lspci, lsusb, dmidecode)\n"
        " iscsi       | iSCSI initiator and target configuration\n"
        " kernel      | Kernel parameters, modules, and ring buffer\n"
        " logs        | System log files (journalctl, /var/log)\n"
        " memory      | Memory statistics and NUMA topology\n"
        " networking  | Network interface, routing, and firewall data\n"
        " pacemaker   | High-availability cluster state\n"
        " podman      | Podman container runtime information\n"
        " process     | Running processes and resource consumption\n"
        " rpm         | Installed RPM package database\n"
        " selinux     | SELinux policy and enforcement state\n"
        " subscription| RHSM subscription and repository data\n"
        " systemd     | Systemd units, journals, and configuration\n"
        " uname       | Kernel version and machine identity\n"
        " yum         | Legacy yum configuration (compat)\n"
        "\n"
        "The following plugins are currently disabled:\n"
        "\n"
        " Plugin      | Reason\n"
        "-------------|-----------------------------------------------------------\n"
        " openshift   | openshift binary not found\n"
        " kubernetes  | kubectl binary not found\n"
    )
    line_count = stdout.count("\n")
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"sos plugin listing retrieved ({line_count} lines).",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "generate": _sim_generate,
    "info": _sim_info,
}


def simulate_sosreport(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'sosreport' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the real ops in the sosreport ToolSpec.
    args : argument dict (may be sparse; defaults applied per-op).
    ctx  : system context — snapshot_text str or a profile dict.

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
            f"simulate_sosreport: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
