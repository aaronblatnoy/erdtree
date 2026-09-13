"""finetune/scenarios_v2 — corpus v2: label-known scenarios that carry the
reference call (args) and the reference answer, so traces assemble directly
without a separate judgment fan-out.  Per-tool modules define SCENARIOS_V2 and
self-check at import via check_module().  Never joined with the held-out
finetune.scenarios.eval_pool."""
from __future__ import annotations

import importlib, json, re
from dataclasses import dataclass, field
from typing import Literal

from finetune import coreimports

_BANNED = re.compile(r"\b(ai|artificial intelligence|llm|large language model|model|agent|neural|neural network|machine learning|gpt|ollama|inference)\b", re.I)


@dataclass(frozen=True)
class V2:
    id: str
    tool: str
    operation: str
    complexity: Literal["single", "multi", "diagnostic"]
    user_input: str
    args: dict
    answer: str
    notes: str = ""


def check_module(tool: str, scenarios: list[V2]) -> None:
    spec = coreimports.registry.get(tool)
    assert spec is not None, f"unknown tool {tool}"
    ids = [s.id for s in scenarios]
    assert len(ids) == len(set(ids)), f"{tool}: duplicate ids"
    for s in scenarios:
        assert s.tool == tool, f"{s.id}: tool mismatch"
        assert s.operation in spec.ops, f"{s.id}: unknown operation {s.operation}"
        assert s.complexity in ("single", "multi", "diagnostic"), f"{s.id}: bad complexity"
        assert s.args.get("operation") == s.operation, f"{s.id}: args.operation must equal operation"
        coreimports.validate_arguments(spec, dict(s.args))  # raises ValueError on a bad call
        for label, text in (("user_input", s.user_input), ("answer", s.answer), ("args", json.dumps(s.args))):
            m = _BANNED.search(text)
            assert not m, f"{s.id}: banned word {m.group(0)!r} in {label}"
        assert s.user_input.strip() and s.answer.strip(), f"{s.id}: empty text"


def load_all() -> list[V2]:
    out: list[V2] = []
    for t in sorted(coreimports.TOOL_NAMES):
        try:
            mod = importlib.import_module(f"finetune.scenarios_v2.{t}")
        except ModuleNotFoundError:
            continue
        out.extend(mod.SCENARIOS_V2)
    return out
