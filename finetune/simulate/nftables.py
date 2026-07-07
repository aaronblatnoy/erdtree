"""finetune/simulate/nftables.py — Rocky Linux 9 output simulator for the 'nftables' tool.

Public API
----------
simulate_nftables(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 4 real operations declared in core/tools/nftables.py
           (list_ruleset, add_rule, delete_rule, flush_ruleset)
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by make_context(), or a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real nft behaviour:
    0  — success
    1  — generic error (table/chain not found, invalid rule, permission denied)
  127  — nft binary not found (simulated via error token in ctx or args)
* stdout/stderr reflect Rocky 9 nft output format.
* Failure triggers are deterministic:
    - 'notfound', 'noexist', 'broken', 'bogus', 'missing' in table/chain names
    - Hash-based ~15% scatter for variety among otherwise valid names

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent/neural language).

INV-read-only-core: imports NOTHING from core/ or finetune.coreimports.
The 4-key dict mirrors ToolResult with no class dependency.
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
    """Extract hostname from ctx for realistic output."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _name_is_invalid(name: str) -> bool:
    """Deterministically decide if a table/chain name should trigger an error.

    Triggers: known bad tokens in the name, OR a hash-based ~15% scatter.
    """
    lower = name.lower()
    for tok in ("notfound", "noexist", "broken", "bogus", "missing", "fail"):
        if tok in lower:
            return True
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 20 == 0


def _handle_is_invalid(handle: str) -> bool:
    """Return True if the handle looks non-numeric or out of range."""
    try:
        val = int(handle)
        return val <= 0 or val > 99999
    except (ValueError, TypeError):
        return True


def _has_ruleset(ctx: Any) -> bool:
    """Return True if ctx suggests an active nftables ruleset."""
    if isinstance(ctx, dict):
        return bool(ctx.get("nftables_active", True))
    if isinstance(ctx, str):
        return "nftables" in ctx.lower() or "nft" in ctx.lower()
    return True


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_list_ruleset(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: nft list ruleset."""
    if not _has_ruleset(ctx):
        # Empty ruleset — nft exits 0 with no output
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="nftables ruleset listed (0 table(s) found).",
        )

    stdout = (
        "table inet filter {\n"
        "\tchain input {\n"
        "\t\ttype filter hook input priority filter; policy drop;\n"
        "\t\tct state established,related accept # handle 1\n"
        "\t\tiif \"lo\" accept # handle 2\n"
        "\t\tip saddr 10.0.0.0/8 accept # handle 3\n"
        "\t\ttcp dport { 22, 80, 443 } accept # handle 4\n"
        "\t\ttcp dport 8080 accept # handle 5\n"
        "\t}\n"
        "\tchain forward {\n"
        "\t\ttype filter hook forward priority filter; policy drop;\n"
        "\t\tct state established,related accept # handle 6\n"
        "\t}\n"
        "\tchain output {\n"
        "\t\ttype filter hook output priority filter; policy accept;\n"
        "\t}\n"
        "}\n"
        "table ip nat {\n"
        "\tchain prerouting {\n"
        "\t\ttype nat hook prerouting priority dstnat;\n"
        "\t}\n"
        "\tchain postrouting {\n"
        "\t\ttype nat hook postrouting priority srcnat;\n"
        "\t\tip saddr 192.168.0.0/16 masquerade # handle 7\n"
        "\t}\n"
        "}\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="nftables ruleset listed (2 table(s) found).",
    )


def _sim_add_rule(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: nft add rule [family] table chain <rule-expr>."""
    family = args.get("family", "inet") or "inet"
    table = args.get("table", "filter")
    chain = args.get("chain", "input")
    rule = args.get("rule", "tcp dport 8080 accept")

    # Check for bad table or chain names
    if _name_is_invalid(table):
        stderr = (
            f"Error: No such file or directory: table '{family} {table}' does not exist\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to add rule to chain '{chain}' in table '{family} {table}' "
                f"(exit 1)."
            ),
        )

    if _name_is_invalid(chain):
        stderr = (
            f"Error: Chain '{chain}' does not exist in table '{family} {table}'\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to add rule to chain '{chain}' in table '{family} {table}' "
                f"(exit 1)."
            ),
        )

    # Simulate parse error for obviously invalid rule expressions
    if not rule.strip():
        stderr = "Error: syntax error, unexpected newline\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to add rule to chain '{chain}' in table '{family} {table}' "
                f"(exit 1)."
            ),
        )

    # Success — nft add rule exits 0 with no stdout
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=(
            f"Rule added to chain '{chain}' in table '{family} {table}'."
        ),
    )


def _sim_delete_rule(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: nft delete rule [family] table chain handle <handle>."""
    family = args.get("family", "inet") or "inet"
    table = args.get("table", "filter")
    chain = args.get("chain", "input")
    handle = args.get("handle", "1")

    if _name_is_invalid(table):
        stderr = (
            f"Error: Table '{family} {table}' does not exist\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to delete rule handle {handle} from chain '{chain}' in table "
                f"'{family} {table}' (exit 1)."
            ),
        )

    if _name_is_invalid(chain):
        stderr = (
            f"Error: Chain '{chain}' does not exist in table '{family} {table}'\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to delete rule handle {handle} from chain '{chain}' in table "
                f"'{family} {table}' (exit 1)."
            ),
        )

    if _handle_is_invalid(handle):
        stderr = (
            f"Error: Rule with handle {handle} does not exist in chain '{chain}'\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to delete rule handle {handle} from chain '{chain}' in table "
                f"'{family} {table}' (exit 1)."
            ),
        )

    # Hash-based scatter: some valid-looking handles will also fail
    h = int(hashlib.md5(f"{table}:{chain}:{handle}".encode()).hexdigest(), 16)
    if h % 15 == 0:
        stderr = (
            f"Error: Rule with handle {handle} does not exist in chain '{chain}'\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to delete rule handle {handle} from chain '{chain}' in table "
                f"'{family} {table}' (exit 1)."
            ),
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=(
            f"Rule handle {handle} deleted from chain '{chain}' in table "
            f"'{family} {table}'."
        ),
    )


def _sim_flush_ruleset(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: nft flush ruleset — clears all tables, chains, and rules."""
    # This command rarely fails (it is idempotent on an empty ruleset).
    # Simulate a failure if ctx explicitly marks nft as absent.
    nft_absent = False
    if isinstance(ctx, dict):
        nft_absent = ctx.get("nft_absent", False)

    if nft_absent:
        stderr = "nft: command not found\n"
        return _make_result(
            exit_code=127,
            stdout="",
            stderr=stderr,
            summary="Failed to flush nftables ruleset (exit 127).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="nftables ruleset flushed; all tables and rules have been removed.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list_ruleset": _sim_list_ruleset,
    "add_rule": _sim_add_rule,
    "delete_rule": _sim_delete_rule,
    "flush_ruleset": _sim_flush_ruleset,
}


def simulate_nftables(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'nftables' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 4 real ops declared in the
           nftables ToolSpec (list_ruleset, add_rule, delete_rule, flush_ruleset).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict (e.g. {'hostname': ..., 'nftables_active': True}).

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
            f"simulate_nftables: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
