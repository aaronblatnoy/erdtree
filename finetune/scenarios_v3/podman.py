"""finetune/scenarios_v3/podman.py — corpus v3 multi-turn scenarios for 'podman'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="podman-v3-0001", tool="podman", kind="followup", turns=(
        Turn(user_input="list the running containers", tool="podman", operation="ps",
             args={"operation": "ps"}),
        Turn(user_input="that missed the stopped ones, show all containers instead", tool="podman", operation="ps",
             args={"operation": "ps", "all": True}),
    )),
    V3(id="podman-v3-0002", tool="podman", kind="followup", turns=(
        Turn(user_input="pull registry.access.redhat.com/ubi9:latest", tool="podman", operation="pull",
             args={"operation": "pull", "image": "registry.access.redhat.com/ubi9:latest"}),
        Turn(user_input="now run it as a container named ubi9-test", tool="podman", operation="run",
             args={"operation": "run", "image": "registry.access.redhat.com/ubi9:latest", "name": "ubi9-test"}),
    )),
    V3(id="podman-v3-0003", tool="podman", kind="followup", turns=(
        Turn(user_input="tail the logs for container nginx-proxy", tool="podman", operation="logs",
             args={"operation": "logs", "container": "nginx-proxy"}),
        Turn(user_input="and the same for the haproxy container", tool="podman", operation="logs",
             args={"operation": "logs", "container": "haproxy"}),
    )),
    V3(id="podman-v3-0004", tool="podman", kind="followup", turns=(
        Turn(user_input="show detailed info on the postgres-14 container", tool="podman", operation="inspect",
             args={"operation": "inspect", "target": "postgres-14"}),
        Turn(user_input="it looks unhealthy, stop it", tool="podman", operation="stop",
             args={"operation": "stop", "container": "postgres-14"}),
    )),
    V3(id="podman-v3-0005", tool="podman", kind="followup", turns=(
        Turn(user_input="run a container from registry.access.redhat.com/ubi9:latest named build-env", tool="podman", operation="run",
             args={"operation": "run", "image": "registry.access.redhat.com/ubi9:latest", "name": "build-env"}),
        Turn(user_input="now open a shell inside it and run dnf makecache", tool="podman", operation="exec",
             args={"operation": "exec", "container": "build-env", "command": "dnf makecache"}),
    )),
    V3(id="podman-v3-0006", tool="podman", kind="followup", turns=(
        Turn(user_input="build an image tagged webapp:1.0 from the context at /srv/webapp", tool="podman", operation="build",
             args={"operation": "build", "context": "/srv/webapp", "tag": "webapp:1.0"}),
        Turn(user_input="that built clean, push it to the registry now", tool="podman", operation="push",
             args={"operation": "push", "image": "webapp:1.0"}),
    )),
    V3(id="podman-v3-0007", tool="podman", kind="followup", turns=(
        Turn(user_input="list local images", tool="podman", operation="images",
             args={"operation": "images"}),
        Turn(user_input="the old webapp:0.9 one is dangling, remove that image", tool="podman", operation="rmi",
             args={"operation": "rmi", "image": "webapp:0.9"}),
    )),
    V3(id="podman-v3-0008", tool="podman", kind="followup", turns=(
        Turn(user_input="stop the redis-cache container", tool="podman", operation="stop",
             args={"operation": "stop", "container": "redis-cache"}),
        Turn(user_input="yes, go ahead and force-remove that container too", tool="podman", operation="rm",
             args={"operation": "rm", "container": "redis-cache"}),
        Turn(user_input="also clear out its image, it's no longer used", tool="podman", operation="rmi",
             args={"operation": "rmi", "image": "redis:7"}),
    )),
    V3(id="podman-v3-0009", tool="podman", kind="followup", turns=(
        Turn(user_input="pull registry.access.redhat.com/ubi9/nginx-122:latest", tool="podman", operation="pull",
             args={"operation": "pull", "image": "registry.access.redhat.com/ubi9/nginx-122:latest"}),
        Turn(user_input="run it detached as web-front", tool="podman", operation="run",
             args={"operation": "run", "image": "registry.access.redhat.com/ubi9/nginx-122:latest", "name": "web-front", "detach": True}),
        Turn(user_input="confirm it's up by listing running containers", tool="podman", operation="ps",
             args={"operation": "ps"}),
    )),
    V3(id="podman-v3-0010", tool="podman", kind="question", turns=(
        Turn(user_input="tail the last 200 log lines from container auth-svc", tool="podman", operation="logs",
             args={"operation": "logs", "container": "auth-svc", "lines": 200}),
        Turn(user_input="why would that container be spamming connection refused",
             answer="Connection refused in the logs almost always means auth-svc is trying to reach a backend (a database, another service) that isn't listening yet or isn't reachable on that address. Check that the dependency container is actually running and on the same network before restarting anything."),
    )),
    V3(id="podman-v3-0011", tool="podman", kind="question", turns=(
        Turn(user_input="show detailed inspect output on the mail-relay container", tool="podman", operation="inspect",
             args={"operation": "inspect", "target": "mail-relay"}),
        Turn(user_input="what's the restart policy that shows up in there",
             answer="The restart policy field in inspect output controls whether podman automatically restarts the container when it exits — values like no, on-failure, or always. If it's set to no and the container keeps dying silently, that's why nothing brought it back up on its own."),
    )),
    V3(id="podman-v3-0012", tool="podman", kind="question", turns=(
        Turn(user_input="force-remove the stuck old-backup container", tool="podman", operation="rm",
             args={"operation": "rm", "container": "old-backup"}),
        Turn(user_input="did that also delete the image it was built from",
             answer="No — removing a container only deletes that container's writable layer and its state; the underlying image it was created from stays cached locally. If you also want the image gone, that's a separate rmi against the image name or ID."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("podman", SCENARIOS_V3)
