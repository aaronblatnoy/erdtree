"""finetune/scenarios_v3 — corpus v3: MULTI-TURN and CONTRASTIVE scenarios.

Corpus v2 records were single-turn.  In the shell the model sees follow-ups
("now do the same for postgres", "ok do it", "why did that fail") and it had
never trained on a transcript.  v3 records carry 2-3 turns; each turn is
either a tool call (answer derived from the simulated result at assembly) or a
plain-English answer turn (a question the operator asks about what just
happened).  Follow-up turns MUST refer back so the runtime history gate
(core/agent/historygate.needs_history) would actually send the history.

Contrastive records ("contrast") are single-turn requests written to sit right
next to a confusable tool or operation (sssd status vs services status, disk
format vs wipe, ...).
"""
from __future__ import annotations

import importlib, json, re
from dataclasses import dataclass
from typing import Literal, Optional

from finetune import coreimports
from core.agent.historygate import needs_history

_BANNED = re.compile(r"\b(ai|artificial intelligence|llm|large language model|model|agent|neural|neural network|machine learning|gpt|ollama|inference)\b", re.I)


@dataclass(frozen=True)
class Turn:
    user_input: str
    tool: Optional[str] = None        # None => plain-English answer turn
    operation: Optional[str] = None
    args: Optional[dict] = None       # includes "operation"
    answer: Optional[str] = None      # required when tool is None


@dataclass(frozen=True)
class V3:
    id: str
    tool: str                         # primary tool the record is about
    kind: Literal["followup", "contrast", "question"]
    turns: tuple


def check_module(tool: str, scenarios: list) -> None:
    ids = [s.id for s in scenarios]
    assert len(ids) == len(set(ids)), f"{tool}: duplicate ids"
    for s in scenarios:
        assert s.tool == tool, f"{s.id}: tool mismatch"
        assert s.kind in ("followup", "contrast", "question"), f"{s.id}: bad kind"
        assert 1 <= len(s.turns) <= 3, f"{s.id}: 1-3 turns"
        assert s.kind != "followup" or len(s.turns) >= 2, f"{s.id}: followup needs 2+ turns"
        assert s.kind != "contrast" or len(s.turns) == 1, f"{s.id}: contrast is single-turn"
        for i, t in enumerate(s.turns):
            assert t.user_input.strip(), f"{s.id}: empty user_input"
            m = _BANNED.search(t.user_input); assert not m, f"{s.id}: banned {m.group(0)!r} in user_input"
            if i > 0:
                assert needs_history(t.user_input), f"{s.id} turn {i+1}: follow-up must refer back ({t.user_input!r})"
            if t.tool is None:
                assert t.answer and t.answer.strip(), f"{s.id} turn {i+1}: answer turn needs answer"
                m = _BANNED.search(t.answer); assert not m, f"{s.id}: banned {m.group(0)!r} in answer"
                assert i > 0, f"{s.id}: first turn must be a tool call"
            else:
                spec = coreimports.registry.get(t.tool); assert spec is not None, f"{s.id}: unknown tool {t.tool}"
                assert t.operation in spec.ops, f"{s.id}: unknown operation {t.tool}.{t.operation}"
                assert isinstance(t.args, dict) and t.args.get("operation") == t.operation, f"{s.id} turn {i+1}: args.operation"
                coreimports.validate_arguments(spec, dict(t.args))
                m = _BANNED.search(json.dumps(t.args)); assert not m, f"{s.id}: banned {m.group(0)!r} in args"
        assert s.turns[0].tool is not None, f"{s.id}: first turn must be a tool call"


def load_all() -> list:
    out = []
    for t in sorted(coreimports.TOOL_NAMES) + ["_contrast"]:
        try:
            mod = importlib.import_module(f"finetune.scenarios_v3.{t}")
        except ModuleNotFoundError:
            continue
        out.extend(mod.SCENARIOS_V3)
    return out
