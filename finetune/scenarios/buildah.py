"""finetune/scenarios/buildah.py — Scenario corpus for the 'buildah' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  images   READ        — list locally stored OCI images
  from     WRITE       — create a working container from a base image
  copy     WRITE       — copy files into a working container
  run      WRITE       — run a command inside a working container
  commit   WRITE       — commit a working container to a new image
  push     WRITE       — push a local image to a registry
  build    WRITE       — build an image from a Containerfile/Dockerfile
  rm       DESTRUCTIVE — remove one or more working containers

Coverage targets
----------------
  >= 40 entries total across all 8 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so traces teach the gate.

INV-schema-sync:  permission_class for each entry is derived from the LIVE
  registry via finetune.coreimports, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass
# Compatible field names are EXACT so the Phase-13 JOIN can unify without renames.
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
    """Return the live permission class for a buildah operation."""
    return registry.get("buildah").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # images  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="buildah-images-0001",
        tool="buildah",
        operation="images",
        permission_class=_pc("images"),
        complexity="single",
        user_input="list all local container images",
        notes="Basic image inventory before starting a build.",
    ),
    Scenario(
        id="buildah-images-0002",
        tool="buildah",
        operation="images",
        permission_class=_pc("images"),
        complexity="single",
        user_input="show me what container images buildah knows about",
        notes="Admin verifying image cache on the build host.",
    ),
    Scenario(
        id="buildah-images-0003",
        tool="buildah",
        operation="images",
        permission_class=_pc("images"),
        complexity="single",
        user_input="list buildah images including intermediate layers",
        notes="Using --all to surface intermediate/dangling images.",
    ),
    Scenario(
        id="buildah-images-0004",
        tool="buildah",
        operation="images",
        permission_class=_pc("images"),
        complexity="multi",
        user_input="show the local buildah images and tell me which ones look like dangling intermediates",
        notes="Multi-step: list images then interpret which lack a tag.",
    ),
    Scenario(
        id="buildah-images-0005",
        tool="buildah",
        operation="images",
        permission_class=_pc("images"),
        complexity="diagnostic",
        user_input="the build server is running low on disk — list buildah images so I can decide what to clean up",
        notes="Diagnostic: image inventory to inform cleanup decision.",
    ),
    Scenario(
        id="buildah-images-0006",
        tool="buildah",
        operation="images",
        permission_class=_pc("images"),
        complexity="single",
        user_input="what UBI9 images does buildah have cached locally?",
        notes="Filtering interest: admin checks for RHEL UBI base images.",
    ),

    # =========================================================================
    # from  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="buildah-from-0001",
        tool="buildah",
        operation="from",
        permission_class=_pc("from"),
        complexity="single",
        user_input="create a working container from ubi9",
        notes="WRITE: pull/use UBI9 as base and create a working container.",
    ),
    Scenario(
        id="buildah-from-0002",
        tool="buildah",
        operation="from",
        permission_class=_pc("from"),
        complexity="single",
        user_input="start a new buildah container from the official nginx image",
        notes="WRITE: create working container from nginx base for customization.",
    ),
    Scenario(
        id="buildah-from-0003",
        tool="buildah",
        operation="from",
        permission_class=_pc("from"),
        complexity="multi",
        user_input="create a working container from ubi9-minimal and then install python3 in it",
        notes="Multi-step: from base image then run an install command inside.",
    ),
    Scenario(
        id="buildah-from-0004",
        tool="buildah",
        operation="from",
        permission_class=_pc("from"),
        complexity="single",
        user_input="initialize a container from registry.access.redhat.com/ubi9/ubi:9.3",
        notes="WRITE: explicit registry path with pinned tag.",
    ),
    Scenario(
        id="buildah-from-0005",
        tool="buildah",
        operation="from",
        permission_class=_pc("from"),
        complexity="diagnostic",
        user_input="the build is failing — start fresh with a new working container from scratch",
        notes="Diagnostic-triggered WRITE: create a new base after a failed attempt.",
    ),
    Scenario(
        id="buildah-from-0006",
        tool="buildah",
        operation="from",
        permission_class=_pc("from"),
        complexity="single",
        user_input="use buildah to create a container based on the fedora image",
        notes="WRITE: fedora base for development container.",
    ),

    # =========================================================================
    # copy  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="buildah-copy-0001",
        tool="buildah",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="single",
        user_input="copy the app directory into the working container at /app",
        notes="WRITE: copy application source files into a build container.",
    ),
    Scenario(
        id="buildah-copy-0002",
        tool="buildah",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="single",
        user_input="add my nginx.conf file to the ubi9-working-container at /etc/nginx/nginx.conf",
        notes="WRITE: install a config file into the container.",
    ),
    Scenario(
        id="buildah-copy-0003",
        tool="buildah",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="multi",
        user_input="copy the binary and the config into the container then commit the result",
        notes="Multi-step: copy files then commit to a new image.",
    ),
    Scenario(
        id="buildah-copy-0004",
        tool="buildah",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="single",
        user_input="copy ./dist/app to /usr/local/bin/app inside myapp-working-container",
        notes="WRITE: place a compiled binary into its target location.",
    ),
    Scenario(
        id="buildah-copy-0005",
        tool="buildah",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="diagnostic",
        user_input="the container is missing the config file — copy ./config/prod.yaml into /etc/app/config.yaml",
        notes="Diagnostic-triggered WRITE: fix a missing file in a build container.",
    ),
    Scenario(
        id="buildah-copy-0006",
        tool="buildah",
        operation="copy",
        permission_class=_pc("copy"),
        complexity="single",
        user_input="add the entrypoint script to /usr/local/sbin/entrypoint.sh in the working container",
        notes="WRITE: install an entrypoint script into the container.",
    ),

    # =========================================================================
    # run  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="buildah-run-0001",
        tool="buildah",
        operation="run",
        permission_class=_pc("run"),
        complexity="single",
        user_input="run dnf install -y nginx inside the ubi9 working container",
        notes="WRITE: install a package inside a build container.",
    ),
    Scenario(
        id="buildah-run-0002",
        tool="buildah",
        operation="run",
        permission_class=_pc("run"),
        complexity="single",
        user_input="execute dnf clean all in the working container to reduce image size",
        notes="WRITE: clean package caches after installation.",
    ),
    Scenario(
        id="buildah-run-0003",
        tool="buildah",
        operation="run",
        permission_class=_pc("run"),
        complexity="multi",
        user_input="run the test suite inside the container and then commit if it passes",
        notes="Multi-step: run tests inside container then conditionally commit.",
    ),
    Scenario(
        id="buildah-run-0004",
        tool="buildah",
        operation="run",
        permission_class=_pc("run"),
        complexity="single",
        user_input="run useradd -r -s /sbin/nologin appuser inside the container",
        notes="WRITE: create a non-login service account inside the build container.",
    ),
    Scenario(
        id="buildah-run-0005",
        tool="buildah",
        operation="run",
        permission_class=_pc("run"),
        complexity="diagnostic",
        user_input="the image startup is failing — run /usr/sbin/nginx -t inside the container to check the config",
        notes="Diagnostic: validate nginx config inside the container before committing.",
    ),
    Scenario(
        id="buildah-run-0006",
        tool="buildah",
        operation="run",
        permission_class=_pc("run"),
        complexity="single",
        user_input="execute chmod 755 /usr/local/bin/app inside myapp-working-container",
        notes="WRITE: set executable permissions on a binary inside the container.",
    ),

    # =========================================================================
    # commit  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="buildah-commit-0001",
        tool="buildah",
        operation="commit",
        permission_class=_pc("commit"),
        complexity="single",
        user_input="commit the working container as myapp:1.0",
        notes="WRITE: snapshot the working container into a named image.",
    ),
    Scenario(
        id="buildah-commit-0002",
        tool="buildah",
        operation="commit",
        permission_class=_pc("commit"),
        complexity="single",
        user_input="save the current ubi9-working-container as localhost/nginx-custom:latest",
        notes="WRITE: commit to local registry namespace.",
    ),
    Scenario(
        id="buildah-commit-0003",
        tool="buildah",
        operation="commit",
        permission_class=_pc("commit"),
        complexity="multi",
        user_input="finish the build by committing the container then push it to the registry",
        notes="Multi-step: commit then push — full build pipeline conclusion.",
    ),
    Scenario(
        id="buildah-commit-0004",
        tool="buildah",
        operation="commit",
        permission_class=_pc("commit"),
        complexity="single",
        user_input="create a new image called api-server:2.1 from the api-working-container",
        notes="WRITE: commit a version-tagged API server image.",
    ),
    Scenario(
        id="buildah-commit-0005",
        tool="buildah",
        operation="commit",
        permission_class=_pc("commit"),
        complexity="diagnostic",
        user_input="the build looks good — commit it so I can test the resulting image",
        notes="Diagnostic-triggered WRITE: commit after verifying content with buildah run.",
    ),
    Scenario(
        id="buildah-commit-0006",
        tool="buildah",
        operation="commit",
        permission_class=_pc("commit"),
        complexity="single",
        user_input="commit the myapp-working-container as quay.io/myorg/myapp:v1.2.3",
        notes="WRITE: commit with a fully qualified registry path.",
    ),

    # =========================================================================
    # push  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="buildah-push-0001",
        tool="buildah",
        operation="push",
        permission_class=_pc("push"),
        complexity="single",
        user_input="push myapp:1.0 to the registry",
        notes="WRITE: push a built image to the default registry.",
    ),
    Scenario(
        id="buildah-push-0002",
        tool="buildah",
        operation="push",
        permission_class=_pc("push"),
        complexity="single",
        user_input="upload quay.io/myorg/nginx-custom:latest to Quay",
        notes="WRITE: push to a specific external registry.",
    ),
    Scenario(
        id="buildah-push-0003",
        tool="buildah",
        operation="push",
        permission_class=_pc("push"),
        complexity="multi",
        user_input="build the image as api-server:3.0 and then push it to the internal registry",
        notes="Multi-step: build then push — complete pipeline.",
    ),
    Scenario(
        id="buildah-push-0004",
        tool="buildah",
        operation="push",
        permission_class=_pc("push"),
        complexity="diagnostic",
        user_input="the CI pipeline failed at the push step — retry pushing localhost/myapp:latest",
        notes="Diagnostic: retry a failed registry push.",
    ),
    Scenario(
        id="buildah-push-0005",
        tool="buildah",
        operation="push",
        permission_class=_pc("push"),
        complexity="single",
        user_input="push registry.example.com/ops/toolbox:9.3 to the internal registry",
        notes="WRITE: push an internal toolbox image.",
    ),

    # =========================================================================
    # build  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="buildah-build-0001",
        tool="buildah",
        operation="build",
        permission_class=_pc("build"),
        complexity="single",
        user_input="build a container image tagged myapp:latest from the current directory",
        notes="WRITE: basic image build from local Containerfile.",
    ),
    Scenario(
        id="buildah-build-0002",
        tool="buildah",
        operation="build",
        permission_class=_pc("build"),
        complexity="single",
        user_input="build the image as api-server:2.0 using the Containerfile in ./docker",
        notes="WRITE: build from a non-default context directory.",
    ),
    Scenario(
        id="buildah-build-0003",
        tool="buildah",
        operation="build",
        permission_class=_pc("build"),
        complexity="multi",
        user_input="build nginx-custom:1.0 from the current directory then push it to the registry",
        notes="Multi-step: build then push — common CI workflow.",
    ),
    Scenario(
        id="buildah-build-0004",
        tool="buildah",
        operation="build",
        permission_class=_pc("build"),
        complexity="single",
        user_input="build a production image tagged quay.io/myorg/myapp:v2.3.1 from ./build",
        notes="WRITE: build with a fully-qualified registry tag from a specific path.",
    ),
    Scenario(
        id="buildah-build-0005",
        tool="buildah",
        operation="build",
        permission_class=_pc("build"),
        complexity="diagnostic",
        user_input="the previous build failed halfway through — rebuild the image tagged myapp:dev from scratch",
        notes="Diagnostic-triggered WRITE: rebuild after a partial failure.",
    ),
    Scenario(
        id="buildah-build-0006",
        tool="buildah",
        operation="build",
        permission_class=_pc("build"),
        complexity="single",
        user_input="use buildah to build the Containerfile in this directory and tag it as ops-toolbox:latest",
        notes="WRITE: build an operations toolbox image for internal use.",
    ),

    # =========================================================================
    # rm  (DESTRUCTIVE) — 5 entries
    # =========================================================================

    Scenario(
        id="buildah-rm-0001",
        tool="buildah",
        operation="rm",
        permission_class=_pc("rm"),
        complexity="single",
        user_input="remove the ubi9-working-container — I'm done with that build",
        notes="DESTRUCTIVE: discard a working container after a build is complete.",
    ),
    Scenario(
        id="buildah-rm-0002",
        tool="buildah",
        operation="rm",
        permission_class=_pc("rm"),
        complexity="single",
        user_input="clean up all buildah working containers on this host",
        notes="DESTRUCTIVE: remove all working containers (--all flag).",
    ),
    Scenario(
        id="buildah-rm-0003",
        tool="buildah",
        operation="rm",
        permission_class=_pc("rm"),
        complexity="multi",
        user_input="list working containers with buildah containers, then remove the stale ones",
        notes="Multi-step: inspect then selectively remove stale working containers.",
    ),
    Scenario(
        id="buildah-rm-0004",
        tool="buildah",
        operation="rm",
        permission_class=_pc("rm"),
        complexity="diagnostic",
        user_input="buildah is complaining about a locked container — remove myapp-working-container and start over",
        notes="Diagnostic-triggered DESTRUCTIVE: remove a corrupted or locked working container.",
    ),
    Scenario(
        id="buildah-rm-0005",
        tool="buildah",
        operation="rm",
        permission_class=_pc("rm"),
        complexity="single",
        user_input="delete the nginx-working-container — the build was committed already",
        notes="DESTRUCTIVE: routine cleanup after a successful commit.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("buildah").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "buildah", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("buildah").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
