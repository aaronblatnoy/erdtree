"""core/tools/buildah.py — OCI image and working-container management via buildah.

Supported operations
--------------------
  images   (READ)        — list locally stored images.
  from     (WRITE)       — create a working container from a base image.
  copy     (WRITE)       — copy files or directories into a working container.
  run      (WRITE)       — execute a command inside a working container.
  commit   (WRITE)       — commit a working container to a new image.
  push     (WRITE)       — push a local image to a registry.
  build    (WRITE)       — build an image from a Containerfile/Dockerfile.
  rm       (DESTRUCTIVE) — remove one or more working containers (discards build state).

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.
"""

from __future__ import annotations

import re
from typing import Any

from core.agent.permissions import OpClass
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)

# ---------------------------------------------------------------------------
# SELinux hint detection (verbatim from services.py)
# ---------------------------------------------------------------------------

_SELINUX_HINT_RE = re.compile(
    r"AVC\s+avc:|Permission\s+denied|dontaudit|type=AVC|selinux",
    re.IGNORECASE,
)

_SELINUX_HINT = (
    "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
    "or 'journalctl -t setroubleshoot' for denial details."
)


def _maybe_selinux_hint(stderr: str) -> str:
    """Return a SELinux hint suffix if stderr looks like an AVC denial."""
    if _SELINUX_HINT_RE.search(stderr):
        return f"  {_SELINUX_HINT}"
    return ""


# ---------------------------------------------------------------------------
# Shared ArgSpec constants
# ---------------------------------------------------------------------------

_CONTAINER_ARG = ArgSpec(
    name="container",
    type=str,
    required=True,
    description="Name or ID of the working container.",
)

_IMAGE_ARG = ArgSpec(
    name="image",
    type=str,
    required=True,
    description="Image name or ID (e.g. 'registry.access.redhat.com/ubi9/ubi:latest').",
)

# ---------------------------------------------------------------------------
# Per-operation implementations
# ---------------------------------------------------------------------------


def _op_images(args: dict[str, Any]) -> ToolResult:
    """buildah images [--all]"""
    show_all: bool = bool(args.get("all", False))
    cmd = ["buildah", "images"]
    if show_all:
        cmd.append("--all")
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        # Subtract header line from count
        count = max(0, len(lines) - 1)
        summary = f"Listed {count} locally stored image(s)."
    else:
        summary = f"Failed to list images (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_from(args: dict[str, Any]) -> ToolResult:
    """buildah from <image>"""
    image: str = args["image"]
    result = run_subprocess(["buildah", "from", image])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        container_name = result.stdout.strip() or f"{image.split('/')[-1].split(':')[0]}-working-container"
        summary = f"Working container '{container_name}' created from '{image}'."
    else:
        summary = f"Failed to create working container from '{image}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_copy(args: dict[str, Any]) -> ToolResult:
    """buildah copy <container> <src> <dst>"""
    container: str = args["container"]
    src: str = args["src"]
    dst: str = args["dst"]
    result = run_subprocess(["buildah", "copy", container, src, dst])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Copied '{src}' into container '{container}' at '{dst}'."
    else:
        summary = f"Failed to copy '{src}' into container '{container}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_run(args: dict[str, Any]) -> ToolResult:
    """buildah run <container> -- <command>"""
    container: str = args["container"]
    command: str = args["command"]
    result = run_subprocess(["buildah", "run", container, "--", command])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Command ran successfully in container '{container}'."
    else:
        summary = f"Command in container '{container}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_commit(args: dict[str, Any]) -> ToolResult:
    """buildah commit <container> <image>"""
    container: str = args["container"]
    image: str = args["image"]
    result = run_subprocess(["buildah", "commit", container, image])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Container '{container}' committed as image '{image}'."
    else:
        summary = f"Failed to commit container '{container}' as '{image}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_push(args: dict[str, Any]) -> ToolResult:
    """buildah push <image>"""
    image: str = args["image"]
    result = run_subprocess(["buildah", "push", image])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Image '{image}' pushed to registry."
    else:
        summary = f"Failed to push image '{image}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_build(args: dict[str, Any]) -> ToolResult:
    """buildah build -t <tag> [<context>]"""
    tag: str = args["tag"]
    context: str = args.get("context") or "."
    result = run_subprocess(["buildah", "build", "-t", tag, context])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Image '{tag}' built from context '{context}'."
    else:
        summary = f"Build of image '{tag}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_rm(args: dict[str, Any]) -> ToolResult:
    """buildah rm <container> | buildah rm --all"""
    all_containers: bool = bool(args.get("all", False))
    if all_containers:
        result = run_subprocess(["buildah", "rm", "--all"])
        selinux = _maybe_selinux_hint(result.stderr)
        if result.ok:
            summary = "All working containers removed."
        else:
            summary = f"Failed to remove all working containers (exit {result.exit_code})."
    else:
        container: str = args["container"]
        result = run_subprocess(["buildah", "rm", container])
        selinux = _maybe_selinux_hint(result.stderr)
        if result.ok:
            summary = f"Working container '{container}' removed."
        else:
            summary = f"Failed to remove working container '{container}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "images": _op_images,
    "from": _op_from,
    "copy": _op_copy,
    "run": _op_run,
    "commit": _op_commit,
    "push": _op_push,
    "build": _op_build,
    "rm": _op_rm,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a buildah operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function never raises (I9): unknown ops and subprocess failures
    both degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for buildah tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

