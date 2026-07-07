"""finetune/simulate/buildah.py — Rocky Linux 9 output simulator for the 'buildah' tool.

Public API
----------
simulate_buildah(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the real operations declared in core/tools/buildah.py
    args : dict of op arguments (may be sparse; per-op defaults are applied)
    ctx  : system context string from make_context(), OR a profile dict.
           Both forms supported via isinstance.

Realism model
-------------
* Exit codes mirror real buildah behaviour on Rocky Linux 9:
    0  — success
    1  — generic failure (container/image not found, push auth error, etc.)
    125 — buildah itself failed to run (e.g. storage not initialized)
* stdout/stderr reflect actual buildah output format.
* Failure triggers are deterministic via hash-based scatter and name tokens.

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent/agentic/neural terms).

INV-read-only-core: this module imports NOTHING from core/ directly.
Does not import finetune.coreimports (avoids circular deps at Phase-13 init).
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


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


def _container_not_found(name: str) -> bool:
    """Deterministically decide if a container name triggers a not-found error."""
    lower = name.lower()
    for tok in ("notfound", "noexist", "broken", "fail", "missing", "bogus", "bad"):
        if tok in lower:
            return True
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 18 == 0


def _image_not_found(name: str) -> bool:
    """Deterministically decide if an image name triggers a not-found error."""
    lower = name.lower()
    for tok in ("notfound", "noexist", "broken", "fail", "missing", "bogus", "bad"):
        if tok in lower:
            return True
    h = int(hashlib.md5((name + "img").encode()).hexdigest(), 16)
    return h % 20 == 0


def _short_id(name: str) -> str:
    """Generate a deterministic short image ID from a name."""
    h = hashlib.sha256(name.encode()).hexdigest()
    return h[:12]


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_images(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    show_all: bool = bool(args.get("all", False))

    # Build a plausible image list; pull known images from ctx if dict
    known: list[str] = []
    if isinstance(ctx, dict):
        known = ctx.get("container_images", [])

    if not known:
        known = [
            "registry.access.redhat.com/ubi9/ubi:9.3",
            "docker.io/library/nginx:1.25",
            "localhost/myapp:1.0",
        ]

    header = (
        "IMAGE NAME                                               IMAGE TAG  "
        "IMAGE ID      CREATED AT             SIZE\n"
    )
    rows = []
    for img in known:
        if ":" in img:
            name_part, tag_part = img.rsplit(":", 1)
        else:
            name_part, tag_part = img, "latest"
        img_id = _short_id(img)
        rows.append(
            f"{name_part:<55} {tag_part:<10} {img_id}  2026-07-03 10:00:00 +0000 UTC  185 MB\n"
        )

    if show_all:
        # Add an intermediate layer image
        rows.append(
            f"<none>                                                   <none>     "
            f"{'a' * 12}  2026-07-03 09:58:00 +0000 UTC   72 MB\n"
        )

    stdout = header + "".join(rows)
    count = len(rows)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Listed {count} locally stored image(s).",
    )


def _sim_from(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    image: str = args.get("image", "ubi9")

    if _image_not_found(image):
        stderr = (
            f"Error: {image}: image not known\n"
            f"trying to pull {image}...\n"
            f"Error: reading manifest latest in {image}: "
            f"manifest unknown: manifest unknown\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create working container from '{image}': image not found.",
        )

    base = image.split("/")[-1].split(":")[0]
    container_name = f"{base}-working-container"
    return _make_result(
        exit_code=0,
        stdout=f"{container_name}\n",
        stderr="",
        summary=f"Working container '{container_name}' created from '{image}'.",
    )


def _sim_copy(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    container: str = args.get("container", "myapp-working-container")
    src: str = args.get("src", "./app")
    dst: str = args.get("dst", "/app")

    if _container_not_found(container):
        stderr = f"Error: {container}: container not known\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to copy into container '{container}': container not found.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Copied '{src}' into container '{container}' at '{dst}'.",
    )


def _sim_run(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    container: str = args.get("container", "ubi9-working-container")
    command: str = args.get("command", "echo hello")

    if _container_not_found(container):
        stderr = f"Error: {container}: container not known\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Command in container '{container}' failed: container not found.",
        )

    # Simulate command-specific output
    cmd_lower = command.lower()
    if cmd_lower.startswith("echo"):
        words = command.split(None, 1)
        stdout = (words[1] if len(words) > 1 else "") + "\n"
    elif "dnf" in cmd_lower or "yum" in cmd_lower:
        stdout = (
            "Last metadata expiration check: 0:01:23 ago on Fri Jul 03 10:00:00 2026.\n"
            "Dependencies resolved.\n"
            "Nothing to do.\n"
            "Complete!\n"
        )
    elif "rpm" in cmd_lower or "install" in cmd_lower:
        stdout = "Complete!\n"
    else:
        stdout = ""

    # Hash-based failure scatter for command execution
    h = int(hashlib.md5((container + command).encode()).hexdigest(), 16)
    if h % 14 == 0:
        stderr = f"Error: command returned non-zero exit code: 1\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Command in container '{container}' failed (exit 1).",
        )

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Command ran successfully in container '{container}'.",
    )


def _sim_commit(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    container: str = args.get("container", "ubi9-working-container")
    image: str = args.get("image", "localhost/myapp:latest")

    if _container_not_found(container):
        stderr = f"Error: {container}: container not known\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to commit container '{container}': container not found.",
        )

    img_id = _short_id(image)
    stdout = (
        f"Getting image source signatures\n"
        f"Copying blob sha256:{img_id}0000000000000000000000000000000000000000000000000000 done\n"
        f"Copying config sha256:{_short_id(container + image)} done\n"
        f"Writing manifest to image destination\n"
        f"Storing signatures\n"
        f"{img_id}\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Container '{container}' committed as image '{image}'.",
    )


def _sim_push(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    image: str = args.get("image", "localhost/myapp:latest")

    if _image_not_found(image):
        stderr = (
            f"Error: {image}: image not known\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to push image '{image}': image not found locally.",
        )

    # Simulate auth failure for some registries (hash-based)
    h = int(hashlib.md5((image + "push").encode()).hexdigest(), 16)
    if h % 15 == 0:
        stderr = (
            f"Error: trying to reuse blob sha256:abc123... at destination: "
            f"unauthorized: access to the requested resource is not authorized\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to push image '{image}': registry authorization error.",
        )

    img_id = _short_id(image)
    stdout = (
        f"Getting image source signatures\n"
        f"Copying blob sha256:{img_id}aabbcc skipped: already exists\n"
        f"Copying config sha256:{_short_id(image + 'cfg')} done\n"
        f"Writing manifest to image destination\n"
        f"Storing signatures\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Image '{image}' pushed to registry.",
    )


def _sim_build(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    tag: str = args.get("tag", "localhost/myapp:latest")
    context: str = args.get("context") or "."

    # Missing Containerfile/Dockerfile
    h = int(hashlib.md5((tag + context).encode()).hexdigest(), 16)
    if h % 13 == 0 or "notfound" in context.lower() or "missing" in context.lower():
        stderr = (
            f"Error: no Containerfile or Dockerfile found in {context}\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Build of image '{tag}' failed: no Containerfile found in '{context}'.",
        )

    step_count = 3 + (h % 5)
    steps = []
    for i in range(1, step_count + 1):
        if i == 1:
            steps.append(f"STEP {i}/{step_count}: FROM registry.access.redhat.com/ubi9/ubi:9.3")
        elif i == step_count:
            steps.append(f"STEP {i}/{step_count}: CMD [\"/usr/sbin/nginx\", \"-g\", \"daemon off;\"]")
            steps.append(f"COMMIT {tag}")
        else:
            steps.append(f"STEP {i}/{step_count}: RUN dnf install -y nginx && dnf clean all")

    img_id = _short_id(tag)
    steps.append(f"--> {img_id}")
    steps.append(f"Successfully tagged {tag}")
    steps.append(f"{img_id}")

    stdout = "\n".join(steps) + "\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Image '{tag}' built from context '{context}'.",
    )


def _sim_rm(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    all_containers: bool = bool(args.get("all", False))

    if all_containers:
        stdout = (
            "ubi9-working-container\n"
            "myapp-working-container\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="All working containers removed.",
        )

    container: str = args.get("container", "")
    if not container:
        stderr = "Error: must specify a container name or --all\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to remove working container: no container name specified.",
        )

    if _container_not_found(container):
        stderr = f"Error: {container}: container not known\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove working container '{container}': container not found.",
        )

    return _make_result(
        exit_code=0,
        stdout=f"{container}\n",
        stderr="",
        summary=f"Working container '{container}' removed.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "images": _sim_images,
    "from": _sim_from,
    "copy": _sim_copy,
    "run": _sim_run,
    "commit": _sim_commit,
    "push": _sim_push,
    "build": _sim_build,
    "rm": _sim_rm,
}


def simulate_buildah(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'buildah' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the real ops declared in the
           buildah ToolSpec (images, from, copy, run, commit, push, build, rm).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with container-related keys.

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
            f"simulate_buildah: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
