"""finetune/scenarios_v3/buildah.py — corpus v3 multi-turn scenarios for 'buildah'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="buildah-v3-0001", tool="buildah", kind="followup", turns=(
        Turn(user_input="list the local images on this box", tool="buildah", operation="images", args={"operation": "images"}),
        Turn(user_input="include the intermediate ones too", tool="buildah", operation="images", args={"operation": "images", "all": True}),
    )),
    V3(id="buildah-v3-0002", tool="buildah", kind="followup", turns=(
        Turn(user_input="start a working container from registry.access.redhat.com/ubi9/ubi:latest", tool="buildah", operation="from", args={"operation": "from", "image": "registry.access.redhat.com/ubi9/ubi:latest"}),
        Turn(user_input="now copy ./app.conf into it at /etc/app.conf", tool="buildah", operation="copy", args={"operation": "copy", "container": "ubi9-working-container", "src": "./app.conf", "dst": "/etc/app.conf"}),
    )),
    V3(id="buildah-v3-0003", tool="buildah", kind="followup", turns=(
        Turn(user_input="run 'dnf install -y nginx' inside the ubi9-working-container", tool="buildah", operation="run", args={"operation": "run", "container": "ubi9-working-container", "command": "dnf install -y nginx"}),
        Turn(user_input="yes go ahead and commit it as myapp:1.0", tool="buildah", operation="commit", args={"operation": "commit", "container": "ubi9-working-container", "image": "myapp:1.0"}),
    )),
    V3(id="buildah-v3-0004", tool="buildah", kind="followup", turns=(
        Turn(user_input="build an image tagged myapp:2.0 from the Containerfile in ./build", tool="buildah", operation="build", args={"operation": "build", "tag": "myapp:2.0", "context": "./build"}),
        Turn(user_input="do the same but tag it myapp:2.0-arm64", tool="buildah", operation="build", args={"operation": "build", "tag": "myapp:2.0-arm64", "context": "./build"}),
    )),
    V3(id="buildah-v3-0005", tool="buildah", kind="followup", turns=(
        Turn(user_input="build myapp:3.0 from the default context", tool="buildah", operation="build", args={"operation": "build", "tag": "myapp:3.0"}),
        Turn(user_input="now push it to the registry", tool="buildah", operation="push", args={"operation": "push", "image": "myapp:3.0"}),
    )),
    V3(id="buildah-v3-0006", tool="buildah", kind="followup", turns=(
        Turn(user_input="create a working container from myapp:1.0", tool="buildah", operation="from", args={"operation": "from", "image": "myapp:1.0"}),
        Turn(user_input="actually undo that, use myapp:0.9 instead", tool="buildah", operation="from", args={"operation": "from", "image": "myapp:0.9"}),
    )),
    V3(id="buildah-v3-0007", tool="buildah", kind="followup", turns=(
        Turn(user_input="remove the working container named stale-build-ctr", tool="buildah", operation="rm", args={"operation": "rm", "container": "stale-build-ctr"}),
        Turn(user_input="and now check what images are left on the host", tool="buildah", operation="images", args={"operation": "images"}),
    )),
    V3(id="buildah-v3-0008", tool="buildah", kind="followup", turns=(
        Turn(user_input="build myapp:4.0 from ./ci/context", tool="buildah", operation="build", args={"operation": "build", "tag": "myapp:4.0", "context": "./ci/context"}),
        Turn(user_input="commit the container it left running as myapp:4.0-checkpoint", tool="buildah", operation="commit", args={"operation": "commit", "container": "myapp-4-0-working-container", "image": "myapp:4.0-checkpoint"}),
        Turn(user_input="now push that checkpoint image", tool="buildah", operation="push", args={"operation": "push", "image": "myapp:4.0-checkpoint"}),
    )),
    V3(id="buildah-v3-0009", tool="buildah", kind="followup", turns=(
        Turn(user_input="from image registry.access.redhat.com/ubi9/ubi-minimal:latest, start a working container", tool="buildah", operation="from", args={"operation": "from", "image": "registry.access.redhat.com/ubi9/ubi-minimal:latest"}),
        Turn(user_input="copy ./bin/entrypoint.sh into it at /usr/local/bin/entrypoint.sh", tool="buildah", operation="copy", args={"operation": "copy", "container": "ubi9-minimal-working-container", "src": "./bin/entrypoint.sh", "dst": "/usr/local/bin/entrypoint.sh"}),
        Turn(user_input="do the same chmod +x /usr/local/bin/entrypoint.sh on that same container", tool="buildah", operation="run", args={"operation": "run", "container": "ubi9-minimal-working-container", "command": "chmod +x /usr/local/bin/entrypoint.sh"}),
    )),
    V3(id="buildah-v3-0010", tool="buildah", kind="question", turns=(
        Turn(user_input="build myapp:5.0 from the ./svc context", tool="buildah", operation="build", args={"operation": "build", "tag": "myapp:5.0", "context": "./svc"}),
        Turn(user_input="what does that build output tell me", answer="The build log shows each Containerfile instruction running in order and the final layer being committed as myapp:5.0. If the last line is a COMMIT with an image ID, the tag exists locally and is ready to push. Check the exit status if you need to confirm no step failed."),
    )),
    V3(id="buildah-v3-0011", tool="buildah", kind="question", turns=(
        Turn(user_input="push myapp:3.0 to the registry", tool="buildah", operation="push", args={"operation": "push", "image": "myapp:3.0"}),
        Turn(user_input="why did that push fail", answer="A push failure is almost always registry auth (no login token or an expired one) or a network/DNS issue reaching the registry host. Check `buildah login` status for the target registry and confirm the tag matches an image that actually exists locally."),
    )),
    V3(id="buildah-v3-0012", tool="buildah", kind="question", turns=(
        Turn(user_input="remove all the working containers on this host", tool="buildah", operation="rm", args={"operation": "rm", "all": True}),
        Turn(user_input="what did removing all of those actually clean up", answer="That drops every working container's writable layer and any uncommitted changes made inside them since buildah from. It does not touch images already committed with buildah commit — those stay in local storage until you remove them separately."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("buildah", SCENARIOS_V3)
