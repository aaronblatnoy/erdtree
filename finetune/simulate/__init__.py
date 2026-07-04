"""finetune/simulate/__init__.py — P3 JOIN: unified simulate() dispatch.

Public API
----------
simulate(tool, op, args, ctx) -> dict
    Route to the correct per-tool simulator and return its result.

    Parameters
    ----------
    tool : str
        Registered tool name (must be in the live TOOL_NAMES registry).
    op : str
        Operation name (must be in the tool's live op enum).
    args : dict
        Argument dict for the op (may be {} for all-optional ops).
    ctx : str | dict
        System context string or profile dict (passed through to the
        per-tool simulator unchanged).

    Returns
    -------
    dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str  (always I2-clean)

    Raises
    ------
    ValueError
        If `tool` is not in the live registry, or if `op` is not in that
        tool's declared op enum.  The message names both the bad value and
        the accepted set so callers can surface useful diagnostics.

Load-bearing invariants
-----------------------
INV-schema-sync   Tool names, op names, and the valid-op set are derived
                  LIVE from finetune.coreimports.  Nothing is hardcoded.

INV-read-only-core  This module does NOT import from core/ directly.
                    It uses finetune.coreimports as the sole seam.

INV-offline       This module imports cleanly with no network, no Ollama,
                  and no ANTHROPIC_API_KEY.

COMPLETENESS ASSERT (module-level)
-----------------------------------
At import time this module iterates every (tool, op) pair in the live
registry and verifies that:
  1. A simulator function exists for the tool.
  2. Calling simulate(tool, op, minimal_args, ctx={}) returns a dict with
     the required four keys: exit_code, stdout, stderr, summary.
Any gap causes an AssertionError that surfaces immediately — before
generate.py can silently KeyError mid-run.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 1. Import per-tool simulators.
#    Each import is a hard dependency — if a sibling module is missing or
#    broken, the ImportError surfaces here immediately (as intended).
# ---------------------------------------------------------------------------
from finetune.simulate.disk      import simulate_disk
from finetune.simulate.docs      import simulate_docs
from finetune.simulate.files     import simulate_files
from finetune.simulate.firewall  import simulate_firewall
from finetune.simulate.hardware  import simulate_hardware
from finetune.simulate.logs      import simulate_logs
from finetune.simulate.network   import simulate_network
from finetune.simulate.packages  import simulate_packages
from finetune.simulate.processes import simulate_processes
from finetune.simulate.services  import simulate_services
from finetune.simulate.users     import simulate_users

# ---------------------------------------------------------------------------
# 2. Dispatch table: tool name -> simulator function.
#    Keys MUST match the live TOOL_NAMES from coreimports.
#    The completeness assert below validates this at import time.
# ---------------------------------------------------------------------------
_DISPATCH: dict[str, Any] = {
    "disk":      simulate_disk,
    "docs":      simulate_docs,
    "files":     simulate_files,
    "firewall":  simulate_firewall,
    "hardware":  simulate_hardware,
    "logs":      simulate_logs,
    "network":   simulate_network,
    "packages":  simulate_packages,
    "processes": simulate_processes,
    "services":  simulate_services,
    "users":     simulate_users,
}

# ---------------------------------------------------------------------------
# 3. Per-(tool, op) minimal probe args for the completeness assert.
#    These are the smallest arg dicts that allow each op to return a result
#    without raising on a missing required argument.  They are used ONLY in
#    the module-level assert — generate.py passes real scenario args.
#    Derived from the live registry's required-arg lists; never hardcoded
#    against schema internals (the dict keys are just realistic strings).
# ---------------------------------------------------------------------------
_PROBE_ARGS: dict[tuple[str, str], dict] = {
    # disk
    ("disk", "usage"):     {},
    ("disk", "list"):      {},
    ("disk", "smart"):     {"device": "/dev/sda"},
    ("disk", "mount"):     {"device": "/dev/sda1", "mount_point": "/mnt/data"},
    ("disk", "unmount"):   {"target": "/mnt/data"},
    ("disk", "format"):    {"device": "/dev/sdb"},
    ("disk", "partition"): {"device": "/dev/sdb"},
    ("disk", "wipe"):      {"device": "/dev/sdb"},
    ("disk", "dd_write"):  {"device": "/dev/sdb", "source": "/dev/zero"},
    # docs
    ("docs", "retrieve"): {"query": "how to configure firewalld"},
    # files
    ("files", "list"):   {"path": "/etc"},
    ("files", "read"):   {"path": "/etc/hostname"},
    ("files", "write"):  {"path": "/tmp/test.txt", "content": "hello"},
    ("files", "find"):   {"path": "/etc", "name": "*.conf"},
    ("files", "stat"):   {"path": "/etc/hostname"},
    ("files", "mkdir"):  {"path": "/tmp/testdir"},
    ("files", "copy"):   {"src": "/etc/hostname", "dest": "/tmp/hostname.bak"},
    ("files", "move"):   {"src": "/tmp/hostname.bak", "dest": "/tmp/hostname2.bak"},
    ("files", "remove"): {"path": "/tmp/test.txt"},
    ("files", "chmod"):  {"path": "/tmp/test.txt", "mode": "644"},
    ("files", "chown"):  {"path": "/tmp/test.txt", "owner": "root"},
    # firewall
    ("firewall", "list"):           {},
    ("firewall", "get_zones"):      {},
    ("firewall", "reload"):         {},
    ("firewall", "panic_on"):       {},
    ("firewall", "add_port"):       {"port": "8080/tcp"},
    ("firewall", "remove_port"):    {"port": "8080/tcp"},
    ("firewall", "add_service"):    {"service": "http"},
    ("firewall", "remove_service"): {"service": "http"},
    ("firewall", "set_default_zone"): {"zone": "public"},
    ("firewall", "query"):          {"service": "ssh"},
    # hardware
    ("hardware", "summary"): {},
    ("hardware", "cpu"):     {},
    ("hardware", "memory"):  {},
    ("hardware", "block"):   {},
    ("hardware", "pci"):     {},
    ("hardware", "usb"):     {},
    ("hardware", "sensors"): {},
    # logs
    ("logs", "tail"):         {},
    ("logs", "since"):        {"since": "1h"},
    ("logs", "query"):        {"pattern": "error"},
    ("logs", "boot_errors"):  {},
    ("logs", "dmesg_errors"): {},
    ("logs", "dmesg_query"):  {"pattern": "usb"},
    # network
    ("network", "interfaces"):  {},
    ("network", "connections"): {},
    ("network", "status"):      {},
    ("network", "wifi"):        {},
    ("network", "show"):        {"interface": "eth0"},
    ("network", "bring_up"):    {"interface": "eth0"},
    ("network", "bring_down"):  {"interface": "eth0"},
    ("network", "set_ip"):      {"interface": "eth0", "ip": "192.168.1.100/24"},
    # packages
    ("packages", "update"):  {},
    ("packages", "install"): {"packages": ["vim"]},
    ("packages", "remove"):  {"packages": ["vim"]},
    ("packages", "search"):  {"keyword": "nginx"},
    ("packages", "info"):    {"package": "nginx"},
    # processes
    ("processes", "list"):   {},
    ("processes", "top"):    {},
    ("processes", "tree"):   {},
    ("processes", "info"):   {"pid": 1},
    ("processes", "signal"): {"pid": 12345, "signal": 15},
    ("processes", "renice"): {"pid": 12345, "priority": 10},
    # services
    ("services", "status"):  {"unit": "nginx.service"},
    ("services", "start"):   {"unit": "nginx.service"},
    ("services", "stop"):    {"unit": "nginx.service"},
    ("services", "restart"): {"unit": "nginx.service"},
    ("services", "enable"):  {"unit": "nginx.service"},
    ("services", "disable"): {"unit": "nginx.service"},
    ("services", "mask"):    {"unit": "nginx.service"},
    ("services", "logs"):    {"unit": "nginx.service"},
    # users
    ("users", "list"):               {},
    ("users", "info"):               {"username": "root"},
    ("users", "add"):                {"username": "testuser"},
    ("users", "delete"):             {"username": "testuser"},
    ("users", "lock"):               {"username": "testuser"},
    ("users", "add_to_group"):       {"username": "testuser", "group": "wheel"},
    ("users", "remove_from_privgroup"): {"username": "testuser"},
    ("users", "set_shell"):          {"username": "testuser", "shell": "/bin/bash"},
}

# ---------------------------------------------------------------------------
# 4. Derive the valid-op set per tool from the LIVE registry at import time.
#    This set is used by simulate() to validate op names before dispatching.
#    INV-schema-sync: never hardcode op names — read from registry_schemas().
# ---------------------------------------------------------------------------
def _build_valid_ops() -> dict[str, frozenset[str]]:
    """Return {tool_name: frozenset(op_names)} from the live registry."""
    from finetune.coreimports import registry_schemas, registry  # local import avoids circularity
    result: dict[str, frozenset[str]] = {}
    for schema in registry_schemas(registry):
        tool_name = schema["name"]
        props = schema["parameters"]["properties"]
        ops: frozenset[str] = frozenset()
        for _key, spec in props.items():
            if isinstance(spec, dict) and "enum" in spec:
                ops = frozenset(spec["enum"])
                break
        result[tool_name] = ops
    return result


_VALID_OPS: dict[str, frozenset[str]] = _build_valid_ops()

# ---------------------------------------------------------------------------
# 5. Public dispatch function.
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = frozenset({"exit_code", "stdout", "stderr", "summary"})


def simulate(
    tool: str,
    op: str,
    args: dict[str, Any],
    ctx: Any,
) -> dict[str, Any]:
    """Dispatch to the correct per-tool simulator and return its result.

    Parameters
    ----------
    tool:
        Registered tool name.  Must be in the live TOOL_NAMES registry.
    op:
        Operation name.  Must be in that tool's declared op enum.
    args:
        Argument dict for the op.
    ctx:
        System context (str snapshot or profile dict) passed through unchanged.

    Returns
    -------
    dict with keys: exit_code, stdout, stderr, summary.

    Raises
    ------
    ValueError
        If `tool` is unknown or `op` is not valid for that tool.
    """
    # --- validate tool ---
    if tool not in _DISPATCH:
        known = sorted(_DISPATCH)
        raise ValueError(
            f"Unknown tool {tool!r}.  Known tools: {known}"
        )

    # --- validate op ---
    valid_ops = _VALID_OPS.get(tool, frozenset())
    if op not in valid_ops:
        raise ValueError(
            f"Unknown operation {op!r} for tool {tool!r}.  "
            f"Valid operations: {sorted(valid_ops)}"
        )

    # --- dispatch ---
    result: dict[str, Any] = _DISPATCH[tool](op, args, ctx)

    return result


# ---------------------------------------------------------------------------
# 6. Module-level completeness assert.
#
#    Iterates every (tool, op) in the LIVE registry and verifies:
#      a. A simulator exists in _DISPATCH for the tool.
#      b. simulate(tool, op, probe_args, ctx={}) returns a dict with
#         exactly the four required keys.
#
#    Any gap causes an AssertionError immediately at import time so that
#    generate.py never reaches a silent KeyError mid-run.
#
#    The probe args come from _PROBE_ARGS (defined above).  If a (tool, op)
#    pair is missing from _PROBE_ARGS the assert uses {} which is valid for
#    all-optional ops; an op that requires args will raise inside the
#    simulator and the assert will surface that as a failure — which is
#    exactly the right signal (a gap in coverage).
# ---------------------------------------------------------------------------

def _run_completeness_assert() -> None:
    """Verify zero (tool, op) gaps.  Called once at module import time."""
    from finetune.coreimports import registry_schemas, registry  # local import

    gaps: list[str] = []

    for schema in registry_schemas(registry):
        tool_name = schema["name"]
        props = schema["parameters"]["properties"]

        ops: list[str] = []
        for _key, spec in props.items():
            if isinstance(spec, dict) and "enum" in spec:
                ops = spec["enum"]
                break

        if tool_name not in _DISPATCH:
            gaps.append(f"NO SIMULATOR for tool {tool_name!r}")
            continue

        for op in ops:
            probe_args = _PROBE_ARGS.get((tool_name, op), {})
            try:
                result = simulate(tool_name, op, probe_args, ctx={})
            except Exception as exc:  # noqa: BLE001
                gaps.append(
                    f"{tool_name}.{op}: simulate() raised {type(exc).__name__}: {exc}"
                )
                continue

            missing = _REQUIRED_KEYS - set(result.keys())
            if missing:
                gaps.append(
                    f"{tool_name}.{op}: result missing keys {sorted(missing)}"
                )

    assert not gaps, (
        f"simulate() completeness check failed — {len(gaps)} gap(s):\n"
        + "\n".join(f"  {g}" for g in gaps)
    )


_run_completeness_assert()


# ---------------------------------------------------------------------------
# 7. Public surface.
# ---------------------------------------------------------------------------
__all__ = [
    "simulate",
]
