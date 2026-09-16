"""finetune/scenarios_v3/at.py — corpus v3 multi-turn scenarios for 'at'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="at-v3-0001", tool="at", kind="followup", turns=(
        Turn(user_input="Queue a job to rotate the archive logs at 2am tomorrow.", tool="at", operation="schedule",
             args={"operation": "schedule", "time": "2:00 tomorrow", "command": "/usr/local/bin/rotate-archive.sh"}),
        Turn(user_input="Now do the same but for the staging box at 3am instead.", tool="at", operation="schedule",
             args={"operation": "schedule", "time": "3:00 tomorrow", "command": "/usr/local/bin/rotate-archive-staging.sh"}),
    )),
    V3(id="at-v3-0002", tool="at", kind="followup", turns=(
        Turn(user_input="List what's queued in the default spool.", tool="at", operation="atq",
             args={"operation": "atq"}),
        Turn(user_input="Pull job 14 out of it, we don't need that run anymore.", tool="at", operation="atrm",
             args={"operation": "atrm", "job_id": "14"}),
    )),
    V3(id="at-v3-0003", tool="at", kind="followup", turns=(
        Turn(user_input="Schedule the invoice export for noon.", tool="at", operation="schedule",
             args={"operation": "schedule", "time": "noon", "command": "/opt/billing/export_invoices.sh"}),
        Turn(user_input="Yes, go ahead and also check the queue to confirm it landed.", tool="at", operation="atq",
             args={"operation": "atq"}),
    )),
    V3(id="at-v3-0004", tool="at", kind="followup", turns=(
        Turn(user_input="Set up a one-off job to restart the sync worker at midnight.", tool="at", operation="schedule",
             args={"operation": "schedule", "time": "midnight", "command": "systemctl restart sync-worker.service"}),
        Turn(user_input="Undo that, I picked the wrong time.", tool="at", operation="atq",
             args={"operation": "atq"}),
        Turn(user_input="Remove job 21, that's the one I just queued.", tool="at", operation="atrm",
             args={"operation": "atrm", "job_id": "21"}),
    )),
    V3(id="at-v3-0005", tool="at", kind="followup", turns=(
        Turn(user_input="Check queue b for pending jobs.", tool="at", operation="atq",
             args={"operation": "atq", "queue": "b"}),
        Turn(user_input="No, use queue c instead, I misread the ticket.", tool="at", operation="atq",
             args={"operation": "atq", "queue": "c"}),
    )),
    V3(id="at-v3-0006", tool="at", kind="followup", turns=(
        Turn(user_input="Schedule a disk cleanup for 4:30am on the media server.", tool="at", operation="schedule",
             args={"operation": "schedule", "time": "4:30", "command": "/usr/local/sbin/cleanup-media-scratch.sh"}),
        Turn(user_input="Ok do it, and then show me the current queue.", tool="at", operation="atq",
             args={"operation": "atq"}),
    )),
    V3(id="at-v3-0007", tool="at", kind="followup", turns=(
        Turn(user_input="Queue a job to email the report at 6pm today.", tool="at", operation="schedule",
             args={"operation": "schedule", "time": "18:00", "command": "/opt/reports/send_daily.sh"}),
        Turn(user_input="Also check whether the cron table has a conflicting entry for that same script.", tool="cron", operation="list",
             args={"operation": "list"}),
    )),
    V3(id="at-v3-0008", tool="at", kind="followup", turns=(
        Turn(user_input="Remove job 9 from the spool, it was a duplicate.", tool="at", operation="atrm",
             args={"operation": "atrm", "job_id": "9"}),
        Turn(user_input="And job 10 too, same duplicate batch.", tool="at", operation="atrm",
             args={"operation": "atrm", "job_id": "10"}),
    )),
    V3(id="at-v3-0009", tool="at", kind="followup", turns=(
        Turn(user_input="Schedule the certificate renewal check for 1am on the edge proxy.", tool="at", operation="schedule",
             args={"operation": "schedule", "time": "1:00", "command": "/usr/local/bin/cert-renew-check.sh"}),
        Turn(user_input="Confirm it's in the queue.", tool="at", operation="atq",
             args={"operation": "atq"}),
        Turn(user_input="Good, now cancel job 33, that was leftover from last week's test.", tool="at", operation="atrm",
             args={"operation": "atrm", "job_id": "33"}),
    )),
    V3(id="at-v3-0010", tool="at", kind="question", turns=(
        Turn(user_input="What's in queue a right now?", tool="at", operation="atq", args={"operation": "atq", "queue": "a"}),
        Turn(user_input="what happened to the job that was supposed to run at 22:30",
             answer="It's still sitting in the spool waiting to fire — atq shows it pending, not run yet.\nIf the clock has already passed 22:30, check the system time and the atd service status."),
    )),
    V3(id="at-v3-0011", tool="at", kind="question", turns=(
        Turn(user_input="Remove job 5, it's stale.", tool="at", operation="atrm", args={"operation": "atrm", "job_id": "5"}),
        Turn(user_input="why did that need root",
             answer="atrm only lets a user cancel jobs they own; removing job 5 as a different owner requires root.\nThat's why the removal ran as root here rather than as the queuing user."),
    )),
    V3(id="at-v3-0012", tool="at", kind="question", turns=(
        Turn(user_input="Schedule a reindex job for 5am on the search cluster.", tool="at", operation="schedule",
             args={"operation": "schedule", "time": "5:00", "command": "/opt/search/reindex.sh"}),
        Turn(user_input="what does that job id mean",
             answer="It's the sequential job number at assigned this spool entry.\nUse it later with atrm to cancel the job, or atq to check whether it already ran."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("at", SCENARIOS_V3)
