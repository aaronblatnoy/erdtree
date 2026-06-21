"""
core/agent/context.py

Per-turn context plumbing.  This is the thin seam between the system-context
layer (core/context: collector -> snapshot -> cache) and the prompt layer
(core/agent/prompt).  It exists so the REPL/loop never has to know how a
snapshot is collected or serialised — it just asks for "the context text for
this turn".

Design contract (load-bearing):

  I1  Nothing here reaches the network.  The collector reads the LOCAL box
      only; this module never adds an egress path.
  I5  Fresh system context is ALWAYS available for injection.  Every turn,
      ``snapshot_text()`` returns a current (within one cache TTL) serialised
      snapshot.  If collection fails, it returns a SAFE, non-empty fallback
      string so the prompt layer still injects a context block (I5 says "if
      the agent doesn't know the environment, that's a bug" — so we degrade to
      a stated-unknown block, never to silence).
  I6  No tier/product/model names.  The cache TTL and collector are injected.
  I8  Context is cached behind a short TTL so repeated turns feel instant.

Nothing here talks to a model.  It is fully unit-testable on any host by
injecting a SnapshotCache built over a mock Collector (the cache already
supports that), or by injecting a snapshot directly.
"""

from __future__ import annotations

from typing import Optional

from core.context.cache import SnapshotCache
from core.context.collector import Collector
from core.context.snapshot import SystemSnapshot


# A SAFE, I2/I6-clean fallback when context collection raises.  I5: we still
# inject a context block; it just states the environment is currently unknown
# rather than going silent (which would be the actual bug I5 guards against).
_FALLBACK_CONTEXT = "System context could not be collected for this request."


class TurnContext:
    """Supplies the per-turn system-context text for prompt injection (I5).

    Wraps a :class:`~core.context.cache.SnapshotCache` so repeated turns reuse
    a fresh-enough snapshot (I8).  Collection errors never propagate to the
    loop: :meth:`snapshot_text` always returns a non-empty string.

    Parameters
    ----------
    cache:
        A pre-built SnapshotCache (inject a mock-Collector-backed one in
        tests).  If omitted, a default cache over a default Collector is built
        lazily — on the dev host that Collector's live calls are absent, so the
        snapshot degrades gracefully to a stated-unknown block rather than
        raising.
    ttl:
        TTL (seconds) for the default cache when ``cache`` is not supplied.
    """

    def __init__(
        self,
        cache: Optional[SnapshotCache] = None,
        *,
        ttl: float = 5.0,
    ) -> None:
        self._cache = cache if cache is not None else SnapshotCache(Collector(), ttl=ttl)

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def snapshot(self, *, force: bool = False) -> Optional[SystemSnapshot]:
        """Return the current SystemSnapshot, or None if collection raised.

        ``force=True`` bypasses the cache TTL and re-collects now.
        """
        try:
            return self._cache.get(force=force)
        except Exception:  # noqa: BLE001 — collection must never crash a turn
            return None

    def snapshot_text(self, *, force: bool = False) -> str:
        """Return the serialised context text for prompt injection (I5).

        ALWAYS non-empty: on a collection failure (or an empty snapshot) it
        returns the safe fallback so the prompt layer still injects a context
        block.  This is the value passed as ``snapshot_text=`` to
        ``core.agent.prompt.assemble`` / ``PromptConfig``.
        """
        snap = self.snapshot(force=force)
        if snap is None:
            return _FALLBACK_CONTEXT
        try:
            text = snap.to_prompt_text()
        except Exception:  # noqa: BLE001
            return _FALLBACK_CONTEXT
        text = text.strip()
        return text if text else _FALLBACK_CONTEXT

    def invalidate(self) -> None:
        """Force the next snapshot read to re-collect (e.g. after a write op).

        The loop calls this after a mutating tool runs so the next turn sees
        the changed system state instead of a stale cached snapshot.
        """
        self._cache.invalidate()
