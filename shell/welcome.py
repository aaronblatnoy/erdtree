"""
shell/welcome.py — the one-time startup banner for an edition.

Printed ONCE when the shell starts: the edition's character sprite on the left
(see shell/splash.py), and to its right a short welcome block — a colored
"Welcome to Linux <Edition>" header, the pitch line, a few live facts about the
machine you're on, and how to drop into a raw bash shell.

LAYOUT (mirrors the familiar terminal-tool startup card)

    ▀▀▀▀▀        Welcome to Linux Marika
    ▀▀▀▀▀        Type in English. Linux does it.
    ▀▀▀▀▀
    ▀▀▀▀▀          edition   Marika · v0.1
    ▀▀▀▀▀          session   user@host
    ▀▀▀▀▀          kernel    6.10.0
    ▀▀▀▀▀          uptime    3 days
    ▀▀▀▀▀          services  142 running
    ▀▀▀▀▀
    ▀▀▀▀▀        !!  bash mode      !cmd  one bash command

INVARIANTS (same spine as shell/prompt.py + shell/splash.py)
  I2  No "AI"/"LLM"/"model"/"agent"/"agentic" language anywhere — the tech is
      invisible. The banner only ever talks about Linux and the machine.
  I6  Edition is keyed by the OPAQUE tier label. Unknown label -> a clean,
      sprite-less generic card; the shell still starts.
  I7  No "Rocky" / base-distro names. "kernel" is the Linux kernel (the product
      IS Linux), never the build distro.
"""

from __future__ import annotations

from shell import splash

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

# Tier label -> (display name, ANSI color). Same colors as shell/prompt.py's
# NL caret so the banner and the prompt agree (I6: keyed by opaque label).
_TIER: dict[str, tuple[str, str]] = {
    "marika":      ("Marika",      "\033[38;5;220m"),   # light gold
    "radagon":     ("Radagon",     "\033[38;5;160m"),   # deep red
    "radahn":      ("Radahn",      "\033[38;5;203m"),   # scarlet
    "starscourge": ("Starscourge", "\033[38;5;93m"),    # purple
}

# How wide the gap is between the sprite and the text column.
_GAP = "   "


def _visible_width(grid: list[str]) -> int:
    """Visible columns one rendered sprite line occupies (indent + cells)."""
    return 2 + max(len(row) for row in grid)   # render_grid uses a 2-space indent


def _facts(tier_name: str, info: dict[str, str]) -> list[tuple[str, str]]:
    """The (label, value) rows shown under the header, in display order.

    *info* carries the live system context (filled by the context layer). Any
    missing key is simply skipped, so the card degrades cleanly.
    """
    rows: list[tuple[str, str]] = []
    edition = info.get("version")
    rows.append(("edition", f"{tier_name}" + (f" · {edition}" if edition else "")))
    for key, label in (
        ("session", "session"),
        ("kernel", "kernel"),
        ("uptime", "uptime"),
        ("packages", "packages"),
        ("services", "services"),
    ):
        if info.get(key):
            rows.append((label, info[key]))
    return rows


def _text_block(tier_name: str, color: str, info: dict[str, str]) -> list[str]:
    """The right-hand column: header, pitch, facts, and the bash hint."""
    facts = _facts(tier_name, info)
    label_w = max((len(lbl) for lbl, _ in facts), default=0)

    lines: list[str] = []
    lines.append(f"{_BOLD}{color}Welcome to Linux {tier_name}{_RESET}")
    lines.append(f"{_DIM}Type in English. Linux does it.{_RESET}")
    lines.append("")
    for lbl, val in facts:
        lines.append(f"  {_DIM}{lbl.ljust(label_w)}{_RESET}  {val}")
    lines.append("")
    lines.append(
        f"  {color}!!{_RESET} {_DIM}bash mode{_RESET}"
        f"      {color}!cmd{_RESET} {_DIM}one bash command{_RESET}"
    )
    return lines


def welcome(tier_label: str, info: dict[str, str] | None = None) -> str:
    """The startup banner for *tier_label*.

    Composes the sprite (left) and the welcome text (right). Unknown editions
    get a clean sprite-less card so the shell always starts (I6).
    """
    info = info or {}
    tier_name, color = _TIER.get(tier_label, (tier_label.capitalize() or "Linux", ""))

    text = _text_block(tier_name, color, info)

    grid = splash._ART.get(tier_label)
    if not grid:                                   # no art for this edition
        return "\n" + "\n".join(text) + "\n"

    sprite = splash.render_grid(grid).split("\n")
    pad = " " * _visible_width(grid)

    # Vertically center the text against the sprite.
    top = max(0, (len(sprite) - len(text)) // 2)
    rows: list[str] = []
    for i in range(max(len(sprite), top + len(text))):
        left = sprite[i] if i < len(sprite) else pad
        j = i - top
        right = text[j] if 0 <= j < len(text) else ""
        rows.append(f"{left}{_GAP}{right}".rstrip())
    return "\n" + "\n".join(rows) + "\n"


# --------------------------------------------------------------------------- #
# Preview: `python -m shell.welcome [tier ...]` with sample facts.            #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import platform
    import getpass
    import socket
    import sys

    sample = {
        "version": "v0.1",
        "session": f"{getpass.getuser()}@{socket.gethostname().split('.')[0]}",
        "kernel": platform.release(),
        "uptime": "3 days, 4 hours",
        "packages": "1,284 installed",
        "services": "142 running",
    }
    tiers = sys.argv[1:] or list(_TIER)
    for label in tiers:
        print(welcome(label, sample))
