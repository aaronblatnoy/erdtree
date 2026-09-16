"""finetune/scenarios_v3/nftables.py — corpus v3 multi-turn scenarios for 'nftables'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="nftables-v3-0001", tool="nftables", kind="followup", turns=(
        Turn(user_input="add a rule to the filter table's input chain allowing tcp dport 22 accept", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 22 accept"}),
        Turn(user_input="now add another rule there for tcp dport 2222 accept", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 2222 accept"}),
    )),
    V3(id="nftables-v3-0002", tool="nftables", kind="followup", turns=(
        Turn(user_input="add a rule in the filter table's input chain for tcp dport 443 accept", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 443 accept"}),
        Turn(user_input="now the same for dport 8443", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 8443 accept"}),
    )),
    V3(id="nftables-v3-0003", tool="nftables", kind="followup", turns=(
        Turn(user_input="add tcp dport 80 accept to filter/input", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 80 accept"}),
        Turn(user_input="and eth1's forward chain too, same rule", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "forward", "rule": "tcp dport 80 accept"}),
    )),
    V3(id="nftables-v3-0004", tool="nftables", kind="followup", turns=(
        Turn(user_input="list the ruleset for the filter table", tool="nftables", operation="list_ruleset", args={"operation": "list_ruleset"}),
        Turn(user_input="also delete handle 14 from filter/input", tool="nftables", operation="delete_rule", args={"operation": "delete_rule", "table": "filter", "chain": "input", "handle": "14"}),
    )),
    V3(id="nftables-v3-0005", tool="nftables", kind="followup", turns=(
        Turn(user_input="add a rule to ip6 filter/input for tcp dport 22 accept", tool="nftables", operation="add_rule", args={"operation": "add_rule", "family": "ip6", "table": "filter", "chain": "input", "rule": "tcp dport 22 accept"}),
        Turn(user_input="yes go ahead and delete the old handle 9 rule that duplicated it", tool="nftables", operation="delete_rule", args={"operation": "delete_rule", "family": "ip6", "table": "filter", "chain": "input", "handle": "9"}),
    )),
    V3(id="nftables-v3-0006", tool="nftables", kind="followup", turns=(
        Turn(user_input="add udp dport 53 accept to the filter table's input chain", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "udp dport 53 accept"}),
        Turn(user_input="no, use tcp dport 53 accept instead", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 53 accept"}),
    )),
    V3(id="nftables-v3-0007", tool="nftables", kind="followup", turns=(
        Turn(user_input="delete rule handle 22 from bridge filter/forward", tool="nftables", operation="delete_rule", args={"operation": "delete_rule", "family": "bridge", "table": "filter", "chain": "forward", "handle": "22"}),
        Turn(user_input="also check what is left in the ruleset", tool="nftables", operation="list_ruleset", args={"operation": "list_ruleset"}),
    )),
    V3(id="nftables-v3-0008", tool="nftables", kind="followup", turns=(
        Turn(user_input="add a rule to filter/input allowing tcp dport 3306 accept", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 3306 accept"}),
        Turn(user_input="also check the firewalld zone config since it sits above this", tool="firewall", operation="list", args={"operation": "list"}),
    )),
    V3(id="nftables-v3-0009", tool="nftables", kind="followup", turns=(
        Turn(user_input="add tcp dport 5432 accept to filter/input", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 5432 accept"}),
        Turn(user_input="add tcp dport 5433 accept there too", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 5433 accept"}),
        Turn(user_input="also dump the ruleset so I can confirm both landed", tool="nftables", operation="list_ruleset", args={"operation": "list_ruleset"}),
    )),
    V3(id="nftables-v3-0010", tool="nftables", kind="question", turns=(
        Turn(user_input="dump the nftables ruleset", tool="nftables", operation="list_ruleset", args={"operation": "list_ruleset"}),
        Turn(user_input="what is that output telling me", answer="Each block is a table (a namespace like filter or nat), containing chains (input/output/forward hooks), and each chain lists its rules with a trailing handle number. Use those handle numbers when you need to delete a specific rule later — nft won't let you delete by rule text alone."),
    )),
    V3(id="nftables-v3-0011", tool="nftables", kind="question", turns=(
        Turn(user_input="flush the entire nftables ruleset", tool="nftables", operation="flush_ruleset", args={"operation": "flush_ruleset"}),
        Turn(user_input="what did that just do to my firewall protection", answer="It wiped every table, chain, and rule — on a host with a default-drop policy that means all filtering is gone, and if remote access depended on an explicit accept rule you may have just locked yourself out. Re-add the baseline rules immediately or restore from a saved ruleset."),
    )),
    V3(id="nftables-v3-0012", tool="nftables", kind="question", turns=(
        Turn(user_input="add a rule to filter/input for tcp dport 22 accept", tool="nftables", operation="add_rule", args={"operation": "add_rule", "table": "filter", "chain": "input", "rule": "tcp dport 22 accept"}),
        Turn(user_input="does that rule apply immediately or after a reload", answer="It takes effect immediately — nft add rule edits the live in-kernel ruleset. It is not persisted to disk on its own, so it will not survive a reboot unless it's also saved into the nftables config file that gets loaded at startup."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("nftables", SCENARIOS_V3)
