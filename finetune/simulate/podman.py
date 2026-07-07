"""finetune/simulate/podman.py — Rocky Linux 9 output simulator for the 'podman' tool.

Public API
----------
simulate_podman(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 12 real operations declared in core/tools/podman.py
    args : dict of op arguments (may be {} for ops with all-optional args;
           per-op defaults are applied internally)
    ctx  : system context string from make_context(), OR a profile dict —
           both forms are supported via isinstance (same pattern as services.py)

Realism model
-------------
* Exit codes mirror real podman behaviour on Rocky Linux 9:
    0   — success
    1   — general error (container/image not found, exec failure, etc.)
    125 — podman daemon error
    127 — command not found inside exec (exec op)
* stdout/stderr reflect actual podman output formats: tabular ps/images output,
  JSON inspect arrays, log lines, build layer output.
* Failure branches are hash-based and deterministic: containers whose name
  contains 'notfound', 'missing', 'fail', 'broken' trigger error paths; a
  small hash-based scatter (~15%) adds variety.
* Rootless note: no sudo prefix; all output represents unprivileged podman
  on RHEL 9 with cgroups v2.

I2 compliance
-------------
All `summary` strings are I2-clean — no AI/LLM/model/agent/neural language.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (avoids circular deps when the
Phase-13 __init__ imports simulate modules before coreimports is settled).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx (dict or snapshot text)."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _container_is_running(name: str, ctx: Any) -> bool:
    """Return True if the container appears to be running in the given context."""
    if isinstance(ctx, dict):
        running: list[str] = ctx.get("running_containers", [])
        return name in running or any(name in c for c in running)
    if isinstance(ctx, str):
        return name in ctx
    return False


def _image_exists(name: str, ctx: Any) -> bool:
    """Return True if the image appears to be present in the given context."""
    if isinstance(ctx, dict):
        images: list[str] = ctx.get("local_images", [])
        return name in images or any(name in img for img in images)
    if isinstance(ctx, str):
        return name in ctx
    return False


def _container_not_found(name: str) -> bool:
    """Deterministically decide if a container/image name triggers not-found."""
    lower = name.lower()
    for tok in ("notfound", "missing", "fail", "broken", "noexist", "bogus"):
        if tok in lower:
            return True
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 20 == 0


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


def _short_id(name: str) -> str:
    """Generate a deterministic short container/image ID from a name."""
    h = hashlib.md5(name.encode()).hexdigest()
    return h[:12]


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_ps(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    show_all: bool = bool(args.get("all", False))
    host = _hostname(ctx)

    header = (
        "CONTAINER ID  IMAGE                    COMMAND               "
        "CREATED         STATUS              PORTS   NAMES\n"
    )

    if isinstance(ctx, dict):
        running: list[str] = ctx.get("running_containers", [])
    else:
        running = []

    if not running:
        if show_all:
            # Show a sample stopped container
            row = (
                f"{_short_id('web-app')}  nginx:1.25               "
                f"\"nginx -g 'daemo...\"  2 hours ago     Exited (0) 1 hour ago       80/tcp  web-app\n"
            )
            stdout = header + row
            summary = "Listed 1 all container(s)."
        else:
            stdout = header
            summary = "Listed 0 running container(s)."
        return _make_result(0, stdout, "", summary)

    rows = []
    for name in running[:5]:
        cid = _short_id(name)
        rows.append(
            f"{cid}  ubi9:latest              \"/bin/bash\"           "
            f"1 hour ago      Up 1 hour                       {name}\n"
        )
    stdout = header + "".join(rows)
    qualifier = "all" if show_all else "running"
    summary = f"Listed {len(rows)} {qualifier} container(s)."
    return _make_result(0, stdout, "", summary)


def _sim_images(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    header = (
        "REPOSITORY                               TAG         IMAGE ID      "
        "CREATED       SIZE\n"
    )

    if isinstance(ctx, dict):
        local_images: list[str] = ctx.get("local_images", [])
    else:
        local_images = []

    if not local_images:
        # Always show at least a base image
        local_images = ["registry.access.redhat.com/ubi9"]

    rows = []
    for img in local_images[:6]:
        iid = _short_id(img)
        tag = "latest" if ":" not in img else img.split(":")[-1]
        repo = img.split(":")[0]
        rows.append(
            f"{repo:<40} {tag:<11} {iid}  3 weeks ago   211 MB\n"
        )
    stdout = header + "".join(rows)
    summary = f"Listed {len(rows)} local image(s)."
    return _make_result(0, stdout, "", summary)


def _sim_inspect(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    target = args.get("target", "unknown")

    if _container_not_found(target):
        stderr = f"Error: no such object: {target}\n"
        return _make_result(
            exit_code=125,
            stdout="",
            stderr=stderr,
            summary=f"No container or image named '{target}' was found.",
        )

    tid = _short_id(target)
    stdout = (
        f"[\n"
        f"    {{\n"
        f"        \"Id\": \"{tid}aabbccdd1234567890abcdef\",\n"
        f"        \"Created\": \"2026-07-04T00:01:00.000000000Z\",\n"
        f"        \"Name\": \"{target}\",\n"
        f"        \"State\": {{\n"
        f"            \"Status\": \"running\",\n"
        f"            \"Running\": true,\n"
        f"            \"Pid\": {1000 + (sum(ord(c) for c in target) % 8000)}\n"
        f"        }},\n"
        f"        \"Image\": \"ubi9:latest\",\n"
        f"        \"NetworkSettings\": {{\n"
        f"            \"IPAddress\": \"10.88.0.2\"\n"
        f"        }}\n"
        f"    }}\n"
        f"]\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Inspection data for '{target}' retrieved.",
    )


def _sim_logs(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    container = args.get("container", "unknown")
    lines = int(args.get("lines", 50))
    lines = max(1, min(lines, 500))
    host = _hostname(ctx)

    if _container_not_found(container):
        stderr = f"Error: no such container: {container}\n"
        return _make_result(
            exit_code=125,
            stdout="",
            stderr=stderr,
            summary=f"Container '{container}' was not found.",
        )

    active = _container_is_running(container, ctx)
    log_lines: list[str] = [
        f"2026-07-04T00:01:00.000000000Z Starting application...",
        f"2026-07-04T00:01:01.123456789Z Listening on port 8080",
        f"2026-07-04T00:01:02.000000000Z Configuration loaded.",
    ]
    if active:
        log_lines += [
            f"2026-07-04T02:15:33.000000000Z Handled request GET /health -> 200",
            f"2026-07-04T04:00:01.000000000Z Periodic cleanup complete.",
            f"2026-07-04T08:42:11.000000000Z Connection from 10.0.1.5 accepted.",
        ]
    else:
        log_lines += [
            f"2026-07-04T06:30:10.000000000Z Received shutdown signal.",
            f"2026-07-04T06:30:11.000000000Z Flushing buffers.",
            f"2026-07-04T06:30:12.000000000Z Exited cleanly.",
        ]

    body = log_lines[:lines]
    # podman logs writes to stderr by default; simulate that
    stderr_out = "\n".join(body) + "\n"
    line_count = len(body)
    return _make_result(
        exit_code=0,
        stdout="",
        stderr=stderr_out,
        summary=f"Retrieved {line_count} log line(s) for container '{container}'.",
    )


def _sim_pull(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    image = args.get("image", "unknown")

    if _container_not_found(image):
        stderr = (
            f"Error: trying to pull {image}: "
            f"initializing source docker://{image}: "
            f"reading manifest latest: name unknown: repository name not known to registry\n"
        )
        return _make_result(
            exit_code=125,
            stdout="",
            stderr=stderr,
            summary=f"Failed to pull image '{image}' — not found in registry.",
        )

    iid = _short_id(image)
    stdout = (
        f"Trying to pull {image}...\n"
        f"Getting image source signatures\n"
        f"Copying blob sha256:{iid}aabb done\n"
        f"Copying config sha256:{iid}ccdd done\n"
        f"Writing manifest to image destination\n"
        f"Storing signatures\n"
        f"{iid}eeff11223344556677889900aabbccddeeff\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Image '{image}' pulled successfully.",
    )


def _sim_run(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    image = args.get("image", "unknown")
    name = args.get("name", "")
    detach = bool(args.get("detach", True))

    if _container_not_found(image):
        stderr = f"Error: unable to find image '{image}' locally or in registry\n"
        return _make_result(
            exit_code=125,
            stdout="",
            stderr=stderr,
            summary=f"Failed to run container from '{image}' — image not found.",
        )

    # Hash-based failure branch for run (resource exhaustion, etc.)
    h = int(hashlib.md5((image + "run").encode()).hexdigest(), 16)
    if h % 15 == 0:
        stderr = (
            f"Error: crun: mount `/proc/sys` to `/proc/sys`: "
            f"mount `/proc/sys` to `/proc/sys`: Operation not permitted: "
            f"OCI runtime error\n"
        )
        return _make_result(
            exit_code=126,
            stdout="",
            stderr=stderr,
            summary=f"Container from '{image}' could not start due to a runtime error.",
        )

    cid = _short_id(image + (name or "") + "run")
    stdout = cid + "aabb1122334455667788990011223344\n" if detach else ""
    label = f" as '{name}'" if name else ""
    mode = " in detached mode" if detach else ""
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Container from image '{image}' started{label}{mode}.",
    )


def _sim_stop(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    container = args.get("container", "unknown")

    if _container_not_found(container):
        stderr = f"Error: no such container: {container}\n"
        return _make_result(
            exit_code=125,
            stdout="",
            stderr=stderr,
            summary=f"Container '{container}' was not found.",
        )

    if not _container_is_running(container, ctx):
        return _make_result(
            exit_code=0,
            stdout=container + "\n",
            stderr="",
            summary=f"Container '{container}' was already stopped.",
        )

    return _make_result(
        exit_code=0,
        stdout=container + "\n",
        stderr="",
        summary=f"Container '{container}' stopped.",
    )


def _sim_exec(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    container = args.get("container", "unknown")
    command = args.get("command", "")

    if _container_not_found(container):
        stderr = f"Error: no such container: {container}\n"
        return _make_result(
            exit_code=125,
            stdout="",
            stderr=stderr,
            summary=f"Container '{container}' was not found.",
        )

    if not _container_is_running(container, ctx):
        stderr = (
            f"Error: container {container} is not running\n"
        )
        return _make_result(
            exit_code=125,
            stdout="",
            stderr=stderr,
            summary=f"Container '{container}' is not running; exec requires a running container.",
        )

    # Simulate some common commands
    cmd_lower = command.lower().strip()
    if cmd_lower.startswith("ls"):
        stdout = "bin  etc  proc  sys  tmp  usr  var\n"
    elif cmd_lower.startswith("ps"):
        stdout = (
            "PID   USER     TIME  COMMAND\n"
            "    1 root      0:00 /bin/sh -c entrypoint.sh\n"
            "   12 root      0:01 python app.py\n"
        )
    elif cmd_lower.startswith("cat") or cmd_lower.startswith("echo"):
        stdout = "output from: " + command + "\n"
    else:
        stdout = ""

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Command '{command}' executed in container '{container}'.",
    )


def _sim_build(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    context = args.get("context", ".")
    tag = args.get("tag", "")

    if _container_not_found(context):
        stderr = (
            f"Error: error building at STEP \"FROM ubi9\": "
            f"no such file or directory: {context}\n"
        )
        return _make_result(
            exit_code=125,
            stdout="",
            stderr=stderr,
            summary=f"Build from context '{context}' failed — directory not found.",
        )

    iid = _short_id(context + tag)
    stdout = (
        f"STEP 1/4: FROM registry.access.redhat.com/ubi9:latest\n"
        f"STEP 2/4: RUN dnf install -y curl\n"
        f"STEP 3/4: COPY . /app\n"
        f"STEP 4/4: CMD [\"/app/entrypoint.sh\"]\n"
        f"COMMIT{(' ' + tag) if tag else ''}\n"
        f"--> {iid}aabb\n"
        f"Successfully tagged {tag}:latest\n" if tag else f"--> {iid}aabb\n"
    )
    label = f" tagged '{tag}'" if tag else ""
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Image{label} built from context '{context}'.",
    )


def _sim_push(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    image = args.get("image", "unknown")

    if _container_not_found(image):
        stderr = (
            f"Error: {image}: image not known\n"
        )
        return _make_result(
            exit_code=125,
            stdout="",
            stderr=stderr,
            summary=f"Failed to push '{image}' — image not found in local storage.",
        )

    iid = _short_id(image)
    stdout = (
        f"Getting image source signatures\n"
        f"Copying blob sha256:{iid}aabb done\n"
        f"Copying config sha256:{iid}ccdd done\n"
        f"Writing manifest to image destination\n"
        f"Storing signatures\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Image '{image}' pushed to registry.",
    )


def _sim_rm(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    container = args.get("container", "unknown")

    if _container_not_found(container):
        stderr = f"Error: no such container: {container}\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Container '{container}' was not found.",
        )

    return _make_result(
        exit_code=0,
        stdout=container + "\n",
        stderr="",
        summary=f"Container '{container}' removed.",
    )


def _sim_rmi(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    image = args.get("image", "unknown")

    if _container_not_found(image):
        stderr = f"Error: {image}: image not known\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Image '{image}' was not found in local storage.",
        )

    # Check for containers still using this image
    h = int(hashlib.md5((image + "rmi").encode()).hexdigest(), 16)
    if h % 10 == 0:
        stderr = (
            f"Error: image used by {_short_id(image)}aabb: "
            f"image is in use by a container\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Cannot remove image '{image}' — it is in use by an existing container.",
        )

    iid = _short_id(image)
    stdout = f"Untagged: {image}\nDeleted: {iid}aabbccddeeff\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Image '{image}' removed from local storage.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "ps":      _sim_ps,
    "images":  _sim_images,
    "inspect": _sim_inspect,
    "logs":    _sim_logs,
    "pull":    _sim_pull,
    "run":     _sim_run,
    "stop":    _sim_stop,
    "exec":    _sim_exec,
    "build":   _sim_build,
    "push":    _sim_push,
    "rm":      _sim_rm,
    "rmi":     _sim_rmi,
}


def simulate_podman(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'podman' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 12 real ops declared in
           core/tools/podman.py.
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'running_containers'/'local_images' lists.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_podman: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
