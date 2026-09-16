"""finetune/scenarios_v3/services.py — corpus v3 multi-turn scenarios for 'services'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="services-v3-0001", tool="services", kind="followup", turns=(
        Turn(user_input="check status of nginx.service", tool="services", operation="status",
             args={"operation": "status", "unit": "nginx.service"}),
        Turn(user_input="now the same for haproxy.service", tool="services", operation="status",
             args={"operation": "status", "unit": "haproxy.service"}),
    )),
    V3(id="services-v3-0002", tool="services", kind="followup", turns=(
        Turn(user_input="stop the sidekiq.service unit", tool="services", operation="stop",
             args={"operation": "stop", "unit": "sidekiq.service"}),
        Turn(user_input="ok, now restart it", tool="services", operation="restart",
             args={"operation": "restart", "unit": "sidekiq.service"}),
    )),
    V3(id="services-v3-0003", tool="services", kind="followup", turns=(
        Turn(user_input="status of redis.service please", tool="services", operation="status",
             args={"operation": "status", "unit": "redis.service"}),
        Turn(user_input="yes, do it, start it up", tool="services", operation="start",
             args={"operation": "start", "unit": "redis.service"}),
    )),
    V3(id="services-v3-0004", tool="services", kind="followup", turns=(
        Turn(user_input="disable telnet.socket from starting at boot", tool="services", operation="disable",
             args={"operation": "disable", "unit": "telnet.socket"}),
        Turn(user_input="undo that, re-enable it", tool="services", operation="enable",
             args={"operation": "enable", "unit": "telnet.socket"}),
    )),
    V3(id="services-v3-0005", tool="services", kind="followup", turns=(
        Turn(user_input="restart postgresql.service", tool="services", operation="restart",
             args={"operation": "restart", "unit": "postgresql.service"}),
        Turn(user_input="that is still erroring, pull the journal logs for it", tool="services", operation="logs",
             args={"operation": "logs", "unit": "postgresql.service", "lines": 100}),
    )),
    V3(id="services-v3-0006", tool="services", kind="followup", turns=(
        Turn(user_input="enable crond at boot", tool="services", operation="enable",
             args={"operation": "enable", "unit": "crond.service"}),
        Turn(user_input="and then start it now too", tool="services", operation="start",
             args={"operation": "start", "unit": "crond.service"}),
        Turn(user_input="confirm it's running with a status check", tool="services", operation="status",
             args={"operation": "status", "unit": "crond.service"}),
    )),
    V3(id="services-v3-0007", tool="services", kind="followup", turns=(
        Turn(user_input="mask rpcbind.service so it can't be started", tool="services", operation="mask",
             args={"operation": "mask", "unit": "rpcbind.service"}),
        Turn(user_input="no, use the other approach instead, just disable it", tool="services", operation="disable",
             args={"operation": "disable", "unit": "rpcbind.service"}),
        Turn(user_input="and stop it if it's currently running", tool="services", operation="stop",
             args={"operation": "stop", "unit": "rpcbind.service"}),
    )),
    V3(id="services-v3-0008", tool="services", kind="followup", turns=(
        Turn(user_input="pull 50 lines of logs for docker.service", tool="services", operation="logs",
             args={"operation": "logs", "unit": "docker.service", "lines": 50}),
        Turn(user_input="that's not enough, give me 300 instead", tool="services", operation="logs",
             args={"operation": "logs", "unit": "docker.service", "lines": 300}),
    )),
    V3(id="services-v3-0009", tool="services", kind="followup", turns=(
        Turn(user_input="status of sshd.service", tool="services", operation="status",
             args={"operation": "status", "unit": "sshd.service"}),
        Turn(user_input="it's fine, check named.service too since dns lookups failed earlier", tool="dns", operation="named_status",
             args={"operation": "named_status"}),
    )),
    V3(id="services-v3-0010", tool="services", kind="question", turns=(
        Turn(user_input="check status of nfs-server.service", tool="services", operation="status",
             args={"operation": "status", "unit": "nfs-server.service"}),
        Turn(user_input="what does that 'activating (auto-restart)' state mean",
             answer="It means the unit crashed or exited and systemd is waiting out its configured restart delay before trying again. If it keeps cycling through that state, pull its journal logs to find why it keeps dying rather than just restarting it manually."),
    )),
    V3(id="services-v3-0011", tool="services", kind="question", turns=(
        Turn(user_input="restart haproxy.service", tool="services", operation="restart",
             args={"operation": "restart", "unit": "haproxy.service"}),
        Turn(user_input="is a restart the same as stop then start here",
             answer="Functionally yes for haproxy — systemctl restart stops the unit and starts it again in one command, briefly dropping any in-flight connections. If zero-downtime reload matters, `systemctl reload` is the better choice when the unit supports it."),
    )),
    V3(id="services-v3-0012", tool="services", kind="question", turns=(
        Turn(user_input="get logs for elasticsearch.service, 200 lines", tool="services", operation="logs",
             args={"operation": "logs", "unit": "elasticsearch.service", "lines": 200}),
        Turn(user_input="what does that repeated 'JVM heap space' error mean",
             answer="It means the Java process ran out of allocated heap memory, usually from indexing or query load exceeding the configured -Xmx setting. Increasing the heap size or reducing shard/query load are the usual fixes, not just restarting the service."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("services", SCENARIOS_V3)
