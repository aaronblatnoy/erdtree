"""finetune/scenarios_v3/performance.py — corpus v3 multi-turn scenarios for 'performance'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="performance-v3-0001", tool="performance", kind="followup", turns=(
        Turn(user_input="run sar with a 2 second interval, 5 samples", tool="performance", operation="sar",
             args={"operation": "sar", "interval": 2, "count": 5}),
        Turn(user_input="now the same but with mpstat instead", tool="performance", operation="mpstat",
             args={"operation": "mpstat", "interval": 2, "count": 5}),
    )),
    V3(id="performance-v3-0002", tool="performance", kind="followup", turns=(
        Turn(user_input="check current load averages", tool="performance", operation="load",
             args={"operation": "load"}),
        Turn(user_input="that's high, show me uptime too", tool="performance", operation="uptime",
             args={"operation": "uptime"}),
    )),
    V3(id="performance-v3-0003", tool="performance", kind="followup", turns=(
        Turn(user_input="iostat with interval 1, count 3", tool="performance", operation="iostat",
             args={"operation": "iostat", "interval": 1, "count": 3}),
        Turn(user_input="do it again with count 10 instead", tool="performance", operation="iostat",
             args={"operation": "iostat", "interval": 1, "count": 10}),
    )),
    V3(id="performance-v3-0004", tool="performance", kind="followup", turns=(
        Turn(user_input="vmstat, interval 5, 4 samples", tool="performance", operation="vmstat",
             args={"operation": "vmstat", "interval": 5, "count": 4}),
        Turn(user_input="yes go ahead and also pull load averages", tool="performance", operation="load",
             args={"operation": "load"}),
    )),
    V3(id="performance-v3-0005", tool="performance", kind="followup", turns=(
        Turn(user_input="mpstat interval 1 count 1 to see per-cpu load right now", tool="performance", operation="mpstat",
             args={"operation": "mpstat", "interval": 1, "count": 1}),
        Turn(user_input="one core looks pegged, check journal logs for the cron service", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "crond.service", "lines": 50}),
    )),
    V3(id="performance-v3-0006", tool="performance", kind="followup", turns=(
        Turn(user_input="show uptime and load", tool="performance", operation="uptime",
             args={"operation": "uptime"}),
        Turn(user_input="undo that framing, just give me raw /proc/loadavg instead", tool="performance", operation="load",
             args={"operation": "load"}),
        Turn(user_input="and now run sar over 3 samples at 2 second intervals", tool="performance", operation="sar",
             args={"operation": "sar", "interval": 2, "count": 3}),
    )),
    V3(id="performance-v3-0007", tool="performance", kind="followup", turns=(
        Turn(user_input="iostat once with default interval", tool="performance", operation="iostat",
             args={"operation": "iostat"}),
        Turn(user_input="disk wait looks bad, also check vmstat over 5 samples", tool="performance", operation="vmstat",
             args={"operation": "vmstat", "count": 5}),
        Turn(user_input="and then check status of the postgresql service", tool="services", operation="status",
             args={"operation": "status", "unit": "postgresql.service"}),
    )),
    V3(id="performance-v3-0008", tool="performance", kind="followup", turns=(
        Turn(user_input="sar interval 1 count 1 for a quick cpu snapshot", tool="performance", operation="sar",
             args={"operation": "sar", "interval": 1, "count": 1}),
        Turn(user_input="no, use the other interval instead, 3 seconds over 10 counts", tool="performance", operation="sar",
             args={"operation": "sar", "interval": 3, "count": 10}),
    )),
    V3(id="performance-v3-0009", tool="performance", kind="followup", turns=(
        Turn(user_input="mpstat over 2 second intervals, 6 samples", tool="performance", operation="mpstat",
             args={"operation": "mpstat", "interval": 2, "count": 6}),
        Turn(user_input="the same for iostat", tool="performance", operation="iostat",
             args={"operation": "iostat", "interval": 2, "count": 6}),
    )),
    V3(id="performance-v3-0010", tool="performance", kind="question", turns=(
        Turn(user_input="check load averages on this box", tool="performance", operation="load",
             args={"operation": "load"}),
        Turn(user_input="is that 8.5 1-minute load bad on this box",
             answer="It depends on CPU type count — load near or above the number of logical CPUs means processes are queuing for CPU time. Check `sar` or `mpstat` next to see whether it is actually CPU-bound or waiting on I/O."),
    )),
    V3(id="performance-v3-0011", tool="performance", kind="question", turns=(
        Turn(user_input="run iostat, interval 1, count 3", tool="performance", operation="iostat",
             args={"operation": "iostat", "interval": 1, "count": 3}),
        Turn(user_input="what does that %util near 100 mean",
             answer="It means the disk device was busy servicing requests for nearly the entire sampled interval, i.e. it is saturated. Pair it with await time — a high await alongside high %util points to the disk itself being the bottleneck, not just a burst of small requests."),
    )),
    V3(id="performance-v3-0012", tool="performance", kind="question", turns=(
        Turn(user_input="vmstat interval 2 count 5", tool="performance", operation="vmstat",
             args={"operation": "vmstat", "interval": 2, "count": 5}),
        Turn(user_input="why is that si/so column nonzero",
             answer="Nonzero si/so means the system is actively swapping pages in and out of memory, which is a sign of real memory pressure, not just allocated-but-idle swap. If it stays nonzero under normal load, the box needs more RAM or fewer resident processes."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("performance", SCENARIOS_V3)
