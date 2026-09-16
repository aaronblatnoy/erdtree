"""finetune/scenarios_v3/nginx.py — corpus v3 multi-turn scenarios for 'nginx'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="nginx-v3-0001", tool="nginx", kind="followup", turns=(
        Turn(user_input="test the nginx config for syntax errors", tool="nginx", operation="configtest", args={"operation": "configtest"}),
        Turn(user_input="looks clean, go ahead and reload it", tool="nginx", operation="reload", args={"operation": "reload"}),
    )),
    V3(id="nginx-v3-0002", tool="nginx", kind="followup", turns=(
        Turn(user_input="check the status of nginx.service", tool="nginx", operation="status", args={"operation": "status"}),
        Turn(user_input="it's stopped, start it up", tool="nginx", operation="start", args={"operation": "start"}),
    )),
    V3(id="nginx-v3-0003", tool="nginx", kind="followup", turns=(
        Turn(user_input="run configtest against /etc/nginx/sites-available/api.conf", tool="nginx", operation="configtest", args={"operation": "configtest", "config": "/etc/nginx/sites-available/api.conf"}),
        Turn(user_input="no, instead test the default config", tool="nginx", operation="configtest", args={"operation": "configtest"}),
    )),
    V3(id="nginx-v3-0004", tool="nginx", kind="followup", turns=(
        Turn(user_input="restart the nginx unit", tool="nginx", operation="restart", args={"operation": "restart"}),
        Turn(user_input="confirm it came back up", tool="nginx", operation="status", args={"operation": "status"}),
    )),
    V3(id="nginx-v3-0005", tool="nginx", kind="followup", turns=(
        Turn(user_input="stop nginx for maintenance", tool="nginx", operation="stop", args={"operation": "stop"}),
        Turn(user_input="undo that, start it back up", tool="nginx", operation="start", args={"operation": "start"}),
    )),
    V3(id="nginx-v3-0006", tool="nginx", kind="followup", turns=(
        Turn(user_input="reload nginx to pick up the new config", tool="nginx", operation="reload", args={"operation": "reload"}),
        Turn(user_input="pull the recent journal for it in case something didn't apply", tool="services", operation="logs", args={"operation": "logs", "unit": "nginx.service", "lines": 100}),
    )),
    V3(id="nginx-v3-0007", tool="nginx", kind="followup", turns=(
        Turn(user_input="validate the nginx config", tool="nginx", operation="configtest", args={"operation": "configtest"}),
        Turn(user_input="ok do it, restart the service", tool="nginx", operation="restart", args={"operation": "restart"}),
        Turn(user_input="and now confirm the status", tool="nginx", operation="status", args={"operation": "status"}),
    )),
    V3(id="nginx-v3-0008", tool="nginx", kind="followup", turns=(
        Turn(user_input="test /etc/nginx/conf.d/staging.conf for errors", tool="nginx", operation="configtest", args={"operation": "configtest", "config": "/etc/nginx/conf.d/staging.conf"}),
        Turn(user_input="that passed, now reload the running config", tool="nginx", operation="reload", args={"operation": "reload"}),
    )),
    V3(id="nginx-v3-0009", tool="nginx", kind="followup", turns=(
        Turn(user_input="is nginx.service currently running", tool="nginx", operation="status", args={"operation": "status"}),
        Turn(user_input="test the config before I touch anything", tool="nginx", operation="configtest", args={"operation": "configtest"}),
        Turn(user_input="it's fine, reload it", tool="nginx", operation="reload", args={"operation": "reload"}),
    )),
    V3(id="nginx-v3-0010", tool="nginx", kind="question", turns=(
        Turn(user_input="run nginx configtest", tool="nginx", operation="configtest", args={"operation": "configtest"}),
        Turn(user_input="it says syntax is ok but test failed, what does that mean", answer="The syntax is valid but nginx couldn't fully load the config, usually because it references something missing: an upstream file, an SSL cert path, or a port already bound by another process. Check the specific error line above the summary for the actual failing directive."),
    )),
    V3(id="nginx-v3-0011", tool="nginx", kind="question", turns=(
        Turn(user_input="reload nginx", tool="nginx", operation="reload", args={"operation": "reload"}),
        Turn(user_input="why would I reload instead of restart", answer="Reload sends SIGHUP to the master process, which spawns new workers with the updated config while old workers finish serving their current connections, so nothing drops. Restart tears the whole service down and back up, which briefly closes every open connection."),
    )),
    V3(id="nginx-v3-0012", tool="nginx", kind="question", turns=(
        Turn(user_input="check nginx.service status", tool="nginx", operation="status", args={"operation": "status"}),
        Turn(user_input="it shows failed with a bind error, what's the fix", answer="A bind error on start almost always means another process already holds the port nginx wants, commonly 80 or 443. Find the owner with a port lookup and either stop it or change nginx's listen directive, then restart."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("nginx", SCENARIOS_V3)
