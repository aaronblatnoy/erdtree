"""finetune/scenarios_v3/processes.py — corpus v3 multi-turn scenarios for 'processes'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="processes-v3-0001", tool="processes", kind="followup", turns=(
        Turn(user_input="snapshot processes sorted by CPU usage", tool="processes", operation="top",
             args={"operation": "top"}),
        Turn(user_input="get detailed info on that one, PID 4821", tool="processes", operation="info",
             args={"operation": "info", "pid": 4821}),
    )),
    V3(id="processes-v3-0002", tool="processes", kind="followup", turns=(
        Turn(user_input="show detailed info for PID 9902", tool="processes", operation="info",
             args={"operation": "info", "pid": 9902}),
        Turn(user_input="ok, send it a SIGTERM", tool="processes", operation="signal",
             args={"operation": "signal", "pid": 9902, "signal_num": 15}),
    )),
    V3(id="processes-v3-0003", tool="processes", kind="followup", turns=(
        Turn(user_input="send SIGTERM to pid 3310", tool="processes", operation="signal",
             args={"operation": "signal", "pid": 3310, "signal_num": 15}),
        Turn(user_input="it is still not responding, use signal 9 instead", tool="processes", operation="signal",
             args={"operation": "signal", "pid": 3310, "signal_num": 9}),
    )),
    V3(id="processes-v3-0004", tool="processes", kind="followup", turns=(
        Turn(user_input="list all running processes", tool="processes", operation="list",
             args={"operation": "list"}),
        Turn(user_input="also show me the process tree so I can see what's parenting what", tool="processes", operation="tree",
             args={"operation": "tree"}),
    )),
    V3(id="processes-v3-0005", tool="processes", kind="followup", turns=(
        Turn(user_input="renice PID 5501 to priority 10", tool="processes", operation="renice",
             args={"operation": "renice", "pid": 5501, "priority": 10}),
        Turn(user_input="no, use -5 instead, it needs to stay responsive", tool="processes", operation="renice",
             args={"operation": "renice", "pid": 5501, "priority": -5}),
    )),
    V3(id="processes-v3-0006", tool="processes", kind="followup", turns=(
        Turn(user_input="pull info on PID 6120", tool="processes", operation="info",
             args={"operation": "info", "pid": 6120}),
        Turn(user_input="and the same for PID 6121", tool="processes", operation="info",
             args={"operation": "info", "pid": 6121}),
    )),
    V3(id="processes-v3-0007", tool="processes", kind="followup", turns=(
        Turn(user_input="top out the CPU-heavy processes right now", tool="processes", operation="top",
             args={"operation": "top"}),
        Turn(user_input="also renice PID 7744 down to priority 15 so it stops starving everything else", tool="processes", operation="renice",
             args={"operation": "renice", "pid": 7744, "priority": 15}),
        Turn(user_input="now confirm the process tree looks sane", tool="processes", operation="tree",
             args={"operation": "tree"}),
    )),
    V3(id="processes-v3-0008", tool="processes", kind="followup", turns=(
        Turn(user_input="send SIGKILL to every process, signal_num -1", tool="processes", operation="signal",
             args={"operation": "signal", "pid": 1, "signal_num": -1}),
        Turn(user_input="wait, undo that, I did not mean to target everything", tool="processes", operation="info",
             args={"operation": "info", "pid": 1}),
    )),
    V3(id="processes-v3-0009", tool="processes", kind="followup", turns=(
        Turn(user_input="show info for PID 8890, the runaway backup job", tool="processes", operation="info",
             args={"operation": "info", "pid": 8890}),
        Turn(user_input="what happened, check its recent journal entries too", tool="logs", operation="query",
             args={"operation": "query", "grep": "8890", "lines": 100}),
    )),
    V3(id="processes-v3-0010", tool="processes", kind="question", turns=(
        Turn(user_input="get detailed info on PID 2244", tool="processes", operation="info",
             args={"operation": "info", "pid": 2244}),
        Turn(user_input="what does that state column D actually mean",
             answer="State D is uninterruptible sleep — the process is blocked waiting on I/O, usually disk or NFS, and can't be killed with a normal signal while it's stuck there. If it stays in D for a long time, check the underlying storage or mount for trouble."),
    )),
    V3(id="processes-v3-0011", tool="processes", kind="question", turns=(
        Turn(user_input="send SIGTERM to PID 5567", tool="processes", operation="signal",
             args={"operation": "signal", "pid": 5567, "signal_num": 15}),
        Turn(user_input="why did that not actually stop the process",
             answer="SIGTERM asks a process to shut down cleanly, but a process can ignore or handle it if it's stuck or was coded to catch that signal. If it's still running after a few seconds, send signal 9 (SIGKILL) instead, which the kernel enforces unconditionally."),
    )),
    V3(id="processes-v3-0012", tool="processes", kind="question", turns=(
        Turn(user_input="renice PID 6603 to priority -10", tool="processes", operation="renice",
             args={"operation": "renice", "pid": 6603, "priority": -10}),
        Turn(user_input="what does that negative priority actually change",
             answer="Nice values run from -20 to 19, and lower means higher scheduling priority, so -10 tells the kernel to favor this process for CPU time over normal ones at 0. Setting negative values usually needs elevated privileges since it can starve other workloads."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("processes", SCENARIOS_V3)
