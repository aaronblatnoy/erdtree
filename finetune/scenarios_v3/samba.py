"""finetune/scenarios_v3/samba.py — corpus v3 multi-turn scenarios for 'samba'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="samba-v3-0001", tool="samba", kind="followup", turns=(
        Turn(user_input="check smbd status", tool="samba", operation="smbd_status", args={"operation": "smbd_status"}),
        Turn(user_input="now check nmbd too", tool="samba", operation="nmbd_status", args={"operation": "nmbd_status"}),
    )),
    V3(id="samba-v3-0002", tool="samba", kind="followup", turns=(
        Turn(user_input="validate the smb.conf file", tool="samba", operation="testparm", args={"operation": "testparm"}),
        Turn(user_input="ok, now list the current usershares", tool="samba", operation="usershare_list", args={"operation": "usershare_list"}),
    )),
    V3(id="samba-v3-0003", tool="samba", kind="followup", turns=(
        Turn(user_input="add jdoe to the samba user database", tool="samba", operation="smbpasswd_add", args={"operation": "smbpasswd_add", "username": "jdoe", "password": "changeme123"}),
        Turn(user_input="and mrivera too", tool="samba", operation="smbpasswd_add", args={"operation": "smbpasswd_add", "username": "mrivera", "password": "changeme456"}),
    )),
    V3(id="samba-v3-0004", tool="samba", kind="followup", turns=(
        Turn(user_input="list the usershares on this box", tool="samba", operation="usershare_list", args={"operation": "usershare_list"}),
        Turn(user_input="add a new one called finance at /srv/samba/finance", tool="samba", operation="usershare_add", args={"operation": "usershare_add", "name": "finance", "path": "/srv/samba/finance", "comment": "finance team share", "acl": "Everyone:R"}),
    )),
    V3(id="samba-v3-0005", tool="samba", kind="followup", turns=(
        Turn(user_input="add asmith to the samba database with password temp789", tool="samba", operation="smbpasswd_add", args={"operation": "smbpasswd_add", "username": "asmith", "password": "temp789"}),
        Turn(user_input="undo that, remove him instead, he shouldn't have access", tool="samba", operation="smbpasswd_delete", args={"operation": "smbpasswd_delete", "username": "asmith"}),
    )),
    V3(id="samba-v3-0006", tool="samba", kind="followup", turns=(
        Turn(user_input="set up a usershare called engineering at /srv/samba/eng with read-only access", tool="samba", operation="usershare_add", args={"operation": "usershare_add", "name": "engineering", "path": "/srv/samba/eng", "acl": "Everyone:R"}),
        Turn(user_input="no, use full access instead of read-only", tool="samba", operation="usershare_add", args={"operation": "usershare_add", "name": "engineering", "path": "/srv/samba/eng", "acl": "Everyone:F"}),
    )),
    V3(id="samba-v3-0007", tool="samba", kind="followup", turns=(
        Turn(user_input="check nmbd daemon status", tool="samba", operation="nmbd_status", args={"operation": "nmbd_status"}),
        Turn(user_input="also check the smb.conf for errors while we're at it", tool="samba", operation="testparm", args={"operation": "testparm"}),
    )),
    V3(id="samba-v3-0008", tool="samba", kind="followup", turns=(
        Turn(user_input="is smbd running", tool="samba", operation="smbd_status", args={"operation": "smbd_status"}),
        Turn(user_input="also add tking to the samba database", tool="samba", operation="smbpasswd_add", args={"operation": "smbpasswd_add", "username": "tking"}),
        Turn(user_input="confirm the share list still looks right", tool="samba", operation="usershare_list", args={"operation": "usershare_list"}),
    )),
    V3(id="samba-v3-0009", tool="samba", kind="followup", turns=(
        Turn(user_input="validate smb.conf", tool="samba", operation="testparm", args={"operation": "testparm"}),
        Turn(user_input="that looks fine, add the marketing share at /srv/samba/marketing", tool="samba", operation="usershare_add", args={"operation": "usershare_add", "name": "marketing", "path": "/srv/samba/marketing", "comment": "marketing team files"}),
        Turn(user_input="list shares again to confirm it's there", tool="samba", operation="usershare_list", args={"operation": "usershare_list"}),
    )),
    V3(id="samba-v3-0010", tool="samba", kind="question", turns=(
        Turn(user_input="validate the smb.conf configuration", tool="samba", operation="testparm", args={"operation": "testparm"}),
        Turn(user_input="what does that syntax warning mean", answer="Testparm flags lines it can't parse into a valid share or global setting, usually a stray character or a misspelled directive. Fix the flagged line and rerun testparm before restarting smbd, since it will silently drop the broken section otherwise."),
    )),
    V3(id="samba-v3-0011", tool="samba", kind="question", turns=(
        Turn(user_input="check smbd status", tool="samba", operation="smbd_status", args={"operation": "smbd_status"}),
        Turn(user_input="why did that come back stopped", answer="smbd being stopped usually means either the service was never enabled after install, or it crashed on a bad smb.conf and failed to restart. Run testparm to rule out a config error, then check the unit's recent log lines for the actual failure reason."),
    )),
    V3(id="samba-v3-0012", tool="samba", kind="question", turns=(
        Turn(user_input="remove asmith from the samba user database", tool="samba", operation="smbpasswd_delete", args={"operation": "smbpasswd_delete", "username": "asmith"}),
        Turn(user_input="what happened to his access to the shares", answer="Deleting him from the samba database revokes his ability to authenticate to any share immediately, but it doesn't touch his underlying system account or any files he already owns. Existing connections he has open may stay live until they time out or the daemon is restarted."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("samba", SCENARIOS_V3)
