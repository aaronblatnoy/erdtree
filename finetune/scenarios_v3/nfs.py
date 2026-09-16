"""finetune/scenarios_v3/nfs.py — corpus v3 multi-turn scenarios for 'nfs'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="nfs-v3-0001", tool="nfs", kind="followup", turns=(
        Turn(user_input="show what exports the server at 10.0.0.5 advertises", tool="nfs", operation="showmount", args={"operation": "showmount", "server": "10.0.0.5"}),
        Turn(user_input="now the same for 10.0.0.6", tool="nfs", operation="showmount", args={"operation": "showmount", "server": "10.0.0.6"}),
    )),
    V3(id="nfs-v3-0002", tool="nfs", kind="followup", turns=(
        Turn(user_input="mount /srv/nfs/data from 10.0.0.5 onto /mnt/data", tool="nfs", operation="mount_client", args={"operation": "mount_client", "server": "10.0.0.5", "path": "/srv/nfs/data", "mountpoint": "/mnt/data"}),
        Turn(user_input="and then check disk usage on that mount", tool="disk", operation="usage", args={"operation": "usage", "path": "/mnt/data"}),
    )),
    V3(id="nfs-v3-0003", tool="nfs", kind="followup", turns=(
        Turn(user_input="what's in /etc/exports right now", tool="nfs", operation="exports_view", args={"operation": "exports_view"}),
        Turn(user_input="ok, re-read it and publish everything configured there", tool="nfs", operation="exportfs_add", args={"operation": "exportfs_add"}),
    )),
    V3(id="nfs-v3-0004", tool="nfs", kind="followup", turns=(
        Turn(user_input="revoke the export 192.168.1.0/24:/srv/nfs/backups", tool="nfs", operation="exportfs_unexport", args={"operation": "exportfs_unexport", "target": "192.168.1.0/24:/srv/nfs/backups"}),
        Turn(user_input="no wait, undo that, the finance team still needs it", tool="nfs", operation="exportfs_add", args={"operation": "exportfs_add"}),
    )),
    V3(id="nfs-v3-0005", tool="nfs", kind="followup", turns=(
        Turn(user_input="list the exports currently active on this host", tool="nfs", operation="exportfs_list", args={"operation": "exportfs_list"}),
        Turn(user_input="also stop the nfs-server service, we're taking it down for maintenance", tool="nfs", operation="nfs_stop", args={"operation": "nfs_stop"}),
    )),
    V3(id="nfs-v3-0006", tool="nfs", kind="followup", turns=(
        Turn(user_input="start the nfs-server unit", tool="nfs", operation="nfs_start", args={"operation": "nfs_start"}),
        Turn(user_input="do it, then confirm the exports are live again", tool="nfs", operation="exportfs_list", args={"operation": "exportfs_list"}),
        Turn(user_input="also check the unit's own status", tool="services", operation="status", args={"operation": "status", "unit": "nfs-server"}),
    )),
    V3(id="nfs-v3-0007", tool="nfs", kind="followup", turns=(
        Turn(user_input="mount /export/media from build-nas onto /mnt/media", tool="nfs", operation="mount_client", args={"operation": "mount_client", "server": "build-nas", "path": "/export/media", "mountpoint": "/mnt/media"}),
        Turn(user_input="instead use /export/media2 as the path", tool="nfs", operation="mount_client", args={"operation": "mount_client", "server": "build-nas", "path": "/export/media2", "mountpoint": "/mnt/media"}),
        Turn(user_input="ok now show the disk usage on the mountpoint", tool="disk", operation="usage", args={"operation": "usage", "path": "/mnt/media"}),
    )),
    V3(id="nfs-v3-0008", tool="nfs", kind="followup", turns=(
        Turn(user_input="show the exports advertised by qa-storage", tool="nfs", operation="showmount", args={"operation": "showmount", "server": "qa-storage"}),
        Turn(user_input="mount its /srv/nfs/qa export onto /mnt/qa", tool="nfs", operation="mount_client", args={"operation": "mount_client", "server": "qa-storage", "path": "/srv/nfs/qa", "mountpoint": "/mnt/qa"}),
    )),
    V3(id="nfs-v3-0009", tool="nfs", kind="followup", turns=(
        Turn(user_input="unexport 10.20.0.0/16:/srv/nfs/logs", tool="nfs", operation="exportfs_unexport", args={"operation": "exportfs_unexport", "target": "10.20.0.0/16:/srv/nfs/logs"}),
        Turn(user_input="why did that fail", tool="nfs", operation="exportfs_list", args={"operation": "exportfs_list"}),
    )),
    V3(id="nfs-v3-0010", tool="nfs", kind="question", turns=(
        Turn(user_input="show the exports the server at 172.16.0.9 is advertising", tool="nfs", operation="showmount", args={"operation": "showmount", "server": "172.16.0.9"}),
        Turn(user_input="what's the difference between what that shows and what's in /etc/exports on the client side", answer="showmount queries the remote server's live export table over the network, so it reflects what's currently published there, not this host's own configuration. /etc/exports only matters on a machine acting as the NFS server itself."),
    )),
    V3(id="nfs-v3-0011", tool="nfs", kind="question", turns=(
        Turn(user_input="unexport 192.168.2.0/24:/srv/nfs/shared", tool="nfs", operation="exportfs_unexport", args={"operation": "exportfs_unexport", "target": "192.168.2.0/24:/srv/nfs/shared"}),
        Turn(user_input="what happens to clients that already have it mounted", answer="Existing mounts don't unmount automatically; clients keep their stale handle and will start seeing stale file handle errors or hangs on the next access. You need to notify them to unmount before revoking, or expect support tickets."),
    )),
    V3(id="nfs-v3-0012", tool="nfs", kind="question", turns=(
        Turn(user_input="mount /srv/nfs/build from ci-server onto /mnt/build", tool="nfs", operation="mount_client", args={"operation": "mount_client", "server": "ci-server", "path": "/srv/nfs/build", "mountpoint": "/mnt/build"}),
        Turn(user_input="is that mount going to survive a reboot", answer="No, mount_client only creates the live mount for this session. To make it persistent you'd need an entry in /etc/fstab pointing at that server and export path, which this operation doesn't write."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("nfs", SCENARIOS_V3)
