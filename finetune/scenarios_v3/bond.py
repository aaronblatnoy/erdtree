"""finetune/scenarios_v3/bond.py — corpus v3 multi-turn scenarios for 'bond'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="bond-v3-0001", tool="bond", kind="followup", turns=(
        Turn(user_input="show me the bond0 connection details", tool="bond", operation="show", args={"operation": "show", "bond": "bond0"}),
        Turn(user_input="now the same for bond1", tool="bond", operation="show", args={"operation": "show", "bond": "bond1"}),
    )),
    V3(id="bond-v3-0002", tool="bond", kind="followup", turns=(
        Turn(user_input="create a bond called bond0 in active-backup mode", tool="bond", operation="add", args={"operation": "add", "bond": "bond0", "mode": "active-backup"}),
        Turn(user_input="and then set its ipv4 method to manual", tool="bond", operation="modify", args={"operation": "modify", "bond": "bond0", "property": "ipv4.method", "value": "manual"}),
    )),
    V3(id="bond-v3-0003", tool="bond", kind="followup", turns=(
        Turn(user_input="set bond0's miimon option to 100", tool="bond", operation="modify", args={"operation": "modify", "bond": "bond0", "property": "bond.options", "value": "miimon=100"}),
        Turn(user_input="yes go ahead and apply the same value to bond1", tool="bond", operation="modify", args={"operation": "modify", "bond": "bond1", "property": "bond.options", "value": "miimon=100"}),
    )),
    V3(id="bond-v3-0004", tool="bond", kind="followup", turns=(
        Turn(user_input="switch bond0's mode to 802.3ad", tool="bond", operation="modify", args={"operation": "modify", "bond": "bond0", "property": "bond.options", "value": "mode=802.3ad"}),
        Turn(user_input="undo that, go back to active-backup", tool="bond", operation="modify", args={"operation": "modify", "bond": "bond0", "property": "bond.options", "value": "mode=active-backup"}),
    )),
    V3(id="bond-v3-0005", tool="bond", kind="followup", turns=(
        Turn(user_input="delete the bond1 connection", tool="bond", operation="remove", args={"operation": "remove", "bond": "bond1"}),
        Turn(user_input="now confirm that with the interface list", tool="network", operation="interfaces", args={"operation": "interfaces"}),
    )),
    V3(id="bond-v3-0006", tool="bond", kind="followup", turns=(
        Turn(user_input="list every NetworkManager connection", tool="bond", operation="show", args={"operation": "show"}),
        Turn(user_input="instead create bond0 using balance-rr mode", tool="bond", operation="add", args={"operation": "add", "bond": "bond0", "mode": "balance-rr"}),
        Turn(user_input="and set its bond.options primary to eno1", tool="bond", operation="modify", args={"operation": "modify", "bond": "bond0", "property": "bond.options", "value": "primary=eno1"}),
    )),
    V3(id="bond-v3-0007", tool="bond", kind="followup", turns=(
        Turn(user_input="create bond2 with mode balance-alb for the storage NICs", tool="bond", operation="add", args={"operation": "add", "bond": "bond2", "mode": "balance-alb"}),
        Turn(user_input="do it for eno3 and eno4 as slaves too, set bond.options to that", tool="bond", operation="modify", args={"operation": "modify", "bond": "bond2", "property": "bond.options", "value": "slaves=eno3,eno4"}),
        Turn(user_input="ok now confirm the connection profiles show it", tool="network", operation="connections", args={"operation": "connections"}),
    )),
    V3(id="bond-v3-0008", tool="bond", kind="followup", turns=(
        Turn(user_input="remove the bond0 connection, it's being replaced", tool="bond", operation="remove", args={"operation": "remove", "bond": "bond0"}),
        Turn(user_input="no, use the other config instead — recreate it as bond0 in mode 802.3ad", tool="bond", operation="add", args={"operation": "add", "bond": "bond0", "mode": "802.3ad"}),
    )),
    V3(id="bond-v3-0009", tool="bond", kind="followup", turns=(
        Turn(user_input="pull up detail on bond0", tool="bond", operation="show", args={"operation": "show", "bond": "bond0"}),
        Turn(user_input="what happened to its active-backup priority setting", tool="bond", operation="show", args={"operation": "show", "bond": "bond0"}),
    )),
    V3(id="bond-v3-0010", tool="bond", kind="question", turns=(
        Turn(user_input="show detail for bond0", tool="bond", operation="show", args={"operation": "show", "bond": "bond0"}),
        Turn(user_input="what does that state field tell us", answer="It shows whether the bond is up and carrying traffic through its active slave. If the state reads down, none of the underlying NICs are link-active and the bond is passing no traffic even though the connection profile exists."),
    )),
    V3(id="bond-v3-0011", tool="bond", kind="question", turns=(
        Turn(user_input="remove the bond0 connection", tool="bond", operation="remove", args={"operation": "remove", "bond": "bond0"}),
        Turn(user_input="why did that drop my ssh session for a second", answer="Deleting bond0 tore down the aggregated link it was providing, so any traffic routed over it, including this ssh session, had to fail over or re-establish through another interface. That's expected for the active bond carrying remote access."),
    )),
    V3(id="bond-v3-0012", tool="bond", kind="question", turns=(
        Turn(user_input="add a bond named bond0 in 802.3ad mode", tool="bond", operation="add", args={"operation": "add", "bond": "bond0", "mode": "802.3ad"}),
        Turn(user_input="what do I still need before this actually works", answer="802.3ad requires LACP support on the connected switch port, plus at least one slave NIC attached to bond0 — creating the bond alone doesn't add member interfaces. Add slaves with a modify call before expecting failover or aggregated throughput."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("bond", SCENARIOS_V3)
