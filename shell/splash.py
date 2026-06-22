"""
shell/splash.py — one-time pixel-art entrance for an edition.

A small character sprite shown ONCE at launch, then it gets out of the way.
This is the "in motion" entrance, not persistent chrome: print it, then drop
into the clean prompt and never show it again.

HOW IT RENDERS
  Real terminal pixel art uses the upper-half block "▀": the glyph's FOREGROUND
  color paints the TOP pixel and the cell's BACKGROUND color paints the BOTTOM
  pixel. So one text row encodes TWO pixel rows -> square-ish pixels at double
  vertical resolution. Each sprite is authored as a grid of single-char palette
  keys (easy to edit by hand); render_grid turns it into half-block ANSI.

  Palette key '.' (or ' ') = transparent -> the terminal background shows
  through, so the sprite floats on whatever theme the user runs.

INVARIANTS (same spine as shell/prompt.py)
  I2  No "AI"/"LLM"/"model"/"agent"/"agentic" text anywhere — this is art only.
  I6  The tier label is OPAQUE: art is looked up by the label, never branched on
      by tier name in logic elsewhere. Unknown label -> "" (no splash), so an
      edition with no art simply shows nothing and the shell still starts clean.
  I7  No "Rocky" / base-distro names.
"""

from __future__ import annotations

_RESET = "\033[0m"

# 256-color palette. Hair/gold tones match the locked tier caret colors
# (marika gold 220, radagon red 160) so the splash and the prompt agree.
_PALETTE: dict[str, int] = {
    "o": 16,                            # outline
    # red hair (Radagon) — keyed to the radagon caret red 160
    "H": 203, "h": 160, "d": 124,       # scarlet highlight / red / shadow
    # gold hair + gown (Marika) — keyed to the marika caret gold 220
    "Y": 228, "y": 220, "w": 178,       # pale gold / gold / amber shadow
    "C": 226, "c": 214,                 # crown highlight / shadow
    "G": 220, "g": 214, "n": 136,       # gown / gown shadow / deep amber
    # skin
    "S": 223, "L": 224, "k": 180,       # skin / highlight / shadow (blush)
    "e": 16,                            # eye
    "m": 174,                           # lips
    # beard (Radagon)
    "b": 130, "a": 173, "B": 88,        # auburn / highlight / dark shadow
    # robe (Radagon, maroon)
    "V": 88, "M": 52,                   # maroon / deep shadow
}

# Transparent keys: terminal background shows through.
_TRANSPARENT = {".", " "}


# --------------------------------------------------------------------------- #
# Sprites — each row is a string of palette keys; all rows equal width.        #
# An even number of rows so they pair cleanly into half-block lines.           #
# --------------------------------------------------------------------------- #

# Marika — golden hair under a crown, calm face, gold gown. A full little
# figure with outline + shading so it reads at small size.
_MARIKA = [
    "....o..o.o..o.o....",
    "....oCo.CcCcC.oCo....",
    ".....ooooooooooo.....",
    "....ooYYyyyyyYYyyoo...",
    "...oywyyyyyyyyywwyyo..",
    "..oyyyyyyyyyyyyyyyyo..",
    "..oywyoooooooooowyyo..",
    "..oywoSSSSSSSSSSoywo..",
    ".oyyoSLLSSSSSSLLSoywo.",
    ".oywoSSSSSSSSSSSSoywo.",
    ".oywoSSeeSSSSeeSSoywo.",
    ".oywoSSeeSSSSeeSSoywo.",
    ".oywoSSSSSkkSSSSSoywo.",
    ".oywoSSSkmmmmkSSSoywo.",
    ".oywoSSSSSSSSSSSSoywo.",
    ".oywwoSSSSSSSSSSoywwo.",
    "..oywoSSSSSSSSSSoywo..",
    "..oyywoSSSSSSSSoyywo..",
    "...oyywooooooooyywo...",
    "....oyywoooooooywwo...",
    ".....oGGGGGGGGGGGGo...",
    "....oGGCcGGGGGGcCGGo..",
    "...oGGGGnGGGGGGnGGGGo.",
    "...oGGGGGGGnnGGGGGGGo.",
    "..oGGGGGGGGnnGGGGGGGGo",
    "..oGnGGGGGGnnGGGGGGnGo",
    "..oGnGGGGGGGGGGGGGGnGo",
    "..ooGGGGGGGGGGGGGGoo..",
    "....oooonnoooonnoooo..",
    ".......oooo...oooo....",
]

