"""
shell/prompt.py — colored prompt strings.

NL mode prompt:   [NL] ❯   tier-specific color
BASH mode prompt: [BASH] $  pink/magenta for all tiers

Tier colors (passed in as opaque strings — I6: no tier names here):
  marika      gold      \033[38;5;214m
  radagon     red       \033[38;5;196m
  radahn      scarlet   \033[38;5;203m
  starscourge purple    \033[38;5;93m

I2: no AI/LLM/model/agent language anywhere in this module.
"""

from __future__ import annotations

_RESET = "\033[0m"

# Maps the opaque tier label to an ANSI color code for NL mode.
_NL_TIER_COLOR: dict[str, str] = {
    "marika":      "\033[38;5;214m",
    "radagon":     "\033[38;5;196m",
    "radahn":      "\033[38;5;203m",
    "starscourge": "\033[38;5;93m",
}

# BASH mode is the same pink/magenta for every tier.
_BASH_COLOR = "\033[38;5;213m"

# Fallback NL color if tier is unknown.
_NL_DEFAULT_COLOR = "\033[38;5;196m"


def nl_prompt(tier: str) -> str:
    """Return the colored NL-mode prompt string."""
    color = _NL_TIER_COLOR.get(tier, _NL_DEFAULT_COLOR)
    return f"{color}[NL] ❯ {_RESET}"


def bash_prompt() -> str:
    """Return the colored BASH-mode prompt string."""
    return f"{_BASH_COLOR}[BASH] $ {_RESET}"
