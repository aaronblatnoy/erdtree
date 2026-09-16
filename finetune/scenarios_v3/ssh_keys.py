"""finetune/scenarios_v3/ssh_keys.py — corpus v3 multi-turn scenarios for 'ssh_keys'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="ssh_keys-v3-0001", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="Generate a new ed25519 key pair at /home/deploy/.ssh/id_deploy.", tool="ssh_keys", operation="keygen",
             args={"operation": "keygen", "path": "/home/deploy/.ssh/id_deploy"}),
        Turn(user_input="Now the same for /home/backup/.ssh/id_backup.", tool="ssh_keys", operation="keygen",
             args={"operation": "keygen", "path": "/home/backup/.ssh/id_backup"}),
    )),
    V3(id="ssh_keys-v3-0002", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="List the authorized_keys entries for user deploy.", tool="ssh_keys", operation="authorized_keys_list",
             args={"operation": "authorized_keys_list", "user": "deploy"}),
        Turn(user_input="Add this key to it: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... ci@build-runner", tool="ssh_keys", operation="authorized_keys_add",
             args={"operation": "authorized_keys_add", "key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... ci@build-runner", "user": "deploy"}),
    )),
    V3(id="ssh_keys-v3-0003", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="Remove nyc-jump01 from root's known_hosts, it was decommissioned.", tool="ssh_keys", operation="known_hosts_remove",
             args={"operation": "known_hosts_remove", "hostname": "nyc-jump01"}),
        Turn(user_input="Yes, go ahead and confirm the known_hosts list is clean now.", tool="ssh_keys", operation="known_hosts_list",
             args={"operation": "known_hosts_list"}),
    )),
    V3(id="ssh_keys-v3-0004", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="Remove the key commented 'contractor@laptop' from root's authorized_keys.", tool="ssh_keys", operation="authorized_keys_remove",
             args={"operation": "authorized_keys_remove", "key_comment": "contractor@laptop"}),
        Turn(user_input="Undo that, the contractor's engagement got extended.", tool="ssh_keys", operation="authorized_keys_list",
             args={"operation": "authorized_keys_list"}),
    )),
    V3(id="ssh_keys-v3-0005", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="Generate an rsa key at /etc/ssh/svc_keys/id_rsync with 4096 bits.", tool="ssh_keys", operation="keygen",
             args={"operation": "keygen", "path": "/etc/ssh/svc_keys/id_rsync", "key_type": "rsa", "bits": 4096}),
        Turn(user_input="No, use ed25519 instead, we don't need rsa here.", tool="ssh_keys", operation="keygen",
             args={"operation": "keygen", "path": "/etc/ssh/svc_keys/id_rsync", "key_type": "ed25519"}),
    )),
    V3(id="ssh_keys-v3-0006", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="Dump the effective sshd runtime configuration.", tool="ssh_keys", operation="sshd_config_audit",
             args={"operation": "sshd_config_audit"}),
        Turn(user_input="Also check whether the sshd service actually shows as active.", tool="services", operation="status",
             args={"operation": "status", "unit": "sshd.service"}),
    )),
    V3(id="ssh_keys-v3-0007", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="List known_hosts entries for user jenkins.", tool="ssh_keys", operation="known_hosts_list",
             args={"operation": "known_hosts_list", "user": "jenkins"}),
        Turn(user_input="Remove staging-runner03 from that list, its host key rotated.", tool="ssh_keys", operation="known_hosts_remove",
             args={"operation": "known_hosts_remove", "hostname": "staging-runner03", "user": "jenkins"}),
    )),
    V3(id="ssh_keys-v3-0008", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="Add this key to deploy's authorized_keys: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... ops1@laptop", tool="ssh_keys", operation="authorized_keys_add",
             args={"operation": "authorized_keys_add", "key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... ops1@laptop", "user": "deploy"}),
        Turn(user_input="Add this one too, same user: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAJ... ops2@laptop", tool="ssh_keys", operation="authorized_keys_add",
             args={"operation": "authorized_keys_add", "key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAJ... ops2@laptop", "user": "deploy"}),
    )),
    V3(id="ssh_keys-v3-0009", tool="ssh_keys", kind="followup", turns=(
        Turn(user_input="Generate an ed25519 key pair at /home/ci/.ssh/id_pipeline with a passphrase.", tool="ssh_keys", operation="keygen",
             args={"operation": "keygen", "path": "/home/ci/.ssh/id_pipeline", "passphrase": "correct-horse-battery"}),
        Turn(user_input="Confirm the public key landed by listing authorized_keys for ci.", tool="ssh_keys", operation="authorized_keys_list",
             args={"operation": "authorized_keys_list", "user": "ci"}),
        Turn(user_input="Good, now go ahead and add that same public key to authorized_keys for the ci user.", tool="ssh_keys", operation="authorized_keys_add",
             args={"operation": "authorized_keys_add", "key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAK... ci@pipeline", "user": "ci"}),
    )),
    V3(id="ssh_keys-v3-0010", tool="ssh_keys", kind="question", turns=(
        Turn(user_input="Audit the effective sshd configuration.", tool="ssh_keys", operation="sshd_config_audit",
             args={"operation": "sshd_config_audit"}),
        Turn(user_input="what does that PasswordAuthentication line actually control",
             answer="It shows whether sshd will accept a plain password login at all, separate from key-based auth.\nIf it reads no, only key-based logins work and password attempts get rejected outright."),
    )),
    V3(id="ssh_keys-v3-0011", tool="ssh_keys", kind="question", turns=(
        Turn(user_input="Remove the key commented 'old-admin@2019laptop' from root's authorized_keys.", tool="ssh_keys", operation="authorized_keys_remove",
             args={"operation": "authorized_keys_remove", "key_comment": "old-admin@2019laptop"}),
        Turn(user_input="why is that flagged as a lockout risk",
             answer="Removing an authorized_keys entry can cut off the only working credential for that account if it's the last valid key.\nIt's worth confirming another key or console access still works before removing the last one."),
    )),
    V3(id="ssh_keys-v3-0012", tool="ssh_keys", kind="question", turns=(
        Turn(user_input="Generate an ed25519 key pair at /root/.ssh/id_admin.", tool="ssh_keys", operation="keygen",
             args={"operation": "keygen", "path": "/root/.ssh/id_admin"}),
        Turn(user_input="what's the difference between those two files that just got created",
             answer="id_admin is the private key and must stay secret and readable only by root.\nid_admin.pub is the matching public key, safe to distribute and what gets added to a remote authorized_keys file."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("ssh_keys", SCENARIOS_V3)