# Radagon — red hair, auburn beard, maroon robe with gold trim. The same
# little figure (Radagon is Marika), in the red palette.
_RADAGON = [
    ".......ooooooooo.......",
    ".....oodddddddddoo.....",
    "....oddddddddddddddo...",
    "...odddHHdddddHHddddo..",
    "...oddHhhdddddhhHdddo..",
    "..oddhhhdddddddhhhddo..",
    "..odhhdoooooooooddhhdo.",
    "..odhdoSSSSSSSSSSodhdo.",
    ".odhhoSLLSSSSSSLLSoddo.",
    ".odhdoSSSSSSSSSSSSohdo.",
    ".odhdoSSeeSSSSeeSSohdo.",
    ".odhdoSSeeSSSSeeSSohdo.",
    ".odhdoSSSSSkkSSSSSohdo.",
    ".odhdoSSSkmmmmkSSSohdo.",
    ".odhdoSSbbbaaabbSSohdo.",
    ".odhddoSbbbbbbbbSoddho.",
    "..odhdoBbbbbbbbBodhdo..",
    "..oddhooBbbbbbBoohhdo..",
    "...oddhooBBBBBBoohhdo..",
    "....oddhoooooooohhdo...",
    ".....oVVVVVVVVVVVVo....",
    "....oVVGGVVVVVVGGVVo...",
    "...oVVVGgVVVVVVgGVVVo..",
    "...oVVVVVVVMMVVVVVVVo..",
    "..oVVVVVVVVMMVVVVVVVVo.",
    "..oVMVVVVVVMMVVVVVVMVo.",
    "..oVMVVVVVVVVVVVVVVMVo.",
    "..ooVVVVVVVVVVVVVVoo...",
    "....ooooMMooooMMoooo...",
    ".......oooo...oooo.....",
]


# Art keyed by OPAQUE tier label (I6). Add an edition here; no logic elsewhere
# learns a new tier name.
_ART: dict[str, list[str]] = {
    "marika": _MARIKA,
    "radagon": _RADAGON,
}


# --------------------------------------------------------------------------- #
# Rendering                                                                    #
# --------------------------------------------------------------------------- #

def _cell(top: str, bottom: str) -> str:
    """One half-block cell: FG = top pixel, BG = bottom pixel.

    Both transparent  -> a space (background shows through).
    Only one painted   -> a half block in that color, the other half transparent.
    Both painted       -> "▀" with FG=top color and BG=bottom color.
    """
    top_c = None if top in _TRANSPARENT else _PALETTE.get(top)
    bot_c = None if bottom in _TRANSPARENT else _PALETTE.get(bottom)

    if top_c is None and bot_c is None:
        return " "
    if top_c is not None and bot_c is None:
        return f"\033[38;5;{top_c}m▀{_RESET}"      # ▀ upper half
    if top_c is None and bot_c is not None:
        return f"\033[38;5;{bot_c}m▄{_RESET}"      # ▄ lower half
    return f"\033[38;5;{top_c};48;5;{bot_c}m▀{_RESET}"


def render_grid(grid: list[str], *, indent: str = "  ") -> str:
    """Turn a pixel grid into half-block ANSI lines (two pixel rows per line)."""
    width = max(len(row) for row in grid)
    rows = [row.ljust(width, ".") for row in grid]   # pad ragged rows transparently
    if len(rows) % 2:                      # pad to an even number of pixel rows
        rows.append("." * width)

    lines = []
    for top, bottom in zip(rows[0::2], rows[1::2]):
        cells = "".join(_cell(t, b) for t, b in zip(top, bottom))
        lines.append(indent + cells)
    return "\n".join(lines)


def shape(grid: list[str]) -> str:
    """Plain silhouette ('#'/' ') for eyeballing the sprite without color."""
    return "\n".join(
        "".join(" " if ch in _TRANSPARENT else "#" for ch in row) for row in grid
    )


def splash(tier_label: str) -> str:
    """The launch splash for *tier_label*, or "" if the edition has no art (I6).

    Caller prints this once before the prompt loop. Empty string -> no splash,
    shell still starts clean.
    """
    grid = _ART.get(tier_label)
    if not grid:
        return ""
    return "\n" + render_grid(grid) + "\n"


# --------------------------------------------------------------------------- #
# Preview: `python -m shell.splash [tier ...]` — eyeball it on your own theme. #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys

    tiers = sys.argv[1:] or list(_ART)
    for label in tiers:
        out = splash(label)
        if out:
            print(out)
        else:
            print(f"(no art for {label!r})\n")

