"""finetune/scenarios_v3/selinux.py — corpus v3 multi-turn scenarios for 'selinux'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="selinux-v3-0001", tool="selinux", kind="followup", turns=(
        Turn(user_input="check the current selinux boolean for httpd_can_network_connect", tool="selinux", operation="getsebool",
             args={"operation": "getsebool", "boolean": "httpd_can_network_connect"}),
        Turn(user_input="and the same for httpd_can_sendmail", tool="selinux", operation="getsebool",
             args={"operation": "getsebool", "boolean": "httpd_can_sendmail"}),
    )),
    V3(id="selinux-v3-0002", tool="selinux", kind="followup", turns=(
        Turn(user_input="show overall selinux status", tool="selinux", operation="sestatus",
             args={"operation": "sestatus"}),
        Turn(user_input="ok, now set enforcement mode to 1", tool="selinux", operation="setenforce",
             args={"operation": "setenforce", "mode": "1"}),
    )),
    V3(id="selinux-v3-0003", tool="selinux", kind="followup", turns=(
        Turn(user_input="turn on httpd_can_network_connect", tool="selinux", operation="setsebool",
             args={"operation": "setsebool", "boolean": "httpd_can_network_connect", "value": "on"}),
        Turn(user_input="yes go ahead, persist that across reboots too", tool="selinux", operation="setsebool",
             args={"operation": "setsebool", "boolean": "httpd_can_network_connect", "value": "on", "persist": True}),
    )),
    V3(id="selinux-v3-0004", tool="selinux", kind="followup", turns=(
        Turn(user_input="set enforcement mode to permissive", tool="selinux", operation="setenforce",
             args={"operation": "setenforce", "mode": "0"}),
        Turn(user_input="undo that, put it back to enforcing", tool="selinux", operation="setenforce",
             args={"operation": "setenforce", "mode": "1"}),
    )),
    V3(id="selinux-v3-0005", tool="selinux", kind="followup", turns=(
        Turn(user_input="add a file context mapping for httpd_sys_content_t on /srv/www", tool="selinux", operation="semanage_fcontext_add",
             args={"operation": "semanage_fcontext_add", "fcontext_type": "httpd_sys_content_t", "fcontext_spec": "/srv/www(/.*)?"}),
        Turn(user_input="no, use /srv/webapp instead of that path", tool="selinux", operation="semanage_fcontext_add",
             args={"operation": "semanage_fcontext_add", "fcontext_type": "httpd_sys_content_t", "fcontext_spec": "/srv/webapp(/.*)?"}),
    )),
    V3(id="selinux-v3-0006", tool="selinux", kind="followup", turns=(
        Turn(user_input="add a port mapping for http_port_t on tcp port 8443", tool="selinux", operation="semanage_port_add",
             args={"operation": "semanage_port_add", "port_type": "http_port_t", "protocol": "tcp", "port": "8443"}),
        Turn(user_input="now restart nginx so it picks that up", tool="services", operation="restart",
             args={"operation": "restart", "unit": "nginx.service"}),
    )),
    V3(id="selinux-v3-0007", tool="selinux", kind="followup", turns=(
        Turn(user_input="restore the default context on /srv/www recursively", tool="selinux", operation="restorecon",
             args={"operation": "restorecon", "path": "/srv/www"}),
        Turn(user_input="do the same for /var/www/html", tool="selinux", operation="restorecon",
             args={"operation": "restorecon", "path": "/var/www/html"}),
    )),
    V3(id="selinux-v3-0008", tool="selinux", kind="followup", turns=(
        Turn(user_input="list current file context mappings", tool="selinux", operation="semanage_fcontext_list",
             args={"operation": "semanage_fcontext_list"}),
        Turn(user_input="delete that mapping for /opt/legacyapp(/.*)?", tool="selinux", operation="semanage_fcontext_delete",
             args={"operation": "semanage_fcontext_delete", "fcontext_spec": "/opt/legacyapp(/.*)?"}),
        Turn(user_input="confirm it's gone, list them again", tool="selinux", operation="semanage_fcontext_list",
             args={"operation": "semanage_fcontext_list"}),
    )),
    V3(id="selinux-v3-0009", tool="selinux", kind="followup", turns=(
        Turn(user_input="add a seuser mapping for deploy with roles staff_r sysadm_r", tool="selinux", operation="semanage_user_add",
             args={"operation": "semanage_user_add", "seuser": "deploy", "roles": "staff_r sysadm_r"}),
        Turn(user_input="also change the file context type on /srv/deploy to that user's content type", tool="selinux", operation="chcon",
             args={"operation": "chcon", "context_type": "staff_t", "path": "/srv/deploy"}),
    )),
    V3(id="selinux-v3-0010", tool="selinux", kind="question", turns=(
        Turn(user_input="show sestatus", tool="selinux", operation="sestatus",
             args={"operation": "sestatus"}),
        Turn(user_input="in that output, what's the difference between policy type and mode", answer=(
            "The policy type, usually targeted, is which policy set is loaded and "
            "confines specific daemons; the current mode is whether violations are "
            "blocked (Enforcing) or just logged (Permissive) right now."
        )),
    )),
    V3(id="selinux-v3-0011", tool="selinux", kind="question", turns=(
        Turn(user_input="run audit2allow against the audit log", tool="selinux", operation="audit2allow",
             args={"operation": "audit2allow"}),
        Turn(user_input="should I actually apply those suggested rules it printed", answer=(
            "Not blindly. audit2allow turns denials into allow rules, but denials can "
            "also mean a real misconfiguration or attack attempt. Review each denial's "
            "context before loading a generated policy module."
        )),
    )),
    V3(id="selinux-v3-0012", tool="selinux", kind="question", turns=(
        Turn(user_input="set setenforce to 0", tool="selinux", operation="setenforce",
             args={"operation": "setenforce", "mode": "0"}),
        Turn(user_input="why did that get flagged as risky", answer=(
            "Dropping to permissive stops selinux from blocking anything, so any "
            "process, even a compromised one, runs unconfined until you set it back "
            "to enforcing. It's meant for short debugging windows, not to leave running."
        )),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("selinux", SCENARIOS_V3)
