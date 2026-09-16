"""finetune/scenarios_v3/lvm.py — corpus v3 multi-turn scenarios for 'lvm'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="lvm-v3-0001", tool="lvm", kind="followup", turns=(
        Turn(user_input="show attributes for physical volume /dev/sdb1", tool="lvm", operation="pvdisplay",
             args={"operation": "pvdisplay", "pv": "/dev/sdb1"}),
        Turn(user_input="and the same for /dev/sdc1", tool="lvm", operation="pvdisplay",
             args={"operation": "pvdisplay", "pv": "/dev/sdc1"}),
    )),
    V3(id="lvm-v3-0002", tool="lvm", kind="followup", turns=(
        Turn(user_input="initialise /dev/sdb1 as a physical volume", tool="lvm", operation="pvcreate",
             args={"operation": "pvcreate", "pv": "/dev/sdb1"}),
        Turn(user_input="now use it to create a volume group called vg_data", tool="lvm", operation="vgcreate",
             args={"operation": "vgcreate", "vg": "vg_data", "pv": "/dev/sdb1"}),
    )),
    V3(id="lvm-v3-0003", tool="lvm", kind="followup", turns=(
        Turn(user_input="create a 10G logical volume named data_lv in vg_data", tool="lvm", operation="lvcreate",
             args={"operation": "lvcreate", "lv_name": "data_lv", "vg": "vg_data", "size": "10G"}),
        Turn(user_input="that's not enough, extend it to 25G", tool="lvm", operation="lvextend",
             args={"operation": "lvextend", "lv": "vg_data/data_lv", "size": "25G"}),
    )),
    V3(id="lvm-v3-0004", tool="lvm", kind="followup", turns=(
        Turn(user_input="display the vg_data volume group", tool="lvm", operation="vgdisplay",
             args={"operation": "vgdisplay", "vg": "vg_data"}),
        Turn(user_input="it is low on space, add /dev/sdd1 to it", tool="lvm", operation="vgextend",
             args={"operation": "vgextend", "vg": "vg_data", "pv": "/dev/sdd1"}),
    )),
    V3(id="lvm-v3-0005", tool="lvm", kind="followup", turns=(
        Turn(user_input="list logical volumes in vg_data", tool="lvm", operation="lvdisplay",
             args={"operation": "lvdisplay", "lv": "vg_data"}),
        Turn(user_input="remove the archive_lv one, it's no longer needed", tool="lvm", operation="lvremove",
             args={"operation": "lvremove", "lv": "vg_data/archive_lv"}),
    )),
    V3(id="lvm-v3-0006", tool="lvm", kind="followup", turns=(
        Turn(user_input="shrink lv_home in vg_data down to 15G", tool="lvm", operation="lvreduce",
             args={"operation": "lvreduce", "lv": "vg_data/lv_home", "size": "15G"}),
        Turn(user_input="undo that, extend it back up to 20G instead", tool="lvm", operation="lvextend",
             args={"operation": "lvextend", "lv": "vg_data/lv_home", "size": "20G"}),
    )),
    V3(id="lvm-v3-0007", tool="lvm", kind="followup", turns=(
        Turn(user_input="pull up the physical volumes on this host", tool="lvm", operation="pvdisplay",
             args={"operation": "pvdisplay"}),
        Turn(user_input="/dev/sde1 looks unused, wipe it as a physical volume", tool="lvm", operation="pvremove",
             args={"operation": "pvremove", "pv": "/dev/sde1"}),
    )),
    V3(id="lvm-v3-0008", tool="lvm", kind="followup", turns=(
        Turn(user_input="create a volume group db_vg from /dev/sdf1", tool="lvm", operation="vgcreate",
             args={"operation": "vgcreate", "vg": "db_vg", "pv": "/dev/sdf1"}),
        Turn(user_input="now use it to carve out a 50G logical volume named pg_lv", tool="lvm", operation="lvcreate",
             args={"operation": "lvcreate", "lv_name": "pg_lv", "vg": "db_vg", "size": "50G"}),
        Turn(user_input="confirm it shows up by listing logical volumes in db_vg", tool="lvm", operation="lvdisplay",
             args={"operation": "lvdisplay", "lv": "db_vg"}),
    )),
    V3(id="lvm-v3-0009", tool="lvm", kind="followup", turns=(
        Turn(user_input="the app team says db_vg is done with, remove the volume group", tool="lvm", operation="vgremove",
             args={"operation": "vgremove", "vg": "db_vg"}),
        Turn(user_input="yes, confirm and go ahead, remove /dev/sdf1 as a physical volume too", tool="lvm", operation="pvremove",
             args={"operation": "pvremove", "pv": "/dev/sdf1"}),
        Turn(user_input="also confirm nothing else still references it, list physical volumes now", tool="lvm", operation="pvdisplay",
             args={"operation": "pvdisplay"}),
    )),
    V3(id="lvm-v3-0010", tool="lvm", kind="question", turns=(
        Turn(user_input="shrink test_lv in vg_data down to 5G", tool="lvm", operation="lvreduce",
             args={"operation": "lvreduce", "lv": "vg_data/test_lv", "size": "5G"}),
        Turn(user_input="what's the actual danger in that",
             answer="Shrinking a logical volume only resizes the block device — it does not touch the filesystem on top of it. If the filesystem wasn't shrunk to fit first, any data living past the new boundary is now unreachable or corrupted, so this should always be preceded by a filesystem-level shrink."),
    )),
    V3(id="lvm-v3-0011", tool="lvm", kind="question", turns=(
        Turn(user_input="show me the volume groups on this host", tool="lvm", operation="vgdisplay",
             args={"operation": "vgdisplay"}),
        Turn(user_input="in that output, what does the free PE count tell me",
             answer="Free PE (physical extents) is the unallocated space left in the volume group, expressed in extent units rather than bytes. It's the ceiling on how much you can hand out to lvcreate or lvextend before you need to add another physical volume with vgextend."),
    )),
    V3(id="lvm-v3-0012", tool="lvm", kind="question", turns=(
        Turn(user_input="remove logical volume old_lv from vg_data", tool="lvm", operation="lvremove",
             args={"operation": "lvremove", "lv": "vg_data/old_lv"}),
        Turn(user_input="is that data recoverable now, any way to get it back",
             answer="No — lvremove destroys the logical volume's extent mapping immediately and there is no undo built into lvm itself. Recovery, if possible at all, would require a filesystem-level or block-level recovery tool run before the freed extents get reused, and it is not guaranteed to work."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("lvm", SCENARIOS_V3)
