"""Per-turn tool selection — advertise only the tools a request plausibly needs.

The registry holds 55 tools whose full schemas run to ~14k tokens.  Sending all
of them on every turn drowns a small model's attention and dominates training
cost.  This module scores every registered tool against the operator's request
with a weighted keyword overlap (tool name, operation names, descriptions,
argument names; inverse-frequency weighted) and returns the top ``k`` names,
always including a small set of catch-all tools.

Pure stdlib, deterministic, no network, no model.  The router still validates
any call against the FULL registry; selection only decides what is advertised.
Measured recall of the labeled tool within the top 10 on the scenario corpus is
above 0.97 (tests/test_toolselect.py guards the floor).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Optional

from core.tools import ToolRegistry, ToolSpec

DEFAULT_K = 10
ALWAYS = ("docs",)  # question-shaped requests rarely name their tool

_STOP = frozenset(
    "the a an to of for on in and or is are this that my me our it its with from by at as be do "
    "does did can you please show list get check all any some what which how why when where into "
    "onto up down out off over".split()
)
_WORD = re.compile(r"[a-z0-9_.\-/]+")


def _toks(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


def _expand(words: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for w in words:
        out.add(w)
        for p in re.split(r"[-_./]", w):
            if p:
                out.add(p)
        if w.endswith("s"):
            out.add(w[:-1])
        if w.endswith("ing"):
            out.add(w[:-3])
        if w.endswith("ed"):
            out.add(w[:-2])
    return out


class ToolSelector:
    """Builds a term index over a registry once; ``select`` is then O(tools)."""

    def __init__(self, registry: ToolRegistry, *, k: int = DEFAULT_K, always: Iterable[str] = ALWAYS) -> None:
        self._k = max(1, k)
        self._always = tuple(always)
        self._docs: dict[str, Counter] = {}
        for name in registry.list_tools():
            spec = registry.get(name)
            if spec is not None:
                self._docs[name] = self._profile(spec)
        df: Counter = Counter()
        for prof in self._docs.values():
            df.update(prof.keys())
        n = len(self._docs) or 1
        self._idf = {w: math.log(1 + n / c) for w, c in df.items()}

    @staticmethod
    def _profile(spec: ToolSpec) -> Counter:
        f: Counter = Counter()
        for w in _expand([spec.name]):
            f[w] += 6
        for w in _expand(_toks(spec.description or "")):
            f[w] += 2
        for op_name, op in spec.ops.items():
            for w in _expand([op_name]):
                f[w] += 3
            for w in _expand(_toks(op.description or "")):
                f[w] += 1
            for arg in op.args:
                for w in _expand([arg.name]):
                    f[w] += 1
                for w in _expand(_toks(arg.description or "")):
                    f[w] += 0.5
        return f

    def rank(self, user_input: str) -> list[tuple[float, str]]:
        q = _expand(_toks(user_input or ""))
        scored = [
            (sum(prof[w] * self._idf.get(w, 0.0) for w in q if w in prof), name)
            for name, prof in self._docs.items()
        ]
        return sorted(scored, key=lambda t: (-t[0], t[1]))

    def select(self, user_input: str, k: Optional[int] = None, extra: Iterable[str] = ()) -> list[str]:
        """Top-``k`` tool names for the request, plus the always-on set and ``extra``.

        Order is registry order (stable) so the advertised list does not shuffle
        between turns.  ``extra`` lets a caller pin tools already in play this
        conversation (the tool of a previous call in the same turn).
        """
        k = self._k if k is None else max(1, k)
        chosen = {name for _, name in self.rank(user_input)[:k]}
        chosen.update(n for n in self._always if n in self._docs)
        chosen.update(n for n in extra if n in self._docs)
        return [n for n in self._docs if n in chosen]
