"""finetune/scenarios_v3/chrony.py — corpus v3 multi-turn scenarios for 'chrony'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="chrony-v3-0001", tool="chrony", kind="followup", turns=(
        Turn(user_input="show me the ntp sources chrony is using", tool="chrony", operation="sources", args={"operation": "sources"}),
        Turn(user_input="also show me the tracking stats", tool="chrony", operation="tracking", args={"operation": "tracking"}),
    )),
    V3(id="chrony-v3-0002", tool="chrony", kind="followup", turns=(
        Turn(user_input="check the status of the chronyd daemon", tool="chrony", operation="status", args={"operation": "status"}),
        Turn(user_input="ok, now restart it", tool="services", operation="restart", args={"operation": "restart", "unit": "chronyd.service"}),
    )),
    V3(id="chrony-v3-0003", tool="chrony", kind="followup", turns=(
        Turn(user_input="pull up the tracking stats for the clock", tool="chrony", operation="tracking", args={"operation": "tracking"}),
        Turn(user_input="the offset looks bad, step it to the reference time", tool="chrony", operation="makestep", args={"operation": "makestep"}),
    )),
    V3(id="chrony-v3-0004", tool="chrony", kind="followup", turns=(
        Turn(user_input="cat out /etc/chrony.conf for me", tool="chrony", operation="conf_view", args={"operation": "conf_view"}),
        Turn(user_input="yes go ahead and rewrite it with pool time.cloudflare.com iburst plus the rest of the defaults", tool="chrony", operation="conf_edit", args={"operation": "conf_edit", "content": "pool time.cloudflare.com iburst\ndriftfile /var/lib/chrony/drift\nmakestep 1.0 3\nrtcsync\n"}),
    )),
    V3(id="chrony-v3-0005", tool="chrony", kind="followup", turns=(
        Turn(user_input="list the configured ntp sources", tool="chrony", operation="sources", args={"operation": "sources"}),
        Turn(user_input="no, forget that, show me the tracking stats instead", tool="chrony", operation="tracking", args={"operation": "tracking"}),
    )),
    V3(id="chrony-v3-0006", tool="chrony", kind="followup", turns=(
        Turn(user_input="is chronyd even running on this box", tool="chrony", operation="status", args={"operation": "status"}),
        Turn(user_input="also grab the source list while we're here", tool="chrony", operation="sources", args={"operation": "sources"}),
    )),
    V3(id="chrony-v3-0007", tool="chrony", kind="followup", turns=(
        Turn(user_input="dump the current chrony config file", tool="chrony", operation="conf_view", args={"operation": "conf_view"}),
        Turn(user_input="now do the same for the sysctl network params", tool="sysctl", operation="get", args={"operation": "get", "key": "net.ipv4.ip_forward"}),
    )),
    V3(id="chrony-v3-0008", tool="chrony", kind="followup", turns=(
        Turn(user_input="step the clock to the reference time now", tool="chrony", operation="makestep", args={"operation": "makestep"}),
        Turn(user_input="what happened, did the offset clear", tool="chrony", operation="tracking", args={"operation": "tracking"}),
        Turn(user_input="and confirm the sources are still reachable", tool="chrony", operation="sources", args={"operation": "sources"}),
    )),
    V3(id="chrony-v3-0009", tool="chrony", kind="followup", turns=(
        Turn(user_input="show chronyd status", tool="chrony", operation="status", args={"operation": "status"}),
        Turn(user_input="it's dead, pull its journal", tool="services", operation="logs", args={"operation": "logs", "unit": "chronyd.service", "lines": 100}),
        Turn(user_input="ok now restart it", tool="services", operation="restart", args={"operation": "restart", "unit": "chronyd.service"}),
    )),
    V3(id="chrony-v3-0010", tool="chrony", kind="question", turns=(
        Turn(user_input="give me the tracking output for chrony", tool="chrony", operation="tracking", args={"operation": "tracking"}),
        Turn(user_input="in that output, what does the system time offset field tell me", answer="It's how far the local clock has drifted from the reference source at last measurement, in seconds. A small, stable offset (sub-millisecond) means sync is healthy; a growing one means chronyd is struggling to correct drift, often from a flaky source or a clock with bad hardware timing."),
    )),
    V3(id="chrony-v3-0011", tool="chrony", kind="question", turns=(
        Turn(user_input="list ntp sources for chrony", tool="chrony", operation="sources", args={"operation": "sources"}),
        Turn(user_input="why does one of them show a reach value of 0", answer="Reach 0 means the last several polls to that source got no reply, so chronyd has marked it unreachable. Check outbound UDP 123 to that host and whether the source itself is up; chrony will keep polling and recover reach automatically once packets flow again."),
    )),
    V3(id="chrony-v3-0012", tool="chrony", kind="question", turns=(
        Turn(user_input="check chronyd status", tool="chrony", operation="status", args={"operation": "status"}),
        Turn(user_input="in that, what's the difference between makestep and letting it slew", answer="Slewing gradually speeds up or slows down the clock to close small offsets without breaking monotonic time, which is what chronyd does normally. makestep jumps the clock instantly to the reference time, which is faster for large offsets but can confuse anything relying on strictly increasing timestamps, like some databases or cron logic."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("chrony", SCENARIOS_V3)
