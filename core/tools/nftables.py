"""core/tools/nftables.py — raw nftables ruleset management via the nft binary.

Supported operations
--------------------
  list_ruleset  (READ)        — dump the full nft ruleset.
  add_rule      (WRITE)       — add a rule to a chain in a table.
  delete_rule   (WRITE)       — delete a rule by handle from a chain.
  flush_ruleset (DESTRUCTIVE) — remove every rule, chain, and table from the
                                live ruleset (lockout risk on default-drop hosts).

Overlap note (OVERLAP-MAP §Phase 4 C)
--------------------------------------
  The existing 'firewall' tool manages firewalld zones/services via
  firewall-cmd.  On Rocky Linux 9 firewalld sits on top of nftables — editing
  the raw nft ruleset (this tool) can conflict with firewalld's managed chains.
  Keep these tools separate; nftables operates on raw nft objects and does NOT
  manage firewalld zones.  If firewalld is active, use the 'firewall' tool for
  zone/service management.

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
# SELinux hint detection (copied verbatim from services.py)
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
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list_ruleset(args: dict[str, Any]) -> ToolResult:
    """nft list ruleset — dump the full kernel nft ruleset."""
    result = run_subprocess(["nft", "list", "ruleset"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        table_count = result.stdout.count("table ")
        summary = (
            f"nftables ruleset listed ({table_count} table(s) found)."
        )
    else:
        summary = (
            f"Failed to list nftables ruleset (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_add_rule(args: dict[str, Any]) -> ToolResult:
    """nft add rule [family] table chain <rule-expr> — insert a new rule."""
    family: str = args.get("family", "inet") or "inet"
    table: str = args["table"]
    chain: str = args["chain"]
    rule: str = args["rule"]
    # Build argv: nft add rule <family> <table> <chain> <tokens...>
    rule_tokens = rule.split()
    cmd = ["nft", "add", "rule", family, table, chain] + rule_tokens
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Rule added to chain '{chain}' in table '{family} {table}'."
        )
    else:
        summary = (
            f"Failed to add rule to chain '{chain}' in table '{family} {table}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_delete_rule(args: dict[str, Any]) -> ToolResult:
    """nft delete rule [family] table chain handle <handle> — remove a rule by handle."""
    family: str = args.get("family", "inet") or "inet"
    table: str = args["table"]
    chain: str = args["chain"]
    handle: str = args["handle"]
    cmd = ["nft", "delete", "rule", family, table, chain, "handle", handle]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Rule handle {handle} deleted from chain '{chain}' in table "
            f"'{family} {table}'."
        )
    else:
        summary = (
            f"Failed to delete rule handle {handle} from chain '{chain}' in table "
            f"'{family} {table}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_flush_ruleset(args: dict[str, Any]) -> ToolResult:
    """nft flush ruleset — remove ALL rules, chains, and tables from the live ruleset.

    WARNING: on hosts with a default-drop policy this wipes all firewall rules
    and may lock out remote access until rules are restored.
    """
    result = run_subprocess(["nft", "flush", "ruleset"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "nftables ruleset flushed; all tables and rules have been removed."
    else:
        summary = (
            f"Failed to flush nftables ruleset (exit {result.exit_code})."
        )
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
    "list_ruleset": _op_list_ruleset,
    "add_rule": _op_add_rule,
    "delete_rule": _op_delete_rule,
    "flush_ruleset": _op_flush_ruleset,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an nftables operation and return a structured ToolResult.

    I3: The caller resolves the permission gate before calling this function.
    I4: The caller writes the audit record; this function does not.
    I9: This function never raises; every failure returns a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for nftables tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_TABLE_ARG = ArgSpec(
    name="table",
    type=str,
    required=True,
    description="The nftables table name (e.g. 'filter').",
)

_CHAIN_ARG = ArgSpec(
    name="chain",
    type=str,
    required=True,
    description="The nftables chain name within the table (e.g. 'input').",
)

_FAMILY_ARG = ArgSpec(
    name="family",
    type=str,
    required=False,
    description="Address family: ip, ip6, inet, arp, bridge (default: inet).",
    default="inet",
)

NFTABLES_SPEC = ToolSpec(
    name="nftables",
    description=(
        "Manage the raw nftables ruleset via the nft binary. "
        "On Rocky Linux 9 firewalld sits on top of nftables — use the "
        "'firewall' tool for zone/service management and this tool for "
        "direct nft ruleset operations only."
    ),
    ops={
        "list_ruleset": OpSpec(
            op_name="list_ruleset",
            permission_class=OpClass.READ,
            args=[],
            description="Dump the full nftables ruleset including all tables, chains, and rules.",
        ),
        "add_rule": OpSpec(
            op_name="add_rule",
            permission_class=OpClass.WRITE,
            args=[
                _FAMILY_ARG,
                _TABLE_ARG,
                _CHAIN_ARG,
                ArgSpec(
                    name="rule",
                    type=str,
                    required=True,
                    description=(
                        "Rule expression tokens (e.g. 'tcp dport 22 accept'). "
                        "Passed as positional arguments to nft add rule."
                    ),
                ),
            ],
            description="Add a rule to a chain in the nftables ruleset.",
        ),
        "delete_rule": OpSpec(
            op_name="delete_rule",
            permission_class=OpClass.WRITE,
            args=[
                _FAMILY_ARG,
                _TABLE_ARG,
                _CHAIN_ARG,
                ArgSpec(
                    name="handle",
                    type=str,
                    required=True,
                    description=(
                        "The numeric rule handle to delete "
                        "(visible in 'nft list ruleset' output)."
                    ),
                ),
            ],
            description="Delete a specific rule from a chain by its handle number.",
        ),
        "flush_ruleset": OpSpec(
            op_name="flush_ruleset",
            permission_class=OpClass.DESTRUCTIVE,
            args=[],
            description=(
                "Remove ALL rules, chains, and tables from the live nftables ruleset. "
                "On hosts with a default-drop policy this will drop all firewall "
                "protection and may lock out remote access."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(NFTABLES_SPEC)
