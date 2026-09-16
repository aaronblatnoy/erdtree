"""finetune/scenarios_v3/systemd_timers.py — corpus v3 multi-turn scenarios for 'systemd_timers'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="systemd_timers-v3-0001", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="list all the timer units and their next run times", tool="systemd_timers", operation="list-timers",
             args={"operation": "list-timers"}),
        Turn(user_input="also show me the full properties of backup.timer", tool="systemd_timers", operation="timer-show",
             args={"operation": "timer-show", "timer": "backup.timer"}),
    )),
    V3(id="systemd_timers-v3-0002", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="show the properties of logrotate.timer", tool="systemd_timers", operation="timer-show",
             args={"operation": "timer-show", "timer": "logrotate.timer"}),
        Turn(user_input="and the same for fstrim.timer", tool="systemd_timers", operation="timer-show",
             args={"operation": "timer-show", "timer": "fstrim.timer"}),
    )),
    V3(id="systemd_timers-v3-0003", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="install a new timer unit named cert-renew.timer that fires OnCalendar=daily",
             tool="systemd_timers", operation="create",
             args={"operation": "create", "timer": "cert-renew.timer",
                   "content": "[Unit]\nDescription=Renew TLS certificates\n\n[Timer]\nOnCalendar=daily\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n"}),
        Turn(user_input="now enable it so it starts at boot", tool="systemd_timers", operation="enable",
             args={"operation": "enable", "timer": "cert-renew.timer"}),
    )),
    V3(id="systemd_timers-v3-0004", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="disable the old-backup.timer, it's been replaced", tool="systemd_timers", operation="disable",
             args={"operation": "disable", "timer": "old-backup.timer"}),
        Turn(user_input="undo that, I need it running a bit longer for the migration", tool="systemd_timers", operation="enable",
             args={"operation": "enable", "timer": "old-backup.timer"}),
    )),
    V3(id="systemd_timers-v3-0005", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="schedule a one-shot run of /opt/scripts/flush-cache.sh right now as a transient unit",
             tool="systemd_timers", operation="systemd-run",
             args={"operation": "systemd-run", "command": "/opt/scripts/flush-cache.sh", "unit_name": "flush-cache-oneoff"}),
        Turn(user_input="do it again tomorrow at the same time instead of now", tool="systemd_timers", operation="systemd-run",
             args={"operation": "systemd-run", "command": "/opt/scripts/flush-cache.sh", "unit_name": "flush-cache-oneoff",
                   "on_calendar": "*-*-* 09:00:00"}),
    )),
    V3(id="systemd_timers-v3-0006", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="check list-timers output for anything overdue", tool="systemd_timers", operation="list-timers",
             args={"operation": "list-timers"}),
        Turn(user_input="that reindex.timer looks stuck, pull the logs for the service it triggers", tool="rpm", operation="query_file",
             args={"operation": "query_file", "file": "/usr/local/bin/reindex.sh"}),
    )),
    V3(id="systemd_timers-v3-0007", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="create db-snapshot.timer to run OnCalendar=*-*-* 02:15:00",
             tool="systemd_timers", operation="create",
             args={"operation": "create", "timer": "db-snapshot.timer",
                   "content": "[Unit]\nDescription=Nightly database snapshot\n\n[Timer]\nOnCalendar=*-*-* 02:15:00\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n"}),
        Turn(user_input="enable it", tool="systemd_timers", operation="enable",
             args={"operation": "enable", "timer": "db-snapshot.timer"}),
        Turn(user_input="now confirm it's scheduled correctly", tool="systemd_timers", operation="timer-show",
             args={"operation": "timer-show", "timer": "db-snapshot.timer"}),
    )),
    V3(id="systemd_timers-v3-0008", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="run a one-shot cleanup command now: rm -rf /tmp/build-cache/*",
             tool="systemd_timers", operation="systemd-run",
             args={"operation": "systemd-run", "command": "rm -rf /tmp/build-cache/*"}),
        Turn(user_input="yes, go ahead and run it", tool="systemd_timers", operation="systemd-run",
             args={"operation": "systemd-run", "command": "rm -rf /tmp/build-cache/*"}),
    )),
    V3(id="systemd_timers-v3-0009", tool="systemd_timers", kind="followup", turns=(
        Turn(user_input="show properties for snapshot-weekly.timer", tool="systemd_timers", operation="timer-show",
             args={"operation": "timer-show", "timer": "snapshot-weekly.timer"}),
        Turn(user_input="disable that one, we're consolidating into the daily job", tool="systemd_timers", operation="disable",
             args={"operation": "disable", "timer": "snapshot-weekly.timer"}),
    )),
    V3(id="systemd_timers-v3-0010", tool="systemd_timers", kind="question", turns=(
        Turn(user_input="list all timer units", tool="systemd_timers", operation="list-timers", args={"operation": "list-timers"}),
        Turn(user_input="in that output, what's the difference between the LEFT and PASSED columns",
             answer="LEFT is how much time remains until the next scheduled activation, and PASSED is how long ago the last activation happened. A timer with a very old PASSED and no upcoming LEFT is likely disabled or has an expired schedule."),
    )),
    V3(id="systemd_timers-v3-0011", tool="systemd_timers", kind="question", turns=(
        Turn(user_input="show timer-show output for apt-daily.timer", tool="systemd_timers", operation="timer-show",
             args={"operation": "timer-show", "timer": "apt-daily.timer"}),
        Turn(user_input="what does Persistent=yes actually do for this timer",
             answer="It makes systemd run the timer's unit immediately on boot if the scheduled trigger was missed while the machine was off, rather than waiting for the next calendar match. Without it, a missed window is just skipped until the next one comes around."),
    )),
    V3(id="systemd_timers-v3-0012", tool="systemd_timers", kind="question", turns=(
        Turn(user_input="schedule /opt/scripts/rotate-keys.sh to run once as a transient unit named key-rotate-oneoff",
             tool="systemd_timers", operation="systemd-run",
             args={"operation": "systemd-run", "command": "/opt/scripts/rotate-keys.sh", "unit_name": "key-rotate-oneoff"}),
        Turn(user_input="does that transient unit stick around after it finishes",
             answer="It runs once and then the unit is cleaned up automatically after it completes, it isn't persisted like a normal timer or service unit. If it needs to survive reboots or run repeatedly, it should be a real timer unit instead."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("systemd_timers", SCENARIOS_V3)
