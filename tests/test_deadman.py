"""
tests/test_deadman.py — the dead-man bash-fallback gate (I9, SC3).

A headless box must NEVER be left shell-less. This asserts:

  1. STARTUP: when the local service is unreachable (health check fails OR the
     wrapped-loop build raises), the bash fallback fires.
  2. MID-SESSION: when a turn raises ConnectionError (the service died mid
     session), the bash fallback fires.
  3. I2: the fallback/banner text contains NONE of the words AI / LLM / model /
     agent / agentic (case-insensitive substring check).

The exec path is exercised SAFELY: we inject a fake exec_bash that records the
banner and raises a sentinel instead of actually os.execvp-ing (which would
replace the test runner). One test additionally patches os.execvp directly to
prove the real passthrough.exec_bash routes there without replacing the runner.

Run:  python3 -m unittest tests.test_deadman -v
"""

from __future__ import annotations

import unittest

from shell import passthrough
from shell.hooks.startup import HealthResult
from shell.shell import ProductShell


# Words that must never appear in any user-facing fallback string (I2).
_FORBIDDEN_WORDS = ["ai", "llm", "model", "agent", "agentic"]


class _ExecFired(Exception):
    """Sentinel raised by the fake exec_bash so we can stop without exec()."""

    def __init__(self, banner: str) -> None:
        super().__init__("exec fired")
        self.banner = banner


def _assert_i2_clean(testcase: unittest.TestCase, text: str) -> None:
    low = text.lower()
    for word in _FORBIDDEN_WORDS:
        # Word-ish substring check. Use surrounding non-letters to avoid false
        # positives ("available" contains "ai", "normal" is fine). We check the
        # forbidden token as a standalone-ish occurrence.
        import re
        if re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", low):
            testcase.fail(f"I2 violation: forbidden word {word!r} in banner:\n{text}")


class _ShellHarness:
    """Builds a ProductShell with injected seams; records exec banners."""

    def __init__(
        self,
        *,
        health: HealthResult,
        repl_factory=None,
        lines=None,
    ) -> None:
        self.exec_banners: list[str] = []
        self.ran_commands: list[str] = []

        def fake_exec_bash(banner: str) -> None:
            self.exec_banners.append(banner)
            raise _ExecFired(banner)

        def fake_run_command(cmd: str) -> int:
            self.ran_commands.append(cmd)
            return 0

        # A line reader that yields from a script then EOFs.
        self._lines = list(lines or [])

        def fake_read_line(_prompt: str) -> str:
            if not self._lines:
                raise EOFError
            return self._lines.pop(0)

        self.shell = ProductShell(
            tier_label="radagon",
            repl_factory=repl_factory if repl_factory is not None else (lambda: object()),
            health_check=lambda: health,
            read_line=fake_read_line,
            exec_bash=fake_exec_bash,
            run_command=fake_run_command,
        )


class TestStartupFallback(unittest.TestCase):
    def test_unreachable_on_startup_fires_bash_fallback(self):
        h = _ShellHarness(
            health=HealthResult(ok=False, message="The system service is not available."),
        )
        with self.assertRaises(_ExecFired):
            h.shell.run()
        self.assertEqual(len(h.exec_banners), 1)
        self.assertIn("BASH", h.exec_banners[0])

    def test_build_repl_raising_fires_bash_fallback(self):
        def boom_factory():
            raise RuntimeError("could not start service")

        h = _ShellHarness(
            health=HealthResult(ok=True, message=""),
            repl_factory=boom_factory,
        )
        with self.assertRaises(_ExecFired):
            h.shell.run()
        self.assertEqual(len(h.exec_banners), 1)

    def test_crashing_health_probe_still_falls_back(self):
        # A probe that raises (not just returns ok=False) must STILL fall back.
        exec_banners: list[str] = []

        def fake_exec_bash(banner: str) -> None:
            exec_banners.append(banner)
            raise _ExecFired(banner)

        def boom_health() -> HealthResult:
            raise OSError("probe blew up")

        shell = ProductShell(
            tier_label="marika",
            health_check=boom_health,
            exec_bash=fake_exec_bash,
            read_line=lambda _p: (_ for _ in ()).throw(EOFError()),
        )
        with self.assertRaises(_ExecFired):
            shell.run()
        self.assertEqual(len(exec_banners), 1)

    def test_startup_banner_is_i2_clean(self):
        h = _ShellHarness(
            health=HealthResult(ok=False, message="The system service is not available."),
        )
        with self.assertRaises(_ExecFired):
            h.shell.run()
        _assert_i2_clean(self, h.exec_banners[0])


