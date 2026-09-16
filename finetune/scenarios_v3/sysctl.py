"""finetune/scenarios_v3/sysctl.py — corpus v3 multi-turn scenarios for 'sysctl'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="sysctl-v3-0001", tool="sysctl", kind="followup", turns=(
        Turn(user_input="what's the current value of net.ipv4.ip_forward", tool="sysctl", operation="get", args={"operation": "get", "key": "net.ipv4.ip_forward"}),
        Turn(user_input="set it to 1", tool="sysctl", operation="set", args={"operation": "set", "key": "net.ipv4.ip_forward", "value": "1"}),
    )),
    V3(id="sysctl-v3-0002", tool="sysctl", kind="followup", turns=(
        Turn(user_input="check vm.swappiness right now", tool="sysctl", operation="get", args={"operation": "get", "key": "vm.swappiness"}),
        Turn(user_input="set it to 10 and make it survive reboot", tool="sysctl", operation="persist", args={"operation": "persist", "key": "vm.swappiness", "value": "10"}),
    )),
    V3(id="sysctl-v3-0003", tool="sysctl", kind="followup", turns=(
        Turn(user_input="bump fs.file-max to 100000 for now", tool="sysctl", operation="set", args={"operation": "set", "key": "fs.file-max", "value": "100000"}),
        Turn(user_input="that worked, now persist it", tool="sysctl", operation="persist", args={"operation": "persist", "key": "fs.file-max", "value": "100000"}),
    )),
    V3(id="sysctl-v3-0004", tool="sysctl", kind="followup", turns=(
        Turn(user_input="dump every kernel parameter currently set", tool="sysctl", operation="list", args={"operation": "list"}),
        Turn(user_input="from that, just pull out the value for kernel.pid_max", tool="sysctl", operation="get", args={"operation": "get", "key": "kernel.pid_max"}),
    )),
    V3(id="sysctl-v3-0005", tool="sysctl", kind="followup", turns=(
        Turn(user_input="set net.core.somaxconn to 4096", tool="sysctl", operation="set", args={"operation": "set", "key": "net.core.somaxconn", "value": "4096"}),
        Turn(user_input="undo that, put it back at 128", tool="sysctl", operation="set", args={"operation": "set", "key": "net.core.somaxconn", "value": "128"}),
    )),
    V3(id="sysctl-v3-0006", tool="sysctl", kind="followup", turns=(
        Turn(user_input="persist net.ipv4.tcp_syncookies as 1 into a file called 20-security.conf", tool="sysctl", operation="persist", args={"operation": "persist", "key": "net.ipv4.tcp_syncookies", "value": "1", "filename": "20-security.conf"}),
        Turn(user_input="now do the same for net.ipv4.conf.all.rp_filter, also value 1", tool="sysctl", operation="persist", args={"operation": "persist", "key": "net.ipv4.conf.all.rp_filter", "value": "1", "filename": "20-security.conf"}),
    )),
    V3(id="sysctl-v3-0007", tool="sysctl", kind="followup", turns=(
        Turn(user_input="get the value of vm.overcommit_memory", tool="sysctl", operation="get", args={"operation": "get", "key": "vm.overcommit_memory"}),
        Turn(user_input="also check the actual memory usage", tool="hardware", operation="memory", args={"operation": "memory"}),
    )),
    V3(id="sysctl-v3-0008", tool="sysctl", kind="followup", turns=(
        Turn(user_input="set net.ipv4.ip_forward to 1 at runtime", tool="sysctl", operation="set", args={"operation": "set", "key": "net.ipv4.ip_forward", "value": "1"}),
        Turn(user_input="yes, make it permanent too", tool="sysctl", operation="persist", args={"operation": "persist", "key": "net.ipv4.ip_forward", "value": "1"}),
        Turn(user_input="also show the routing table to confirm forwarding is live", tool="routing", operation="route_show", args={"operation": "route_show"}),
    )),
    V3(id="sysctl-v3-0009", tool="sysctl", kind="followup", turns=(
        Turn(user_input="list all current kernel parameters", tool="sysctl", operation="list", args={"operation": "list"}),
        Turn(user_input="from that list, pull out net.core.rmem_max specifically", tool="sysctl", operation="get", args={"operation": "get", "key": "net.core.rmem_max"}),
        Turn(user_input="set it to 26214400", tool="sysctl", operation="set", args={"operation": "set", "key": "net.core.rmem_max", "value": "26214400"}),
    )),
    V3(id="sysctl-v3-0010", tool="sysctl", kind="question", turns=(
        Turn(user_input="set net.ipv4.tcp_syncookies to 1", tool="sysctl", operation="set", args={"operation": "set", "key": "net.ipv4.tcp_syncookies", "value": "1"}),
        Turn(user_input="will that survive a reboot", answer="No, sysctl -w only changes the running kernel value; it reverts to whatever is in /etc/sysctl.conf or /etc/sysctl.d/ on the next boot. Use the persist operation if you want it to stick."),
    )),
    V3(id="sysctl-v3-0011", tool="sysctl", kind="question", turns=(
        Turn(user_input="get the current value of kernel.pid_max", tool="sysctl", operation="get", args={"operation": "get", "key": "kernel.pid_max"}),
        Turn(user_input="why would that ever need raising", answer="pid_max caps how many process IDs the kernel can hand out at once, so on a box running a huge number of processes or threads (container hosts, heavy worker pools) the default can get exhausted and new forks start failing. Raising it just widens the ID space."),
    )),
    V3(id="sysctl-v3-0012", tool="sysctl", kind="question", turns=(
        Turn(user_input="persist vm.swappiness at 10", tool="sysctl", operation="persist", args={"operation": "persist", "key": "vm.swappiness", "value": "10"}),
        Turn(user_input="what does that lower swappiness value change", answer="Swappiness controls how aggressively the kernel swaps memory pages to disk versus reclaiming page cache. A lower value like 10 tells it to prefer keeping processes in RAM and only swap under real pressure, which suits latency-sensitive workloads over the default of 60."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("sysctl", SCENARIOS_V3)
