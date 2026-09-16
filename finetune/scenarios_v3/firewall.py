"""finetune/scenarios_v3/firewall.py — corpus v3 multi-turn scenarios for 'firewall'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="firewall-v3-0001", tool="firewall", kind="followup", turns=(
        Turn(user_input="open port 8080/tcp in the public zone", tool="firewall", operation="add_port", args={"operation": "add_port", "port": "8080/tcp", "zone": "public"}),
        Turn(user_input="and 53/udp too", tool="firewall", operation="add_port", args={"operation": "add_port", "port": "53/udp", "zone": "public"}),
    )),
    V3(id="firewall-v3-0002", tool="firewall", kind="followup", turns=(
        Turn(user_input="allow the http service through the firewall", tool="firewall", operation="add_service", args={"operation": "add_service", "service": "http"}),
        Turn(user_input="now reload so it takes effect", tool="firewall", operation="reload", args={"operation": "reload"}),
    )),
    V3(id="firewall-v3-0003", tool="firewall", kind="followup", turns=(
        Turn(user_input="check whether ssh is allowed in the internal zone", tool="firewall", operation="query", args={"operation": "query", "service": "ssh", "zone": "internal"}),
        Turn(user_input="yes, add it since it's not there", tool="firewall", operation="add_service", args={"operation": "add_service", "service": "ssh", "zone": "internal"}),
    )),
    V3(id="firewall-v3-0004", tool="firewall", kind="followup", turns=(
        Turn(user_input="remove the ftp service from the public zone", tool="firewall", operation="remove_service", args={"operation": "remove_service", "service": "ftp", "zone": "public"}),
        Turn(user_input="undo that, we still need it", tool="firewall", operation="add_service", args={"operation": "add_service", "service": "ftp", "zone": "public"}),
    )),
    V3(id="firewall-v3-0005", tool="firewall", kind="followup", turns=(
        Turn(user_input="close port 9000/tcp on the dmz zone", tool="firewall", operation="remove_port", args={"operation": "remove_port", "port": "9000/tcp", "zone": "dmz"}),
        Turn(user_input="now confirm that in the dmz zone settings", tool="firewall", operation="list", args={"operation": "list", "zone": "dmz"}),
    )),
    V3(id="firewall-v3-0006", tool="firewall", kind="followup", turns=(
        Turn(user_input="what firewall zones are defined on this box", tool="firewall", operation="get_zones", args={"operation": "get_zones"}),
        Turn(user_input="show the other zone's settings, trusted this time", tool="firewall", operation="list", args={"operation": "list", "zone": "trusted"}),
        Turn(user_input="open 5432/tcp there too", tool="firewall", operation="add_port", args={"operation": "add_port", "port": "5432/tcp", "zone": "trusted"}),
    )),
    V3(id="firewall-v3-0007", tool="firewall", kind="followup", turns=(
        Turn(user_input="set the default zone to internal", tool="firewall", operation="set_default_zone", args={"operation": "set_default_zone", "zone": "internal"}),
        Turn(user_input="ok do it, then allow https there as well", tool="firewall", operation="add_service", args={"operation": "add_service", "service": "https", "zone": "internal"}),
        Turn(user_input="and now reload the ruleset", tool="firewall", operation="reload", args={"operation": "reload"}),
    )),
    V3(id="firewall-v3-0008", tool="firewall", kind="followup", turns=(
        Turn(user_input="open port 3306/tcp for the database server on the public zone", tool="firewall", operation="add_port", args={"operation": "add_port", "port": "3306/tcp", "zone": "public"}),
        Turn(user_input="also check the process list to see what's listening", tool="processes", operation="list", args={"operation": "list"}),
    )),
    V3(id="firewall-v3-0009", tool="firewall", kind="followup", turns=(
        Turn(user_input="list all settings for the public zone", tool="firewall", operation="list", args={"operation": "list", "zone": "public"}),
        Turn(user_input="also show what the active zone looks like by default", tool="firewall", operation="list", args={"operation": "list"}),
    )),
    V3(id="firewall-v3-0010", tool="firewall", kind="question", turns=(
        Turn(user_input="query whether http is allowed in the public zone", tool="firewall", operation="query", args={"operation": "query", "service": "http", "zone": "public"}),
        Turn(user_input="so does that mean web traffic gets through right now", answer="Only if the query came back yes and the zone is the one bound to the active interface. A permanent rule that hasn't been reloaded, or a service allowed in the wrong zone, won't actually pass live traffic."),
    )),
    V3(id="firewall-v3-0011", tool="firewall", kind="question", turns=(
        Turn(user_input="turn on panic mode", tool="firewall", operation="panic_on", args={"operation": "panic_on"}),
        Turn(user_input="what does that actually do to traffic on this host", answer="Panic mode drops every packet in and out, including established connections like this ssh session — it's an emergency kill switch, not a rule change. Turn it off as soon as the incident is contained or you'll lock yourself out too."),
    )),
    V3(id="firewall-v3-0012", tool="firewall", kind="question", turns=(
        Turn(user_input="reload the permanent firewall ruleset", tool="firewall", operation="reload", args={"operation": "reload"}),
        Turn(user_input="does that drop any connections that are already open", answer="No, a reload re-applies the permanent configuration without restarting the service, so existing tracked connections stay up. Only rules added with a runtime-only change (not yet made permanent) would be lost."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("firewall", SCENARIOS_V3)
