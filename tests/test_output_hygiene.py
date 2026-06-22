"""Render-layer output hygiene: the terminal shows clean plain text even when
the model emits markdown or chatbot fluff.

These pin the deterministic, render-time cleanup that keeps Erdtree output
terminal-native (matching docs/OUTPUT_SPEC.md) regardless of which small model
is wired underneath:

  - _strip_markdown: removes code fences, inline backticks, bullet/header
    markers, and bold/italic emphasis (a raw terminal is not a doc renderer).
  - _CHATBOT_TRAILER: removes a TRAILING offer of more interaction
    ("Would you like more detail?", "Let me know if...") WITHOUT eating genuine
    sysadmin advice ("If you need to change it, edit sshd_config.").
  - router salvage: a tool call emitted as JSON text in `content` (a common
    small-model failure) is routed as a real call, not printed raw.
"""

from __future__ import annotations

import json

from core.agent.audit import AuditLog
from core.agent.repl import Repl, ConsoleIO, _strip_markdown
from core.agent.router import Router, TurnKind
from core.tools import registry, ToolResult
import core.tools.files  # noqa: F401  (register the files tool)
import core.tools.services  # noqa: F401

from tests.test_repl import FakeContext, ScriptedResponder


_LS_OUTPUT = (
    "total 32K\n"
    "drwx------  5 root root 4.0K Jun 22 06:13 .\n"
    "dr-xr-xr-x  1 root root 4.0K Jun 22 14:00 ..\n"
    "-rw-r--r--  1 root root  733 Jun 22 06:03 README.txt"
)


class CapIO:
    """Captures render() and tool_output() so the suppression rule is testable."""

    def __init__(self):
        self.rendered: list[str] = []
        self.outputs: list[str] = []

    def render(self, text):
        self.rendered.append(text)

    def confirm(self, prompt):
        return True

    def confirm_typed(self, prompt, word):
        return True

    def tool_output(self, text):
        self.outputs.append(text)


def _read_repl(tmp_path, monkeypatch, responder, io, stdout):
    def fake_dispatch(tool, op, args):
        return ToolResult(exit_code=0, stdout=stdout, stderr="", summary=f"{tool} {op}")
    monkeypatch.setattr(registry, "dispatch", fake_dispatch)
    audit = AuditLog(str(tmp_path / "audit.jsonl"))
    return Repl(registry=registry, responder=responder, audit=audit,
                context=FakeContext(), io=io, tier_label="t", interactive=True), audit


# --------------------------------------------------------------------------- #
# Markdown stripping                                                            #
# --------------------------------------------------------------------------- #

def test_strips_code_fences_keeping_content():
    out = _strip_markdown("Here:\n```\nls -lah\n```")
    assert "```" not in out
    assert "ls -lah" in out


def test_strips_inline_backticks():
    assert _strip_markdown("The `/opt/sandbox` directory") == "The /opt/sandbox directory"


def test_strips_bullet_and_header_markers():
    out = _strip_markdown("# Heading\n- one\n- two\n* three")
    assert "#" not in out
    assert out.count("one") == 1
    assert not any(line.lstrip().startswith(("-", "*", "#")) for line in out.splitlines())


def test_strips_bold_and_italic():
    assert _strip_markdown("**bold** and *italic*") == "bold and italic"


def test_plain_text_unchanged():
    plain = "nginx.service is active and running."
    assert _strip_markdown(plain) == plain


# --------------------------------------------------------------------------- #
# Chatbot trailer stripping (narrow on purpose)                                 #
# --------------------------------------------------------------------------- #

def test_strips_would_you_like_trailer():
    out = _strip_markdown(
        "Disk usage is 4%.\n\nWould you like more information on the filesystems?"
    )
    assert "Would you like" not in out
    assert out == "Disk usage is 4%."


def test_strips_inline_would_you_like_after_sentence():
    out = _strip_markdown(
        "The mount point looks wrong. Would you like more details on any device?"
    )
    assert out == "The mount point looks wrong."


def test_strips_let_me_know_trailer():
    out = _strip_markdown("Port 22 is open. Let me know if you want the ruleset.")
    assert out == "Port 22 is open."


def test_preserves_genuine_sysadmin_advice():
    # "If you need to change it, edit sshd_config." is actionable advice, NOT a
    # chatbot offer — it must survive.
    text = "The default SSH port is 22. If you need to change it, edit sshd_config."
    assert _strip_markdown(text) == text


def test_preserves_imperative_followups():
    text = "3 services failed: sshd, nginx, postgresql. Restart them with systemctl."
    assert _strip_markdown(text) == text


# --------------------------------------------------------------------------- #
# Router salvage: JSON tool call emitted as content text                        #
# --------------------------------------------------------------------------- #

def test_router_salvages_json_tool_call_in_content():
    router = Router(registry)
    # A small model wrote the tool call as JSON text instead of via tool_calls[].
    content = '{"name": "files", "arguments": {"operation": "list", "path": "/home"}}'
    result = router.route(content=content, tool_calls=[])
    assert result.kind is TurnKind.TOOL_CALL
    assert len(result.calls) == 1
    assert result.calls[0].tool == "files"
    assert result.calls[0].operation == "list"


def test_router_plain_english_still_english():
    router = Router(registry)
    result = router.route(content="nginx is running fine.", tool_calls=[])
    assert result.kind is TurnKind.ENGLISH


