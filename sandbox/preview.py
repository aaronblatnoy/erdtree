#!/usr/bin/env python3
"""Aesthetic preview — renders the same mock turn in several styles so you can
see real colors/spacing in your terminal and pick a direction.

    python3 sandbox/preview.py

No model, no deps — just prints. Pick a style number (or say "3 but tighter
spacing", "2's gutter with 1's prompt", etc.) and I'll implement it.
"""
import sys

# Tier caret color = radagon deep red (160). Others: marika gold 220, radahn 203.
CARET = "\033[38;5;160m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
GREENDIM = "\033[2;32m"
R = "\033[0m"

USER, HOST, CWD = "aaron", "mossad-server", "~/erdtree"
REQ = "restart nginx and check free disk"
OK_CMD = "systemctl restart nginx"
BAD_CMD = "df -x tmpfs"
ANSWER_L1 = "nginx restarted and is active."
ANSWER_L2 = "Disk check failed (exit 1)."


def hdr(n, name):
    print(f"\n{DIM}{'─'*64}{R}")
    print(f"  STYLE {n}  ·  {name}")
    print(f"{DIM}{'─'*64}{R}\n")


def style1():
    hdr(1, "Minimal (current): bracket prompt, in-place steps")
    print(f"[{USER}@{HOST} {CWD}]{CARET}❯{R} {REQ}")
    print(f"{DIM}  ✔ {OK_CMD}{R}")
    print(f"{RED}  ✘ {BAD_CMD} · exit 1{R}")
    print()
    print(ANSWER_L1)
    print(ANSWER_L2)


def style2():
    hdr(2, "Clean gutter: no brackets, vertical-bar steps, airy")
    print(f"{DIM}{CWD}{R} {CARET}❯{R} {REQ}")
    print()
    print(f"{DIM}  │{R} {GREEN}✓{R} {DIM}{OK_CMD}{R}")
    print(f"{DIM}  │{R} {RED}✗{R} {DIM}{BAD_CMD}{R}  {RED}exit 1{R}")
    print()
    print(f"  {ANSWER_L1}")
    print(f"  {ANSWER_L2}")


def style3():
    hdr(3, "Two-line prompt, arrow steps with trailing status")
    print(f"{DIM}{USER} {CWD}{R}")
    print(f"{CARET}❯{R} {REQ}")
    print(f"{DIM}  → {OK_CMD}{R}  {GREEN}✓{R}")
    print(f"{DIM}  → {BAD_CMD}{R}  {RED}✗ exit 1{R}")
    print()
    print(f"  {ANSWER_L1}")
    print(f"  {ANSWER_L2}")


def style4():
    hdr(4, "Tight: single-glyph steps, no running line, minimal space")
    print(f"{DIM}{CWD}{R} {CARET}❯{R} {REQ}")
    print(f"  {GREENDIM}✔{R} {DIM}{OK_CMD}{R}")
    print(f"  {RED}✘{R} {DIM}{BAD_CMD}{R} {RED}· exit 1{R}")
    print(f"  {ANSWER_L1}")
    print(f"  {ANSWER_L2}")


def style5():
    hdr(5, "Accent gutter bar: thin tier-colored bar down the whole turn")
    bar = f"{CARET}▏{R}"
    print(f"{DIM}{CWD}{R} {CARET}❯{R} {REQ}")
    print(f"{bar} {GREEN}✓{R} {DIM}{OK_CMD}{R}")
    print(f"{bar} {RED}✗{R} {DIM}{BAD_CMD}{R} {RED}exit 1{R}")
    print(bar)
    print(f"{bar} {ANSWER_L1}")
    print(f"{bar} {ANSWER_L2}")


def main():
    print(f"\n{DIM}Same interaction, five looks. Real colors below. "
          f"Pick a number or mix elements.{R}")
    for f in (style1, style2, style3, style4, style5):
        f()
    print(f"\n{DIM}{'─'*64}{R}")
    print("  Tell me: a style number, or e.g. \"2's gutter + 4's tightness\".")
    print(f"{DIM}{'─'*64}{R}\n")


if __name__ == "__main__":
    main()
