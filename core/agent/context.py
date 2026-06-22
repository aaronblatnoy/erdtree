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
from core.context.facts import FactsLoader
from core.context.snapshot import SystemSnapshot, current_identity


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
        facts: Optional[FactsLoader] = None,
    ) -> None:
        self._cache = cache if cache is not None else SnapshotCache(Collector(), ttl=ttl)
        # Optional per-host facts preamble (P8).  None -> no preamble (I9).
        self._facts: Optional[FactsLoader] = facts

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

        When a :class:`~core.context.facts.FactsLoader` was supplied at
        construction time (P8), the operator-curated preamble is PREPENDED to
        the snapshot text (I5 augmentation, never replacement).  An absent or
        empty preamble is a no-op; the output is byte-identical to the
        no-facts path (backward-compatible default).
        """
        snap = self.snapshot(force=force)

        # The cwd changes faster than the snapshot cache TTL — a `cd` between
        # turns must show up immediately.  Refresh the live location/identity
        # every turn so "this folder" always resolves against where the
        # operator actually is, even on a cached or failed snapshot.
        cwd, home, user = current_identity()

        if snap is None:
            # Collection failed, but we still anchor the operator's location so
            # the command interface never guesses an absolute path (I5).
            loc_lines: list[str] = []
            if user or home:
                loc_lines.append(
                    f"User: {user}".rstrip()
                    + (f"  Home: {home}" if home else "")
                )
            if cwd:
                loc_lines.append(f"Working directory: {cwd}")
            base = "\n".join(loc_lines + [_FALLBACK_CONTEXT])
        else:
            snap.cwd, snap.home_dir, snap.login_user = cwd, home, user
            try:
                text = snap.to_prompt_text()
            except Exception:  # noqa: BLE001
                text = ""
            base = text.strip() if text.strip() else _FALLBACK_CONTEXT

        # P8: optionally prepend facts preamble (I5 augment, not replace).
        # When facts=None or the file is absent/empty, this is a no-op and
        # the returned string is identical to the pre-P8 path.
        if self._facts is not None:
            preamble = self._facts.load()
            if preamble:
                return preamble + "\n\n" + base

        return base

    def invalidate(self) -> None:
        """Force the next snapshot read to re-collect (e.g. after a write op).

        The loop calls this after a mutating tool runs so the next turn sees
        the changed system state instead of a stale cached snapshot.
        """
        self._cache.invalidate()
