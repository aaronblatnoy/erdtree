"""finetune/scenarios_v3/tuned.py — corpus v3 multi-turn scenarios for 'tuned'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="tuned-v3-0001", tool="tuned", kind="followup", turns=(
        Turn(user_input="list available tuned profiles", tool="tuned", operation="list", args={"operation": "list"}),
        Turn(user_input="now show which one is active", tool="tuned", operation="active", args={"operation": "active"}),
    )),
    V3(id="tuned-v3-0002", tool="tuned", kind="followup", turns=(
        Turn(user_input="what profile does this box recommend", tool="tuned", operation="recommend", args={"operation": "recommend"}),
        Turn(user_input="ok, switch to that one", tool="tuned", operation="profile", args={"operation": "profile", "profile": "throughput-performance"}),
    )),
    V3(id="tuned-v3-0003", tool="tuned", kind="followup", turns=(
        Turn(user_input="switch to latency-performance", tool="tuned", operation="profile", args={"operation": "profile", "profile": "latency-performance"}),
        Turn(user_input="no, use throughput-performance instead", tool="tuned", operation="profile", args={"operation": "profile", "profile": "throughput-performance"}),
    )),
    V3(id="tuned-v3-0004", tool="tuned", kind="followup", turns=(
        Turn(user_input="show the active profile", tool="tuned", operation="active", args={"operation": "active"}),
        Turn(user_input="also turn tuning off entirely", tool="tuned", operation="off", args={"operation": "off"}),
    )),
    V3(id="tuned-v3-0005", tool="tuned", kind="followup", turns=(
        Turn(user_input="turn off tuning, we're benchmarking with a clean baseline", tool="tuned", operation="off", args={"operation": "off"}),
        Turn(user_input="undo that, turn it back on with virtual-guest", tool="tuned", operation="profile", args={"operation": "profile", "profile": "virtual-guest"}),
    )),
    V3(id="tuned-v3-0006", tool="tuned", kind="followup", turns=(
        Turn(user_input="list the profiles this system offers", tool="tuned", operation="list", args={"operation": "list"}),
        Turn(user_input="instead apply virtual-host, this is a hypervisor node", tool="tuned", operation="profile", args={"operation": "profile", "profile": "virtual-host"}),
    )),
    V3(id="tuned-v3-0007", tool="tuned", kind="followup", turns=(
        Turn(user_input="switch the profile to network-latency", tool="tuned", operation="profile", args={"operation": "profile", "profile": "network-latency"}),
        Turn(user_input="also check which kernel modules are loaded for the nic driver stack", tool="kernel_modules", operation="lsmod", args={"operation": "lsmod"}),
    )),
    V3(id="tuned-v3-0008", tool="tuned", kind="followup", turns=(
        Turn(user_input="what's the recommended profile here", tool="tuned", operation="recommend", args={"operation": "recommend"}),
        Turn(user_input="apply it", tool="tuned", operation="profile", args={"operation": "profile", "profile": "balanced"}),
        Turn(user_input="confirm it actually took effect", tool="tuned", operation="active", args={"operation": "active"}),
    )),
    V3(id="tuned-v3-0009", tool="tuned", kind="followup", turns=(
        Turn(user_input="show active tuning", tool="tuned", operation="active", args={"operation": "active"}),
        Turn(user_input="disable it for now", tool="tuned", operation="off", args={"operation": "off"}),
        Turn(user_input="and then re-enable with the recommended one", tool="tuned", operation="recommend", args={"operation": "recommend"}),
    )),
    V3(id="tuned-v3-0010", tool="tuned", kind="question", turns=(
        Turn(user_input="show the recommended profile for this host", tool="tuned", operation="recommend", args={"operation": "recommend"}),
        Turn(user_input="why did that pick throughput-performance over balanced", answer="The recommendation logic looks at chassis type and workload signals — a server chassis with no virtualization typically wins throughput-performance, while balanced is the default fallback for desktops and laptops. It's a heuristic, not a guarantee, so override it if your workload is latency-sensitive instead of throughput-bound."),
    )),
    V3(id="tuned-v3-0011", tool="tuned", kind="question", turns=(
        Turn(user_input="switch active profile to throughput-performance", tool="tuned", operation="profile", args={"operation": "profile", "profile": "throughput-performance"}),
        Turn(user_input="what did that change on the system", answer="It applied kernel and sysctl tunings favoring bulk I/O over responsiveness — larger read-ahead, deeper disk queues, and CPU governor changes to keep cores at higher frequency. Interactive workloads may feel slightly less snappy in exchange for better sustained throughput."),
    )),
    V3(id="tuned-v3-0012", tool="tuned", kind="question", turns=(
        Turn(user_input="turn off tuning", tool="tuned", operation="off", args={"operation": "off"}),
        Turn(user_input="what happened to the settings it had applied", answer="Turning tuning off reverts the sysctl and kernel parameter changes the active profile had made, returning the system to stock defaults. No profile stays applied until you activate one again, so performance-sensitive workloads may regress until you pick a replacement."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("tuned", SCENARIOS_V3)
