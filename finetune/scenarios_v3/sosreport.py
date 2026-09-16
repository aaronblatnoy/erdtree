"""finetune/scenarios_v3/sosreport.py — corpus v3 multi-turn scenarios for 'sosreport'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="sosreport-v3-0001", tool="sosreport", kind="followup", turns=(
        Turn(user_input="list the available sos plugins", tool="sosreport", operation="info",
             args={"operation": "info"}),
        Turn(user_input="show me the one for networking, just that one", tool="sosreport", operation="info",
             args={"operation": "info", "plugin": "networking"}),
    )),
    V3(id="sosreport-v3-0002", tool="sosreport", kind="followup", turns=(
        Turn(user_input="check the status of the kernel plugin", tool="sosreport", operation="info",
             args={"operation": "info", "plugin": "kernel"}),
        Turn(user_input="that looks fine, go ahead and generate a full diagnostics archive", tool="sosreport", operation="generate",
             args={"operation": "generate"}),
    )),
    V3(id="sosreport-v3-0003", tool="sosreport", kind="followup", turns=(
        Turn(user_input="collect a diagnostics archive labeled outage-0916", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "outage-0916"}),
        Turn(user_input="do the same but write it to /mnt/nfs-share this time", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "outage-0916", "output_dir": "/mnt/nfs-share"}),
    )),
    V3(id="sosreport-v3-0004", tool="sosreport", kind="followup", turns=(
        Turn(user_input="run a sos report with label db-crash into /var/tmp", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "db-crash", "output_dir": "/var/tmp"}),
        Turn(user_input="no, use the other directory instead, /srv/diag-archives", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "db-crash", "output_dir": "/srv/diag-archives"}),
    )),
    V3(id="sosreport-v3-0005", tool="sosreport", kind="followup", turns=(
        Turn(user_input="generate a diagnostics archive labeled weekly-audit", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "weekly-audit"}),
        Turn(user_input="and then confirm the filesystem hasn't drifted, run an aide check", tool="aide", operation="check",
             args={"operation": "check"}),
    )),
    V3(id="sosreport-v3-0006", tool="sosreport", kind="followup", turns=(
        Turn(user_input="show info for the logs plugin", tool="sosreport", operation="info",
             args={"operation": "info", "plugin": "logs"}),
        Turn(user_input="undo that, show me the process plugin instead", tool="sosreport", operation="info",
             args={"operation": "info", "plugin": "process"}),
    )),
    V3(id="sosreport-v3-0007", tool="sosreport", kind="followup", turns=(
        Turn(user_input="list all sos plugins and their status", tool="sosreport", operation="info",
             args={"operation": "info"}),
        Turn(user_input="storage looks enabled, go ahead and collect the full archive", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "storage-review"}),
        Turn(user_input="confirm it by listing plugin status again", tool="sosreport", operation="info",
             args={"operation": "info"}),
    )),
    V3(id="sosreport-v3-0008", tool="sosreport", kind="followup", turns=(
        Turn(user_input="collect a diagnostics archive labeled ticket-4471 into /var/tmp", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "ticket-4471", "output_dir": "/var/tmp"}),
        Turn(user_input="pull up its running containers too while we're at it", tool="podman", operation="ps",
             args={"operation": "ps", "all": True}),
        Turn(user_input="also pull logs for that one crash-looping container, api-gateway", tool="podman", operation="logs",
             args={"operation": "logs", "container": "api-gateway"}),
    )),
    V3(id="sosreport-v3-0009", tool="sosreport", kind="followup", turns=(
        Turn(user_input="show the selinux plugin's status", tool="sosreport", operation="info",
             args={"operation": "info", "plugin": "selinux"}),
        Turn(user_input="and the same for the firewall plugin", tool="sosreport", operation="info",
             args={"operation": "info", "plugin": "firewall"}),
    )),
    V3(id="sosreport-v3-0010", tool="sosreport", kind="question", turns=(
        Turn(user_input="generate a diagnostics archive labeled incident-882", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "incident-882"}),
        Turn(user_input="where did that archive actually get written",
             answer="With no output_dir specified, sos report writes the archive to /var/tmp by default, named with the host and the incident-882 label baked in. Check that directory for a tarball and a matching checksum file next to it."),
    )),
    V3(id="sosreport-v3-0011", tool="sosreport", kind="question", turns=(
        Turn(user_input="list available sos plugins for this host", tool="sosreport", operation="info",
             args={"operation": "info"}),
        Turn(user_input="what does it mean if a plugin shows as not loaded",
             answer="Not loaded means the plugin's dependencies weren't detected on this host — its subsystem isn't installed or isn't applicable, so sos skips collecting for it. It's expected behavior, not an error; a disabled plugin for hardware or a service you don't run just won't appear in the archive."),
    )),
    V3(id="sosreport-v3-0012", tool="sosreport", kind="question", turns=(
        Turn(user_input="collect a full diagnostics archive labeled pre-upgrade", tool="sosreport", operation="generate",
             args={"operation": "generate", "label": "pre-upgrade"}),
        Turn(user_input="roughly how big is that archive going to be",
             answer="A default sos report archive typically lands somewhere between a few hundred megabytes and a couple gigabytes, depending mostly on how much log history and how many installed packages are on the host. Systems with verbose journald logs or many containers tend to sit at the higher end."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("sosreport", SCENARIOS_V3)
