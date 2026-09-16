"""finetune/scenarios_v3/subscription.py — corpus v3 multi-turn scenarios for 'subscription'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="subscription-v3-0001", tool="subscription", kind="followup", turns=(
        Turn(user_input="show the subscription status on this host", tool="subscription", operation="status", args={"operation": "status"}),
        Turn(user_input="also list what's consumed", tool="subscription", operation="list", args={"operation": "list", "what": "consumed"}),
    )),
    V3(id="subscription-v3-0002", tool="subscription", kind="followup", turns=(
        Turn(user_input="list the available subscriptions", tool="subscription", operation="list", args={"operation": "list", "what": "available"}),
        Turn(user_input="now show the consumed ones too", tool="subscription", operation="list", args={"operation": "list", "what": "consumed"}),
    )),
    V3(id="subscription-v3-0003", tool="subscription", kind="followup", turns=(
        Turn(user_input="register this system with activation key rhel9-baseline-key and org 8675309", tool="subscription", operation="register", args={"operation": "register", "activationkey": "rhel9-baseline-key", "org": "8675309"}),
        Turn(user_input="ok now check the status to confirm it took", tool="subscription", operation="status", args={"operation": "status"}),
    )),
    V3(id="subscription-v3-0004", tool="subscription", kind="followup", turns=(
        Turn(user_input="enable rhel-9-for-x86_64-baseos-rpms", tool="subscription", operation="repos_enable", args={"operation": "repos_enable", "repo": "rhel-9-for-x86_64-baseos-rpms"}),
        Turn(user_input="also enable rhel-9-for-x86_64-appstream-rpms", tool="subscription", operation="repos_enable", args={"operation": "repos_enable", "repo": "rhel-9-for-x86_64-appstream-rpms"}),
    )),
    V3(id="subscription-v3-0005", tool="subscription", kind="followup", turns=(
        Turn(user_input="disable rhel-9-for-x86_64-supplementary-rpms", tool="subscription", operation="repos_disable", args={"operation": "repos_disable", "repo": "rhel-9-for-x86_64-supplementary-rpms"}),
        Turn(user_input="no wait, re-enable it instead", tool="subscription", operation="repos_enable", args={"operation": "repos_enable", "repo": "rhel-9-for-x86_64-supplementary-rpms"}),
    )),
    V3(id="subscription-v3-0006", tool="subscription", kind="followup", turns=(
        Turn(user_input="register with username svc-rhsm and password on file, org 8675309", tool="subscription", operation="register", args={"operation": "register", "username": "svc-rhsm", "password": "on-file", "org": "8675309"}),
        Turn(user_input="yes go ahead and enable rhel-9-for-x86_64-baseos-rpms once it's done", tool="subscription", operation="repos_enable", args={"operation": "repos_enable", "repo": "rhel-9-for-x86_64-baseos-rpms"}),
    )),
    V3(id="subscription-v3-0007", tool="subscription", kind="followup", turns=(
        Turn(user_input="enable the codeready-builder-for-rhel-9-x86_64-rpms repo", tool="subscription", operation="repos_enable", args={"operation": "repos_enable", "repo": "codeready-builder-for-rhel-9-x86_64-rpms"}),
        Turn(user_input="also search dnf for the epel-release package since that pairs with it", tool="packages", operation="search", args={"operation": "search", "keyword": "epel-release"}),
    )),
    V3(id="subscription-v3-0008", tool="subscription", kind="followup", turns=(
        Turn(user_input="unregister this system", tool="subscription", operation="unregister", args={"operation": "unregister"}),
        Turn(user_input="confirm the status shows it's gone", tool="subscription", operation="status", args={"operation": "status"}),
    )),
    V3(id="subscription-v3-0009", tool="subscription", kind="followup", turns=(
        Turn(user_input="check current subscription status", tool="subscription", operation="status", args={"operation": "status"}),
        Turn(user_input="register it with activation key rhel9-web-tier and org 8675309", tool="subscription", operation="register", args={"operation": "register", "activationkey": "rhel9-web-tier", "org": "8675309"}),
        Turn(user_input="and then enable rhel-9-for-x86_64-baseos-rpms", tool="subscription", operation="repos_enable", args={"operation": "repos_enable", "repo": "rhel-9-for-x86_64-baseos-rpms"}),
    )),
    V3(id="subscription-v3-0010", tool="subscription", kind="question", turns=(
        Turn(user_input="show the subscription status", tool="subscription", operation="status", args={"operation": "status"}),
        Turn(user_input="what does that 'unknown' status mean", answer="An unknown overall status usually means the system is registered but has no attached subscription covering its installed products, or entitlement data hasn't synced yet. Run list with available to see what can be attached, or re-register with a valid activation key."),
    )),
    V3(id="subscription-v3-0011", tool="subscription", kind="question", turns=(
        Turn(user_input="unregister this system", tool="subscription", operation="unregister", args={"operation": "unregister"}),
        Turn(user_input="what breaks after that", answer="All entitlement certificates are revoked, so any repo backed by a subscription (baseos, appstream, and add-ons like codeready-builder) becomes unreachable. dnf update and installs will fail on those repos until the system is registered again."),
    )),
    V3(id="subscription-v3-0012", tool="subscription", kind="question", turns=(
        Turn(user_input="disable rhel-9-for-x86_64-appstream-rpms", tool="subscription", operation="repos_disable", args={"operation": "repos_disable", "repo": "rhel-9-for-x86_64-appstream-rpms"}),
        Turn(user_input="what packages does that actually cut off", answer="AppStream carries the application-layer content — most user-facing packages like language runtimes, databases, and web servers, as opposed to BaseOS which has the core OS. Disabling it means dnf can no longer install or update anything that only ships there."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("subscription", SCENARIOS_V3)
