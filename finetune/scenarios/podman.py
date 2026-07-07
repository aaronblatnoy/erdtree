"""finetune/scenarios/podman.py — Scenario corpus for the 'podman' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  ps       READ        — list containers (running by default)
  images   READ        — list locally available images
  inspect  READ        — show detailed info for a container or image
  logs     READ        — tail recent output from a container
  pull     WRITE       — pull an image from a registry
  run      WRITE       — create and start a container
  stop     WRITE       — stop a running container
  exec     WRITE       — run a command inside a running container
  build    WRITE       — build an image from a Containerfile/Dockerfile
  push     WRITE       — push a local image to a registry
  rm       DESTRUCTIVE — force-remove a container (running or stopped)
  rmi      DESTRUCTIVE — remove a locally cached image

Coverage targets
----------------
  >= 45 entries across all 12 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios honestly labeled so training traces teach the
  escalated confirm-before-execute gate.

INV-schema-sync: permission_class for each entry is derived from the LIVE
  registry via finetune.coreimports, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass (local — compatible field names for Phase-13 JOIN)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    id: str
    tool: str
    operation: str
    permission_class: OpClass
    complexity: Literal["single", "multi", "diagnostic"]
    user_input: str
    notes: str


# ---------------------------------------------------------------------------
# Live permission-class lookup — INV-schema-sync
# ---------------------------------------------------------------------------


def _pc(op: str) -> OpClass:
    """Return the live permission class for a podman operation."""
    return registry.get("podman").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # ps  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="podman-ps-0001",
        tool="podman",
        operation="ps",
        permission_class=_pc("ps"),
        complexity="single",
        user_input="show me all running containers",
        notes="Simple read: list active containers with ps.",
    ),
    Scenario(
        id="podman-ps-0002",
        tool="podman",
        operation="ps",
        permission_class=_pc("ps"),
        complexity="single",
        user_input="which containers are currently up on this host?",
        notes="Operator check for live container inventory.",
    ),
    Scenario(
        id="podman-ps-0003",
        tool="podman",
        operation="ps",
        permission_class=_pc("ps"),
        complexity="single",
        user_input="list all containers including stopped ones",
        notes="READ with all=true to include exited containers.",
    ),
    Scenario(
        id="podman-ps-0004",
        tool="podman",
        operation="ps",
        permission_class=_pc("ps"),
        complexity="diagnostic",
        user_input="the web app seems down — check if the container is still running",
        notes="Diagnostic first step: confirm container state before deeper investigation.",
    ),
    Scenario(
        id="podman-ps-0005",
        tool="podman",
        operation="ps",
        permission_class=_pc("ps"),
        complexity="multi",
        user_input="list running containers and then show me the logs from the api container",
        notes="Multi-step: discover containers then inspect their logs.",
    ),

    # =========================================================================
    # images  (READ) — 4 entries
    # =========================================================================

    Scenario(
        id="podman-images-0001",
        tool="podman",
        operation="images",
        permission_class=_pc("images"),
        complexity="single",
        user_input="what images do I have locally?",
        notes="Simple inventory of locally cached images.",
    ),
    Scenario(
        id="podman-images-0002",
        tool="podman",
        operation="images",
        permission_class=_pc("images"),
        complexity="single",
        user_input="show me all container images on this machine",
        notes="Full local image list for housekeeping.",
    ),
    Scenario(
        id="podman-images-0003",
        tool="podman",
        operation="images",
        permission_class=_pc("images"),
        complexity="diagnostic",
        user_input="before pulling ubi9, check if I already have it locally",
        notes="Diagnostic: check local cache before initiating a pull.",
    ),
    Scenario(
        id="podman-images-0004",
        tool="podman",
        operation="images",
        permission_class=_pc("images"),
        complexity="multi",
        user_input="list images and then remove any that are tagged '<none>'",
        notes="Multi-step: inventory images then clean up dangling entries.",
    ),

    # =========================================================================
    # inspect  (READ) — 4 entries
    # =========================================================================

    Scenario(
        id="podman-inspect-0001",
        tool="podman",
        operation="inspect",
        permission_class=_pc("inspect"),
        complexity="single",
        user_input="inspect the web-app container",
        notes="Single READ: detailed JSON info for a named container.",
    ),
    Scenario(
        id="podman-inspect-0002",
        tool="podman",
        operation="inspect",
        permission_class=_pc("inspect"),
        complexity="single",
        user_input="show me the full details for the nginx:1.25 image",
        notes="Inspect an image to check its config and layers.",
    ),
    Scenario(
        id="podman-inspect-0003",
        tool="podman",
        operation="inspect",
        permission_class=_pc("inspect"),
        complexity="diagnostic",
        user_input="the container keeps restarting — inspect it to find the exit code",
        notes="Diagnostic: inspect state block to determine crash reason.",
    ),
    Scenario(
        id="podman-inspect-0004",
        tool="podman",
        operation="inspect",
        permission_class=_pc("inspect"),
        complexity="multi",
        user_input="inspect the postgres container to find its IP address, then verify the port is open",
        notes="Multi-step: inspect for network config, then connectivity check.",
    ),

    # =========================================================================
    # logs  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="podman-logs-0001",
        tool="podman",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="single",
        user_input="show me the last 50 log lines from the api container",
        notes="Standard log tail for a running application container.",
    ),
    Scenario(
        id="podman-logs-0002",
        tool="podman",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="single",
        user_input="get recent output from the nginx container",
        notes="READ: quick log check for a web server container.",
    ),
    Scenario(
        id="podman-logs-0003",
        tool="podman",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="diagnostic",
        user_input="the app crashed — pull the last 200 log lines from the web-app container to find the error",
        notes="Diagnostic: post-crash log pull with increased line count.",
    ),
    Scenario(
        id="podman-logs-0004",
        tool="podman",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="multi",
        user_input="show logs from the worker container and flag any ERROR lines",
        notes="Multi-step: retrieve logs and analyse for error patterns.",
    ),
    Scenario(
        id="podman-logs-0005",
        tool="podman",
        operation="logs",
        permission_class=_pc("logs"),
        complexity="diagnostic",
        user_input="the database container is slow — show me the last 100 log entries",
        notes="Diagnostic: performance investigation via log review.",
    ),

    # =========================================================================
    # pull  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="podman-pull-0001",
        tool="podman",
        operation="pull",
        permission_class=_pc("pull"),
        complexity="single",
        user_input="pull the latest ubi9 base image",
        notes="WRITE: pull a Red Hat UBI base image.",
    ),
    Scenario(
        id="podman-pull-0002",
        tool="podman",
        operation="pull",
        permission_class=_pc("pull"),
        complexity="single",
        user_input="download the nginx 1.25 container image",
        notes="WRITE: pull a specific versioned image.",
    ),
    Scenario(
        id="podman-pull-0003",
        tool="podman",
        operation="pull",
        permission_class=_pc("pull"),
        complexity="multi",
        user_input="pull the postgres image and then run a container from it",
        notes="Multi-step WRITE: pull then run.",
    ),
    Scenario(
        id="podman-pull-0004",
        tool="podman",
        operation="pull",
        permission_class=_pc("pull"),
        complexity="diagnostic",
        user_input="the app needs a newer version of redis — pull redis:7.2 to update",
        notes="Diagnostic-triggered WRITE: pull a newer image version as remediation.",
    ),

    # =========================================================================
    # run  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="podman-run-0001",
        tool="podman",
        operation="run",
        permission_class=_pc("run"),
        complexity="single",
        user_input="start a detached nginx container named web-front",
        notes="WRITE: launch a named web server container in detached mode.",
    ),
    Scenario(
        id="podman-run-0002",
        tool="podman",
        operation="run",
        permission_class=_pc("run"),
        complexity="single",
        user_input="run a redis container in the background",
        notes="WRITE: start an in-memory cache container detached.",
    ),
    Scenario(
        id="podman-run-0003",
        tool="podman",
        operation="run",
        permission_class=_pc("run"),
        complexity="multi",
        user_input="run a postgres container called db and then check that it is running",
        notes="Multi-step WRITE: start container, then verify via ps.",
    ),
    Scenario(
        id="podman-run-0004",
        tool="podman",
        operation="run",
        permission_class=_pc("run"),
        complexity="diagnostic",
        user_input="the old container stopped — restart it by running a new one from the same image",
        notes="Diagnostic-triggered WRITE: re-launch a stopped service as a new container.",
    ),

    # =========================================================================
    # stop  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="podman-stop-0001",
        tool="podman",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="stop the web-front container",
        notes="WRITE: graceful stop of a named container.",
    ),
    Scenario(
        id="podman-stop-0002",
        tool="podman",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="single",
        user_input="shut down the redis container for maintenance",
        notes="WRITE: stop cache container before maintenance.",
    ),
    Scenario(
        id="podman-stop-0003",
        tool="podman",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="multi",
        user_input="stop the api container and confirm it is no longer running",
        notes="Multi-step WRITE: stop then verify with ps.",
    ),
    Scenario(
        id="podman-stop-0004",
        tool="podman",
        operation="stop",
        permission_class=_pc("stop"),
        complexity="diagnostic",
        user_input="the worker container is consuming too much CPU — stop it immediately",
        notes="Diagnostic-triggered WRITE: emergency stop of a runaway container.",
    ),

    # =========================================================================
    # exec  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="podman-exec-0001",
        tool="podman",
        operation="exec",
        permission_class=_pc("exec"),
        complexity="single",
        user_input="run 'ls /app' inside the web-app container",
        notes="WRITE: inspect container filesystem via exec.",
    ),
    Scenario(
        id="podman-exec-0002",
        tool="podman",
        operation="exec",
        permission_class=_pc("exec"),
        complexity="single",
        user_input="execute 'ps aux' in the db container to see its processes",
        notes="WRITE: check running processes inside a container.",
    ),
    Scenario(
        id="podman-exec-0003",
        tool="podman",
        operation="exec",
        permission_class=_pc("exec"),
        complexity="diagnostic",
        user_input="the app can't connect to the database — exec into the api container and try 'curl db:5432'",
        notes="Diagnostic: connectivity check from inside the container network namespace.",
    ),
    Scenario(
        id="podman-exec-0004",
        tool="podman",
        operation="exec",
        permission_class=_pc("exec"),
        complexity="multi",
        user_input="exec into the worker container to run a manual flush command, then check the logs",
        notes="Multi-step WRITE: exec to trigger an action, then review output via logs.",
    ),

    # =========================================================================
    # build  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="podman-build-0001",
        tool="podman",
        operation="build",
        permission_class=_pc("build"),
        complexity="single",
        user_input="build an image tagged myapp:1.0 from the current directory",
        notes="WRITE: build image from a local Containerfile.",
    ),
    Scenario(
        id="podman-build-0002",
        tool="podman",
        operation="build",
        permission_class=_pc("build"),
        complexity="single",
        user_input="build a container image from the /opt/myservice build context",
        notes="WRITE: build from a named context directory.",
    ),
    Scenario(
        id="podman-build-0003",
        tool="podman",
        operation="build",
        permission_class=_pc("build"),
        complexity="multi",
        user_input="build the app image and then push it to the registry",
        notes="Multi-step WRITE: build then push pipeline.",
    ),
    Scenario(
        id="podman-build-0004",
        tool="podman",
        operation="build",
        permission_class=_pc("build"),
        complexity="diagnostic",
        user_input="the previous image had a bug — rebuild from ./app tagged fix:1.1",
        notes="Diagnostic-triggered WRITE: rebuild image after a fix is applied.",
    ),

    # =========================================================================
    # push  (WRITE) — 3 entries
    # =========================================================================

    Scenario(
        id="podman-push-0001",
        tool="podman",
        operation="push",
        permission_class=_pc("push"),
        complexity="single",
        user_input="push the myapp:1.0 image to the company registry",
        notes="WRITE: publish a locally built image to a container registry.",
    ),
    Scenario(
        id="podman-push-0002",
        tool="podman",
        operation="push",
        permission_class=_pc("push"),
        complexity="multi",
        user_input="build the image tagged release:2.0 and then push it to the registry",
        notes="Multi-step WRITE: build + push pipeline.",
    ),
    Scenario(
        id="podman-push-0003",
        tool="podman",
        operation="push",
        permission_class=_pc("push"),
        complexity="diagnostic",
        user_input="the deployment pipeline failed because the image wasn't in the registry — push it now",
        notes="Diagnostic-triggered WRITE: push a missing image to unblock deployment.",
    ),

    # =========================================================================
    # rm  (DESTRUCTIVE) — 4 entries
    # =========================================================================

    Scenario(
        id="podman-rm-0001",
        tool="podman",
        operation="rm",
        permission_class=_pc("rm"),
        complexity="single",
        user_input="force remove the old-worker container",
        notes="DESTRUCTIVE: force-remove a stopped container by name.",
    ),
    Scenario(
        id="podman-rm-0002",
        tool="podman",
        operation="rm",
        permission_class=_pc("rm"),
        complexity="single",
        user_input="delete the crashed api container so I can start a fresh one",
        notes="DESTRUCTIVE: clean up a crashed container before re-launching.",
    ),
    Scenario(
        id="podman-rm-0003",
        tool="podman",
        operation="rm",
        permission_class=_pc("rm"),
        complexity="multi",
        user_input="stop the web-front container and then remove it",
        notes="Multi-step DESTRUCTIVE: stop then force-remove a container.",
    ),
    Scenario(
        id="podman-rm-0004",
        tool="podman",
        operation="rm",
        permission_class=_pc("rm"),
        complexity="diagnostic",
        user_input="the container is stuck in a bad state and won't stop normally — force remove it",
        notes="Diagnostic-triggered DESTRUCTIVE: force-remove a stuck container.",
    ),

    # =========================================================================
    # rmi  (DESTRUCTIVE) — 4 entries
    # =========================================================================

    Scenario(
        id="podman-rmi-0001",
        tool="podman",
        operation="rmi",
        permission_class=_pc("rmi"),
        complexity="single",
        user_input="remove the old nginx:1.24 image from local storage",
        notes="DESTRUCTIVE: delete an outdated image from local cache.",
    ),
    Scenario(
        id="podman-rmi-0002",
        tool="podman",
        operation="rmi",
        permission_class=_pc("rmi"),
        complexity="single",
        user_input="delete the myapp:0.9 image — we've moved to 1.0",
        notes="DESTRUCTIVE: remove a superseded application image.",
    ),
    Scenario(
        id="podman-rmi-0003",
        tool="podman",
        operation="rmi",
        permission_class=_pc("rmi"),
        complexity="multi",
        user_input="list images and remove any that are older versions of ubi9",
        notes="Multi-step DESTRUCTIVE: inventory then selectively remove old images.",
    ),
    Scenario(
        id="podman-rmi-0004",
        tool="podman",
        operation="rmi",
        permission_class=_pc("rmi"),
        complexity="diagnostic",
        user_input="disk space is running low — remove the unused test:latest image to free up space",
        notes="Diagnostic-triggered DESTRUCTIVE: remove an image to reclaim disk space.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("podman").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "podman", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("podman").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
