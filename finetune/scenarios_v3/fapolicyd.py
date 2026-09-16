"""finetune/scenarios_v3/fapolicyd.py — corpus v3 multi-turn scenarios for 'fapolicyd'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="fapolicyd-v3-0001", tool="fapolicyd", kind="followup", turns=(
        Turn(user_input="Add an allow rule for /opt/vendor/bin/agentless-scan.", tool="fapolicyd", operation="allow",
             args={"operation": "allow", "path": "/opt/vendor/bin/agentless-scan"}),
        Turn(user_input="Now the same for /opt/vendor/bin/agentless-report.", tool="fapolicyd", operation="allow",
             args={"operation": "allow", "path": "/opt/vendor/bin/agentless-report"}),
    )),
    V3(id="fapolicyd-v3-0002", tool="fapolicyd", kind="followup", turns=(
        Turn(user_input="Add a deny rule for /tmp/suspicious_payload.", tool="fapolicyd", operation="deny",
             args={"operation": "deny", "path": "/tmp/suspicious_payload"}),
        Turn(user_input="Ok, now reload the rules so it takes effect.", tool="fapolicyd", operation="update",
             args={"operation": "update"}),
    )),
    V3(id="fapolicyd-v3-0003", tool="fapolicyd", kind="followup", turns=(
        Turn(user_input="Check whether fapolicyd is currently running.", tool="fapolicyd", operation="status",
             args={"operation": "status"}),
        Turn(user_input="Show me the loaded rules too.", tool="fapolicyd", operation="list_rules",
             args={"operation": "list_rules"}),
    )),
    V3(id="fapolicyd-v3-0004", tool="fapolicyd", kind="followup", turns=(
        Turn(user_input="Deny /usr/local/bin/legacy-uploader, it shouldn't be executing anymore.", tool="fapolicyd", operation="deny",
             args={"operation": "deny", "path": "/usr/local/bin/legacy-uploader"}),
        Turn(user_input="Undo that, turns out the deploy team still needs it.", tool="fapolicyd", operation="allow",
             args={"operation": "allow", "path": "/usr/local/bin/legacy-uploader"}),
    )),
    V3(id="fapolicyd-v3-0005", tool="fapolicyd", kind="followup", turns=(
        Turn(user_input="Allow /opt/monitoring/bin/probe to execute.", tool="fapolicyd", operation="allow",
             args={"operation": "allow", "path": "/opt/monitoring/bin/probe"}),
        Turn(user_input="Yes go ahead and push that rule live now.", tool="fapolicyd", operation="update",
             args={"operation": "update"}),
    )),
    V3(id="fapolicyd-v3-0006", tool="fapolicyd", kind="followup", turns=(
        Turn(user_input="List the current fapolicyd rules.", tool="fapolicyd", operation="list_rules",
             args={"operation": "list_rules"}),
        Turn(user_input="Instead deny /srv/apps/oldjar/run.sh, that's the real problem path.", tool="fapolicyd", operation="deny",
             args={"operation": "deny", "path": "/srv/apps/oldjar/run.sh"}),
    )),
    V3(id="fapolicyd-v3-0007", tool="fapolicyd", kind="followup", turns=(
        Turn(user_input="Allow /opt/etl/bin/loader to run under the new policy.", tool="fapolicyd", operation="allow",
             args={"operation": "allow", "path": "/opt/etl/bin/loader"}),
        Turn(user_input="Also check if the file integrity baseline has that binary flagged too.", tool="aide", operation="check",
             args={"operation": "check"}),
    )),
    V3(id="fapolicyd-v3-0008", tool="fapolicyd", kind="followup", turns=(
        Turn(user_input="Deny execution of /home/shared/scripts/run_untrusted.sh.", tool="fapolicyd", operation="deny",
             args={"operation": "deny", "path": "/home/shared/scripts/run_untrusted.sh"}),
        Turn(user_input="Also deny /home/shared/scripts/run_untrusted2.sh, same batch of scripts.", tool="fapolicyd", operation="deny",
             args={"operation": "deny", "path": "/home/shared/scripts/run_untrusted2.sh"}),
    )),
    V3(id="fapolicyd-v3-0009", tool="fapolicyd", kind="followup", turns=(
        Turn(user_input="Add an allow entry for /opt/backup-daemon/bin/backupd.", tool="fapolicyd", operation="allow",
             args={"operation": "allow", "path": "/opt/backup-daemon/bin/backupd"}),
        Turn(user_input="Reload the daemon so it picks that up.", tool="fapolicyd", operation="update",
             args={"operation": "update"}),
        Turn(user_input="Now confirm it's actually in the rule list.", tool="fapolicyd", operation="list_rules",
             args={"operation": "list_rules"}),
    )),
    V3(id="fapolicyd-v3-0010", tool="fapolicyd", kind="question", turns=(
        Turn(user_input="Check fapolicyd status on this host.", tool="fapolicyd", operation="status",
             args={"operation": "status"}),
        Turn(user_input="why did that come back inactive",
             answer="The unit isn't running right now, so no execution rules are being enforced at all.\nAny binary can run until the daemon is restarted and its rules reloaded."),
    )),
    V3(id="fapolicyd-v3-0011", tool="fapolicyd", kind="question", turns=(
        Turn(user_input="Deny /opt/ctf-tool/run for now.", tool="fapolicyd", operation="deny",
             args={"operation": "deny", "path": "/opt/ctf-tool/run"}),
        Turn(user_input="what about processes already running from that path",
             answer="A deny rule blocks new executions from that path but does not kill processes already running.\nAnything currently in memory from /opt/ctf-tool/run keeps running until it exits or is stopped manually."),
    )),
    V3(id="fapolicyd-v3-0012", tool="fapolicyd", kind="question", turns=(
        Turn(user_input="List the loaded rules.", tool="fapolicyd", operation="list_rules",
             args={"operation": "list_rules"}),
        Turn(user_input="what does that update operation actually do",
             answer="It tells the running daemon to re-read its rule files via fapolicyd-cli --update.\nWithout it, edits to the rule files sit on disk and aren't enforced until the next reload or restart."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("fapolicyd", SCENARIOS_V3)