def test_router_non_json_brace_text_is_english():
    router = Router(registry)
    # Looks like it starts with a brace but isn't a tool call — stays English.
    result = router.route(content="{this is not json", tool_calls=[])
    assert result.kind is TurnKind.ENGLISH


# --------------------------------------------------------------------------- #
# Real read output shown verbatim; the model's re-typing suppressed            #
# --------------------------------------------------------------------------- #

_LS_CALL = {"id": "c1", "name": "files",
            "arguments": json.dumps({"operation": "list", "path": "/root"})}


def test_read_output_shown_verbatim_and_retype_suppressed(tmp_path, monkeypatch):
    # The model runs ls, then re-types the listing as bulky prose. The harness
    # must show the REAL stdout and DROP the re-typing (a data echo).
    responder = ScriptedResponder([
        ("", [_LS_CALL]),
        ("The file structure is as follows:\n.\n..\nREADME.txt\n"
         "The directory contains 3 entries including . and ..", []),
    ])
    io = CapIO()
    repl, audit = _read_repl(tmp_path, monkeypatch, responder, io, _LS_OUTPUT)
    outcome = repl.run_turn("show me my files")
    audit.close()

    # Real ls output was displayed verbatim.
    assert io.outputs == [_LS_OUTPUT]
    assert outcome.read_output_shown is True
    # The bulky re-typing was NOT rendered (the real output above is the answer).
    assert io.rendered == []


def test_terse_insight_kept_even_with_read_output(tmp_path, monkeypatch):
    # A short diagnosis is genuine added value — it must survive even though
    # read output was shown (the nginx "port conflict" case).
    responder = ScriptedResponder([
        ("", [_LS_CALL]),
        ("README.txt is the only non-dotfile here.", []),
    ])
    io = CapIO()
    repl, audit = _read_repl(tmp_path, monkeypatch, responder, io, _LS_OUTPUT)
    repl.run_turn("anything interesting in my files?")
    audit.close()

    assert io.outputs == [_LS_OUTPUT]
    # The terse insight WAS rendered.
    assert io.rendered == ["README.txt is the only non-dotfile here."]


def test_io_without_tool_output_hook_still_works(tmp_path, monkeypatch):
    # BACK-COMPAT: an IO with no tool_output hook degrades to a no-op; the
    # model's answer is rendered as before (no read output was displayable).
    class BareIO:
        def __init__(self):
            self.rendered = []

        def render(self, text):
            self.rendered.append(text)

        def confirm(self, prompt):
            return True

        def confirm_typed(self, prompt, word):
            return True

    responder = ScriptedResponder([
        ("", [_LS_CALL]),
        ("done.", []),
    ])
    io = BareIO()
    repl, audit = _read_repl(tmp_path, monkeypatch, responder, io, _LS_OUTPUT)
    outcome = repl.run_turn("show me my files")
    audit.close()

    # No tool_output hook -> read_output_shown stays False -> answer rendered.
    assert outcome.read_output_shown is False
    assert io.rendered == ["done."]


# --------------------------------------------------------------------------- #
# Block rendering (ConsoleIO) — the OpenCode BlockTool port                      #
# --------------------------------------------------------------------------- #

def _plain(s: str) -> str:
    # Strip ANSI so assertions read cleanly.
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def test_read_renders_as_gutter_block(capsys):
    io = ConsoleIO(interactive=True)
    io.begin_turn()
    io.tool_step("running: ls -lah")
    io.tool_step_result("done")
    io.tool_output("total 4\n-rw-r--r-- README.txt")
    out = _plain(capsys.readouterr().out)
    # Title line (the command) and output lines all carry the │ gutter.
    assert "│ ls -lah" in out
    assert "│ total 4" in out
    assert "│ -rw-r--r-- README.txt" in out


def test_consecutive_blocks_separated_by_blank_line(capsys):
    io = ConsoleIO(interactive=True)
    io.begin_turn()
    io.tool_step("running: uname -a"); io.tool_step_result("done"); io.tool_output("Linux box")
    io.tool_step("running: lsblk"); io.tool_step_result("done"); io.tool_output("sda 119G")
    out = _plain(capsys.readouterr().out)
    # A blank line precedes the second block's title.
    assert "Linux box\n\n│ lsblk" in out


def test_write_success_is_check_line_not_block(capsys):
    io = ConsoleIO(interactive=True)
    io.begin_turn()
    io._pending_confirmed = True  # a confirmed write
    io.tool_step("running: systemctl restart nginx.service")
    io.tool_step_result("done")
    out = _plain(capsys.readouterr().out)
    assert "✓ systemctl restart nginx.service" in out
    assert "│" not in out  # writes are not blocks


def test_read_error_shown_in_block(capsys):
    io = ConsoleIO(interactive=True)
    io.begin_turn()
    io.tool_step("running: ls -lah /opt/sandbox")
    io.tool_step_result("exit 2")
    out = _plain(capsys.readouterr().out)
    assert "│ ls -lah /opt/sandbox" in out
    assert "✗ exit 2" in out


def test_long_output_capped_with_note(capsys):
    io = ConsoleIO(interactive=True)
    io.begin_turn()
    io.tool_step("running: cat big.txt")
    io.tool_step_result("done")
    io.tool_output("\n".join(f"line {i}" for i in range(200)))
    out = _plain(capsys.readouterr().out)
    assert "more line" in out  # truncation note present
    assert "line 199" not in out  # the tail was capped
