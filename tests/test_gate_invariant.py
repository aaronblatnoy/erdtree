"""Deterministic gate sweep: NO write or destructive operation in the registry
can execute without confirmation, whatever the model emits.

This is the runtime guarantee behind the product rule.  The model is not
trained to ask permission (corpus v2 dropped the confirm turns); the REPL's
permission gate is the only thing that asks, and it is code.
"""
from __future__ import annotations

import json

import pytest

import importlib, pkgutil
import core.tools
for _m in pkgutil.iter_modules(core.tools.__path__):
    importlib.import_module(f"core.tools.{_m.name}")  # registers every tool
from core.tools import registry, ToolResult
from core.agent.audit import AuditLog
from core.agent.permissions import OpClass
from core.agent.repl import Repl
from tests.test_repl import FakeContext, FakeIO, ScriptedResponder


def _example_args(spec, op_name):
    op = spec.ops[op_name]
    args = {"operation": op_name}
    for a in op.args:
        if not a.required:
            continue
        args[a.name] = {str: "example", int: 1, bool: True, list: ["example"]}.get(a.type, "example")
    return args


def _non_read_ops():
    for name in registry.list_tools():
        spec = registry.get(name)
        for op_name in spec.ops:
            if spec.permission_class_for(op_name) is not OpClass.READ:
                yield name, op_name


@pytest.mark.parametrize("tool,op", list(_non_read_ops()))
def test_non_read_op_never_dispatches_without_confirmation(tmp_path, monkeypatch, tool, op):
    dispatched = []

    def fake_dispatch(t, o, a):
        dispatched.append((t, o))
        return ToolResult(exit_code=0, stdout="ok", stderr="", summary="ok")

    monkeypatch.setattr(registry, "dispatch", fake_dispatch)
    spec = registry.get(tool)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": tool, "arguments": json.dumps(_example_args(spec, op))}]),
        ("done", []),
    ])
    for interactive, io in ((True, FakeIO(confirm=False, typed_ok=False)), (False, FakeIO(confirm=True, typed_ok=True))):
        dispatched.clear()
        repl = Repl(registry=registry, responder=responder, audit=AuditLog(str(tmp_path / f"a-{interactive}.jsonl")),
                    context=FakeContext(), io=io, tier_label="t", interactive=interactive)
        responder._i = 0
        repl.run_turn(f"{tool} {op}")
        assert dispatched == [], f"{tool}.{op} executed without confirmation (interactive={interactive})"