class TestMidSessionFallback(unittest.TestCase):
    def test_connection_error_mid_turn_fires_bash_fallback(self):
        class FlakyRepl:
            def run_turn(self, text: str):
                raise ConnectionError("service went away mid-session")

        h = _ShellHarness(
            health=HealthResult(ok=True, message=""),
            repl_factory=lambda: FlakyRepl(),
            lines=["why is nginx not starting"],  # routes to ENGLISH -> run_turn
        )
        with self.assertRaises(_ExecFired):
            h.shell.run()
        self.assertEqual(len(h.exec_banners), 1)
        self.assertIn("BASH", h.exec_banners[0])

    def test_midsession_banner_is_i2_clean(self):
        class FlakyRepl:
            def run_turn(self, text: str):
                raise ConnectionError("gone")

        h = _ShellHarness(
            health=HealthResult(ok=True, message=""),
            repl_factory=lambda: FlakyRepl(),
            lines=["show me failing services"],
        )
        with self.assertRaises(_ExecFired):
            h.shell.run()
        _assert_i2_clean(self, h.exec_banners[0])

    def test_non_connection_error_does_not_fire_fallback(self):
        # A generic per-turn error must NOT drop to bash — only ConnectionError
        # (service-down) is a dead-man condition. One bad turn keeps the session.
        class BadTurnRepl:
            def __init__(self):
                self.calls = 0

            def run_turn(self, text: str):
                self.calls += 1
                raise ValueError("some tool blew up")

        h = _ShellHarness(
            health=HealthResult(ok=True, message=""),
            repl_factory=lambda: BadTurnRepl(),
            lines=["show me failing services", "show me failing services"],
        )
        # Loop runs both lines then EOFs cleanly (rc 0); fallback never fires.
        rc = h.shell.run()
        self.assertEqual(rc, 0)
        self.assertEqual(h.exec_banners, [])


class TestRealExecRouting(unittest.TestCase):
    """Prove passthrough.exec_bash routes to os.execvp without replacing us."""

    def test_exec_bash_calls_execvp_safely(self):
        captured = {}

        real_execvp = passthrough.os.execvp

        def fake_execvp(file, args):
            captured["file"] = file
            captured["args"] = list(args)
            # Do NOT actually exec — just record and return.

        passthrough.os.execvp = fake_execvp  # type: ignore[assignment]
        try:
            passthrough.exec_bash("PLAIN BASH MODE banner")
        finally:
            passthrough.os.execvp = real_execvp  # type: ignore[assignment]

        self.assertEqual(captured.get("file"), "bash")
        self.assertEqual(captured.get("args"), ["bash"])


class TestBannerContent(unittest.TestCase):
    """Static check that the module banners are loud and I2-clean."""

    def test_module_banners_i2_clean_and_loud(self):
        from shell import shell as shell_mod

        for banner in (
            shell_mod._STARTUP_FALLBACK_BANNER.format(detail="x"),
            shell_mod._MIDSESSION_FALLBACK_BANNER,
        ):
            _assert_i2_clean(self, banner)
            self.assertIn("BASH", banner)  # loud + names the degraded state


if __name__ == "__main__":
    unittest.main()
