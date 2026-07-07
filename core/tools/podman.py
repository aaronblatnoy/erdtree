"""core/tools/podman.py — rootless container management via the podman CLI.

Supported operations
--------------------
  ps       (READ)        — list containers (running by default; --all to include stopped).
  images   (READ)        — list locally available images.
  inspect  (READ)        — show detailed JSON info for a container or image.
  logs     (READ)        — tail recent output from a container.
  pull     (WRITE)       — pull an image from a registry.
  run      (WRITE)       — create and start a container from an image.
  stop     (WRITE)       — send SIGTERM then SIGKILL to a running container.
  exec     (WRITE)       — run a command inside an existing running container.
  build    (WRITE)       — build an image from a Containerfile/Dockerfile context.
  push     (WRITE)       — push a local image to a registry.
  rm       (DESTRUCTIVE) — force-remove a container (running or stopped) with -f.
  rmi      (DESTRUCTIVE) — remove a local image.

Permission mapping (ADVISORY — the Phase-1 classifier is authoritative):
  READ        : ps, images, inspect, logs
  WRITE       : pull, run, stop, exec, build, push
  DESTRUCTIVE : rm, rmi

Notes
-----
  Rootless by default on RHEL 9 — no sudo prefix in any command vector.
  'podman rm -f' is always used for the rm op so the destructive argv shape is
  present verbatim and Phase-1 can detect it.  'podman rmi' removes a locally
  cached image; it is destructive even without -f.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against the LOCAL
      podman binary; this module imports NO socket-opening library.
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
# SELinux hint detection (copied verbatim per SLICE-CONTRACT §3)
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
    description="Container name or ID.",
)

_IMAGE_ARG = ArgSpec(
    name="image",
    type=str,
    required=True,
    description="Image name with optional tag (e.g. 'registry.access.redhat.com/ubi9:latest').",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_ps(args: dict[str, Any]) -> ToolResult:
    """podman ps [--all]"""
    show_all: bool = bool(args.get("all", False))
    cmd = ["podman", "ps"]
    if show_all:
        cmd.append("--all")
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        lines = result.stdout.strip().splitlines()
        count = max(0, len(lines) - 1)  # subtract header row
        qualifier = "all" if show_all else "running"
        summary = f"Listed {count} {qualifier} container(s)."
    else:
        summary = f"Failed to list containers (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_images(args: dict[str, Any]) -> ToolResult:
    """podman images"""
    result = run_subprocess(["podman", "images"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        lines = result.stdout.strip().splitlines()
        count = max(0, len(lines) - 1)  # subtract header row
        summary = f"Listed {count} local image(s)."
    else:
        summary = f"Failed to list images (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_inspect(args: dict[str, Any]) -> ToolResult:
    """podman inspect <target>"""
    target: str = args["target"]
    result = run_subprocess(["podman", "inspect", target])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Inspection data for '{target}' retrieved."
    else:
        summary = f"Failed to inspect '{target}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_logs(args: dict[str, Any]) -> ToolResult:
    """podman logs --tail <lines> <container>"""
    container: str = args["container"]
    raw_lines = args.get("lines")
    lines: int = int(raw_lines) if raw_lines is not None else 50
    lines = max(1, min(lines, 500))
    result = run_subprocess(
        ["podman", "logs", "--tail", str(lines), container]
    )
    selinux = _maybe_selinux_hint(result.stdout + result.stderr)
    if result.ok:
        line_count = (result.stdout + result.stderr).count("\n")
        summary = f"Retrieved {line_count} log line(s) for container '{container}'."
    else:
        summary = f"Log retrieval for container '{container}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pull(args: dict[str, Any]) -> ToolResult:
    """podman pull <image>"""
    image: str = args["image"]
    result = run_subprocess(["podman", "pull", image], timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Image '{image}' pulled successfully."
    else:
        summary = f"Failed to pull image '{image}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_run(args: dict[str, Any]) -> ToolResult:
    """podman run [--detach] [--name NAME] <image>"""
    image: str = args["image"]
    name: str = args.get("name", "")
    detach: bool = bool(args.get("detach", True))
    cmd = ["podman", "run"]
    if detach:
        cmd.append("--detach")
    if name:
        cmd.extend(["--name", name])
    cmd.append(image)
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        label = f" as '{name}'" if name else ""
        mode = " in detached mode" if detach else ""
        summary = f"Container from image '{image}' started{label}{mode}."
    else:
        summary = f"Failed to run container from '{image}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_stop(args: dict[str, Any]) -> ToolResult:
    """podman stop <container>"""
    container: str = args["container"]
    result = run_subprocess(["podman", "stop", container])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Container '{container}' stopped."
    else:
        summary = f"Failed to stop container '{container}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_exec(args: dict[str, Any]) -> ToolResult:
    """podman exec <container> <command...>"""
    container: str = args["container"]
    command: str = args["command"]
    cmd_parts = command.split()
    result = run_subprocess(["podman", "exec", container] + cmd_parts)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Command '{command}' executed in container '{container}'."
    else:
        summary = (
            f"Command '{command}' in container '{container}' failed "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_build(args: dict[str, Any]) -> ToolResult:
    """podman build [-t <tag>] <context>"""
    context: str = args["context"]
    tag: str = args.get("tag", "")
    cmd = ["podman", "build"]
    if tag:
        cmd.extend(["-t", tag])
    cmd.append(context)
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        label = f" tagged '{tag}'" if tag else ""
        summary = f"Image{label} built from context '{context}'."
    else:
        summary = f"Build from context '{context}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_push(args: dict[str, Any]) -> ToolResult:
    """podman push <image>"""
    image: str = args["image"]
    result = run_subprocess(["podman", "push", image], timeout=120)
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


def _op_rm(args: dict[str, Any]) -> ToolResult:
    """podman rm -f <container>  (DESTRUCTIVE — force-removes even running containers)"""
    container: str = args["container"]
    result = run_subprocess(["podman", "rm", "-f", container])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Container '{container}' removed."
    else:
        summary = f"Failed to remove container '{container}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_rmi(args: dict[str, Any]) -> ToolResult:
    """podman rmi <image>  (DESTRUCTIVE — removes locally cached image)"""
    image: str = args["image"]
    result = run_subprocess(["podman", "rmi", image])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Image '{image}' removed from local storage."
    else:
        summary = f"Failed to remove image '{image}' (exit {result.exit_code})."
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
    "ps":      _op_ps,
    "images":  _op_images,
    "inspect": _op_inspect,
    "logs":    _op_logs,
    "pull":    _op_pull,
    "run":     _op_run,
    "stop":    _op_stop,
    "exec":    _op_exec,
    "build":   _op_build,
    "push":    _op_push,
    "rm":      _op_rm,
    "rmi":     _op_rmi,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a podman operation and return a structured ToolResult.

    The caller (Phase 4 router) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never writes to the audit log (I4) and never calls permissions.classify()
    (I3).  It never raises (I9): any failure degrades to a well-formed result.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for podman tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

PODMAN_SPEC = ToolSpec(
    name="podman",
    description="Manage rootless containers and images via the podman CLI.",
    ops={
        "ps": OpSpec(
            op_name="ps",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="all",
                    type=bool,
                    required=False,
                    description="If true, show all containers including stopped ones.",
                    default=False,
                ),
            ],
            description="List containers (running by default; pass all=true to include stopped).",
        ),
        "images": OpSpec(
            op_name="images",
            permission_class=OpClass.READ,
            args=[],
            description="List locally available container images.",
        ),
        "inspect": OpSpec(
            op_name="inspect",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="target",
                    type=str,
                    required=True,
                    description="Container or image name/ID to inspect.",
                ),
            ],
            description="Show detailed information for a container or image.",
        ),
        "logs": OpSpec(
            op_name="logs",
            permission_class=OpClass.READ,
            args=[
                _CONTAINER_ARG,
                ArgSpec(
                    name="lines",
                    type=int,
                    required=False,
                    description="Number of log lines to retrieve (default 50, max 500).",
                    default=50,
                ),
            ],
            description="Retrieve recent log output from a container.",
        ),
        "pull": OpSpec(
            op_name="pull",
            permission_class=OpClass.WRITE,
            args=[_IMAGE_ARG],
            description="Pull an image from a container registry.",
        ),
        "run": OpSpec(
            op_name="run",
            permission_class=OpClass.WRITE,
            args=[
                _IMAGE_ARG,
                ArgSpec(
                    name="name",
                    type=str,
                    required=False,
                    description="Optional container name (--name).",
                    default=None,
                ),
                ArgSpec(
                    name="detach",
                    type=bool,
                    required=False,
                    description="Run container in detached mode (default true).",
                    default=True,
                ),
            ],
            description="Create and start a container from an image.",
        ),
        "stop": OpSpec(
            op_name="stop",
            permission_class=OpClass.WRITE,
            args=[_CONTAINER_ARG],
            description="Stop a running container.",
        ),
        "exec": OpSpec(
            op_name="exec",
            permission_class=OpClass.WRITE,
            args=[
                _CONTAINER_ARG,
                ArgSpec(
                    name="command",
                    type=str,
                    required=True,
                    description="Command string to execute inside the container (space-separated).",
                ),
            ],
            description="Run a command inside a running container.",
        ),
        "build": OpSpec(
            op_name="build",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="context",
                    type=str,
                    required=True,
                    description="Path to the build context directory containing a Containerfile or Dockerfile.",
                ),
                ArgSpec(
                    name="tag",
                    type=str,
                    required=False,
                    description="Optional image tag to apply to the built image (e.g. 'myapp:1.0').",
                    default=None,
                ),
            ],
            description="Build a container image from a Containerfile/Dockerfile.",
        ),
        "push": OpSpec(
            op_name="push",
            permission_class=OpClass.WRITE,
            args=[_IMAGE_ARG],
            description="Push a local image to a container registry.",
        ),
        "rm": OpSpec(
            op_name="rm",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_CONTAINER_ARG],
            description=(
                "Force-remove a container (running or stopped) with -f. "
                "Destroys the container's writable layer — irreversible."
            ),
        ),
        "rmi": OpSpec(
            op_name="rmi",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_IMAGE_ARG],
            description=(
                "Remove a locally cached image. "
                "Destroys the image from local storage — irreversible."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(PODMAN_SPEC)
