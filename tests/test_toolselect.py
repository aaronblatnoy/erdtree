"""Tool selection recall floor and stability (core/agent/toolselect.py)."""
from core.agent.toolselect import ToolSelector, DEFAULT_K
from core.tools import registry


def _registry():
    return registry


def test_recall_floor_on_scenario_corpus():
    from finetune.scenarios import ALL_SCENARIOS
    sel = ToolSelector(_registry())
    hits = sum(1 for s in ALL_SCENARIOS if s.tool in sel.select(s.user_input))
    assert hits / len(ALL_SCENARIOS) >= 0.96


def test_always_includes_docs_and_is_stable_order():
    reg = _registry()
    sel = ToolSelector(reg)
    names = sel.select("restart nginx")
    assert "docs" in names and "services" in names
    assert names == [n for n in reg.list_tools() if n in set(names)]
    assert len(names) <= DEFAULT_K + 1


def test_extra_pins_tool():
    sel = ToolSelector(_registry())
    assert "virsh" in sel.select("show disk usage", extra=["virsh"])
