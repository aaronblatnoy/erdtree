"""finetune/scenarios_v3/aide.py — corpus v3 multi-turn scenarios for 'aide'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="aide-v3-0001", tool="aide", kind="followup", turns=(
        Turn(user_input="run an integrity check against /etc/aide.conf", tool="aide", operation="check",
             args={"operation": "check", "config": "/etc/aide.conf"}),
        Turn(user_input="now the same for the web-tier config at /etc/aide-web.conf", tool="aide", operation="check",
             args={"operation": "check", "config": "/etc/aide-web.conf"}),
    )),
    V3(id="aide-v3-0002", tool="aide", kind="followup", turns=(
        Turn(user_input="check the filesystem against the reference database", tool="aide", operation="check",
             args={"operation": "check"}),
        Turn(user_input="those changes are expected, update the baseline to accept them", tool="aide", operation="update",
             args={"operation": "update"}),
    )),
    V3(id="aide-v3-0003", tool="aide", kind="followup", turns=(
        Turn(user_input="show me the metadata on the aide database file", tool="aide", operation="db_status",
             args={"operation": "db_status"}),
        Turn(user_input="that timestamp looks stale, go ahead and update it now", tool="aide", operation="update",
             args={"operation": "update"}),
    )),
    V3(id="aide-v3-0004", tool="aide", kind="followup", turns=(
        Turn(user_input="initialise a fresh aide database with the default config", tool="aide", operation="init",
             args={"operation": "init"}),
        Turn(user_input="no, use the other config instead, /etc/aide-strict.conf", tool="aide", operation="init",
             args={"operation": "init", "config": "/etc/aide-strict.conf"}),
    )),
    V3(id="aide-v3-0005", tool="aide", kind="followup", turns=(
        Turn(user_input="run a check with /etc/aide-strict.conf", tool="aide", operation="check",
             args={"operation": "check", "config": "/etc/aide-strict.conf"}),
        Turn(user_input="archive that finding, pull together a diagnostics report", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "aide-integrity"}),
    )),
    V3(id="aide-v3-0006", tool="aide", kind="followup", turns=(
        Turn(user_input="check aide integrity on this box", tool="aide", operation="check",
             args={"operation": "check"}),
        Turn(user_input="undo that, actually check it against /etc/aide.conf.bak instead", tool="aide", operation="check",
             args={"operation": "check", "config": "/etc/aide.conf.bak"}),
    )),
    V3(id="aide-v3-0007", tool="aide", kind="followup", turns=(
        Turn(user_input="what does the aide database file look like right now, size and timestamp", tool="aide", operation="db_status",
             args={"operation": "db_status"}),
        Turn(user_input="and the same for the backup copy at /var/lib/aide/aide.db.gz.bak", tool="aide", operation="db_status",
             args={"operation": "db_status", "db_path": "/var/lib/aide/aide.db.gz.bak"}),
    )),
    V3(id="aide-v3-0008", tool="aide", kind="followup", turns=(
        Turn(user_input="check the filesystem against the database using /etc/aide-prod.conf", tool="aide", operation="check",
             args={"operation": "check", "config": "/etc/aide-prod.conf"}),
        Turn(user_input="those are all legitimate patch changes, update the baseline", tool="aide", operation="update",
             args={"operation": "update", "config": "/etc/aide-prod.conf"}),
        Turn(user_input="confirm the database metadata reflects that update", tool="aide", operation="db_status",
             args={"operation": "db_status"}),
    )),
    V3(id="aide-v3-0009", tool="aide", kind="followup", turns=(
        Turn(user_input="set up a brand new reference database on this host", tool="aide", operation="init",
             args={"operation": "init"}),
        Turn(user_input="now confirm it took by checking the filesystem against it", tool="aide", operation="check",
             args={"operation": "check"}),
        Turn(user_input="also show me the database file's metadata", tool="aide", operation="db_status",
             args={"operation": "db_status"}),
    )),
    V3(id="aide-v3-0010", tool="aide", kind="question", turns=(
        Turn(user_input="run an aide check against /etc/aide.conf", tool="aide", operation="check",
             args={"operation": "check", "config": "/etc/aide.conf"}),
        Turn(user_input="what does that nonzero exit code actually mean",
             answer="A nonzero exit from an aide check means the scan found at least one difference between the live filesystem and the reference database — added, removed, or changed files. It does not by itself mean anything was compromised; review the diffs before deciding whether to update the baseline."),
    )),
    V3(id="aide-v3-0011", tool="aide", kind="question", turns=(
        Turn(user_input="show me the current aide database file metadata", tool="aide", operation="db_status",
             args={"operation": "db_status"}),
        Turn(user_input="why would that file's timestamp be so old",
             answer="An old timestamp on the database file just means it hasn't been regenerated since it was last built — nobody has run init or update since then. If real filesystem changes have happened since, a check will flag all of them as drift until the baseline is refreshed."),
    )),
    V3(id="aide-v3-0012", tool="aide", kind="question", turns=(
        Turn(user_input="update the aide database to accept the current state", tool="aide", operation="update",
             args={"operation": "update"}),
        Turn(user_input="what happened to the old baseline after that",
             answer="The prior reference database is overwritten by the update; the changes you just accepted become the new baseline going forward. Future checks compare against this new snapshot, not the one that existed before the update."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("aide", SCENARIOS_V3)
