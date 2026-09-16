"""finetune/scenarios_v3/hostname.py — corpus v3 multi-turn scenarios for 'hostname'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="hostname-v3-0001", tool="hostname", kind="followup", turns=(
        Turn(user_input="what's the current hostname on this box", tool="hostname", operation="status",
             args={"operation": "status"}),
        Turn(user_input="also show me what's in /etc/hosts", tool="hostname", operation="hosts-view",
             args={"operation": "hosts-view"}),
    )),
    V3(id="hostname-v3-0002", tool="hostname", kind="followup", turns=(
        Turn(user_input="rename this host to app-node-04.internal.example.com", tool="hostname", operation="set-hostname",
             args={"operation": "set-hostname", "name": "app-node-04.internal.example.com"}),
        Turn(user_input="confirm it took", tool="hostname", operation="status", args={"operation": "status"}),
    )),
    V3(id="hostname-v3-0003", tool="hostname", kind="followup", turns=(
        Turn(user_input="add an entry for 10.0.4.12 pointing at db-primary.internal db-primary", tool="hostname", operation="hosts-edit",
             args={"operation": "hosts-edit", "entry": "10.0.4.12 db-primary.internal db-primary"}),
        Turn(user_input="do the same for the replica at 10.0.4.13", tool="hostname", operation="hosts-edit",
             args={"operation": "hosts-edit", "entry": "10.0.4.13 db-replica.internal db-replica"}),
    )),
    V3(id="hostname-v3-0004", tool="hostname", kind="followup", turns=(
        Turn(user_input="check the current hostname", tool="hostname", operation="status", args={"operation": "status"}),
        Turn(user_input="ok switch it to cache-node-02", tool="hostname", operation="set-hostname",
             args={"operation": "set-hostname", "name": "cache-node-02"}),
    )),
    V3(id="hostname-v3-0005", tool="hostname", kind="followup", turns=(
        Turn(user_input="set the hostname to staging-web-01", tool="hostname", operation="set-hostname",
             args={"operation": "set-hostname", "name": "staging-web-01"}),
        Turn(user_input="no, instead use staging-web-01.example.internal, needs the domain suffix", tool="hostname", operation="set-hostname",
             args={"operation": "set-hostname", "name": "staging-web-01.example.internal"}),
        Turn(user_input="yes do it", tool="hostname", operation="set-hostname",
             args={"operation": "set-hostname", "name": "staging-web-01.example.internal"}),
    )),
    V3(id="hostname-v3-0006", tool="hostname", kind="followup", turns=(
        Turn(user_input="pull up /etc/hosts", tool="hostname", operation="hosts-view", args={"operation": "hosts-view"}),
        Turn(user_input="that jenkins entry looks stale, check if the jenkins service unit is even running", tool="systemd_timers", operation="list-timers",
             args={"operation": "list-timers"}),
    )),
    V3(id="hostname-v3-0007", tool="hostname", kind="followup", turns=(
        Turn(user_input="add an entry mapping 192.168.9.50 to build-runner build-runner-01", tool="hostname", operation="hosts-edit",
             args={"operation": "hosts-edit", "entry": "192.168.9.50 build-runner build-runner-01"}),
        Turn(user_input="show it to me now to make sure it landed right", tool="hostname", operation="hosts-view",
             args={"operation": "hosts-view"}),
    )),
    V3(id="hostname-v3-0008", tool="hostname", kind="followup", turns=(
        Turn(user_input="rename this to edge-proxy-07", tool="hostname", operation="set-hostname",
             args={"operation": "set-hostname", "name": "edge-proxy-07"}),
        Turn(user_input="no, use edge-proxy-07-east instead, we're regionally tagging these now", tool="hostname", operation="set-hostname",
             args={"operation": "set-hostname", "name": "edge-proxy-07-east"}),
    )),
    V3(id="hostname-v3-0009", tool="hostname", kind="followup", turns=(
        Turn(user_input="show the hostname status", tool="hostname", operation="status", args={"operation": "status"}),
        Turn(user_input="also append an entry for 127.0.1.1 pointed at that same name for local resolution", tool="hostname", operation="hosts-edit",
             args={"operation": "hosts-edit", "entry": "127.0.1.1 app-node-04.internal.example.com app-node-04"}),
    )),
    V3(id="hostname-v3-0010", tool="hostname", kind="question", turns=(
        Turn(user_input="show hostname status", tool="hostname", operation="status", args={"operation": "status"}),
        Turn(user_input="in that output, what does the static vs transient hostname distinction actually mean",
             answer="Static is the persistent name stored in /etc/hostname and used across reboots; transient is a runtime name the kernel or DHCP can set temporarily and it disappears on reboot if not also written to the static value. When they differ, something set the transient name without updating /etc/hostname."),
    )),
    V3(id="hostname-v3-0011", tool="hostname", kind="question", turns=(
        Turn(user_input="set the hostname to mail-relay-03", tool="hostname", operation="set-hostname",
             args={"operation": "set-hostname", "name": "mail-relay-03"}),
        Turn(user_input="for that to take effect, will running services need a restart",
             answer="Yes, anything that read the hostname at startup and cached it, like some logging agents or mail daemons, keeps using the old value until restarted. A fresh SSH session or new process will already see the new name."),
    )),
    V3(id="hostname-v3-0012", tool="hostname", kind="question", turns=(
        Turn(user_input="view /etc/hosts", tool="hostname", operation="hosts-view", args={"operation": "hosts-view"}),
        Turn(user_input="in that file, what happens if two lines map the same name to different addresses",
             answer="Most resolvers just use the first matching line and ignore the rest, so the second entry is effectively dead weight. It's worth cleaning up duplicates rather than leaving both, since it makes the file misleading to the next person who reads it."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("hostname", SCENARIOS_V3)
