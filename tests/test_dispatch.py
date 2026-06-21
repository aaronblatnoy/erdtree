"""
tests/test_dispatch.py — the command-vs-English dispatch regression gate (SC4).

0 mis-dispatches is the gate. A false-RAW on a live box is the cardinal sin; a
false-ENGLISH is a tolerable annoyance (the wrapped loop handles it). So the
corpus asserts:
  - genuine raw commands (flags / path args / explicit "!cmd" / path invocation)
    dispatch RAW;
  - genuine English intent dispatches ENGLISH;
  - "!!" returns the TOGGLE signal.

HOST-INDEPENDENCE: the conservative heuristic depends on shutil.which (is the
first token on PATH?). To keep this corpus a PERMANENT regression gate and not a
host-flaky test, the on-PATH cases monkeypatch shutil.which deterministically.
A second class of tests pins behavior using commands that genuinely exist on
this build host (df/ls/grep/cat/pwd/whoami) as belt-and-suspenders.

Run:  python3 -m unittest tests.test_dispatch -v
"""

from __future__ import annotations

import shutil
import unittest

from shell import dispatch as dispatch_mod
from shell.dispatch import DispatchKind, dispatch


# A deterministic PATH oracle so the corpus is not host-dependent. Anything in
# this set is "on PATH"; everything else is not.
_FAKE_ON_PATH = {
    "df", "ls", "systemctl", "grep", "cat", "pwd", "whoami", "nginx",
    "journalctl", "find",
}


def _fake_which(cmd: str):
    return f"/usr/bin/{cmd}" if cmd in _FAKE_ON_PATH else None


class _DeterministicPathMixin(unittest.TestCase):
    """Patches shell.dispatch's shutil.which to the fake PATH oracle."""

    def setUp(self) -> None:
        self._real_which = shutil.which
        dispatch_mod.shutil.which = _fake_which  # type: ignore[attr-defined]

    def tearDown(self) -> None:
        dispatch_mod.shutil.which = self._real_which  # type: ignore[attr-defined]


class TestRawWithFlags(_DeterministicPathMixin):
    """First token on PATH + a flag token present -> RAW (rule 3)."""

    CASES = [
        "df -h",
        "ls -la /tmp",
        "systemctl status nginx",  # 'status'/'nginx' have no '/', but...
        "grep -r foo /etc",
    ]

    def test_flag_cases_dispatch_raw(self):
        # df -h, ls -la /tmp, grep -r foo /etc each carry a flag token.
        for line in ("df -h", "ls -la /tmp", "grep -r foo /etc"):
            with self.subTest(line=line):
                r = dispatch(line)
                self.assertIs(r.kind, DispatchKind.RAW, f"{line!r} should be RAW")
                self.assertEqual(r.command, line)

    def test_systemctl_status_nginx_is_raw_via_path_arg_or_english_safe(self):
        # "systemctl status nginx" has NO flag and NO '/', so by the conservative
        # rules it falls through to ENGLISH (safe default — the loop handles it).
        # This is explicitly NOT a mis-dispatch: a false-ENGLISH is acceptable.
        r = dispatch("systemctl status nginx")
        self.assertIs(r.kind, DispatchKind.ENGLISH)
        self.assertEqual(r.text, "systemctl status nginx")


class TestRawWithPath(_DeterministicPathMixin):
    """First token on PATH + a path-like arg ('/') -> RAW (rule 4)."""

    def test_cat_etc_fstab_is_raw(self):
        r = dispatch("cat /etc/fstab")
        self.assertIs(r.kind, DispatchKind.RAW)
        self.assertEqual(r.command, "cat /etc/fstab")

    def test_grep_with_path_is_raw(self):
        r = dispatch("grep foo /var/log/messages")
        self.assertIs(r.kind, DispatchKind.RAW)


class TestPathInvocation(unittest.TestCase):
    """First token starts with / ./ ../ -> RAW (rule 1), no PATH lookup."""

    def test_absolute_path(self):
        r = dispatch("/usr/bin/uptime")
        self.assertIs(r.kind, DispatchKind.RAW)

    def test_relative_dot_slash(self):
        r = dispatch("./build.sh --release")
        self.assertIs(r.kind, DispatchKind.RAW)

    def test_relative_dotdot_slash(self):
        r = dispatch("../scripts/run")
        self.assertIs(r.kind, DispatchKind.RAW)


class TestSingleWordOnPath(_DeterministicPathMixin):
    """First token on PATH, no flag, no path arg -> ENGLISH (rule 5, safe).

    A bare 'pwd' / 'whoami' has no structural raw signal, so the conservative
    heuristic routes it to the loop. This is a false-ENGLISH (acceptable): the
    loop will run it correctly. It is NEVER a false-RAW.
    """

    def test_pwd_is_english(self):
        r = dispatch("pwd")
        self.assertIs(r.kind, DispatchKind.ENGLISH)
        self.assertEqual(r.text, "pwd")

    def test_whoami_is_english(self):
        r = dispatch("whoami")
        self.assertIs(r.kind, DispatchKind.ENGLISH)


