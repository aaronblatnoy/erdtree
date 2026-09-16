"""finetune/scenarios_v3/quota.py — corpus v3 multi-turn scenarios for 'quota'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="quota-v3-0001", tool="quota", kind="followup", turns=(
        Turn(user_input="show quota usage for jdoe", tool="quota", operation="quota_user", args={"operation": "quota_user", "username": "jdoe"}),
        Turn(user_input="now the same for msmith", tool="quota", operation="quota_user", args={"operation": "quota_user", "username": "msmith"}),
    )),
    V3(id="quota-v3-0002", tool="quota", kind="followup", turns=(
        Turn(user_input="report quota usage across all quota-enabled filesystems", tool="quota", operation="repquota", args={"operation": "repquota"}),
        Turn(user_input="limit that to just /home", tool="quota", operation="repquota", args={"operation": "repquota", "filesystem": "/home"}),
    )),
    V3(id="quota-v3-0003", tool="quota", kind="followup", turns=(
        Turn(user_input="enable quota enforcement on /home", tool="quota", operation="quotaon", args={"operation": "quotaon", "filesystem": "/home"}),
        Turn(user_input="and /data too", tool="quota", operation="quotaon", args={"operation": "quotaon", "filesystem": "/data"}),
    )),
    V3(id="quota-v3-0004", tool="quota", kind="followup", turns=(
        Turn(user_input="turn off quota enforcement on /home for the migration", tool="quota", operation="quotaoff", args={"operation": "quotaoff", "filesystem": "/home"}),
        Turn(user_input="ok, now rebuild the accounting files for it", tool="quota", operation="quotacheck", args={"operation": "quotacheck", "filesystem": "/home"}),
        Turn(user_input="turn that back on once the check finishes", tool="quota", operation="quotaon", args={"operation": "quotaon", "filesystem": "/home"}),
    )),
    V3(id="quota-v3-0005", tool="quota", kind="followup", turns=(
        Turn(user_input="set a soft limit of 10000000 blocks and hard limit of 12000000 blocks for jdoe on /home", tool="quota", operation="edquota", args={"operation": "edquota", "username": "jdoe", "filesystem": "/home", "soft_blocks": 10000000, "hard_blocks": 12000000}),
        Turn(user_input="undo that, set both back to 0 for no limit", tool="quota", operation="edquota", args={"operation": "edquota", "username": "jdoe", "filesystem": "/home", "soft_blocks": 0, "hard_blocks": 0}),
    )),
    V3(id="quota-v3-0006", tool="quota", kind="followup", turns=(
        Turn(user_input="what does msmith's quota look like on /home", tool="quota", operation="quota_user", args={"operation": "quota_user", "username": "msmith"}),
        Turn(user_input="also raise the hard inode limit to 500000 for them", tool="quota", operation="edquota", args={"operation": "edquota", "username": "msmith", "filesystem": "/home", "hard_inodes": 500000}),
    )),
    V3(id="quota-v3-0007", tool="quota", kind="followup", turns=(
        Turn(user_input="run a quota scan on /data to rebuild the accounting files", tool="quota", operation="quotacheck", args={"operation": "quotacheck", "filesystem": "/data"}),
        Turn(user_input="now also check the disk usage there", tool="disk", operation="usage", args={"operation": "usage", "path": "/data"}),
    )),
    V3(id="quota-v3-0008", tool="quota", kind="followup", turns=(
        Turn(user_input="set soft inode limit 200000 and hard inode limit 250000 for deploy on /srv", tool="quota", operation="edquota", args={"operation": "edquota", "username": "deploy", "filesystem": "/srv", "soft_inodes": 200000, "hard_inodes": 250000}),
        Turn(user_input="do the same for the ci user on /srv", tool="quota", operation="edquota", args={"operation": "edquota", "username": "ci", "filesystem": "/srv", "soft_inodes": 200000, "hard_inodes": 250000}),
        Turn(user_input="also pull up their current usage to verify", tool="quota", operation="quota_user", args={"operation": "quota_user", "username": "ci"}),
    )),
    V3(id="quota-v3-0009", tool="quota", kind="followup", turns=(
        Turn(user_input="disable quota enforcement on /dev/sdb1", tool="quota", operation="quotaoff", args={"operation": "quotaoff", "filesystem": "/dev/sdb1"}),
        Turn(user_input="why did that report an error", tool="quota", operation="repquota", args={"operation": "repquota", "filesystem": "/dev/sdb1"}),
    )),
    V3(id="quota-v3-0010", tool="quota", kind="question", turns=(
        Turn(user_input="show jdoe's quota on /home", tool="quota", operation="quota_user", args={"operation": "quota_user", "username": "jdoe"}),
        Turn(user_input="what happens once that soft limit is crossed but not the hard one", answer="They can keep writing past the soft limit for a grace period, usually seven days by default, after which the system enforces it like a hard limit and blocks further writes. Crossing the hard limit itself fails writes immediately, no grace period."),
    )),
    V3(id="quota-v3-0011", tool="quota", kind="question", turns=(
        Turn(user_input="run quotacheck on /home", tool="quota", operation="quotacheck", args={"operation": "quotacheck", "filesystem": "/home"}),
        Turn(user_input="does that interrupt users currently writing files there", answer="quotacheck needs a fairly quiet filesystem to get accurate counts, so it's best run with quota enforcement off and minimal active writes; it won't corrupt data but concurrent writes during the scan can produce inaccurate usage numbers until the next check."),
    )),
    V3(id="quota-v3-0012", tool="quota", kind="question", turns=(
        Turn(user_input="set jdoe's hard block limit to 0 on /home", tool="quota", operation="edquota", args={"operation": "edquota", "username": "jdoe", "filesystem": "/home", "hard_blocks": 0}),
        Turn(user_input="does that mean they have no quota now", answer="A limit of 0 for that field means unlimited for that specific dimension, block usage in this case, not that all limits are gone. Their inode limits and soft block limit, if still set, would still apply."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("quota", SCENARIOS_V3)
