"""finetune/scenarios_v3/kernel_modules.py — corpus v3 multi-turn scenarios for 'kernel_modules'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="kernel_modules-v3-0001", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="show metadata for the nf_conntrack module", tool="kernel_modules", operation="modinfo", args={"operation": "modinfo", "module": "nf_conntrack"}),
        Turn(user_input="now the same for br_netfilter", tool="kernel_modules", operation="modinfo", args={"operation": "modinfo", "module": "br_netfilter"}),
    )),
    V3(id="kernel_modules-v3-0002", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="load the overlay module", tool="kernel_modules", operation="modprobe", args={"operation": "modprobe", "module": "overlay"}),
        Turn(user_input="and load ip_vs too", tool="kernel_modules", operation="modprobe", args={"operation": "modprobe", "module": "ip_vs"}),
    )),
    V3(id="kernel_modules-v3-0003", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="list what's currently loaded", tool="kernel_modules", operation="lsmod", args={"operation": "lsmod"}),
        Turn(user_input="ok, load br_netfilter for the bridge filtering rules", tool="kernel_modules", operation="modprobe", args={"operation": "modprobe", "module": "br_netfilter"}),
    )),
    V3(id="kernel_modules-v3-0004", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="load the vfio_pci module", tool="kernel_modules", operation="modprobe", args={"operation": "modprobe", "module": "vfio_pci"}),
        Turn(user_input="yes, persist it so it loads at every boot", tool="kernel_modules", operation="modules-load.d", args={"operation": "modules-load.d", "module": "vfio_pci"}),
    )),
    V3(id="kernel_modules-v3-0005", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="load the dm_mirror module", tool="kernel_modules", operation="modprobe", args={"operation": "modprobe", "module": "dm_mirror"}),
        Turn(user_input="undo that, remove it again", tool="kernel_modules", operation="rmmod", args={"operation": "rmmod", "module": "dm_mirror"}),
    )),
    V3(id="kernel_modules-v3-0006", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="remove the pcspkr module", tool="kernel_modules", operation="rmmod", args={"operation": "rmmod", "module": "pcspkr"}),
        Turn(user_input="no, use snd_pcsp instead", tool="kernel_modules", operation="rmmod", args={"operation": "rmmod", "module": "snd_pcsp"}),
    )),
    V3(id="kernel_modules-v3-0007", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="what's the status of the network bridge filtering", tool="kernel_modules", operation="lsmod", args={"operation": "lsmod"}),
        Turn(user_input="also check what's using it right now", tool="kernel_modules", operation="modinfo", args={"operation": "modinfo", "module": "br_netfilter"}),
    )),
    V3(id="kernel_modules-v3-0008", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="show info on the nvme module", tool="kernel_modules", operation="modinfo", args={"operation": "modinfo", "module": "nvme"}),
        Turn(user_input="it's not loaded, load it now", tool="kernel_modules", operation="modprobe", args={"operation": "modprobe", "module": "nvme"}),
        Turn(user_input="also persist that one under a custom filename", tool="kernel_modules", operation="modules-load.d", args={"operation": "modules-load.d", "module": "nvme", "filename": "storage"}),
    )),
    V3(id="kernel_modules-v3-0009", tool="kernel_modules", kind="followup", turns=(
        Turn(user_input="list every loaded module", tool="kernel_modules", operation="lsmod", args={"operation": "lsmod"}),
        Turn(user_input="also unload the floppy module, it's unused here", tool="kernel_modules", operation="rmmod", args={"operation": "rmmod", "module": "floppy"}),
        Turn(user_input="confirm it's gone", tool="kernel_modules", operation="lsmod", args={"operation": "lsmod"}),
    )),
    V3(id="kernel_modules-v3-0010", tool="kernel_modules", kind="question", turns=(
        Turn(user_input="show metadata for the ip_tables module", tool="kernel_modules", operation="modinfo", args={"operation": "modinfo", "module": "ip_tables"}),
        Turn(user_input="what do those dependencies mean for removing it", answer="Those are modules that must be unloaded first, or that depend on ip_tables and would break if it's pulled. Check the 'used by' count before rmmod — anything nonzero means an active dependent, and removal will fail or disrupt traffic."),
    )),
    V3(id="kernel_modules-v3-0011", tool="kernel_modules", kind="question", turns=(
        Turn(user_input="try to remove the xt_conntrack module", tool="kernel_modules", operation="rmmod", args={"operation": "rmmod", "module": "xt_conntrack"}),
        Turn(user_input="why did that fail", answer="rmmod fails with 'in use' when another loaded module or an active netfilter rule still references it. Check lsmod's usedby column for xt_conntrack and clear or unload whatever depends on it before retrying."),
    )),
    V3(id="kernel_modules-v3-0012", tool="kernel_modules", kind="question", turns=(
        Turn(user_input="load the tcp_bbr module", tool="kernel_modules", operation="modprobe", args={"operation": "modprobe", "module": "tcp_bbr"}),
        Turn(user_input="what happened, does that stick after a reboot", answer="No — modprobe only loads it for the current session. To make it survive a reboot you need to persist the module name under /etc/modules-load.d/, otherwise it disappears on the next restart."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("kernel_modules", SCENARIOS_V3)