class TestEnglishNotOnPath(_DeterministicPathMixin):
    """First token NOT on PATH -> ENGLISH (rule 2)."""

    CASES = [
        "show me failing services",
        "why is nginx not starting",
        "install postgresql and configure it",
        "what is using all my disk",
    ]

    def test_english_cases(self):
        for line in self.CASES:
            with self.subTest(line=line):
                r = dispatch(line)
                self.assertIs(r.kind, DispatchKind.ENGLISH, f"{line!r} should be ENGLISH")
                self.assertEqual(r.text, line)

    def test_english_first_token_on_path_but_sentence(self):
        # "find me a solution" — 'find' IS on PATH, but no flag/path arg, so the
        # conservative default sends it to ENGLISH. No mis-dispatch to RAW.
        r = dispatch("find me a solution")
        self.assertIs(r.kind, DispatchKind.ENGLISH)


class TestBangCmdAlwaysRaw(unittest.TestCase):
    """'!cmd' explicit escape -> always RAW, regardless of PATH (rule: R2)."""

    def test_bang_known_command(self):
        r = dispatch("!df -h")
        self.assertIs(r.kind, DispatchKind.RAW)
        self.assertEqual(r.command, "df -h")

    def test_bang_unknown_token_still_raw(self):
        # Even an English-looking line after '!' is an EXPLICIT raw request.
        r = dispatch("!some-thing-not-on-path --weird")
        self.assertIs(r.kind, DispatchKind.RAW)
        self.assertEqual(r.command, "some-thing-not-on-path --weird")

    def test_bang_strips_only_the_prefix(self):
        r = dispatch("!echo hi")
        self.assertIs(r.kind, DispatchKind.RAW)
        self.assertEqual(r.command, "echo hi")


class TestToggle(unittest.TestCase):
    """'!!' -> TOGGLE signal (not a command)."""

    def test_double_bang_is_toggle(self):
        r = dispatch("!!")
        self.assertIs(r.kind, DispatchKind.TOGGLE)

    def test_double_bang_with_surrounding_space_is_toggle(self):
        r = dispatch("   !!   ")
        self.assertIs(r.kind, DispatchKind.TOGGLE)


class TestZeroMisdispatchCorpus(_DeterministicPathMixin):
    """The permanent gate: a labeled corpus with 0 mis-dispatches.

    The cardinal sin is a false-RAW (running a guessed command on a live box).
    This corpus asserts every English line is NOT RAW, and every raw line IS RAW.
    """

    # (input, expected_kind)
    CORPUS = [
        # genuine raw commands
        ("df -h", DispatchKind.RAW),
        ("ls -la /tmp", DispatchKind.RAW),
        ("grep -r foo /etc", DispatchKind.RAW),
        ("cat /etc/fstab", DispatchKind.RAW),
        ("/usr/bin/uptime", DispatchKind.RAW),
        ("./deploy.sh", DispatchKind.RAW),
        ("!systemctl restart nginx", DispatchKind.RAW),  # explicit escape
        # genuine English intent
        ("show me failing services", DispatchKind.ENGLISH),
        ("why is nginx not starting", DispatchKind.ENGLISH),
        ("systemctl status nginx", DispatchKind.ENGLISH),  # safe default
        ("pwd", DispatchKind.ENGLISH),
        ("whoami", DispatchKind.ENGLISH),
        ("find me a solution", DispatchKind.ENGLISH),
        # toggle
        ("!!", DispatchKind.TOGGLE),
        # cardinal-sin regression: English words with a leading dash must NOT
        # trigger raw dispatch — these are word fragments, not shell flags.
        ("cat -alyze this file", DispatchKind.ENGLISH),
        ("find -ing solutions now", DispatchKind.ENGLISH),
        ("rm -arefully delete stuff", DispatchKind.ENGLISH),
    ]

    def test_corpus_zero_misdispatch(self):
        misdispatches = []
        for line, expected in self.CORPUS:
            actual = dispatch(line).kind
            if actual is not expected:
                misdispatches.append((line, expected.name, actual.name))
        self.assertEqual(
            misdispatches, [],
            f"mis-dispatches found (gate requires 0): {misdispatches}",
        )

    def test_no_english_line_ever_dispatches_raw(self):
        # The cardinal-sin check: nothing labeled ENGLISH may become RAW.
        for line, expected in self.CORPUS:
            if expected is DispatchKind.ENGLISH:
                self.assertIsNot(
                    dispatch(line).kind, DispatchKind.RAW,
                    f"CARDINAL SIN: {line!r} mis-dispatched to RAW",
                )


if __name__ == "__main__":
    unittest.main()
