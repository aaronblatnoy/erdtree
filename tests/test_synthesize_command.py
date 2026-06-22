"""tests/test_synthesize_command.py — THE GATE (Phase 6 consolidation, P6.8).

This is the load-bearing correctness test for the classifier bridge. For EVERY
(tool, op) across all 7 Phase-6 tools (network, firewall, users, disk,
processes, hardware, files) plus the docs reference tool, it asserts that:

    synthesize_command(ParsedCall(...))  ->  permissions.classify(...)

yields the intended OpClass + Gate. The permission seam (core.agent.permissions)
is the single hardened classifier; P6 only SYNTHESIZES the right command string
so its existing logic fires. We never re-implement or weaken the classifier here.

The keystone assertions (SC-P6.2 / SC-P6.3): the lockout / data-loss set
  firewall.panic_on; users.lock/delete/remove_from_privgroup;
  disk.format/partition/wipe/dd_write; processes.signal(kill -1); files.remove -rf
ALL classify DESTRUCTIVE -> CONFIRM_TYPED in an interactive context, and REFUSE
under a non-interactive ExecContext (no one present to type the word in full).

Read ops (incl. docs.retrieve) classify READ -> ALLOW so a pure read runs with
no gate friction.

I2: this test also imports core.agent.prompt._FORBIDDEN_AI_TERMS (the canonical
filter) and asserts every advertised schema (name + description + parameters)
is clean of AI/LLM/model/agent language.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

# Import side-effect: register all 10 core tools + docs.
import core.agent.main  # noqa: F401  (registers tools on import)

from core.agent.permissions import ExecContext, Gate, OpClass, classify
from core.agent.prompt import _FORBIDDEN_AI_TERMS
from core.agent.repl import synthesize_command
from core.agent.router import ParsedCall, registry_schemas
from core.tools import registry

INTERACTIVE = ExecContext(interactive=True)
NON_INTERACTIVE = ExecContext(interactive=False)


def _call(tool: str, op: str, args: dict) -> ParsedCall:
    """Build a ParsedCall the way the router would, with the declared class."""
    pc = registry.permission_class_for(tool, op) or OpClass.WRITE
    return ParsedCall(call_id="t", tool=tool, operation=op, args=args, permission_class=pc)


def _gate_of(tool: str, op: str, args: dict, ctx: ExecContext) -> Gate:
    return classify(synthesize_command(_call(tool, op, args)), ctx).gate


def _class_of(tool: str, op: str, args: dict) -> OpClass:
    return classify(synthesize_command(_call(tool, op, args)), INTERACTIVE).op_class


# ---------------------------------------------------------------------------
# The exhaustive (tool, op) -> (OpClass, interactive Gate) expectation table.
# ---------------------------------------------------------------------------
# Each row: (tool, op, args, expected_OpClass, expected_interactive_Gate).
# Non-interactive expectations are DERIVED: READ -> ALLOW, everything else ->
# REFUSE (the classifier refuses any write/destructive without a human present).
_CASES: list[tuple[str, str, dict, OpClass, Gate]] = [
    # ---- docs (READ) ----
    ("docs", "retrieve", {"query": "how do I mount a disk", "k": 3}, OpClass.READ, Gate.ALLOW),
    # a query whose text contains words that ARE classifier write-shapes must
    # still classify READ (the sentinel must not splice user text into the gate):
    ("docs", "retrieve", {"query": "rm mount nmcli userdel mkfs"}, OpClass.READ, Gate.ALLOW),

    # ---- hardware (ALL READ) ----
    ("hardware", "cpu", {}, OpClass.READ, Gate.ALLOW),
    ("hardware", "memory", {}, OpClass.READ, Gate.ALLOW),
    ("hardware", "pci", {}, OpClass.READ, Gate.ALLOW),
    ("hardware", "usb", {}, OpClass.READ, Gate.ALLOW),
    ("hardware", "block", {}, OpClass.READ, Gate.ALLOW),
    ("hardware", "sensors", {}, OpClass.READ, Gate.ALLOW),
    ("hardware", "summary", {}, OpClass.READ, Gate.ALLOW),

    # ---- disk ----
    ("disk", "usage", {"path": "/"}, OpClass.READ, Gate.ALLOW),
    ("disk", "list", {"device": "/dev/sdb"}, OpClass.READ, Gate.ALLOW),
    ("disk", "smart", {"device": "/dev/sdb"}, OpClass.READ, Gate.ALLOW),
    ("disk", "mount", {"device": "/dev/sdb1", "mount_point": "/mnt"}, OpClass.WRITE, Gate.CONFIRM),
    ("disk", "unmount", {"target": "/mnt"}, OpClass.WRITE, Gate.CONFIRM),
    ("disk", "format", {"device": "/dev/sdb", "fstype": "xfs"}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),
    ("disk", "partition", {"device": "/dev/sdb", "command": ["mklabel", "gpt"]}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),
    ("disk", "wipe", {"device": "/dev/sdb"}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),
    ("disk", "dd_write", {"source": "/tmp/img", "device": "/dev/sdb", "bs": "4M"}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),

    # ---- users ----
    ("users", "list", {}, OpClass.READ, Gate.ALLOW),
    ("users", "info", {"user": "bob"}, OpClass.READ, Gate.ALLOW),
    ("users", "add", {"user": "bob"}, OpClass.WRITE, Gate.CONFIRM),
    ("users", "set_shell", {"user": "bob", "shell": "/bin/bash"}, OpClass.WRITE, Gate.CONFIRM),
    ("users", "add_to_group", {"user": "bob", "group": "docker"}, OpClass.WRITE, Gate.CONFIRM),
    ("users", "lock", {"user": "bob"}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),
    ("users", "delete", {"user": "bob"}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),
    ("users", "remove_from_privgroup", {"user": "bob"}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),

    # ---- firewall ----
    ("firewall", "list", {"zone": "public"}, OpClass.READ, Gate.ALLOW),
    ("firewall", "get_zones", {}, OpClass.READ, Gate.ALLOW),
    ("firewall", "query", {"service": "ssh", "zone": "public"}, OpClass.READ, Gate.ALLOW),
    ("firewall", "add_service", {"service": "http", "zone": "public"}, OpClass.WRITE, Gate.CONFIRM),
    ("firewall", "add_port", {"port": "8080/tcp"}, OpClass.WRITE, Gate.CONFIRM),
    ("firewall", "remove_service", {"service": "http"}, OpClass.WRITE, Gate.CONFIRM),
    ("firewall", "remove_port", {"port": "8080/tcp"}, OpClass.WRITE, Gate.CONFIRM),
    ("firewall", "reload", {}, OpClass.WRITE, Gate.CONFIRM),
    ("firewall", "set_default_zone", {"zone": "public"}, OpClass.WRITE, Gate.CONFIRM),
    ("firewall", "panic_on", {}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),

    # ---- network ----
    ("network", "show", {}, OpClass.READ, Gate.ALLOW),
    ("network", "status", {}, OpClass.READ, Gate.ALLOW),
    ("network", "connections", {}, OpClass.READ, Gate.ALLOW),
    ("network", "interfaces", {}, OpClass.READ, Gate.ALLOW),
    ("network", "wifi", {}, OpClass.READ, Gate.ALLOW),
    ("network", "bring_up", {"interface": "eth0"}, OpClass.WRITE, Gate.CONFIRM),
    ("network", "set_ip", {"interface": "eth0", "address": "1.2.3.4/24"}, OpClass.WRITE, Gate.CONFIRM),
    # network.bring_down: DESTRUCTIVE — permissions.py now has an explicit rule
    # for `ip link set <if> down` (lockout risk on SSH sessions).
    # gated, REFUSE non-interactively — never auto-run.
    ("network", "bring_down", {"interface": "eth0"}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),

    # ---- processes ----
    ("processes", "list", {}, OpClass.READ, Gate.ALLOW),
    ("processes", "tree", {}, OpClass.READ, Gate.ALLOW),
    ("processes", "top", {}, OpClass.READ, Gate.ALLOW),
    ("processes", "info", {"pid": 123}, OpClass.READ, Gate.ALLOW),
    ("processes", "renice", {"pid": 123, "priority": 5}, OpClass.WRITE, Gate.CONFIRM),
    ("processes", "signal", {"pid": 123}, OpClass.WRITE, Gate.CONFIRM),
    ("processes", "signal", {"pid": 123, "signal_num": 9}, OpClass.WRITE, Gate.CONFIRM),
    # kill -1 (signal every process) -> DESTRUCTIVE.
    ("processes", "signal", {"pid": 1, "signal_num": -1}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),

    # ---- files ----
    ("files", "list", {"path": "/var/log"}, OpClass.READ, Gate.ALLOW),
    ("files", "read", {"path": "/etc/hosts"}, OpClass.READ, Gate.ALLOW),
    ("files", "stat", {"path": "/etc/hosts"}, OpClass.READ, Gate.ALLOW),
    ("files", "find", {"path": "/var/log", "name": "*.log"}, OpClass.READ, Gate.ALLOW),
    ("files", "copy", {"src": "/a", "dst": "/b"}, OpClass.WRITE, Gate.CONFIRM),
    ("files", "move", {"src": "/a", "dst": "/b"}, OpClass.WRITE, Gate.CONFIRM),
    ("files", "mkdir", {"path": "/a/b"}, OpClass.WRITE, Gate.CONFIRM),
    ("files", "chmod", {"mode": "644", "path": "/a"}, OpClass.WRITE, Gate.CONFIRM),
    ("files", "chown", {"owner": "root", "path": "/a"}, OpClass.WRITE, Gate.CONFIRM),
    ("files", "write", {"path": "/a", "content": "x"}, OpClass.WRITE, Gate.CONFIRM),
    ("files", "remove", {"path": "/tmp/scratch"}, OpClass.WRITE, Gate.CONFIRM),
    # recursive + forced removal -> DESTRUCTIVE.
    ("files", "remove", {"path": "/srv/data", "recursive": True, "force": True}, OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED),
]


class TestEverySynthesizedGate(unittest.TestCase):
    """Every (tool, op) maps to its intended OpClass + Gate, both contexts."""

    def test_all_pairs(self) -> None:
        for tool, op, args, exp_class, exp_gate in _CASES:
            with self.subTest(tool=tool, op=op, args=args):
                cmd = synthesize_command(_call(tool, op, args))
                d_i = classify(cmd, INTERACTIVE)
                self.assertEqual(
                    d_i.op_class, exp_class,
                    f"{tool}.{op} synthesized {cmd!r} classified {d_i.op_class} "
                    f"(expected {exp_class})",
                )
                self.assertEqual(
                    d_i.gate, exp_gate,
                    f"{tool}.{op} synthesized {cmd!r} gate {d_i.gate} "
                    f"(expected {exp_gate})",
                )
                # Non-interactive: reads still ALLOW; everything else REFUSE.
                d_n = classify(cmd, NON_INTERACTIVE)
                exp_n = Gate.ALLOW if exp_class is OpClass.READ else Gate.REFUSE
                self.assertEqual(
                    d_n.gate, exp_n,
                    f"{tool}.{op} non-interactive gate {d_n.gate} (expected {exp_n})",
                )

    def test_no_read_op_is_ever_gated(self) -> None:
        """Every READ op must auto-clear (I8 — reads feel instant)."""
        for tool, op, args, exp_class, _ in _CASES:
            if exp_class is not OpClass.READ:
                continue
            with self.subTest(tool=tool, op=op):
                d = classify(synthesize_command(_call(tool, op, args)), INTERACTIVE)
                self.assertEqual(d.gate, Gate.ALLOW)
                self.assertTrue(d.auto_ok)


class TestDestructiveLockoutSet(unittest.TestCase):
    """SC-P6.2 / SC-P6.3: the lockout / data-loss keystone.

    Every member classifies DESTRUCTIVE -> CONFIRM_TYPED interactively AND
    REFUSE under a non-interactive context (no human to type the word in full).
    """

    # (tool, op, args) — the canonical lockout/data-loss set.
    _DESTRUCTIVE_SET: list[tuple[str, str, dict]] = [
        ("firewall", "panic_on", {}),
        ("users", "lock", {"user": "bob"}),
        ("users", "delete", {"user": "bob"}),
        ("users", "remove_from_privgroup", {"user": "bob"}),
        ("disk", "format", {"device": "/dev/sdb", "fstype": "ext4"}),
        ("disk", "partition", {"device": "/dev/sdb", "command": ["mklabel", "gpt"]}),
        ("disk", "wipe", {"device": "/dev/sdb"}),
        ("disk", "dd_write", {"source": "/tmp/x.img", "device": "/dev/sdb"}),
        ("processes", "signal", {"pid": 1, "signal_num": -1}),
        ("files", "remove", {"path": "/srv/data", "recursive": True, "force": True}),
    ]

    def test_destructive_confirm_typed_interactive(self) -> None:
        for tool, op, args in self._DESTRUCTIVE_SET:
            with self.subTest(tool=tool, op=op):
                d = classify(synthesize_command(_call(tool, op, args)), INTERACTIVE)
                self.assertEqual(d.op_class, OpClass.DESTRUCTIVE)
                self.assertEqual(d.gate, Gate.CONFIRM_TYPED)
                self.assertEqual(d.confirm_word, "DESTROY")
                self.assertFalse(d.auto_ok)

    def test_destructive_refuse_non_interactive(self) -> None:
        for tool, op, args in self._DESTRUCTIVE_SET:
            with self.subTest(tool=tool, op=op):
                d = classify(synthesize_command(_call(tool, op, args)), NON_INTERACTIVE)
                self.assertEqual(d.gate, Gate.REFUSE)
                self.assertFalse(d.auto_ok)

    def test_recursive_remove_escalates_but_plain_remove_does_not(self) -> None:
        plain = classify(synthesize_command(
            _call("files", "remove", {"path": "/tmp/scratch"})), INTERACTIVE)
        self.assertEqual(plain.op_class, OpClass.WRITE)
        rec = classify(synthesize_command(
            _call("files", "remove", {"path": "/tmp/x", "recursive": True})), INTERACTIVE)
        self.assertEqual(rec.op_class, OpClass.DESTRUCTIVE)


class TestDocsRead(unittest.TestCase):
    """docs.retrieve is a pure READ -> ALLOW, regardless of query text."""

    def test_docs_read_allow(self) -> None:
        for q in ("how to restart nginx", "rm -rf semantics", "mkfs and wipefs"):
            with self.subTest(query=q):
                d = classify(synthesize_command(
                    _call("docs", "retrieve", {"query": q})), INTERACTIVE)
                self.assertEqual(d.op_class, OpClass.READ)
                self.assertEqual(d.gate, Gate.ALLOW)
                self.assertTrue(d.auto_ok)

    def test_docs_read_allow_non_interactive(self) -> None:
        d = classify(synthesize_command(
            _call("docs", "retrieve", {"query": "x"})), NON_INTERACTIVE)
        self.assertEqual(d.gate, Gate.ALLOW)


class TestEveryRegisteredOpCovered(unittest.TestCase):
    """No (tool, op) on a P6/docs tool may be left unverified by _CASES."""

    _P6_TOOLS = (
        "network", "firewall", "users", "disk",
        "processes", "hardware", "files", "docs",
    )

    def test_every_op_has_a_case(self) -> None:
        covered = {(t, o) for (t, o, *_rest) in _CASES}
        for tool in self._P6_TOOLS:
            spec = registry.get(tool)
            self.assertIsNotNone(spec, f"tool {tool} not registered")
            for op in spec.ops:
                self.assertIn(
                    (tool, op), covered,
                    f"{tool}.{op} has no synthesize-command gate assertion",
                )


class TestRegistryAndSchemas(unittest.TestCase):
    """One-shot: importing all tools yields the full 10 + docs; schemas build
    clean with zero I2-forbidden terms in any user-facing string."""

    _EXPECTED = {
        # the original three
        "services", "packages", "logs",
        # the seven Phase-6 tools
        "network", "firewall", "users", "disk", "processes", "hardware", "files",
        # the docs reference tool
        "docs",
    }

    def test_registry_has_full_set(self) -> None:
        tools = set(registry.list_tools())
        self.assertEqual(
            tools, self._EXPECTED,
            f"registry mismatch: missing {self._EXPECTED - tools}, "
            f"extra {tools - self._EXPECTED}",
        )
        # The full 10 operator tools + docs == 11 entries.
        self.assertEqual(len(registry.list_tools()), 11)

    def test_schemas_build_clean(self) -> None:
        schemas = registry_schemas(registry)
        self.assertEqual(len(schemas), 11)
        for s in schemas:
            self.assertIn("name", s)
            self.assertIn("description", s)
            self.assertIn("parameters", s)
            self.assertIsInstance(s["parameters"], dict)

    def test_no_forbidden_ai_terms_in_advertised_strings(self) -> None:
        """Every advertised schema string (name, description, nested param
        descriptions) is clean of the canonical I2 forbidden-term list."""
        import re

        terms = sorted(_FORBIDDEN_AI_TERMS)
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.IGNORECASE
        )

        def _scan(value: object, path: str) -> None:
            if isinstance(value, str):
                m = pattern.search(value)
                if m is not None:
                    self.fail(f"I2 forbidden term {m.group()!r} at {path}: {value!r}")
            elif isinstance(value, dict):
                for k, v in value.items():
                    _scan(v, f"{path}.{k}")
            elif isinstance(value, (list, tuple)):
                for idx, v in enumerate(value):
                    _scan(v, f"{path}[{idx}]")

        for s in registry_schemas(registry):
            _scan(s, s.get("name", "<schema>"))

    def test_tool_descriptions_and_op_descriptions_clean(self) -> None:
        """Belt-and-suspenders: the raw ToolSpec/OpSpec descriptions are also
        I2-clean (descriptions are surfaced to the operator)."""
        import re

        pattern = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in sorted(_FORBIDDEN_AI_TERMS)) + r")\b",
            re.IGNORECASE,
        )
        for name in registry.list_tools():
            spec = registry.get(name)
            self.assertIsNone(pattern.search(spec.description or ""),
                              f"tool {name} description trips I2: {spec.description!r}")
            for op_name, op in spec.ops.items():
                self.assertIsNone(
                    pattern.search(op.description or ""),
                    f"{name}.{op_name} op description trips I2: {op.description!r}",
                )


class TestGrepGate(unittest.TestCase):
    """No P6 tool may import psutil/pyroute2 or call shutil.rmtree / os.remove
    directly. Subprocess via run_subprocess is the ONLY sanctioned path (it is
    the only one the classifier can reason about)."""

    _TOOL_FILES = (
        "network", "firewall", "users", "disk",
        "processes", "hardware", "files", "docs",
    )

    def _tool_path(self, name: str) -> pathlib.Path:
        return pathlib.Path(__file__).resolve().parent.parent / "core" / "tools" / f"{name}.py"

    def test_no_forbidden_imports_or_direct_destructive_calls(self) -> None:
        for name in self._TOOL_FILES:
            path = self._tool_path(name)
            self.assertTrue(path.exists(), f"missing tool file {path}")
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(path))

            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])

            for banned in ("psutil", "pyroute2"):
                self.assertNotIn(
                    banned, imported,
                    f"{name}.py imports forbidden module {banned!r}",
                )

            # No direct shutil.rmtree / os.remove / os.unlink / os.rmdir calls:
            # destructive mutation must go through run_subprocess so the gate
            # (which keys off the synthesized command string) can see it.
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        qualified = f"{node.value.id}.{node.attr}"
                        self.assertNotIn(
                            qualified,
                            {"shutil.rmtree", "os.remove", "os.unlink", "os.rmdir"},
                            f"{name}.py calls {qualified} directly "
                            "(must use run_subprocess)",
                        )


if __name__ == "__main__":
    unittest.main()
