"""finetune/validate.py — replay every tool_call through the LIVE router.

__main__ CLI: ``python -m finetune.validate PATH``

For each record in PATH (JSONL, one record per line):

  1. Locate every assistant tool_calls turn.
  2. For each call: ``json.loads(arguments)`` and run the parsed dict through
     ``coreimports.validate_arguments(registry.get(tool), parsed_args)`` — the
     LIVE router, NEVER a re-implementation (INV-schema-sync; no bench drift).
  3. Count VALID vs MISS.
  4. Verify each tool_call_id in an assistant turn correlates to a following
     ``role:"tool"`` message in the same record (INV-0002 §3).
  5. Scan every assistant ``content`` string for I2 violations via
     ``coreimports.assert_no_ai_language`` (INV-I2).

Report
------
  total records, total tool_calls, valid, MISS count + rate,
  per-tool coverage table, permission-class coverage, I2-violation count.

Exit codes
----------
  0   MISS rate <= 0.5%, zero I2 violations, all 11 tools covered.
  1   MISS rate > 0.5%, or any I2 violation, or any tool has zero valid calls.
  2   Bad arguments (empty path, unreadable file, etc.).

Invariants
----------
INV-schema-sync   Validation comes EXCLUSIVELY from the LIVE router
                  (coreimports.validate_arguments + coreimports.registry).
                  Nothing is hardcoded.
INV-I2            assert_no_ai_language is called on every assistant content
                  string; violations are counted and surface non-zero exit.
INV-0002 §2       arguments must be a JSON-encoded STRING; a nested object is
                  counted as a MISS (the wire format violation is the bug to
                  catch).
INV-0002 §3       Every tool_call_id must correlate to a following role:"tool"
                  message; missing correlations are reported as errors.
INV-offline       No network, no key, no anthropic required.
INV-read-only-core  All core/ access is via finetune.coreimports.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Optional

from finetune import coreimports

# --------------------------------------------------------------------------- #
# Data structures                                                              #
# --------------------------------------------------------------------------- #

MISS_RATE_THRESHOLD = 0.005  # 0.5 % — exit non-zero above this


@dataclass
class CallVerdict:
    """Verdict for a single tool_call entry."""

    call_id: str
    tool: str
    operation: str        # "" on MISS (operation not parseable)
    permission_class: str  # "" on MISS
    is_valid: bool
    reason: str           # "" on VALID; human detail on MISS


@dataclass
class RecordVerdict:
    """Verdict for one JSONL record."""

    record_idx: int
    call_verdicts: list[CallVerdict] = field(default_factory=list)
    i2_violations: int = 0
    correlation_errors: int = 0  # tool_call_ids with no following role:"tool" msg


@dataclass
class ValidationReport:
    """Aggregated report over the entire JSONL file."""

    total_records: int = 0
    total_tool_calls: int = 0
    valid_count: int = 0
    miss_count: int = 0
    i2_violation_count: int = 0
    correlation_error_count: int = 0
    # {tool_name: {"total": int, "valid": int, "miss": int}}
    per_tool: dict = field(default_factory=dict)
    # {class_name: {"total": int, "valid": int}}
    per_permission_class: dict = field(default_factory=dict)

    @property
    def miss_rate(self) -> float:
        if self.total_tool_calls == 0:
            return 0.0
        return self.miss_count / self.total_tool_calls

    @property
    def missing_tools(self) -> list[str]:
        """Tools in TOOL_NAMES with zero valid calls (coverage gap)."""
        return [
            t for t in coreimports.TOOL_NAMES
            if self.per_tool.get(t, {}).get("valid", 0) == 0
        ]

    @property
    def should_fail(self) -> bool:
        return (
            self.miss_rate > MISS_RATE_THRESHOLD
            or self.i2_violation_count > 0
            or bool(self.missing_tools)
        )


# --------------------------------------------------------------------------- #
# Per-call validation (the atomic unit)                                       #
# --------------------------------------------------------------------------- #

def check_call(call: dict) -> CallVerdict:
    """Validate a single OpenAI §2 tool_call dict through the LIVE router.

    This is the ONLY place in validate.py where validation logic lives.  It
    calls ``coreimports.validate_arguments`` (the authoritative router function)
    and NEVER reimplements schema logic (INV-schema-sync).

    Returns a :class:`CallVerdict` whose ``is_valid`` matches the bench
    predicate ``RouterResult.is_valid_action`` for the same call (proven in
    tests/finetune/test_validate.py — no drift from bench semantics).
    """
    call_id: str = call.get("id") or ""
    fn: dict = call.get("function") or {}
    tool_name: str = fn.get("name") or ""
    arguments = fn.get("arguments")

    # --- Unknown tool (registry miss) --------------------------------------- #
    spec = coreimports.registry.get(tool_name)
    if spec is None:
        return CallVerdict(
            call_id=call_id,
            tool=tool_name,
            operation="",
            permission_class="",
            is_valid=False,
            reason=f"unknown tool {tool_name!r} (not in live registry)",
        )

    # --- arguments must be a JSON-encoded STRING (INV-0002 §2) -------------- #
    if not isinstance(arguments, str):
        return CallVerdict(
            call_id=call_id,
            tool=tool_name,
            operation="",
            permission_class="",
            is_valid=False,
            reason=(
                f"arguments must be a JSON-encoded string (INV-0002 §2), "
                f"got {type(arguments).__name__}"
            ),
        )

    # --- Parse the JSON string --------------------------------------------- #
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as exc:
        return CallVerdict(
            call_id=call_id,
            tool=tool_name,
            operation="",
            permission_class="",
            is_valid=False,
            reason=f"arguments not valid JSON: {exc}",
        )

    if not isinstance(parsed, dict):
        return CallVerdict(
            call_id=call_id,
            tool=tool_name,
            operation="",
            permission_class="",
            is_valid=False,
            reason="arguments must decode to a JSON object",
        )

    # --- LIVE router validation (INV-schema-sync) --------------------------- #
    try:
        operation, _op_args = coreimports.validate_arguments(spec, parsed)
    except ValueError as exc:
        return CallVerdict(
            call_id=call_id,
            tool=tool_name,
            operation="",
            permission_class="",
            is_valid=False,
            reason=str(exc),
        )

    perm = spec.permission_class_for(operation)
    perm_str = perm.value if perm is not None else ""

    return CallVerdict(
        call_id=call_id,
        tool=tool_name,
        operation=operation,
        permission_class=perm_str,
        is_valid=True,
        reason="",
    )


# --------------------------------------------------------------------------- #
# Record-level validation                                                      #
# --------------------------------------------------------------------------- #

def _check_record(record: dict, idx: int) -> RecordVerdict:
    """Validate one parsed record dict."""
    verdict = RecordVerdict(record_idx=idx)
    messages: list[dict] = record.get("messages") or []

    # Build the set of all tool_call_ids from assistant turns, so we can check
    # that each correlates to a following role:"tool" message (INV-0002 §3).
    # We also track which tool_call_ids have been resolved by a tool message.
    pending_ids: dict[str, int] = {}  # {tool_call_id: message_index}
    resolved_ids: set[str] = set()

    for msg_idx, msg in enumerate(messages):
        role = msg.get("role") or ""

        if role == "assistant":
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content")

            # Validate each tool call.
            for call in tool_calls:
                cv = check_call(call)
                verdict.call_verdicts.append(cv)
                call_id = call.get("id") or ""
                if call_id:
                    pending_ids[call_id] = msg_idx

            # I2 check on assistant content string (INV-I2).
            # content is None on a tool-call turn (0002 §2) — None is fine.
            if content is not None and isinstance(content, str) and content.strip():
                try:
                    coreimports.assert_no_ai_language(content, f"msg[{msg_idx}].content")
                except ValueError:
                    verdict.i2_violations += 1

        elif role == "tool":
            tcid = msg.get("tool_call_id") or ""
            if tcid:
                resolved_ids.add(tcid)

    # Any tool_call_id that was never resolved -> correlation error.
    for tcid in pending_ids:
        if tcid not in resolved_ids:
            verdict.correlation_errors += 1

    return verdict


# --------------------------------------------------------------------------- #
# File-level validation                                                        #
# --------------------------------------------------------------------------- #

def validate_jsonl(path: str) -> ValidationReport:
    """Read ``path`` line by line and validate every record.

    Returns a :class:`ValidationReport` with aggregated counts.
    Skips blank lines; raises ``ValueError`` on a completely unreadable file.
    """
    report = ValidationReport()

    try:
        fh = open(path, "r", encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot open {path!r}: {exc}") from exc

    with fh:
        for line_no, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                sys.stderr.write(
                    f"[warn] line {line_no}: JSON parse error ({exc}); skipping\n"
                )
                continue

            report.total_records += 1
            rv = _check_record(record, line_no)

            for cv in rv.call_verdicts:
                report.total_tool_calls += 1

                # Per-tool accumulation.
                entry = report.per_tool.setdefault(
                    cv.tool, {"total": 0, "valid": 0, "miss": 0}
                )
                entry["total"] += 1
                if cv.is_valid:
                    report.valid_count += 1
                    entry["valid"] += 1
                    # Per-permission-class accumulation (only for valid calls
                    # where the permission class is known).
                    if cv.permission_class:
                        pc = report.per_permission_class.setdefault(
                            cv.permission_class, {"total": 0, "valid": 0}
                        )
                        pc["total"] += 1
                        pc["valid"] += 1
                else:
                    report.miss_count += 1
                    entry["miss"] += 1

            report.i2_violation_count += rv.i2_violations
            report.correlation_error_count += rv.correlation_errors

    return report


# --------------------------------------------------------------------------- #
# Report printer                                                               #
# --------------------------------------------------------------------------- #

def print_report(report: ValidationReport, path: str) -> None:
    """Print the validation report to stdout."""
    rate_pct = report.miss_rate * 100
    pass_fail = "PASS" if not report.should_fail else "FAIL"

    print(f"finetune.validate — {path}")
    print(f"{'=' * 60}")
    print(f"  Records         : {report.total_records}")
    print(f"  Tool calls      : {report.total_tool_calls}")
    print(f"  Valid           : {report.valid_count}")
    print(f"  MISS            : {report.miss_count}  ({rate_pct:.3f}%)")
    print(f"  MISS threshold  : {MISS_RATE_THRESHOLD * 100:.1f}%")
    print(f"  I2 violations   : {report.i2_violation_count}")
    print(f"  Correlation errs: {report.correlation_error_count}")
    print()

    # Per-tool table.
    print("  Per-tool coverage:")
    header = f"  {'Tool':<16} {'Total':>6} {'Valid':>6} {'MISS':>6}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for tool in sorted(coreimports.TOOL_NAMES):
        row = report.per_tool.get(tool, {"total": 0, "valid": 0, "miss": 0})
        gap = " [NO VALID CALLS]" if row["valid"] == 0 else ""
        print(
            f"  {tool:<16} {row['total']:>6} {row['valid']:>6} {row['miss']:>6}{gap}"
        )
    print()

    # Per-permission-class table.
    print("  Per-permission-class coverage (valid calls only):")
    for cls in ("read", "write", "destructive"):
        row = report.per_permission_class.get(cls, {"total": 0, "valid": 0})
        print(f"  {cls:<14}: {row['valid']} valid")
    print()

    # Missing tools.
    missing = report.missing_tools
    if missing:
        print(f"  COVERAGE GAP — tools with zero valid calls: {missing}")
        print()

    print(f"  Result: {pass_fail}")
    if report.should_fail:
        reasons = []
        if report.miss_rate > MISS_RATE_THRESHOLD:
            reasons.append(f"MISS rate {rate_pct:.3f}% > {MISS_RATE_THRESHOLD * 100:.1f}%")
        if report.i2_violation_count > 0:
            reasons.append(f"{report.i2_violation_count} I2 violation(s)")
        if missing:
            reasons.append(f"coverage gap: {missing}")
        print(f"  Reasons: {'; '.join(reasons)}")


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m finetune.validate",
        description=(
            "Validate a finetune JSONL corpus: replay every tool_call through "
            "the LIVE router and scan assistant content for I2 violations. "
            "Exit 0 iff MISS rate <= 0.5%, zero I2 violations, and all tools covered."
        ),
    )
    p.add_argument("path", help="Path to the JSONL file to validate.")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.path:
        sys.stderr.write("error: PATH argument is required\n")
        return 2

    try:
        report = validate_jsonl(args.path)
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    print_report(report, args.path)
    return 1 if report.should_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
