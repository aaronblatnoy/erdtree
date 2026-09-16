"""finetune/scenarios_v3/audit.py — corpus v3 multi-turn scenarios for 'audit'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="audit-v3-0001", tool="audit", kind="followup", turns=(
        Turn(user_input="search the audit log for events tied to key exec_watch", tool="audit", operation="search-by-key",
             args={"operation": "search-by-key", "key": "exec_watch"}),
        Turn(user_input="now the same search but for the key net_watch", tool="audit", operation="search-by-key",
             args={"operation": "search-by-key", "key": "net_watch"}),
    )),
    V3(id="audit-v3-0002", tool="audit", kind="followup", turns=(
        Turn(user_input="check whether the audit daemon is actually running on this host", tool="audit", operation="status",
             args={"operation": "status"}),
        Turn(user_input="ok, go ahead and start it", tool="audit", operation="auditd-start",
             args={"operation": "auditd-start"}),
    )),
    V3(id="audit-v3-0003", tool="audit", kind="followup", turns=(
        Turn(user_input="list the kernel audit rules currently loaded", tool="audit", operation="list",
             args={"operation": "list"}),
        Turn(user_input="add the same kind of rule, watching execve calls with key exec_watch", tool="audit", operation="add-rule",
             args={"operation": "add-rule", "rule": "always,exit -F arch=b64 -S execve -k exec_watch"}),
        Turn(user_input="now list them again to confirm it took", tool="audit", operation="list",
             args={"operation": "list"}),
    )),
    V3(id="audit-v3-0004", tool="audit", kind="followup", turns=(
        Turn(user_input="add a watch rule on /etc/shadow with key identity_watch", tool="audit", operation="add-rule",
             args={"operation": "add-rule", "rule": "-w /etc/shadow -p wa -k identity_watch"}),
        Turn(user_input="undo that, I typed the wrong key name", tool="audit", operation="delete-rule",
             args={"operation": "delete-rule", "rule": "-w /etc/shadow -p wa -k identity_watch"}),
    )),
    V3(id="audit-v3-0005", tool="audit", kind="followup", turns=(
        Turn(user_input="pull the audit summary report for today", tool="audit", operation="report",
             args={"operation": "report", "report_type": "summary"}),
        Turn(user_input="instead, give me the auth report", tool="audit", operation="report",
             args={"operation": "report", "report_type": "auth"}),
    )),
    V3(id="audit-v3-0006", tool="audit", kind="followup", turns=(
        Turn(user_input="search the audit log for anything from the sudo executable", tool="audit", operation="search-by-comm",
             args={"operation": "search-by-comm", "comm": "sudo"}),
        Turn(user_input="and the same lookup for su", tool="audit", operation="search-by-comm",
             args={"operation": "search-by-comm", "comm": "su"}),
    )),
    V3(id="audit-v3-0007", tool="audit", kind="followup", turns=(
        Turn(user_input="search the audit trail for events between yesterday and now", tool="audit", operation="search-by-time",
             args={"operation": "search-by-time", "start": "yesterday", "end": "now"}),
        Turn(user_input="also check whether auditd itself is up", tool="audit", operation="status",
             args={"operation": "status"}),
    )),
    V3(id="audit-v3-0008", tool="audit", kind="followup", turns=(
        Turn(user_input="stop the audit daemon, we're rotating log storage", tool="audit", operation="auditd-stop",
             args={"operation": "auditd-stop"}),
        Turn(user_input="yes go ahead", tool="audit", operation="auditd-stop",
             args={"operation": "auditd-stop"}),
        Turn(user_input="now confirm its status", tool="audit", operation="status",
             args={"operation": "status"}),
    )),
    V3(id="audit-v3-0009", tool="audit", kind="followup", turns=(
        Turn(user_input="get today's exec report from aureport", tool="audit", operation="report",
             args={"operation": "report", "report_type": "exec"}),
        Turn(user_input="what happened, cross check the process table for anything still running from that", tool="processes", operation="list",
             args={"operation": "list"}),
    )),
    V3(id="audit-v3-0010", tool="audit", kind="question", turns=(
        Turn(user_input="show the current audit subsystem status", tool="audit", operation="status",
             args={"operation": "status"}),
        Turn(user_input="what does that tell me about whether events are actually being logged right now",
             answer="Status here just reports whether auditd is enabled and running, plus the backlog and rate limits it's configured with. If it shows enabled and running with a low lost-event count, events are being captured; a stopped state or a growing backlog means logging has gaps you need to fix before trusting the trail."),
    )),
    V3(id="audit-v3-0011", tool="audit", kind="question", turns=(
        Turn(user_input="run aureport for avc denials", tool="audit", operation="report",
             args={"operation": "report", "report_type": "avc"}),
        Turn(user_input="why did that come back with denial counts against the same process",
             answer="Repeated denials from one process usually mean a policy module or file context hasn't been updated for something the app legitimately needs to do. Worth checking sealert or generating a local policy module rather than disabling enforcement."),
    )),
    V3(id="audit-v3-0012", tool="audit", kind="question", turns=(
        Turn(user_input="delete all audit rules, we're about to reload a fresh ruleset", tool="audit", operation="delete-rule",
             args={"operation": "delete-rule"}),
        Turn(user_input="what happened to the coverage we had before that",
             answer="With no rule argument, delete-rule wipes every active kernel rule, not just one — so all watches and syscall rules are gone until you reload them from /etc/audit/rules.d/ or add them back manually. There's a window with zero audit coverage until that happens."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("audit", SCENARIOS_V3)
