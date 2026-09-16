"""finetune/scenarios_v3/logs.py — corpus v3 multi-turn scenarios for 'logs'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="logs-v3-0001", tool="logs", kind="followup", turns=(
        Turn(user_input="tail the last 50 lines for haproxy.service", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "haproxy.service", "lines": 50}),
        Turn(user_input="and eth1's dhcp client too", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "dhcpcd@eth1.service", "lines": 50}),
    )),
    V3(id="logs-v3-0002", tool="logs", kind="followup", turns=(
        Turn(user_input="query journalctl for postgresql.service errors in the last hour", tool="logs", operation="query",
             args={"operation": "query", "unit": "postgresql.service", "since": "1 hour ago", "priority": "err"}),
        Turn(user_input="ok, now restart the service", tool="services", operation="restart",
             args={"operation": "restart", "unit": "postgresql.service"}),
    )),
    V3(id="logs-v3-0003", tool="logs", kind="followup", turns=(
        Turn(user_input="show boot errors for the current boot", tool="logs", operation="boot_errors",
             args={"operation": "boot_errors"}),
        Turn(user_input="the same but for the previous boot", tool="logs", operation="boot_errors",
             args={"operation": "boot_errors", "boot": "-1"}),
    )),
    V3(id="logs-v3-0004", tool="logs", kind="followup", turns=(
        Turn(user_input="check the kernel ring buffer for usb errors", tool="logs", operation="dmesg_query",
             args={"operation": "dmesg_query", "level": "err", "grep": "usb"}),
        Turn(user_input="yes, pull the dmesg error summary too", tool="logs", operation="dmesg_errors",
             args={"operation": "dmesg_errors", "lines": 100}),
    )),
    V3(id="logs-v3-0005", tool="logs", kind="followup", turns=(
        Turn(user_input="journalctl since '2 hours ago' for sshd", tool="logs", operation="since",
             args={"operation": "since", "since": "2 hours ago", "unit": "sshd.service"}),
        Turn(user_input="no, use the other window instead, since '30 minutes ago'", tool="logs", operation="since",
             args={"operation": "since", "since": "30 minutes ago", "unit": "sshd.service"}),
    )),
    V3(id="logs-v3-0006", tool="logs", kind="followup", turns=(
        Turn(user_input="grep the journal for 'out of memory' across the whole system in the last day", tool="logs", operation="query",
             args={"operation": "query", "since": "1 day ago", "grep": "out of memory"}),
        Turn(user_input="also check dmesg for oom-killer lines, that's alarming", tool="logs", operation="dmesg_query",
             args={"operation": "dmesg_query", "grep": "oom-killer"}),
        Turn(user_input="also check vmstat to see current memory pressure", tool="performance", operation="vmstat",
             args={"operation": "vmstat"}),
    )),
    V3(id="logs-v3-0007", tool="logs", kind="followup", turns=(
        Turn(user_input="tail 30 lines for crond", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "crond.service", "lines": 30}),
        Turn(user_input="undo that, give me 200 lines instead", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "crond.service", "lines": 200}),
        Turn(user_input="do it also with priority warning and above", tool="logs", operation="query",
             args={"operation": "query", "unit": "crond.service", "priority": "warning", "lines": 200}),
    )),
    V3(id="logs-v3-0008", tool="logs", kind="followup", turns=(
        Turn(user_input="dmesg with level warn for the last boot", tool="logs", operation="dmesg_query",
             args={"operation": "dmesg_query", "level": "warn"}),
        Turn(user_input="the same query but only since '10 minutes ago'", tool="logs", operation="dmesg_query",
             args={"operation": "dmesg_query", "level": "warn", "since": "10 minutes ago"}),
    )),
    V3(id="logs-v3-0009", tool="logs", kind="followup", turns=(
        Turn(user_input="query journalctl for nginx with identifier nginx and priority err", tool="logs", operation="query",
             args={"operation": "query", "identifier": "nginx", "priority": "err", "lines": 100}),
        Turn(user_input="ok do it, now check nginx.service status directly", tool="services", operation="status",
             args={"operation": "status", "unit": "nginx.service"}),
    )),
    V3(id="logs-v3-0010", tool="logs", kind="question", turns=(
        Turn(user_input="tail the last 50 lines for docker.service", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "docker.service", "lines": 50}),
        Turn(user_input="what does that repeated 'failed to start containerd' line mean",
             answer="It means the containerd shim docker depends on could not initialize, so the docker daemon itself keeps failing to come up. Check containerd.service status separately — it is usually the actual root cause."),
    )),
    V3(id="logs-v3-0011", tool="logs", kind="question", turns=(
        Turn(user_input="show boot errors for boot 0", tool="logs", operation="boot_errors",
             args={"operation": "boot_errors", "boot": "0"}),
        Turn(user_input="is that filesystem warning something to worry about",
             answer="An EXT4 remount-read-only or journal-recovery warning at boot means the filesystem was not unmounted cleanly last shutdown. It usually self-heals via journal replay, but repeated occurrences point at a failing disk worth checking with a SMART read."),
    )),
    V3(id="logs-v3-0012", tool="logs", kind="question", turns=(
        Turn(user_input="dmesg errors, last 100 lines", tool="logs", operation="dmesg_errors",
             args={"operation": "dmesg_errors", "lines": 100}),
        Turn(user_input="what should I check next given those NIC link errors",
             answer="Repeated NIC link-down/link-up messages usually mean a flaky cable, transceiver, or switch port rather than a driver bug. Check ethtool link stats on that interface and swap the cable before suspecting the kernel driver."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("logs", SCENARIOS_V3)
