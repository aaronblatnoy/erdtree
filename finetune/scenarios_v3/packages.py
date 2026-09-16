"""finetune/scenarios_v3/packages.py — corpus v3 multi-turn scenarios for 'packages'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="packages-v3-0001", tool="packages", kind="followup", turns=(
        Turn(user_input="search for postgresql packages", tool="packages", operation="search", args={"operation": "search", "keyword": "postgresql"}),
        Turn(user_input="show me info on that one, the server package", tool="packages", operation="info", args={"operation": "info", "package": "postgresql-server"}),
    )),
    V3(id="packages-v3-0002", tool="packages", kind="followup", turns=(
        Turn(user_input="install nginx and certbot", tool="packages", operation="install", args={"operation": "install", "packages": ["nginx", "certbot"]}),
        Turn(user_input="now the same for haproxy", tool="packages", operation="install", args={"operation": "install", "packages": ["haproxy"]}),
    )),
    V3(id="packages-v3-0003", tool="packages", kind="followup", turns=(
        Turn(user_input="update the vim-enhanced package", tool="packages", operation="update", args={"operation": "update", "packages": ["vim-enhanced"]}),
        Turn(user_input="and tmux too", tool="packages", operation="update", args={"operation": "update", "packages": ["tmux"]}),
    )),
    V3(id="packages-v3-0004", tool="packages", kind="followup", turns=(
        Turn(user_input="show me metadata for the git package", tool="packages", operation="info", args={"operation": "info", "package": "git"}),
        Turn(user_input="ok, install it", tool="packages", operation="install", args={"operation": "install", "packages": ["git"]}),
    )),
    V3(id="packages-v3-0005", tool="packages", kind="followup", turns=(
        Turn(user_input="remove the telnet package from this host", tool="packages", operation="remove", args={"operation": "remove", "packages": ["telnet"]}),
        Turn(user_input="the transaction plan looks fine, go ahead", tool="packages", operation="remove", args={"operation": "remove", "packages": ["telnet"], "gate_cleared": True}),
    )),
    V3(id="packages-v3-0006", tool="packages", kind="followup", turns=(
        Turn(user_input="search for anything matching redis", tool="packages", operation="search", args={"operation": "search", "keyword": "redis"}),
        Turn(user_input="no, search for valkey instead", tool="packages", operation="search", args={"operation": "search", "keyword": "valkey"}),
    )),
    V3(id="packages-v3-0007", tool="packages", kind="followup", turns=(
        Turn(user_input="update every package on this host, it's been a while", tool="packages", operation="update", args={"operation": "update", "packages": []}),
        Turn(user_input="also check if the mariadb service needs a restart because of that", tool="services", operation="status", args={"operation": "status", "unit": "mariadb.service"}),
    )),
    V3(id="packages-v3-0008", tool="packages", kind="followup", turns=(
        Turn(user_input="install the mariadb-server package", tool="packages", operation="install", args={"operation": "install", "packages": ["mariadb-server"]}),
        Turn(user_input="did it actually go on, show me its info", tool="packages", operation="info", args={"operation": "info", "package": "mariadb-server"}),
        Turn(user_input="also check its service status", tool="services", operation="status", args={"operation": "status", "unit": "mariadb.service"}),
    )),
    V3(id="packages-v3-0009", tool="packages", kind="followup", turns=(
        Turn(user_input="remove the old python2 packages, gate_cleared, I already reviewed the transaction", tool="packages", operation="remove", args={"operation": "remove", "packages": ["python2", "python2-libs"], "gate_cleared": True}),
        Turn(user_input="actually undo that removal, reinstall python2-libs", tool="packages", operation="install", args={"operation": "install", "packages": ["python2-libs"]}),
    )),
    V3(id="packages-v3-0010", tool="packages", kind="question", turns=(
        Turn(user_input="remove the sendmail package from this box", tool="packages", operation="remove", args={"operation": "remove", "packages": ["sendmail"]}),
        Turn(user_input="why didn't that just remove it outright", answer="Removing a package always runs a dry-run first because dependency cascades can pull in things like the kernel or sudo.\nThe result you got back is the proposed transaction plan, nothing was removed yet.\nReview the packages it lists, then confirm with gate_cleared to actually run the removal."),
    )),
    V3(id="packages-v3-0011", tool="packages", kind="question", turns=(
        Turn(user_input="search dnf for anything related to ansible", tool="packages", operation="search", args={"operation": "search", "keyword": "ansible"}),
        Turn(user_input="how do I pick which one to install off that list", answer="Match the summary text against what you actually need, not just the shortest name.\nCheck a candidate's info output for its exact version and description before installing.\nOn Rocky 9, ansible-core is usually the base package; the full ansible metapackage pulls in extra collections."),
    )),
    V3(id="packages-v3-0012", tool="packages", kind="question", turns=(
        Turn(user_input="update all packages on the app server", tool="packages", operation="update", args={"operation": "update", "packages": []}),
        Turn(user_input="after that, what should I check", answer="Check for services running against now-stale libraries, especially ones that don't auto-restart on package update.\nReview the transaction summary for kernel or glibc updates, which usually need a reboot to fully apply.\nWatch application logs for a bit afterward in case a dependency bump changed behavior."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("packages", SCENARIOS_V3)
