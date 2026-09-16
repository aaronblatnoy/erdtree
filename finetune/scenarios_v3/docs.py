"""finetune/scenarios_v3/docs.py — corpus v3 multi-turn scenarios for 'docs'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="docs-v3-0001", tool="docs", kind="followup", turns=(
        Turn(user_input="look up the noexec mount flag behaviour", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "noexec mount flag behaviour"}),
        Turn(user_input="and the same lookup for the nosuid flag", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "nosuid mount flag behaviour"}),
    )),
    V3(id="docs-v3-0002", tool="docs", kind="followup", turns=(
        Turn(user_input="check what the docs say about lvreduce shrinking a logical volume", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "lvreduce shrink logical volume filesystem"}),
        Turn(user_input="that confirms it needs a filesystem pre-shrink, go ahead and shrink data_lv to 20G", tool="lvm", operation="lvreduce",
             args={"operation": "lvreduce", "lv": "vg_data/data_lv", "size": "20G"}),
    )),
    V3(id="docs-v3-0003", tool="docs", kind="followup", turns=(
        Turn(user_input="pull passages on firewalld rich rule syntax", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "firewalld rich rule syntax"}),
        Turn(user_input="also look up masquerade behaviour in the same context", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "firewalld masquerade behaviour"}),
    )),
    V3(id="docs-v3-0004", tool="docs", kind="followup", turns=(
        Turn(user_input="what do the docs say about podman rootless networking limits", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "podman rootless networking limits"}),
        Turn(user_input="no, instead look up rootless port binding below 1024", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "podman rootless port binding below 1024"}),
    )),
    V3(id="docs-v3-0005", tool="docs", kind="followup", turns=(
        Turn(user_input="retrieve reference material on aide database initialisation", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "aide database initialisation init"}),
        Turn(user_input="that's what I needed, go ahead and initialise it with /etc/aide.conf", tool="aide", operation="init",
             args={"operation": "init", "config": "/etc/aide.conf"}),
    )),
    V3(id="docs-v3-0006", tool="docs", kind="followup", turns=(
        Turn(user_input="look up sos report plugin selection options, give me 5 passages", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "sos report plugin selection options", "k": 5}),
        Turn(user_input="show me more results, just on the batch flag this time", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "sos report batch flag", "k": 2}),
    )),
    V3(id="docs-v3-0007", tool="docs", kind="followup", turns=(
        Turn(user_input="check the docs on lvm pvremove data-loss warnings", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "lvm pvremove data loss warning"}),
        Turn(user_input="that's concerning, first show me the physical volumes on this host", tool="lvm", operation="pvdisplay",
             args={"operation": "pvdisplay"}),
        Turn(user_input="also pull passages on vgremove for the same reason", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "lvm vgremove data loss warning"}),
    )),
    V3(id="docs-v3-0008", tool="docs", kind="followup", turns=(
        Turn(user_input="retrieve passages on podman rmi and dangling image cleanup", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "podman rmi dangling image cleanup"}),
        Turn(user_input="ok now list the local images so I can see what's dangling", tool="podman", operation="images",
             args={"operation": "images"}),
        Turn(user_input="and the same lookup but for prune instead of rmi", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "podman image prune behaviour"}),
    )),
    V3(id="docs-v3-0009", tool="docs", kind="followup", turns=(
        Turn(user_input="look up how aide check exit codes are structured", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "aide check exit code structure"}),
        Turn(user_input="do it again but narrow the query to just the database-corrupt case", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "aide check exit code database corrupt"}),
    )),
    V3(id="docs-v3-0010", tool="docs", kind="question", turns=(
        Turn(user_input="retrieve passages on the noexec mount flag", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "noexec mount flag behaviour"}),
        Turn(user_input="which of those passages is most relevant to a shared /tmp",
             answer="The passage covering noexec's effect on shared or world-writable mounts is the relevant one — it explains that noexec blocks direct execution of binaries from that mount, which is the standard hardening measure for a shared /tmp. The others cover general mount option syntax rather than that specific risk."),
    )),
    V3(id="docs-v3-0011", tool="docs", kind="question", turns=(
        Turn(user_input="look up reference material on sos report archive retention", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "sos report archive retention cleanup"}),
        Turn(user_input="based on that, where do old archives actually pile up",
             answer="Sos report archives are written to /var/tmp by default unless an output directory is specified, and nothing automatically prunes them. Old archives accumulate there until someone deletes them manually or points future runs at a different output directory."),
    )),
    V3(id="docs-v3-0012", tool="docs", kind="question", turns=(
        Turn(user_input="pull passages covering lvm volume group extend behaviour", tool="docs", operation="retrieve",
             args={"operation": "retrieve", "query": "lvm volume group extend vgextend"}),
        Turn(user_input="based on that, what's the actual risk on a live system",
             answer="Extending a volume group by adding a physical volume is low risk on a live system — it only grows the pool of extents available and does not touch existing data or logical volumes. The riskier follow-on step is extending a logical volume onto the new space without also growing its filesystem."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("docs", SCENARIOS_V3)
