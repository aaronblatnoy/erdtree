"""finetune/scenarios_v3/users.py — corpus v3 multi-turn scenarios for 'users'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="users-v3-0001", tool="users", kind="followup", turns=(
        Turn(user_input="show the record for the jdoe account", tool="users", operation="info",
             args={"operation": "info", "user": "jdoe"}),
        Turn(user_input="and the same for the deploy account", tool="users", operation="info",
             args={"operation": "info", "user": "deploy"}),
    )),
    V3(id="users-v3-0002", tool="users", kind="followup", turns=(
        Turn(user_input="create a new account named svc-backup", tool="users", operation="add",
             args={"operation": "add", "user": "svc-backup"}),
        Turn(user_input="ok, now set its shell to /sbin/nologin", tool="users", operation="set_shell",
             args={"operation": "set_shell", "user": "svc-backup", "shell": "/sbin/nologin"}),
    )),
    V3(id="users-v3-0003", tool="users", kind="followup", turns=(
        Turn(user_input="lock the account for tsmith", tool="users", operation="lock",
             args={"operation": "lock", "user": "tsmith"}),
        Turn(user_input="yes go ahead, delete it entirely instead", tool="users", operation="delete",
             args={"operation": "delete", "user": "tsmith"}),
    )),
    V3(id="users-v3-0004", tool="users", kind="followup", turns=(
        Turn(user_input="add mreyes to the wheel group", tool="users", operation="add_to_group",
             args={"operation": "add_to_group", "user": "mreyes", "group": "wheel"}),
        Turn(user_input="undo that, remove mreyes from the privileged group instead", tool="users", operation="remove_from_privgroup",
             args={"operation": "remove_from_privgroup", "user": "mreyes"}),
    )),
    V3(id="users-v3-0005", tool="users", kind="followup", turns=(
        Turn(user_input="set jdoe's shell to /bin/zsh", tool="users", operation="set_shell",
             args={"operation": "set_shell", "user": "jdoe", "shell": "/bin/zsh"}),
        Turn(user_input="no, use /bin/bash instead", tool="users", operation="set_shell",
             args={"operation": "set_shell", "user": "jdoe", "shell": "/bin/bash"}),
    )),
    V3(id="users-v3-0006", tool="users", kind="followup", turns=(
        Turn(user_input="create the account kwilson", tool="users", operation="add",
             args={"operation": "add", "user": "kwilson"}),
        Turn(user_input="check what shell that account ended up with in sssd", tool="sssd", operation="status",
             args={"operation": "status"}),
    )),
    V3(id="users-v3-0007", tool="users", kind="followup", turns=(
        Turn(user_input="list every local user account", tool="users", operation="list",
             args={"operation": "list"}),
        Turn(user_input="the third one, redis, show me its full record", tool="users", operation="info",
             args={"operation": "info", "user": "redis"}),
    )),
    V3(id="users-v3-0008", tool="users", kind="followup", turns=(
        Turn(user_input="add svc-monitor to the docker group", tool="users", operation="add_to_group",
             args={"operation": "add_to_group", "user": "svc-monitor", "group": "docker"}),
        Turn(user_input="also add it to the adm group", tool="users", operation="add_to_group",
             args={"operation": "add_to_group", "user": "svc-monitor", "group": "adm"}),
        Turn(user_input="now show its full info to confirm both landed", tool="users", operation="info",
             args={"operation": "info", "user": "svc-monitor"}),
    )),
    V3(id="users-v3-0009", tool="users", kind="followup", turns=(
        Turn(user_input="lock the account nramirez", tool="users", operation="lock",
             args={"operation": "lock", "user": "nramirez"}),
        Turn(user_input="do it", tool="users", operation="lock",
             args={"operation": "lock", "user": "nramirez"}),
    )),
    V3(id="users-v3-0010", tool="users", kind="question", turns=(
        Turn(user_input="show info for the account www-data", tool="users", operation="info",
             args={"operation": "info", "user": "www-data"}),
        Turn(user_input="what does that UID under 1000 tell me about this account", answer=(
            "A UID below 1000 marks it as a system account created for a service, not "
            "a person, which is why it typically has no password login and a shell "
            "like /sbin/nologin. Regular human accounts start at 1000 by convention."
        )),
    )),
    V3(id="users-v3-0011", tool="users", kind="question", turns=(
        Turn(user_input="delete the account for former employee bthompson", tool="users", operation="delete",
             args={"operation": "delete", "user": "bthompson"}),
        Turn(user_input="why did it warn about that being destructive", answer=(
            "Deleting an account removes their login and, depending on flags, their "
            "home directory and mail spool, which is not reversible from the account "
            "record alone. Confirm any files that must be preserved before it runs."
        )),
    )),
    V3(id="users-v3-0012", tool="users", kind="question", turns=(
        Turn(user_input="remove pkelly from the privileged group", tool="users", operation="remove_from_privgroup",
             args={"operation": "remove_from_privgroup", "user": "pkelly"}),
        Turn(user_input="does that also lock their account", answer=(
            "No, it only drops sudo access by pulling them out of the privileged "
            "group. The account itself stays active and they can still log in "
            "with whatever else they're authorized for; lock it separately if needed."
        )),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("users", SCENARIOS_V3)