BUILDAH_SPEC = ToolSpec(
    name="buildah",
    description="Build and manage OCI container images and working containers via buildah.",
    ops={
        "images": OpSpec(
            op_name="images",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="all",
                    type=bool,
                    required=False,
                    description="Include intermediate images (--all).",
                    default=False,
                ),
            ],
            description="List locally stored OCI images.",
        ),
        "from": OpSpec(
            op_name="from",
            permission_class=OpClass.WRITE,
            args=[_IMAGE_ARG],
            description="Create a new working container from a base image.",
        ),
        "copy": OpSpec(
            op_name="copy",
            permission_class=OpClass.WRITE,
            args=[
                _CONTAINER_ARG,
                ArgSpec(
                    name="src",
                    type=str,
                    required=True,
                    description="Source path on the host.",
                ),
                ArgSpec(
                    name="dst",
                    type=str,
                    required=True,
                    description="Destination path inside the working container.",
                ),
            ],
            description="Copy files or directories from the host into a working container.",
        ),
        "run": OpSpec(
            op_name="run",
            permission_class=OpClass.WRITE,
            args=[
                _CONTAINER_ARG,
                ArgSpec(
                    name="command",
                    type=str,
                    required=True,
                    description="Command to execute inside the working container.",
                ),
            ],
            description="Run a command inside a working container.",
        ),
        "commit": OpSpec(
            op_name="commit",
            permission_class=OpClass.WRITE,
            args=[
                _CONTAINER_ARG,
                ArgSpec(
                    name="image",
                    type=str,
                    required=True,
                    description="Name for the resulting image (e.g. 'myapp:1.0').",
                ),
            ],
            description="Commit a working container to a new OCI image.",
        ),
        "push": OpSpec(
            op_name="push",
            permission_class=OpClass.WRITE,
            args=[_IMAGE_ARG],
            description="Push a local OCI image to a remote registry.",
        ),
        "build": OpSpec(
            op_name="build",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="tag",
                    type=str,
                    required=True,
                    description="Tag for the resulting image (e.g. 'myapp:1.0').",
                ),
                ArgSpec(
                    name="context",
                    type=str,
                    required=False,
                    description="Build context directory (default '.').",
                    default=".",
                ),
            ],
            description="Build an OCI image from a Containerfile or Dockerfile.",
        ),
        "rm": OpSpec(
            op_name="rm",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="container",
                    type=str,
                    required=False,
                    description="Name or ID of the working container to remove.",
                    default="",
                ),
                ArgSpec(
                    name="all",
                    type=bool,
                    required=False,
                    description="Remove all working containers (--all).",
                    default=False,
                ),
            ],
            description="Remove one or all working containers, discarding in-progress build state.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

registry.register(BUILDAH_SPEC)
