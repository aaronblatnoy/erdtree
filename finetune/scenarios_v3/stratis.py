"""finetune/scenarios_v3/stratis.py — corpus v3 multi-turn scenarios for 'stratis'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="stratis-v3-0001", tool="stratis", kind="followup", turns=(
        Turn(user_input="list every stratis pool on this host", tool="stratis", operation="pool-list", args={"operation": "pool-list"}),
        Turn(user_input="now list that pool's filesystems, it's called poolA", tool="stratis", operation="filesystem-list", args={"operation": "filesystem-list", "pool": "poolA"}),
    )),
    V3(id="stratis-v3-0002", tool="stratis", kind="followup", turns=(
        Turn(user_input="create a pool named datapool on /dev/sdc", tool="stratis", operation="pool-create", args={"operation": "pool-create", "pool": "datapool", "blockdev": "/dev/sdc"}),
        Turn(user_input="and then create a filesystem named archive in it", tool="stratis", operation="filesystem-create", args={"operation": "filesystem-create", "pool": "datapool", "filesystem": "archive"}),
    )),
    V3(id="stratis-v3-0003", tool="stratis", kind="followup", turns=(
        Turn(user_input="snapshot the archive filesystem in datapool as archive-snap1", tool="stratis", operation="filesystem-snapshot", args={"operation": "filesystem-snapshot", "pool": "datapool", "filesystem": "archive", "snapshot": "archive-snap1"}),
        Turn(user_input="do the same again but call it archive-snap2", tool="stratis", operation="filesystem-snapshot", args={"operation": "filesystem-snapshot", "pool": "datapool", "filesystem": "archive", "snapshot": "archive-snap2"}),
    )),
    V3(id="stratis-v3-0004", tool="stratis", kind="followup", turns=(
        Turn(user_input="destroy the filesystem scratch in pool buildpool", tool="stratis", operation="filesystem-destroy", args={"operation": "filesystem-destroy", "pool": "buildpool", "filesystem": "scratch"}),
        Turn(user_input="no wait, undo that, recreate scratch in buildpool", tool="stratis", operation="filesystem-create", args={"operation": "filesystem-create", "pool": "buildpool", "filesystem": "scratch"}),
    )),
    V3(id="stratis-v3-0005", tool="stratis", kind="followup", turns=(
        Turn(user_input="create a new pool named logpool on /dev/sdd", tool="stratis", operation="pool-create", args={"operation": "pool-create", "pool": "logpool", "blockdev": "/dev/sdd"}),
        Turn(user_input="yes go ahead, then create a filesystem in it called syslogs", tool="stratis", operation="filesystem-create", args={"operation": "filesystem-create", "pool": "logpool", "filesystem": "syslogs"}),
        Turn(user_input="now check disk usage on that filesystem's mount", tool="disk", operation="usage", args={"operation": "usage", "path": "/stratis/logpool/syslogs"}),
    )),
    V3(id="stratis-v3-0006", tool="stratis", kind="followup", turns=(
        Turn(user_input="destroy the pool oldpool, it's fully decommissioned", tool="stratis", operation="pool-destroy", args={"operation": "pool-destroy", "pool": "oldpool"}),
        Turn(user_input="confirm the pool list no longer shows it", tool="stratis", operation="pool-list", args={"operation": "pool-list"}),
    )),
    V3(id="stratis-v3-0007", tool="stratis", kind="followup", turns=(
        Turn(user_input="list the filesystems across all pools", tool="stratis", operation="filesystem-list", args={"operation": "filesystem-list"}),
        Turn(user_input="just show me poolB's instead", tool="stratis", operation="filesystem-list", args={"operation": "filesystem-list", "pool": "poolB"}),
    )),
    V3(id="stratis-v3-0008", tool="stratis", kind="followup", turns=(
        Turn(user_input="snapshot the users filesystem in homepool as users-backup", tool="stratis", operation="filesystem-snapshot", args={"operation": "filesystem-snapshot", "pool": "homepool", "filesystem": "users", "snapshot": "users-backup"}),
        Turn(user_input="instead call the snapshot users-nightly", tool="stratis", operation="filesystem-snapshot", args={"operation": "filesystem-snapshot", "pool": "homepool", "filesystem": "users", "snapshot": "users-nightly"}),
        Turn(user_input="and then list the filesystems in homepool to verify", tool="stratis", operation="filesystem-list", args={"operation": "filesystem-list", "pool": "homepool"}),
    )),
    V3(id="stratis-v3-0009", tool="stratis", kind="followup", turns=(
        Turn(user_input="create pool mediapool on /dev/sde", tool="stratis", operation="pool-create", args={"operation": "pool-create", "pool": "mediapool", "blockdev": "/dev/sde"}),
        Turn(user_input="why did that fail", tool="stratis", operation="pool-list", args={"operation": "pool-list"}),
    )),
    V3(id="stratis-v3-0010", tool="stratis", kind="question", turns=(
        Turn(user_input="list the stratis pools", tool="stratis", operation="pool-list", args={"operation": "pool-list"}),
        Turn(user_input="what does that total versus used size column mean", answer="Total physical size is the raw capacity of the block devices assigned to the pool, while used is what stratis has actually allocated to filesystems and metadata so far. Stratis thin-provisions filesystems, so used can grow well past what any single filesystem reports."),
    )),
    V3(id="stratis-v3-0011", tool="stratis", kind="question", turns=(
        Turn(user_input="destroy the pool testpool", tool="stratis", operation="pool-destroy", args={"operation": "pool-destroy", "pool": "testpool"}),
        Turn(user_input="is that data recoverable at all", answer="No, destroying a pool wipes every filesystem and snapshot inside it along with the pool metadata, and there's no undo. Recovery only comes from whatever external backup existed before the destroy ran."),
    )),
    V3(id="stratis-v3-0012", tool="stratis", kind="question", turns=(
        Turn(user_input="snapshot the app filesystem in poolA as app-pre-upgrade", tool="stratis", operation="filesystem-snapshot", args={"operation": "filesystem-snapshot", "pool": "poolA", "filesystem": "app", "snapshot": "app-pre-upgrade"}),
        Turn(user_input="does taking that snapshot pause writes to the live filesystem", answer="No, stratis snapshots are created near-instantly using copy-on-write metadata, so the source filesystem stays fully writable during and after the snapshot. Space usage grows only as blocks diverge between the two."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("stratis", SCENARIOS_V3)
