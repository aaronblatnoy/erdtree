"""finetune/simulate/virsh.py — Rocky Linux 9 output simulator for the 'virsh' tool.

Public API
----------
simulate_virsh(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 10 real operations declared in core/tools/virsh.py
    args : dict of op arguments (may be {} for all-optional / no-arg ops)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Realistic Rocky Linux 9 / libvirt virsh output format including column tables
  and domain/pool status messages.
* Failure triggers are deterministic: a domain/pool name that contains the
  tokens "notfound", "noexist", "broken", "missing", or "bogus" returns an
  error result; a hash-based 15% scatter adds variety for otherwise valid names.
* ctx is used to decide which domains are currently running.

I2 compliance
-------------
All `summary` strings are I2-clean (no AI/LLM/agent/neural/language model).

INV-read-only-core: this module imports NOTHING from core/ directly and
NOTHING from finetune.coreimports (to avoid circular deps during Phase-13
init import).  The ToolResult shape is mirrored as a plain dict.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-kvm.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-kvm"


def _domain_is_running(domain: str, ctx: Any) -> bool:
    """Return True if the domain appears to be running in the given context."""
    if isinstance(ctx, dict):
        running: list[str] = ctx.get("running_vms", [])
        return domain in running or any(domain in v for v in running)
    if isinstance(ctx, str):
        return domain in ctx
    return False


def _object_not_found(name: str) -> bool:
    """Deterministically decide if a name should trigger a not-found error.

    Triggers: token "notfound", "noexist", "broken", "missing", "bogus" in
    the lowercase name; OR a hash-based 15% scatter for variety.
    """
    lower = name.lower()
    for tok in ("notfound", "noexist", "broken", "missing", "bogus"):
        if tok in lower:
            return True
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 20 == 0


def _fake_uuid(name: str) -> str:
    """Generate a deterministic UUID-shaped string from a name."""
    h = hashlib.md5(name.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _fake_id(name: str) -> int:
    """Deterministic small integer ID for a running domain."""
    return 1 + (sum(ord(c) for c in name) % 99)


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh list --all"""
    # Build a plausible table of domains
    header = (
        " Id   Name                 State\n"
        "-----------------------------------\n"
    )
    # Fixed set of typical domains; augment from ctx if dict
    domains = []
    if isinstance(ctx, dict):
        for vm in ctx.get("running_vms", []):
            vid = _fake_id(vm)
            domains.append(f" {vid:<4} {vm:<20} running")
        for vm in ctx.get("stopped_vms", []):
            domains.append(f" -    {vm:<20} shut off")
    if not domains:
        # Default plausible output
        domains = [
            " 1    centos9-web          running",
            " 2    rhel9-db             running",
            " -    fedora38-dev         shut off",
            " -    ubuntu22-test        shut off",
        ]
    stdout = header + "\n".join(domains) + "\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Listed all defined virtual machine domains.",
    )


def _sim_dominfo(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh dominfo <domain>"""
    domain = args.get("domain", "unknown-vm")

    if _object_not_found(domain):
        stderr = f"error: failed to get domain '{domain}'\nerror: Domain not found: no domain with matching name '{domain}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Domain '{domain}' was not found in the libvirt database.",
        )

    running = _domain_is_running(domain, ctx)
    state = "running" if running else "shut off"
    vid = str(_fake_id(domain)) if running else "-"
    uuid = _fake_uuid(domain)
    cpu_time = f"{(sum(ord(c) for c in domain) % 9000) + 100:.1f}s"
    mem_kb = 4194304

    stdout = (
        f"Id:             {vid}\n"
        f"Name:           {domain}\n"
        f"UUID:           {uuid}\n"
        f"OS Type:        hvm\n"
        f"State:          {state}\n"
        f"CPU(s):         4\n"
        f"CPU time:       {cpu_time}\n"
        f"Max memory:     {mem_kb} KiB\n"
        f"Used memory:    {mem_kb} KiB\n"
        f"Persistent:     yes\n"
        f"Autostart:      disable\n"
        f"Managed save:   no\n"
        f"Security model: selinux\n"
        f"Security DOI:   0\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Retrieved domain info for '{domain}': state is {state}.",
    )


def _sim_start(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh start <domain>"""
    domain = args.get("domain", "unknown-vm")

    if _object_not_found(domain):
        stderr = f"error: failed to get domain '{domain}'\nerror: Domain not found: no domain with matching name '{domain}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Domain '{domain}' could not be started; it was not found.",
        )

    if _domain_is_running(domain, ctx):
        stderr = f"error: domain '{domain}' is already running\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Domain '{domain}' is already running.",
        )

    stdout = f"Domain '{domain}' started\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Domain '{domain}' started successfully.",
    )


