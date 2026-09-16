"""finetune/scenarios_v3/httpd.py — corpus v3 multi-turn scenarios for 'httpd'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="httpd-v3-0001", tool="httpd", kind="followup", turns=(
        Turn(user_input="check the status of the apache service", tool="httpd", operation="status", args={"operation": "status"}),
        Turn(user_input="go ahead and restart it", tool="httpd", operation="restart", args={"operation": "restart"}),
    )),
    V3(id="httpd-v3-0002", tool="httpd", kind="followup", turns=(
        Turn(user_input="run a configtest on the apache config", tool="httpd", operation="configtest", args={"operation": "configtest"}),
        Turn(user_input="it passed, restart apache now", tool="httpd", operation="restart", args={"operation": "restart"}),
    )),
    V3(id="httpd-v3-0003", tool="httpd", kind="followup", turns=(
        Turn(user_input="stop apache on web03, we're taking it out of rotation", tool="httpd", operation="stop", args={"operation": "stop"}),
        Turn(user_input="undo that, start it back up", tool="httpd", operation="start", args={"operation": "start"}),
    )),
    V3(id="httpd-v3-0004", tool="httpd", kind="followup", turns=(
        Turn(user_input="pull the list of configured vhosts on this box", tool="httpd", operation="vhost_list", args={"operation": "vhost_list"}),
        Turn(user_input="now check apache's status too", tool="httpd", operation="status", args={"operation": "status"}),
    )),
    V3(id="httpd-v3-0005", tool="httpd", kind="followup", turns=(
        Turn(user_input="grab live metrics from mod_status", tool="httpd", operation="mod_status", args={"operation": "mod_status"}),
        Turn(user_input="also show me the apache service status", tool="httpd", operation="status", args={"operation": "status"}),
    )),
    V3(id="httpd-v3-0006", tool="httpd", kind="followup", turns=(
        Turn(user_input="validate the apache config syntax before we touch anything", tool="httpd", operation="configtest", args={"operation": "configtest"}),
        Turn(user_input="also check the vhost bindings now that config passed", tool="httpd", operation="vhost_list", args={"operation": "vhost_list"}),
    )),
    V3(id="httpd-v3-0007", tool="httpd", kind="followup", turns=(
        Turn(user_input="restart apache after the config change", tool="httpd", operation="restart", args={"operation": "restart"}),
        Turn(user_input="now pull the journal for that unit so I can see what happened", tool="logs", operation="query", args={"operation": "query", "unit": "httpd.service"}),
    )),
    V3(id="httpd-v3-0008", tool="httpd", kind="followup", turns=(
        Turn(user_input="apache seems slow, check mod_status", tool="httpd", operation="mod_status", args={"operation": "mod_status"}),
        Turn(user_input="what about the service status itself", tool="httpd", operation="status", args={"operation": "status"}),
        Turn(user_input="run a configtest too while we're diagnosing", tool="httpd", operation="configtest", args={"operation": "configtest"}),
    )),
    V3(id="httpd-v3-0009", tool="httpd", kind="followup", turns=(
        Turn(user_input="start httpd.service on the new staging host", tool="httpd", operation="start", args={"operation": "start"}),
        Turn(user_input="confirm it came up with a status check", tool="httpd", operation="status", args={"operation": "status"}),
        Turn(user_input="also list the vhosts so I can verify the port bindings", tool="httpd", operation="vhost_list", args={"operation": "vhost_list"}),
    )),
    V3(id="httpd-v3-0010", tool="httpd", kind="question", turns=(
        Turn(user_input="run apachectl configtest on this server", tool="httpd", operation="configtest", args={"operation": "configtest"}),
        Turn(user_input="what should I do if that reports a syntax error", answer="Fix the reported directive in the config file before touching the running service.\nA failed configtest means restarting apache right now would either fail to start or serve stale config.\nRe-run configtest after the edit and only restart once it comes back clean."),
    )),
    V3(id="httpd-v3-0011", tool="httpd", kind="question", turns=(
        Turn(user_input="pull the mod_status metrics for the apache instance on web01", tool="httpd", operation="mod_status", args={"operation": "mod_status"}),
        Turn(user_input="in that, what should I look for", answer="Look at the number of busy versus idle workers to see if the server is saturated.\nA high request rate with most workers busy points to a capacity or slow-backend problem.\nIf mod_status itself failed to respond, the status_module probably isn't loaded or enabled."),
    )),
    V3(id="httpd-v3-0012", tool="httpd", kind="question", turns=(
        Turn(user_input="list the virtual hosts on this apache instance", tool="httpd", operation="vhost_list", args={"operation": "vhost_list"}),
        Turn(user_input="in that output, why would a vhost be missing", answer="It usually means the vhost's config file isn't included by the main config or Include directive.\nA syntax error in that specific vhost file can also make apache skip it silently on reload.\nRun configtest and check the vhost's conf file is actually under the enabled sites directory."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("httpd", SCENARIOS_V3)
