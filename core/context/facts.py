"""
core/context/facts.py

Per-host facts preamble loader (P8).

Loads a tiny operator-curated facts file from the path given by the opaque
config key ERDTREE_FACTS_PATH (I6: read like all other ERDTREE_* knobs, never
hardcoded) and exposes it as a plain string preamble.

Design contract:

  I1  No network calls — reads only the local filesystem.
  I2  The preamble text is operator-authored; this module does NOT generate
      user-facing strings of its own except the empty string on absence.
      Callers that inject the preamble into a prompt MUST NOT add I2-forbidden
      terms.  The load() function itself does NOT validate the content: that
      check belongs to the test that imports _FORBIDDEN_AI_TERMS from
      core.agent.prompt and asserts the loaded text passes the filter.
  I5  Augments, never replaces, the live system snapshot.  The caller
      (TurnContext.snapshot_text) prepends the preamble to the snapshot text.
  I6  The path is supplied by the caller (from AppConfig / ERDTREE_FACTS_PATH);
      this module has no knowledge of tier names or product names.
  I9  Absent file -> empty string, no exception, no user-visible message.

Usage::

    from core.context.facts import FactsLoader

    loader = FactsLoader(path="/etc/erdtree/facts.txt")
    preamble = loader.load()   # "" when file absent; text otherwise
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class FactsLoader:
    """Load a per-host facts preamble from an operator-curated file.

    Parameters
    ----------
    path:
        Absolute (or relative) path to the facts file.  Typically read from
        ``ERDTREE_FACTS_PATH`` via AppConfig.  May be ``None`` or empty string
        — both resolve to an empty preamble (I9).
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self._path: Optional[Path] = Path(path) if path else None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def load(self) -> str:
        """Return the facts preamble string.

        Returns an empty string when:
        - no path was supplied, or
        - the file does not exist, or
        - the file is empty, or
        - any IO error occurs during reading.

        Never raises.  (I9)
        """
        if self._path is None:
            return ""
        try:
            text = self._path.read_text(encoding="utf-8").strip()
            return text
        except (OSError, UnicodeDecodeError):
            # Absent, unreadable, or mis-encoded file -> silent empty preamble.
            # No user-visible error message (I9 / I2 — no surprise output).
            return ""

    @property
    def path(self) -> Optional[Path]:
        """The configured facts file path (may be None)."""
        return self._path


def load_facts(path: Optional[str] = None) -> str:
    """Convenience function: load the facts preamble from *path*.

    Equivalent to ``FactsLoader(path).load()``.  Returns ``""`` on any failure.
    """
    return FactsLoader(path).load()
