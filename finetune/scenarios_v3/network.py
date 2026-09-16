"""finetune/scenarios_v3/network.py — corpus v3 multi-turn scenarios for 'network'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="network-v3-0001", tool="network", kind="followup", turns=(
        Turn(user_input="show all the IP addresses on this box", tool="network", operation="show",
             args={"operation": "show"}),
        Turn(user_input="also list what wifi SSID it's on", tool="network", operation="wifi",
             args={"operation": "wifi"}),
    )),
    V3(id="network-v3-0002", tool="network", kind="followup", turns=(
        Turn(user_input="bring up eth0", tool="network", operation="bring_up",
             args={"operation": "bring_up", "interface": "eth0"}),
        Turn(user_input="now the same for eth1", tool="network", operation="bring_up",
             args={"operation": "bring_up", "interface": "eth1"}),
    )),
    V3(id="network-v3-0003", tool="network", kind="followup", turns=(
        Turn(user_input="give me a one-line summary of every interface", tool="network", operation="status",
             args={"operation": "status"}),
        Turn(user_input="ok, bring down ens5, it's the failed bond member", tool="network", operation="bring_down",
             args={"operation": "bring_down", "interface": "ens5"}),
    )),
    V3(id="network-v3-0004", tool="network", kind="followup", turns=(
        Turn(user_input="set the IP on ens192 to 10.0.4.20/24", tool="network", operation="set_ip",
             args={"operation": "set_ip", "interface": "ens192", "address": "10.0.4.20/24"}),
        Turn(user_input="no, use the other address instead, 10.0.4.21/24", tool="network", operation="set_ip",
             args={"operation": "set_ip", "interface": "ens192", "address": "10.0.4.21/24"}),
    )),
    V3(id="network-v3-0005", tool="network", kind="followup", turns=(
        Turn(user_input="list every network interface on the host", tool="network", operation="interfaces",
             args={"operation": "interfaces"}),
        Turn(user_input="also show the NetworkManager connection profiles", tool="network", operation="connections",
             args={"operation": "connections"}),
    )),
    V3(id="network-v3-0006", tool="network", kind="followup", turns=(
        Turn(user_input="bring the corp-vpn connection profile up", tool="network", operation="bring_up",
             args={"operation": "bring_up", "connection": "corp-vpn"}),
        Turn(user_input="yes, do it", tool="network", operation="bring_up",
             args={"operation": "bring_up", "connection": "corp-vpn"}),
    )),
    V3(id="network-v3-0007", tool="network", kind="followup", turns=(
        Turn(user_input="assign 172.16.9.5/24 to the office-lan connection profile", tool="network", operation="set_ip",
             args={"operation": "set_ip", "connection": "office-lan", "address": "172.16.9.5/24"}),
        Turn(user_input="now bring that connection up", tool="network", operation="bring_up",
             args={"operation": "bring_up", "connection": "office-lan"}),
    )),
    V3(id="network-v3-0008", tool="network", kind="followup", turns=(
        Turn(user_input="show all interface addresses and state", tool="network", operation="show",
             args={"operation": "show"}),
        Turn(user_input="also bring down bond0, we're replacing the NIC", tool="network", operation="bring_down",
             args={"operation": "bring_down", "interface": "bond0"}),
        Turn(user_input="and then bring up bond0-backup once it's cabled", tool="network", operation="bring_up",
             args={"operation": "bring_up", "interface": "bond0-backup"}),
    )),
    V3(id="network-v3-0009", tool="network", kind="followup", turns=(
        Turn(user_input="check the wireless SSID we're associated to", tool="network", operation="wifi",
             args={"operation": "wifi"}),
        Turn(user_input="what happened, pull the recent kernel and NetworkManager log lines to see if it's flapping", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "NetworkManager", "lines": 100}),
    )),
    V3(id="network-v3-0010", tool="network", kind="question", turns=(
        Turn(user_input="show a brief status line for every interface", tool="network", operation="status",
             args={"operation": "status"}),
        Turn(user_input="what does it mean that ens224 shows as UNMANAGED",
             answer="UNMANAGED means NetworkManager isn't controlling that interface at all — usually because it's listed in an ifcfg file with NM_CONTROLLED=no, or matched by a udev/NetworkManager exclusion rule. Its IP config has to be handled outside NetworkManager until that's changed."),
    )),
    V3(id="network-v3-0011", tool="network", kind="question", turns=(
        Turn(user_input="bring down interface eth2", tool="network", operation="bring_down",
             args={"operation": "bring_down", "interface": "eth2"}),
        Turn(user_input="why did that say the session might drop",
             answer="bring_down is flagged destructive because if eth2 happens to carry your current management connection, taking it down cuts that session immediately with no warning shown to you first. Always confirm which interface carries your active connection before running it on a live box."),
    )),
    V3(id="network-v3-0012", tool="network", kind="question", turns=(
        Turn(user_input="list the connection profiles NetworkManager knows about", tool="network", operation="connections",
             args={"operation": "connections"}),
        Turn(user_input="what does it mean that two profiles show the same interface name",
             answer="That's normal when you have multiple saved profiles targeting one device, like a DHCP profile and a static one for eth0 — only whichever is marked active is actually applied. Bringing the other one up will replace the current config on that interface."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("network", SCENARIOS_V3)
