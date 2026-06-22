#!/usr/bin/env python3
"""Aesthetic preview — renders mock turns through the REAL ConsoleIO so you can
see the actual terminal look (block output, status glyphs, spacing) without a
model or a live box.

    python3 sandbox/preview.py

This mirrors the harness's display layer (core/agent/repl.py:ConsoleIO),
which ports OpenCode's BlockTool: a left-gutter panel whose title is the
command, the real command output shown verbatim below it, a green ✓ for a
confirmed write, a red ✗ for a failure, and an amber ⚠ before a destructive
confirm. On a real tty a braille spinner animates on the title line while a
slow op runs (it does not show here when stdout is piped).
"""
import os
import sys

# Import the real display layer so the preview never drifts from the product.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.agent.repl import ConsoleIO  # noqa: E402

CARET = "\033[38;5;160m$\033[0m"   # radagon deep red; marika=220, radahn=203
DIM = "\033[2m"
AMBER = "\033[33m"
R = "\033[0m"

LS = (
    "total 32K\n"
    "drwx------  5 root root 4.0K Jun 22 06:13 .\n"
    "dr-xr-xr-x  1 root root 4.0K Jun 22 14:00 ..\n"
    "-rw-r--r--  1 root root  733 Jun 22 06:03 README.txt"
)
LSBLK = (
    "NAME        SIZE TYPE MOUNTPOINT\n"
    "sda       119.2G disk\n"
    "├─sda1      100M part /boot/efi\n"
    "└─sda3    118.6G part /\n"
    "nvme0n1   931.5G disk"
)


def prompt(req):
    print(f"[root@mossad-server ~]{CARET} {req}")


def rule():
    print(f"{DIM}{'─' * 64}{R}")


def main():
    rule()

    # 1) A read: real ls output in a gutter block; no model re-typing.
    prompt("show me my file structure")
    io = ConsoleIO()
    io.begin_turn()
    io.tool_step("running: ls -lah")
    io.tool_step_result("done")
    io.tool_output(LS)
    rule()

    # 2) A multi-op rundown: two blocks, separated, then a terse synthesis.
    prompt("give me a rundown of this box")
    io = ConsoleIO()
    io.begin_turn()
    io.tool_step("running: uname -a")
    io.tool_step_result("done")
    io.tool_output("Linux mossad-server 5.14.0-427 x86_64 GNU/Linux")
    io.tool_step("running: lsblk")
    io.tool_step_result("done")
    io.tool_output(LSBLK)
    io.render("4 disks, 261 packages on Rocky 9.8. Root filesystem 4% used.")
    rule()

    # 3) A confirmed write: a single green ✓ line (no block).
    prompt("restart nginx")
    io = ConsoleIO()
    io.begin_turn()
    io._pending_confirmed = True
    io.tool_step("running: systemctl restart nginx.service")
    io.tool_step_result("done")
    io.render("nginx.service is active and running.")
    rule()

    # 4) A destructive op: amber ⚠ then the typed-word gate.
    prompt("delete the old logs directory")
    print(f"{AMBER}⚠  recursive forced file removal cannot be undone{R}")
    print(f"Type DESTROY to proceed: {DIM}(declined){R}")
    rule()

    # 5) A failed read: red ✗ in the block, then a plain one-line explanation.
    prompt("show me /opt/sandbox")
    io = ConsoleIO()
    io.begin_turn()
    io.tool_step("running: ls -lah /opt/sandbox")
    io.tool_step_result("exit 2")
    io.render("The /opt/sandbox directory does not exist on this host.")
    rule()


if __name__ == "__main__":
    main()