def _sim_shutdown(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh shutdown <domain>"""
    domain = args.get("domain", "unknown-vm")

    if _object_not_found(domain):
        stderr = f"error: failed to get domain '{domain}'\nerror: Domain not found: no domain with matching name '{domain}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Domain '{domain}' could not be shut down; it was not found.",
        )

    if not _domain_is_running(domain, ctx):
        # virsh shutdown on an already-stopped domain exits non-zero
        h = int(hashlib.md5((domain + "shutdown").encode()).hexdigest(), 16)
        if h % 4 == 0:
            stderr = f"error: domain '{domain}' is not running\n"
            return _make_result(
                exit_code=1,
                stdout="",
                stderr=stderr,
                summary=f"Domain '{domain}' is not running; shutdown not required.",
            )

    stdout = f"Domain {domain} is being shutdown\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Shutdown signal sent to domain '{domain}'.",
    )


def _sim_define(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh define <xmlfile>"""
    xmlfile = args.get("xmlfile", "/tmp/vm.xml")

    # Simulate missing file
    if "notfound" in xmlfile.lower() or "missing" in xmlfile.lower():
        stderr = f"error: Failed to open file '{xmlfile}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to define domain: XML file '{xmlfile}' was not found.",
        )

    # Derive a plausible domain name from the file path
    basename = xmlfile.rstrip("/").split("/")[-1].replace(".xml", "")
    dom_name = basename if basename else "newdomain"
    stdout = f"Domain '{dom_name}' defined from {xmlfile}\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Domain defined from XML file '{xmlfile}'.",
    )


def _sim_destroy(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh destroy <domain> — DESTRUCTIVE"""
    domain = args.get("domain", "unknown-vm")

    if _object_not_found(domain):
        stderr = f"error: failed to get domain '{domain}'\nerror: Domain not found: no domain with matching name '{domain}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Domain '{domain}' could not be destroyed; it was not found.",
        )

    stdout = f"Domain {domain} destroyed\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Domain '{domain}' forcibly powered off.",
    )


def _sim_undefine(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh undefine <domain> [--remove-all-storage] — DESTRUCTIVE"""
    domain = args.get("domain", "unknown-vm")
    remove_storage = bool(args.get("remove_storage", False))

    if _object_not_found(domain):
        stderr = f"error: failed to get domain '{domain}'\nerror: Domain not found: no domain with matching name '{domain}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Domain '{domain}' could not be undefined; it was not found.",
        )

    if remove_storage:
        stdout = (
            f"Domain {domain} has been undefined\n"
            f"Volume '/var/lib/libvirt/images/{domain}.qcow2' removed.\n"
        )
        summary = f"Domain '{domain}' undefined and all associated storage removed."
    else:
        stdout = f"Domain {domain} has been undefined\n"
        summary = f"Domain '{domain}' undefined; disk images were not removed."

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=summary,
    )


def _sim_pool_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh pool-list --all"""
    header = (
        " Name      State    Autostart\n"
        "-------------------------------\n"
    )
    pools = []
    if isinstance(ctx, dict):
        for p in ctx.get("storage_pools", []):
            pools.append(f" {p:<9} active   yes")
    if not pools:
        pools = [
            " default   active   yes",
            " images    active   no ",
            " backups   inactive no ",
        ]
    stdout = header + "\n".join(pools) + "\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Listed all storage pools.",
    )


def _sim_pool_define(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh pool-define <xmlfile>"""
    xmlfile = args.get("xmlfile", "/tmp/pool.xml")

    if "notfound" in xmlfile.lower() or "missing" in xmlfile.lower():
        stderr = f"error: Failed to open file '{xmlfile}': No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to define storage pool: XML file '{xmlfile}' was not found.",
        )

    basename = xmlfile.rstrip("/").split("/")[-1].replace(".xml", "")
    pool_name = basename if basename else "newpool"
    stdout = f"Pool {pool_name} defined from {xmlfile}\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Storage pool defined from XML file '{xmlfile}'.",
    )


def _sim_pool_destroy(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """virsh pool-destroy <pool> — DESTRUCTIVE"""
    pool = args.get("pool", "unknown-pool")

    if _object_not_found(pool):
        stderr = f"error: failed to get storage pool '{pool}'\nerror: Storage pool not found: no storage pool with matching name '{pool}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Storage pool '{pool}' could not be destroyed; it was not found.",
        )

    stdout = f"Pool {pool} destroyed\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Storage pool '{pool}' destroyed (stopped and deactivated).",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "list":         _sim_list,
    "dominfo":      _sim_dominfo,
    "start":        _sim_start,
    "shutdown":     _sim_shutdown,
    "define":       _sim_define,
    "destroy":      _sim_destroy,
    "undefine":     _sim_undefine,
    "pool-list":    _sim_pool_list,
    "pool-define":  _sim_pool_define,
    "pool-destroy": _sim_pool_destroy,
}


def simulate_virsh(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'virsh' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 10 real ops in core/tools/virsh.py.
    args : argument dict (may be sparse; per-op defaults are applied).
    ctx  : system context — either a snapshot_text str or a profile dict with
           'running_vms', 'stopped_vms', 'storage_pools' lists.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present. summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_virsh: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
