"""finetune/scenarios_v3/cron.py — corpus v3 multi-turn scenarios for 'cron'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="cron-v3-0001", tool="cron", kind="followup", turns=(
        Turn(user_input="show me the backup-jobs file under cron.d", tool="cron", operation="crond-view",
             args={"operation": "crond-view", "name": "backup-jobs"}),
        Turn(user_input="now show me the same for nightly-sync", tool="cron", operation="crond-view",
             args={"operation": "crond-view", "name": "nightly-sync"}),
    )),
    V3(id="cron-v3-0002", tool="cron", kind="followup", turns=(
        Turn(user_input="list the crontab for the deploy user", tool="cron", operation="list",
             args={"operation": "list", "user": "deploy"}),
        Turn(user_input="and the postgres one too", tool="cron", operation="list",
             args={"operation": "list", "user": "postgres"}),
    )),
    V3(id="cron-v3-0003", tool="cron", kind="followup", turns=(
        Turn(user_input="replace root's crontab with a job that runs /opt/scripts/rotate-logs.sh every day at 3am",
             tool="cron", operation="edit",
             args={"operation": "edit", "content": "0 3 * * * /opt/scripts/rotate-logs.sh\n", "user": "root"}),
        Turn(user_input="ok that looks right, now list it back to confirm", tool="cron", operation="list",
             args={"operation": "list", "user": "root"}),
    )),
    V3(id="cron-v3-0004", tool="cron", kind="followup", turns=(
        Turn(user_input="write a cron.d drop-in named db-vacuum that runs vacuumdb nightly at 2:30",
             tool="cron", operation="crond-add",
             args={"operation": "crond-add", "name": "db-vacuum",
                   "content": "30 2 * * * postgres /usr/bin/vacuumdb --all --analyze\n"}),
        Turn(user_input="do it", tool="cron", operation="crond-add",
             args={"operation": "crond-add", "name": "db-vacuum",
                   "content": "30 2 * * * postgres /usr/bin/vacuumdb --all --analyze\n"}),
    )),
    V3(id="cron-v3-0005", tool="cron", kind="followup", turns=(
        Turn(user_input="wipe out the www-data crontab entirely, we're moving those jobs to cron.d",
             tool="cron", operation="remove", args={"operation": "remove", "user": "www-data"}),
        Turn(user_input="no wait, undo that, I still need one of those jobs", tool="cron", operation="list",
             args={"operation": "list", "user": "www-data"}),
    )),
    V3(id="cron-v3-0006", tool="cron", kind="followup", turns=(
        Turn(user_input="check what cron.d drop-in files exist on this box", tool="cron", operation="crond-view",
             args={"operation": "crond-view"}),
        Turn(user_input="open the one called certbot-renew", tool="cron", operation="crond-view",
             args={"operation": "crond-view", "name": "certbot-renew"}),
        Turn(user_input="now update it to renew at 4am instead of midnight", tool="cron", operation="crond-add",
             args={"operation": "crond-add", "name": "certbot-renew",
                   "content": "0 4 * * * root /usr/bin/certbot renew --quiet\n"}),
    )),
    V3(id="cron-v3-0007", tool="cron", kind="followup", turns=(
        Turn(user_input="pull up every crontab file sitting in /var/spool/cron", tool="cron", operation="list-all",
             args={"operation": "list-all"}),
        Turn(user_input="that svc-monitor account looks unfamiliar, check the health of the service it drives",
             tool="systemd_timers", operation="list-timers", args={"operation": "list-timers"}),
    )),
    V3(id="cron-v3-0008", tool="cron", kind="followup", turns=(
        Turn(user_input="set up a crontab for the analytics user that runs the nightly rollup at 1am",
             tool="cron", operation="edit",
             args={"operation": "edit", "content": "0 1 * * * /opt/analytics/rollup.sh\n", "user": "analytics"}),
        Turn(user_input="actually instead use the hourly rollup script, not the nightly one", tool="cron", operation="edit",
             args={"operation": "edit", "content": "0 * * * * /opt/analytics/rollup_hourly.sh\n", "user": "analytics"}),
        Turn(user_input="yes go ahead and confirm it stuck", tool="cron", operation="list",
             args={"operation": "list", "user": "analytics"}),
    )),
    V3(id="cron-v3-0009", tool="cron", kind="followup", turns=(
        Turn(user_input="show the current user's crontab", tool="cron", operation="list", args={"operation": "list"}),
        Turn(user_input="why did that come back empty", tool="cron", operation="list-all",
             args={"operation": "list-all"}),
    )),
    V3(id="cron-v3-0010", tool="cron", kind="question", turns=(
        Turn(user_input="list the crontab for the reports user", tool="cron", operation="list",
             args={"operation": "list", "user": "reports"}),
        Turn(user_input="what do those five fields at the start of each line mean",
             answer="They are minute, hour, day-of-month, month, and day-of-week, in that order, followed by the command to run. A star in any field means every value of that field, so '0 6 * * *' fires at 6:00am daily."),
    )),
    V3(id="cron-v3-0011", tool="cron", kind="question", turns=(
        Turn(user_input="view the disk-cleanup drop-in in cron.d", tool="cron", operation="crond-view",
             args={"operation": "crond-view", "name": "disk-cleanup"}),
        Turn(user_input="does that file need a username field like the crontab entries do",
             answer="Yes, unlike a per-user crontab, /etc/cron.d/ files run as root by default and each line must name a user to run as (the field right after the schedule). If that's missing, cron will typically treat the next token as the user and misfire."),
    )),
    V3(id="cron-v3-0012", tool="cron", kind="question", turns=(
        Turn(user_input="remove the temp-worker crontab, that account is being decommissioned", tool="cron", operation="remove",
             args={"operation": "remove", "user": "temp-worker"}),
        Turn(user_input="is that reversible if we need one of those jobs back later",
             answer="No, crontab -r deletes the whole file with no backup or trash. If any of those jobs still matter, they need to be recreated from scratch or from a saved copy of the crontab before this ran."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("cron", SCENARIOS_V3)
