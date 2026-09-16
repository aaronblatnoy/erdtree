"""finetune/scenarios_v3/routing.py — corpus v3 multi-turn scenarios for 'routing'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="routing-v3-0001", tool="routing", kind="followup", turns=(
        Turn(user_input="show the main routing table", tool="routing", operation="route_show", args={"operation": "route_show"}),
        Turn(user_input="now show table 100 too", tool="routing", operation="route_show", args={"operation": "route_show", "table": "100"}),
    )),
    V3(id="routing-v3-0002", tool="routing", kind="followup", turns=(
        Turn(user_input="add a route for 192.168.50.0/24 via 10.0.0.1 on eth0", tool="routing", operation="route_add", args={"operation": "route_add", "dest": "192.168.50.0/24", "gateway": "10.0.0.1", "dev": "eth0"}),
        Turn(user_input="confirm it landed", tool="routing", operation="route_show", args={"operation": "route_show"}),
    )),
    V3(id="routing-v3-0003", tool="routing", kind="followup", turns=(
        Turn(user_input="list the ip policy rules", tool="routing", operation="policy_rule_show", args={"operation": "policy_rule_show"}),
        Turn(user_input="add one for source 10.1.0.0/24 pointing at table 200", tool="routing", operation="policy_rule_add", args={"operation": "policy_rule_add", "src": "10.1.0.0/24", "table": "200"}),
    )),
    V3(id="routing-v3-0004", tool="routing", kind="followup", turns=(
        Turn(user_input="delete the route to 172.16.5.0/24", tool="routing", operation="route_del", args={"operation": "route_del", "dest": "172.16.5.0/24"}),
        Turn(user_input="undo that, add it back with gateway 172.16.0.1", tool="routing", operation="route_add", args={"operation": "route_add", "dest": "172.16.5.0/24", "gateway": "172.16.0.1"}),
    )),
    V3(id="routing-v3-0005", tool="routing", kind="followup", turns=(
        Turn(user_input="add a static route for 10.20.0.0/16 via 10.0.0.254", tool="routing", operation="route_add", args={"operation": "route_add", "dest": "10.20.0.0/16", "gateway": "10.0.0.254"}),
        Turn(user_input="do the same for 10.21.0.0/16", tool="routing", operation="route_add", args={"operation": "route_add", "dest": "10.21.0.0/16", "gateway": "10.0.0.254"}),
        Turn(user_input="and one more, 10.22.0.0/16 with the same gateway", tool="routing", operation="route_add", args={"operation": "route_add", "dest": "10.22.0.0/16", "gateway": "10.0.0.254"}),
    )),
    V3(id="routing-v3-0006", tool="routing", kind="followup", turns=(
        Turn(user_input="show me the policy routing rules", tool="routing", operation="policy_rule_show", args={"operation": "policy_rule_show"}),
        Turn(user_input="also pull the current interface list", tool="network", operation="interfaces", args={"operation": "interfaces"}),
    )),
    V3(id="routing-v3-0007", tool="routing", kind="followup", turns=(
        Turn(user_input="add a route to default via 203.0.113.1 on eth1", tool="routing", operation="route_add", args={"operation": "route_add", "dest": "default", "gateway": "203.0.113.1", "dev": "eth1"}),
        Turn(user_input="go ahead and show the table to verify it took", tool="routing", operation="route_show", args={"operation": "route_show"}),
    )),
    V3(id="routing-v3-0008", tool="routing", kind="followup", turns=(
        Turn(user_input="delete the route to 192.168.99.0/24 via 10.0.0.5", tool="routing", operation="route_del", args={"operation": "route_del", "dest": "192.168.99.0/24", "gateway": "10.0.0.5"}),
        Turn(user_input="yes, confirmed, go ahead", tool="routing", operation="route_del", args={"operation": "route_del", "dest": "192.168.99.0/24", "gateway": "10.0.0.5"}),
    )),
    V3(id="routing-v3-0009", tool="routing", kind="followup", turns=(
        Turn(user_input="add a policy rule for destination 10.5.0.0/24 with priority 500 into table 50", tool="routing", operation="policy_rule_add", args={"operation": "policy_rule_add", "dest": "10.5.0.0/24", "priority": 500, "table": "50"}),
        Turn(user_input="go ahead and show all the rules so I can see it in order", tool="routing", operation="policy_rule_show", args={"operation": "policy_rule_show"}),
        Turn(user_input="also show table 50's routes", tool="routing", operation="route_show", args={"operation": "route_show", "table": "50"}),
    )),
    V3(id="routing-v3-0010", tool="routing", kind="question", turns=(
        Turn(user_input="add a route for 10.30.0.0/16 via 10.0.0.9 with metric 50", tool="routing", operation="route_add", args={"operation": "route_add", "dest": "10.30.0.0/16", "gateway": "10.0.0.9", "metric": 50}),
        Turn(user_input="in that, what does the metric number control", answer="Metric is the route's preference weight when multiple routes could match the same destination; the kernel picks the one with the lowest metric. It only matters when routes overlap, so a unique destination like this one won't be affected by other entries."),
    )),
    V3(id="routing-v3-0011", tool="routing", kind="question", turns=(
        Turn(user_input="show the routing table", tool="routing", operation="route_show", args={"operation": "route_show"}),
        Turn(user_input="why do those show two default routes", answer="Multiple default routes usually come from more than one interface handing out a gateway, commonly a wired and a wifi connection both active, or a VPN adding its own default. The kernel uses the one with the lower metric; check each route's metric to see which wins."),
    )),
    V3(id="routing-v3-0012", tool="routing", kind="question", turns=(
        Turn(user_input="list the policy rules", tool="routing", operation="policy_rule_show", args={"operation": "policy_rule_show"}),
        Turn(user_input="what's the point of the other rules beyond the default one", answer="Extra rules let you route traffic differently based on source address, destination, or mark rather than a single global table, which is how you'd send specific subnets or users out a different gateway or VPN. Rules are evaluated in priority order, lowest number first, until one matches."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("routing", SCENARIOS_V3)
