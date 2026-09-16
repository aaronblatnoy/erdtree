"""finetune/scenarios_v3/perf.py — corpus v3 multi-turn scenarios for 'perf'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="perf-v3-0001", tool="perf", kind="followup", turns=(
        Turn(user_input="run perf stat on the command sleep 2", tool="perf", operation="stat",
             args={"operation": "stat", "command": "sleep 2"}),
        Turn(user_input="now the same for tar -cf /dev/null /var/log", tool="perf", operation="stat",
             args={"operation": "stat", "command": "tar -cf /dev/null /var/log"}),
    )),
    V3(id="perf-v3-0002", tool="perf", kind="followup", turns=(
        Turn(user_input="show live CPU hotspots for 15 seconds", tool="perf", operation="top",
             args={"operation": "top", "duration": 15}),
        Turn(user_input="ok, now record it to a file so I can look later", tool="perf", operation="record",
             args={"operation": "record", "duration": 15, "output": "/tmp/hotspots.data"}),
    )),
    V3(id="perf-v3-0003", tool="perf", kind="followup", turns=(
        Turn(user_input="record perf events for pid 4821", tool="perf", operation="record",
             args={"operation": "record", "pid": 4821, "output": "/tmp/pid4821.data"}),
        Turn(user_input="yes go ahead, run it for 30 seconds this time", tool="perf", operation="record",
             args={"operation": "record", "pid": 4821, "duration": 30, "output": "/tmp/pid4821_30s.data"}),
    )),
    V3(id="perf-v3-0004", tool="perf", kind="followup", turns=(
        Turn(user_input="record events attached to pid 9102", tool="perf", operation="record",
             args={"operation": "record", "pid": 9102}),
        Turn(user_input="no, use a command instead of that pid, run make -j4", tool="perf", operation="record",
             args={"operation": "record", "command": "make -j4"}),
    )),
    V3(id="perf-v3-0005", tool="perf", kind="followup", turns=(
        Turn(user_input="run perf stat with cycles and instructions on the postgresql restore script", tool="perf", operation="stat",
             args={"operation": "stat", "command": "/opt/pg/restore.sh", "events": "cycles,instructions"}),
        Turn(user_input="check what that restore process is actually doing right now", tool="processes", operation="info",
             args={"operation": "info", "pid": 4821}),
    )),
    V3(id="perf-v3-0006", tool="perf", kind="followup", turns=(
        Turn(user_input="record perf data for pid 3310, 20 second window", tool="perf", operation="record",
             args={"operation": "record", "pid": 3310, "duration": 20}),
        Turn(user_input="undo that, cancel it and instead just run perf top on that pid's box for 10 seconds", tool="perf", operation="top",
             args={"operation": "top", "duration": 10}),
    )),
    V3(id="perf-v3-0007", tool="perf", kind="followup", turns=(
        Turn(user_input="run perf stat repeating the measurement 5 times on curl localhost:8080", tool="perf", operation="stat",
             args={"operation": "stat", "command": "curl localhost:8080", "repeats": 5}),
        Turn(user_input="do the same but for curl localhost:9090 instead", tool="perf", operation="stat",
             args={"operation": "stat", "command": "curl localhost:9090", "repeats": 5}),
    )),
    V3(id="perf-v3-0008", tool="perf", kind="followup", turns=(
        Turn(user_input="show live hotspots sorted by cpu for 20 seconds", tool="perf", operation="top",
             args={"operation": "top", "duration": 20, "sort": "cpu"}),
        Turn(user_input="do it again but sort by overhead and dso this time", tool="perf", operation="top",
             args={"operation": "top", "duration": 20, "sort": "overhead,dso"}),
        Turn(user_input="also record that same window to a file", tool="perf", operation="record",
             args={"operation": "record", "duration": 20, "output": "/tmp/overhead_dso.data"}),
    )),
    V3(id="perf-v3-0009", tool="perf", kind="followup", turns=(
        Turn(user_input="record perf events for the command nginx -t", tool="perf", operation="record",
             args={"operation": "record", "command": "nginx -t", "output": "/tmp/nginx_check.data"}),
        Turn(user_input="and then check the nginx service logs from that test", tool="services", operation="logs",
             args={"operation": "logs", "unit": "nginx.service", "lines": 50}),
    )),
    V3(id="perf-v3-0010", tool="perf", kind="question", turns=(
        Turn(user_input="run perf stat on the command find / -name '*.log'", tool="perf", operation="stat",
             args={"operation": "stat", "command": "find / -name '*.log'"}),
        Turn(user_input="what does that instructions per cycle number tell me", answer=(
            "IPC above roughly 1.0 means the CPU is retiring work efficiently per "
            "cycle; a low IPC (well under 1) usually points to cache misses or "
            "branch mispredicts stalling the pipeline rather than raw CPU shortage."
        )),
    )),
    V3(id="perf-v3-0011", tool="perf", kind="question", turns=(
        Turn(user_input="show perf top hotspots for 60 seconds", tool="perf", operation="top",
             args={"operation": "top", "duration": 60}),
        Turn(user_input="why is one kernel symbol dominating that list", answer=(
            "A single kernel symbol eating most of the overhead usually means heavy "
            "syscall activity, interrupt handling, or lock contention in that path. "
            "Cross-check with process-level CPU usage to find which process is driving it."
        )),
    )),
    V3(id="perf-v3-0012", tool="perf", kind="question", turns=(
        Turn(user_input="record perf events for pid 5544 for 45 seconds", tool="perf", operation="record",
             args={"operation": "record", "pid": 5544, "duration": 45}),
        Turn(user_input="what do I do with that perf.data file now", answer=(
            "Analyze it with perf report or perf script on the host to see the "
            "call-graph breakdown; this tool only captures the recording, it does "
            "not open or summarize perf.data itself."
        )),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("perf", SCENARIOS_V3)
