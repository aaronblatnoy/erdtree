"""finetune/scenarios_v3/dns.py — corpus v3 multi-turn scenarios for 'dns'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="dns-v3-0001", tool="dns", kind="followup", turns=(
        Turn(user_input="dig billing.corp-internal.net", tool="dns", operation="dig",
             args={"operation": "dig", "name": "billing.corp-internal.net"}),
        Turn(user_input="now the same lookup for reporting.corp-internal.net", tool="dns", operation="dig",
             args={"operation": "dig", "name": "reporting.corp-internal.net"}),
    )),
    V3(id="dns-v3-0002", tool="dns", kind="followup", turns=(
        Turn(user_input="look up MX records for orlandodermgroup.com with dig", tool="dns", operation="dig",
             args={"operation": "dig", "name": "orlandodermgroup.com", "record_type": "MX"}),
        Turn(user_input="and the TXT records too", tool="dns", operation="dig",
             args={"operation": "dig", "name": "orlandodermgroup.com", "record_type": "TXT"}),
    )),
    V3(id="dns-v3-0003", tool="dns", kind="followup", turns=(
        Turn(user_input="check named.service status", tool="dns", operation="named_status",
             args={"operation": "named_status"}),
        Turn(user_input="ok, now restart it", tool="services", operation="restart",
             args={"operation": "restart", "unit": "named.service"}),
    )),
    V3(id="dns-v3-0004", tool="dns", kind="followup", turns=(
        Turn(user_input="resolve vpn-gw03.internal using nslookup", tool="dns", operation="nslookup",
             args={"operation": "nslookup", "name": "vpn-gw03.internal"}),
        Turn(user_input="yes go ahead and flush the resolver cache too", tool="dns", operation="flush_caches",
             args={"operation": "flush_caches"}),
    )),
    V3(id="dns-v3-0005", tool="dns", kind="followup", turns=(
        Turn(user_input="host lookup for archive-node4.example.org", tool="dns", operation="host",
             args={"operation": "host", "name": "archive-node4.example.org"}),
        Turn(user_input="no, use the other config instead, query 8.8.8.8 directly", tool="dns", operation="host",
             args={"operation": "host", "name": "archive-node4.example.org", "server": "8.8.8.8"}),
    )),
    V3(id="dns-v3-0006", tool="dns", kind="followup", turns=(
        Turn(user_input="show me /etc/resolv.conf", tool="dns", operation="resolv_view",
             args={"operation": "resolv_view"}),
        Turn(user_input="those nameservers look stale, flush the cache", tool="dns", operation="flush_caches",
             args={"operation": "flush_caches"}),
        Turn(user_input="now redo the nslookup for payroll-db.internal", tool="dns", operation="nslookup",
             args={"operation": "nslookup", "name": "payroll-db.internal"}),
    )),
    V3(id="dns-v3-0007", tool="dns", kind="followup", turns=(
        Turn(user_input="dig AAAA for cdn-edge7.example.net", tool="dns", operation="dig",
             args={"operation": "dig", "name": "cdn-edge7.example.net", "record_type": "AAAA"}),
        Turn(user_input="undo that, just get the plain A record instead", tool="dns", operation="dig",
             args={"operation": "dig", "name": "cdn-edge7.example.net", "record_type": "A"}),
        Turn(user_input="and then check named.service is still up", tool="dns", operation="named_status",
             args={"operation": "named_status"}),
    )),
    V3(id="dns-v3-0008", tool="dns", kind="followup", turns=(
        Turn(user_input="nslookup ftp-old.example.com against 10.0.0.53", tool="dns", operation="nslookup",
             args={"operation": "nslookup", "name": "ftp-old.example.com", "server": "10.0.0.53"}),
        Turn(user_input="it failed, try that again against the public resolver 1.1.1.1", tool="dns", operation="nslookup",
             args={"operation": "nslookup", "name": "ftp-old.example.com", "server": "1.1.1.1"}),
    )),
    V3(id="dns-v3-0009", tool="dns", kind="followup", turns=(
        Turn(user_input="host ci-runner02.internal", tool="dns", operation="host",
             args={"operation": "host", "name": "ci-runner02.internal"}),
        Turn(user_input="that address seems wrong, check the logs for named.service", tool="services", operation="logs",
             args={"operation": "logs", "unit": "named.service", "lines": 100}),
    )),
    V3(id="dns-v3-0010", tool="dns", kind="question", turns=(
        Turn(user_input="dig CNAME for shop.legacyvendor.net", tool="dns", operation="dig",
             args={"operation": "dig", "name": "shop.legacyvendor.net", "record_type": "CNAME"}),
        Turn(user_input="what does that CNAME output tell us",
             answer="It shows shop.legacyvendor.net is an alias pointing at another hostname rather than a direct A record. Clients still need to resolve that target name to an IP, so DNS resolution takes an extra hop."),
    )),
    V3(id="dns-v3-0011", tool="dns", kind="question", turns=(
        Turn(user_input="check status of named.service", tool="dns", operation="named_status",
             args={"operation": "named_status"}),
        Turn(user_input="why did it show inactive (dead)",
             answer="Inactive (dead) means the unit is not currently running and was not left in a failed state — it was stopped cleanly or never started this boot. Start it with services.start if name resolution through this server is expected to work."),
    )),
    V3(id="dns-v3-0012", tool="dns", kind="question", turns=(
        Turn(user_input="nslookup partner-api.example.com", tool="dns", operation="nslookup",
             args={"operation": "nslookup", "name": "partner-api.example.com"}),
        Turn(user_input="what does that NXDOMAIN mean",
             answer="NXDOMAIN means the queried name does not exist in DNS at all, not just that this record type is missing. Check for a typo in the hostname or confirm the domain is actually registered and has an authoritative zone."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("dns", SCENARIOS_V3)
