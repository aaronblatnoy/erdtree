"""finetune/scenarios_v3/nmcli.py — corpus v3 multi-turn scenarios for 'nmcli'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="nmcli-v3-0001", tool="nmcli", kind="followup", turns=(
        Turn(user_input="show device status for all interfaces", tool="nmcli", operation="device_status",
             args={"operation": "device_status"}),
        Turn(user_input="also show me the full settings on the eth0 profile", tool="nmcli", operation="connection_show",
             args={"operation": "connection_show", "name": "eth0"}),
    )),
    V3(id="nmcli-v3-0002", tool="nmcli", kind="followup", turns=(
        Turn(user_input="bring up the office-vpn connection", tool="nmcli", operation="connection_up",
             args={"operation": "connection_up", "name": "office-vpn"}),
        Turn(user_input="and bring up backup-vpn too", tool="nmcli", operation="connection_up",
             args={"operation": "connection_up", "name": "backup-vpn"}),
    )),
    V3(id="nmcli-v3-0003", tool="nmcli", kind="followup", turns=(
        Turn(user_input="create a new ethernet connection named lan0 on interface enp3s0 with address 192.168.10.20/24",
             tool="nmcli", operation="connection_add",
             args={"operation": "connection_add", "type": "ethernet", "con_name": "lan0", "ifname": "enp3s0",
                   "ip4": "192.168.10.20/24", "gw4": "192.168.10.1"}),
        Turn(user_input="ok, now bring it up", tool="nmcli", operation="connection_up",
             args={"operation": "connection_up", "name": "lan0"}),
    )),
    V3(id="nmcli-v3-0004", tool="nmcli", kind="followup", turns=(
        Turn(user_input="set connection.autoconnect to no on the guest-wifi profile", tool="nmcli", operation="connection_modify",
             args={"operation": "connection_modify", "name": "guest-wifi", "property": "connection.autoconnect", "value": "no"}),
        Turn(user_input="undo that, set it back to yes", tool="nmcli", operation="connection_modify",
             args={"operation": "connection_modify", "name": "guest-wifi", "property": "connection.autoconnect", "value": "yes"}),
    )),
    V3(id="nmcli-v3-0005", tool="nmcli", kind="followup", turns=(
        Turn(user_input="scan for wifi networks on wlan0", tool="nmcli", operation="wifi_list",
             args={"operation": "wifi_list", "ifname": "wlan0"}),
        Turn(user_input="connect to the one named front-office-5g with password sunflower82", tool="nmcli", operation="wifi_connect",
             args={"operation": "wifi_connect", "ssid": "front-office-5g", "password": "sunflower82"}),
    )),
    V3(id="nmcli-v3-0006", tool="nmcli", kind="followup", turns=(
        Turn(user_input="take down the old-uplink connection, it's being replaced", tool="nmcli", operation="connection_down",
             args={"operation": "connection_down", "name": "old-uplink"}),
        Turn(user_input="go ahead and delete that profile entirely, we don't need it anymore", tool="nmcli", operation="connection_delete",
             args={"operation": "connection_delete", "name": "old-uplink"}),
    )),
    V3(id="nmcli-v3-0007", tool="nmcli", kind="followup", turns=(
        Turn(user_input="point the dns servers on eth0 at 1.1.1.1 and 1.0.0.1", tool="nmcli", operation="dns_configure",
             args={"operation": "dns_configure", "name": "eth0", "dns": "1.1.1.1 1.0.0.1"}),
        Turn(user_input="now bring that connection down and back up so it picks up the change", tool="nmcli", operation="connection_down",
             args={"operation": "connection_down", "name": "eth0"}),
        Turn(user_input="ok now bring it back up", tool="nmcli", operation="connection_up",
             args={"operation": "connection_up", "name": "eth0"}),
    )),
    V3(id="nmcli-v3-0008", tool="nmcli", kind="followup", turns=(
        Turn(user_input="show me the settings on the corp-vpn profile", tool="nmcli", operation="connection_show",
             args={"operation": "connection_show", "name": "corp-vpn"}),
        Turn(user_input="that address looks wrong, check the journal for NetworkManager to see what's happening", tool="rpm", operation="query_file",
             args={"operation": "query_file", "file": "/usr/sbin/NetworkManager"}),
    )),
    V3(id="nmcli-v3-0009", tool="nmcli", kind="followup", turns=(
        Turn(user_input="add a bond connection named bond0 on interface bond0 with address 10.5.0.4/24",
             tool="nmcli", operation="connection_add",
             args={"operation": "connection_add", "type": "bond", "con_name": "bond0", "ifname": "bond0",
                   "ip4": "10.5.0.4/24"}),
        Turn(user_input="actually set the gateway on it to 10.5.0.1 too", tool="nmcli", operation="connection_modify",
             args={"operation": "connection_modify", "name": "bond0", "property": "ipv4.gateway", "value": "10.5.0.1"}),
        Turn(user_input="yes, bring it up now", tool="nmcli", operation="connection_up",
             args={"operation": "connection_up", "name": "bond0"}),
    )),
    V3(id="nmcli-v3-0010", tool="nmcli", kind="question", turns=(
        Turn(user_input="show device status", tool="nmcli", operation="device_status", args={"operation": "device_status"}),
        Turn(user_input="what does that unmanaged state mean for the one interface",
             answer="NetworkManager isn't controlling that device at all, usually because of a udev rule, a config file excluding it, or it being a virtual interface owned by something else like a container runtime. Its IP config has to be handled outside nmcli until that's changed."),
    )),
    V3(id="nmcli-v3-0011", tool="nmcli", kind="question", turns=(
        Turn(user_input="delete the temp-test connection profile", tool="nmcli", operation="connection_delete",
             args={"operation": "connection_delete", "name": "temp-test"}),
        Turn(user_input="could that have knocked anything else offline",
             answer="Only if temp-test was the active profile on its interface, in which case that interface loses its IP config immediately. Other connections and interfaces are unaffected since profiles are deleted individually."),
    )),
    V3(id="nmcli-v3-0012", tool="nmcli", kind="question", turns=(
        Turn(user_input="list wifi networks visible on wlan1", tool="nmcli", operation="wifi_list",
             args={"operation": "wifi_list", "ifname": "wlan1"}),
        Turn(user_input="why does that show two entries with the same SSID at different signal strength",
             answer="That's two access points broadcasting the same network name, common in multi-AP setups doing roaming. nmcli lists each BSSID it hears separately even when the SSID is identical, and the client will normally pick the stronger one."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("nmcli", SCENARIOS_V3)
