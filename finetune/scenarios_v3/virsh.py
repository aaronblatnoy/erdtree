"""finetune/scenarios_v3/virsh.py — corpus v3 multi-turn scenarios for 'virsh'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="virsh-v3-0001", tool="virsh", kind="followup", turns=(
        Turn(user_input="list all defined domains", tool="virsh", operation="list",
             args={"operation": "list"}),
        Turn(user_input="also show dominfo for rocky9-build01", tool="virsh", operation="dominfo",
             args={"operation": "dominfo", "domain": "rocky9-build01"}),
    )),
    V3(id="virsh-v3-0002", tool="virsh", kind="followup", turns=(
        Turn(user_input="start the domain win10-testbed", tool="virsh", operation="start",
             args={"operation": "start", "domain": "win10-testbed"}),
        Turn(user_input="now the same for centos9-qa", tool="virsh", operation="start",
             args={"operation": "start", "domain": "centos9-qa"}),
    )),
    V3(id="virsh-v3-0003", tool="virsh", kind="followup", turns=(
        Turn(user_input="dominfo for ubuntu22-jenkins-worker", tool="virsh", operation="dominfo",
             args={"operation": "dominfo", "domain": "ubuntu22-jenkins-worker"}),
        Turn(user_input="yes, shut it down gracefully", tool="virsh", operation="shutdown",
             args={"operation": "shutdown", "domain": "ubuntu22-jenkins-worker"}),
    )),
    V3(id="virsh-v3-0004", tool="virsh", kind="followup", turns=(
        Turn(user_input="shutdown the domain staging-web03", tool="virsh", operation="shutdown",
             args={"operation": "shutdown", "domain": "staging-web03"}),
        Turn(user_input="it's not responding, do it the hard way instead, destroy it", tool="virsh", operation="destroy",
             args={"operation": "destroy", "domain": "staging-web03"}),
    )),
    V3(id="virsh-v3-0005", tool="virsh", kind="followup", turns=(
        Turn(user_input="define a domain from /tmp/rhel9-vm.xml", tool="virsh", operation="define",
             args={"operation": "define", "xmlfile": "/tmp/rhel9-vm.xml"}),
        Turn(user_input="ok do it, start that domain now", tool="virsh", operation="start",
             args={"operation": "start", "domain": "rhel9-vm"}),
    )),
    V3(id="virsh-v3-0006", tool="virsh", kind="followup", turns=(
        Turn(user_input="list the storage pools", tool="virsh", operation="pool-list",
             args={"operation": "pool-list"}),
        Turn(user_input="define a new one from /tmp/backup-pool.xml", tool="virsh", operation="pool-define",
             args={"operation": "pool-define", "xmlfile": "/tmp/backup-pool.xml"}),
    )),
    V3(id="virsh-v3-0007", tool="virsh", kind="followup", turns=(
        Turn(user_input="dominfo for devbox-erdtree", tool="virsh", operation="dominfo",
             args={"operation": "dominfo", "domain": "devbox-erdtree"}),
        Turn(user_input="undo my earlier shutdown, start it back up", tool="virsh", operation="start",
             args={"operation": "start", "domain": "devbox-erdtree"}),
        Turn(user_input="confirm with dominfo again", tool="virsh", operation="dominfo",
             args={"operation": "dominfo", "domain": "devbox-erdtree"}),
    )),
    V3(id="virsh-v3-0008", tool="virsh", kind="followup", turns=(
        Turn(user_input="destroy the stuck domain legacy-fileserver", tool="virsh", operation="destroy",
             args={"operation": "destroy", "domain": "legacy-fileserver"}),
        Turn(user_input="now undefine it, and remove its storage too", tool="virsh", operation="undefine",
             args={"operation": "undefine", "domain": "legacy-fileserver", "remove_storage": True}),
    )),
    V3(id="virsh-v3-0009", tool="virsh", kind="followup", turns=(
        Turn(user_input="list domains on this host", tool="virsh", operation="list",
             args={"operation": "list"}),
        Turn(user_input="one of those looks unresponsive, check host cpu load", tool="performance", operation="load",
             args={"operation": "load"}),
        Turn(user_input="also pull recent journal logs for libvirtd", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "libvirtd.service", "lines": 100}),
    )),
    V3(id="virsh-v3-0010", tool="virsh", kind="question", turns=(
        Turn(user_input="dominfo for finance-erp-vm", tool="virsh", operation="dominfo",
             args={"operation": "dominfo", "domain": "finance-erp-vm"}),
        Turn(user_input="what does that state 'paused' mean",
             answer="Paused means the domain's virtual CPUs are frozen in place — memory and disk state are preserved but nothing is executing. It is usually the result of a manual suspend or a hypervisor resource pressure event; resume it or check host memory before assuming it crashed."),
    )),
    V3(id="virsh-v3-0011", tool="virsh", kind="question", turns=(
        Turn(user_input="destroy the domain test-sandbox09", tool="virsh", operation="destroy",
             args={"operation": "destroy", "domain": "test-sandbox09"}),
        Turn(user_input="was that safe to run on a domain with unsaved writes",
             answer="No — destroy is equivalent to pulling the power cord, so any unflushed disk writes or in-memory state are lost. It is fine for a genuinely stuck domain, but a graceful shutdown should always be tried first when the guest is still responsive."),
    )),
    V3(id="virsh-v3-0012", tool="virsh", kind="question", turns=(
        Turn(user_input="list storage pools", tool="virsh", operation="pool-list",
             args={"operation": "pool-list"}),
        Turn(user_input="what does that inactive state mean for the backup-pool row",
             answer="Inactive means the pool definition exists but libvirt has not started it, so its volumes are not currently accessible to any domain. It needs to be started before a domain can attach storage from it."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("virsh", SCENARIOS_V3)
