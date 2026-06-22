"""
shell/prompt.py — colored prompt strings.

Both modes look like a normal Linux prompt — [user@host dir] — so you always
see where you are. The mode is told apart by the tail:

  NL mode:    [user@host dir] NATURAL LANGUAGE ❯   (label + caret in tier color)
  BASH mode:  [user@host dir]$                     (plain Linux)

Tier colors (passed in as opaque strings — I6: no tier names baked into logic):
  marika      gold      \033[38;5;214m
  radagon     red       \033[38;5;196m
  radahn      scarlet   \033[38;5;203m
  starscourge purple    \033[38;5;93m

I2: no AI/LLM/model/agent language anywhere in this module.
"""

from __future__ import annotations

import getpass
import os
import socket

_RESET = "\033[0m"

# Maps the opaque tier label to an ANSI color code for the NL-mode tail.
_NL_TIER_COLOR: dict[str, str] = {
    "marika":      "\033[38;5;214m",
    "radagon":     "\033[38;5;196m",
    "radahn":      "\033[38;5;203m",
    "starscourge": "\033[38;5;93m",
}

# Fallback NL color if the tier label is unknown.
_NL_DEFAULT_COLOR = "\033[38;5;196m"


def _cwd_display(cwd: str | None) -> str:
    """Linux `\\w`-style directory: the full path, home-relative with ~. Shows
    exactly where you are. Never raises."""
    try:
        path = cwd if cwd is not None else os.getcwd()
    except OSError:
        return "?"
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if home != "/" and path.startswith(home + "/"):
        return "~" + path[len(home):]
    return path or "/"


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 — the prompt must never crash the shell
        return os.environ.get("USER") or "user"


def _host() -> str:
    try:
        return socket.gethostname().split(".")[0] or "host"
    except Exception:  # noqa: BLE001
        return "host"


def _linux_prefix(cwd: str | None, user: str | None, host: str | None) -> str:
    u = user if user is not None else _user()
    h = host if host is not None else _host()
    return f"[{u}@{h} {_cwd_display(cwd)}]"


def nl_prompt(
    tier: str,
    *,
    cwd: str | None = None,
    user: str | None = None,
    host: str | None = None,
) -> str:
    """Linux-style prompt with a tier-colored NATURAL LANGUAGE caret tail."""
    color = _NL_TIER_COLOR.get(tier, _NL_DEFAULT_COLOR)
    return f"{_linux_prefix(cwd, user, host)}{color} NATURAL LANGUAGE ❯ {_RESET}"


def bash_prompt(
    *,
    cwd: str | None = None,
    user: str | None = None,
    host: str | None = None,
) -> str:
    """Plain Linux prompt for BASH mode."""
    return f"{_linux_prefix(cwd, user, host)}$ "
