"""tests/finetune/test_scenarios.py — coverage assertions for the scenario corpus.

Validates that the aggregated ALL_SCENARIOS list meets every acceptance
criterion defined in the Phase-1 JOIN spec:

  * Volume: >= 600 entries
  * All 11 live tool names present
  * All 3 permission classes present (READ, WRITE, DESTRUCTIVE)
  * All 3 complexities present (single, multi, diagnostic)
  * IDs globally unique across all per-tool modules
  * Every scenario.tool is in the live TOOL_NAMES
  * Every scenario.operation is a real operation of its tool (live registry)

Load-bearing invariants
-----------------------
INV-schema-sync   Tool names, op names, and permission classes are derived
                  LIVE from finetune.coreimports — never hardcoded here.
INV-read-only-core  Tests import from finetune only; never from core/ directly.
INV-offline       Tests run with no network, no Ollama, no API key.
"""

from __future__ import annotations

import pytest

from finetune.coreimports import OpClass, TOOL_NAMES, registry
from finetune.scenarios import (
    ALL_SCENARIOS,
    Scenario,
    by_complexity,
    by_permission,
    by_tool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _live_ops(tool_name: str) -> frozenset[str]:
    """Return the live set of operation names for *tool_name*."""
    return frozenset(registry.get(tool_name).ops.keys())


# ---------------------------------------------------------------------------
# Volume gate
# ---------------------------------------------------------------------------


def test_total_count_at_least_600() -> None:
    """ALL_SCENARIOS must contain >= 600 entries."""
    assert len(ALL_SCENARIOS) >= 600, (
        f"Expected >= 600 scenarios, got {len(ALL_SCENARIOS)}"
    )


# ---------------------------------------------------------------------------
# Structural type checks
# ---------------------------------------------------------------------------


def test_all_entries_are_scenario_instances() -> None:
    """Every element of ALL_SCENARIOS must be a canonical Scenario instance."""
    non_canonical = [
        (i, type(s).__qualname__)
        for i, s in enumerate(ALL_SCENARIOS)
        if not isinstance(s, Scenario)
    ]
    assert not non_canonical, (
        f"Non-canonical Scenario instances at indices: {non_canonical[:5]}"
    )


# ---------------------------------------------------------------------------
# Tool name coverage
# ---------------------------------------------------------------------------


def test_all_11_tool_names_present() -> None:
    """Every live TOOL_NAME must have at least one scenario."""
    tools_in_corpus = {s.tool for s in ALL_SCENARIOS}
    missing = sorted(set(TOOL_NAMES) - tools_in_corpus)
    assert not missing, (
        f"These registered tools have no scenarios: {missing}"
    )


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_tool_has_scenarios(tool_name: str) -> None:
    """Each tool individually appears at least once in ALL_SCENARIOS."""
    matches = by_tool(tool_name)
    assert len(matches) >= 1, (
        f"by_tool({tool_name!r}) returned 0 results"
    )


# ---------------------------------------------------------------------------
# Permission class coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("opclass", list(OpClass))
def test_permission_class_present(opclass: OpClass) -> None:
    """Each OpClass (READ, WRITE, DESTRUCTIVE) must be present in the corpus."""
    matches = by_permission(opclass)
    assert len(matches) >= 1, (
        f"by_permission({opclass!r}) returned 0 results"
    )


def test_all_3_permission_classes_present() -> None:
    """READ, WRITE, and DESTRUCTIVE must ALL be represented."""
    present = {s.permission_class for s in ALL_SCENARIOS}
    for opc in (OpClass.READ, OpClass.WRITE, OpClass.DESTRUCTIVE):
        assert opc in present, f"Permission class {opc!r} absent from corpus"


# ---------------------------------------------------------------------------
# Complexity coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("complexity", ["single", "multi", "diagnostic"])
def test_complexity_present(complexity: str) -> None:
    """Each complexity kind must appear at least once."""
    matches = by_complexity(complexity)
    assert len(matches) >= 1, (
        f"by_complexity({complexity!r}) returned 0 results"
    )


def test_all_3_complexities_present() -> None:
    """single, multi, and diagnostic must ALL be represented."""
    present = {s.complexity for s in ALL_SCENARIOS}
    for c in ("single", "multi", "diagnostic"):
        assert c in present, f"Complexity {c!r} absent from corpus"


# ---------------------------------------------------------------------------
# Global ID uniqueness
# ---------------------------------------------------------------------------


def test_ids_globally_unique() -> None:
    """Scenario IDs must be unique across ALL per-tool modules."""
    all_ids = [s.id for s in ALL_SCENARIOS]
    duplicates = sorted({i for i in all_ids if all_ids.count(i) > 1})
    assert not duplicates, (
        f"Duplicate scenario ids detected: {duplicates}"
    )


# ---------------------------------------------------------------------------
# Live-registry integrity checks
# ---------------------------------------------------------------------------


def test_every_tool_in_tool_names() -> None:
    """Every scenario.tool must be in the live TOOL_NAMES."""
    bad = [
        s.id
        for s in ALL_SCENARIOS
        if s.tool not in TOOL_NAMES
    ]
    assert not bad, (
        f"Scenarios referencing unregistered tools: {bad[:10]}"
    )


def test_every_operation_is_real_op_of_its_tool() -> None:
    """Every scenario.operation must exist in the live registry for its tool."""
    bad = [
        (s.id, s.tool, s.operation)
        for s in ALL_SCENARIOS
        if s.operation not in _live_ops(s.tool)
    ]
    assert not bad, (
        "Scenarios with operations not in the live registry:\n"
        + "\n".join(f"  {sid!r}: tool={tool!r}, op={op!r}" for sid, tool, op in bad[:10])
    )


# ---------------------------------------------------------------------------
# Filter helper sanity
# ---------------------------------------------------------------------------


def test_by_tool_returns_only_matching_tool() -> None:
    """by_tool() must return ONLY scenarios for the requested tool."""
    for tool_name in TOOL_NAMES:
        for s in by_tool(tool_name):
            assert s.tool == tool_name, (
                f"by_tool({tool_name!r}) returned scenario {s.id!r} "
                f"with tool={s.tool!r}"
            )


def test_by_permission_returns_only_matching_class() -> None:
    """by_permission() must return ONLY scenarios with the requested OpClass."""
    for opc in OpClass:
        for s in by_permission(opc):
            assert s.permission_class == opc, (
                f"by_permission({opc!r}) returned scenario {s.id!r} "
                f"with permission_class={s.permission_class!r}"
            )


def test_by_complexity_returns_only_matching_kind() -> None:
    """by_complexity() must return ONLY scenarios with the requested complexity."""
    for kind in ("single", "multi", "diagnostic"):
        for s in by_complexity(kind):
            assert s.complexity == kind, (
                f"by_complexity({kind!r}) returned scenario {s.id!r} "
                f"with complexity={s.complexity!r}"
            )


def test_filter_counts_are_consistent() -> None:
    """Sum of filter results must equal total scenario count."""
    by_tool_total = sum(len(by_tool(t)) for t in TOOL_NAMES)
    assert by_tool_total == len(ALL_SCENARIOS), (
        f"by_tool sum ({by_tool_total}) != len(ALL_SCENARIOS) ({len(ALL_SCENARIOS)})"
    )

    by_perm_total = sum(len(by_permission(opc)) for opc in OpClass)
    assert by_perm_total == len(ALL_SCENARIOS), (
        f"by_permission sum ({by_perm_total}) != len(ALL_SCENARIOS) ({len(ALL_SCENARIOS)})"
    )

    by_complex_total = sum(
        len(by_complexity(k)) for k in ("single", "multi", "diagnostic")
    )
    assert by_complex_total == len(ALL_SCENARIOS), (
        f"by_complexity sum ({by_complex_total}) != len(ALL_SCENARIOS) ({len(ALL_SCENARIOS)})"
    )


# ---------------------------------------------------------------------------
# Shim module check — finetune.scenarios (the .py file) re-exports correctly
# ---------------------------------------------------------------------------


def test_shim_module_re_exports_all_symbols() -> None:
    """finetune/scenarios.py re-exports ALL_SCENARIOS, Scenario, and helpers."""
    import finetune.scenarios as shim  # the .py file, not the package

    assert hasattr(shim, "ALL_SCENARIOS"), "shim missing ALL_SCENARIOS"
    assert hasattr(shim, "Scenario"), "shim missing Scenario"
    assert hasattr(shim, "by_tool"), "shim missing by_tool"
    assert hasattr(shim, "by_permission"), "shim missing by_permission"
    assert hasattr(shim, "by_complexity"), "shim missing by_complexity"


def test_shim_all_scenarios_is_same_object() -> None:
    """The shim and the package must expose the same ALL_SCENARIOS object."""
    from finetune.scenarios import ALL_SCENARIOS as pkg_list
    import finetune.scenarios as shim
    assert shim.ALL_SCENARIOS is pkg_list, (
        "finetune/scenarios.py ALL_SCENARIOS is not the same object as "
        "finetune/scenarios/__init__.py ALL_SCENARIOS"
    )
