"""finetune/scenarios_v3/disk.py — corpus v3 multi-turn scenarios for 'disk'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="disk-v3-0001", tool="disk", kind="followup", turns=(
        Turn(user_input="show free space on /var", tool="disk", operation="usage", args={"operation": "usage", "path": "/var"}),
        Turn(user_input="now the same for /home", tool="disk", operation="usage", args={"operation": "usage", "path": "/home"}),
    )),
    V3(id="disk-v3-0002", tool="disk", kind="followup", turns=(
        Turn(user_input="list the partitions on /dev/sdb", tool="disk", operation="list", args={"operation": "list", "device": "/dev/sdb"}),
        Turn(user_input="and /dev/sdc too", tool="disk", operation="list", args={"operation": "list", "device": "/dev/sdc"}),
    )),
    V3(id="disk-v3-0003", tool="disk", kind="followup", turns=(
        Turn(user_input="check the health of /dev/nvme0n1", tool="disk", operation="smart", args={"operation": "smart", "device": "/dev/nvme0n1"}),
        Turn(user_input="pull the same report for /dev/nvme1n1", tool="disk", operation="smart", args={"operation": "smart", "device": "/dev/nvme1n1"}),
    )),
    V3(id="disk-v3-0004", tool="disk", kind="followup", turns=(
        Turn(user_input="list block devices on the host", tool="disk", operation="list", args={"operation": "list"}),
        Turn(user_input="ok, now mount /dev/sdb1 at /mnt/backup", tool="disk", operation="mount", args={"operation": "mount", "device": "/dev/sdb1", "mount_point": "/mnt/backup"}),
    )),
    V3(id="disk-v3-0005", tool="disk", kind="followup", turns=(
        Turn(user_input="mount /dev/sdc1 at /mnt/scratch", tool="disk", operation="mount", args={"operation": "mount", "device": "/dev/sdc1", "mount_point": "/mnt/scratch"}),
        Turn(user_input="yes go ahead and unmount it again", tool="disk", operation="unmount", args={"operation": "unmount", "target": "/mnt/scratch"}),
    )),
    V3(id="disk-v3-0006", tool="disk", kind="followup", turns=(
        Turn(user_input="format /dev/sdd1 as xfs", tool="disk", operation="format", args={"operation": "format", "device": "/dev/sdd1", "fstype": "xfs"}),
        Turn(user_input="no, use ext4 instead", tool="disk", operation="format", args={"operation": "format", "device": "/dev/sdd1", "fstype": "ext4"}),
    )),
    V3(id="disk-v3-0007", tool="disk", kind="followup", turns=(
        Turn(user_input="unmount /mnt/data1", tool="disk", operation="unmount", args={"operation": "unmount", "target": "/mnt/data1"}),
        Turn(user_input="instead, check disk usage on the root filesystem", tool="disk", operation="usage", args={"operation": "usage", "path": "/"}),
    )),
    V3(id="disk-v3-0008", tool="disk", kind="followup", turns=(
        Turn(user_input="show SMART attributes for /dev/sda", tool="disk", operation="smart", args={"operation": "smart", "device": "/dev/sda"}),
        Turn(user_input="that drive looks bad, wipe /dev/sdz first so I can repurpose it", tool="disk", operation="wipe", args={"operation": "wipe", "device": "/dev/sdz"}),
        Turn(user_input="and now partition it with a new table", tool="disk", operation="partition", args={"operation": "partition", "device": "/dev/sdz", "command": ["mklabel", "msdos"]}),
    )),
    V3(id="disk-v3-0009", tool="disk", kind="followup", turns=(
        Turn(user_input="list devices attached to the host", tool="disk", operation="list", args={"operation": "list"}),
        Turn(user_input="use it to write the rocky9.iso image onto /dev/sdb", tool="disk", operation="dd_write", args={"operation": "dd_write", "source": "/root/rocky9.iso", "device": "/dev/sdb", "bs": "4M"}),
        Turn(user_input="what happened, is it done", tool="disk", operation="usage", args={"operation": "usage"}),
    )),
    V3(id="disk-v3-0010", tool="disk", kind="question", turns=(
        Turn(user_input="report SMART health for /dev/sdb", tool="disk", operation="smart", args={"operation": "smart", "device": "/dev/sdb"}),
        Turn(user_input="what does that reallocated sector count mean", answer="A nonzero reallocated sector count means the drive already remapped bad sectors to spares. A handful is common on an older drive, but a rising count means the media is degrading and you should plan to replace it before it fails outright."),
    )),
    V3(id="disk-v3-0011", tool="disk", kind="question", turns=(
        Turn(user_input="show usage for the filesystem holding /var/log", tool="disk", operation="usage", args={"operation": "usage", "path": "/var/log"}),
        Turn(user_input="why did that filesystem fill up so fast", answer="Fast growth on /var/log is almost always runaway logging: a service in a crash loop, verbose debug logging left on, or journald not rotating. Check the largest files under /var/log and the journal size before deciding whether to rotate, compress, or grow the volume."),
    )),
    V3(id="disk-v3-0012", tool="disk", kind="question", turns=(
        Turn(user_input="list partitions on /dev/sda", tool="disk", operation="list", args={"operation": "list", "device": "/dev/sda"}),
        Turn(user_input="what happened to the free space at the end of that disk", answer="Unpartitioned space past the last partition just means the table doesn't extend to the end of the disk yet. You'd grow the last partition or add a new one to claim it; it isn't lost, just unallocated."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("disk", SCENARIOS_V3)
