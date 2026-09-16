"""finetune/scenarios_v3/sssd.py — corpus v3 multi-turn scenarios for 'sssd'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="sssd-v3-0001", tool="sssd", kind="followup", turns=(
        Turn(user_input="check whether sssd is running on this host", tool="sssd", operation="status",
             args={"operation": "status"}),
        Turn(user_input="also look up user jsmith's identity", tool="sssd", operation="id_lookup",
             args={"operation": "id_lookup", "user": "jsmith"}),
    )),
    V3(id="sssd-v3-0002", tool="sssd", kind="followup", turns=(
        Turn(user_input="look up identity info for user mbailey", tool="sssd", operation="id_lookup",
             args={"operation": "id_lookup", "user": "mbailey"}),
        Turn(user_input="and the same lookup for the group domain-admins", tool="sssd", operation="id_lookup",
             args={"operation": "id_lookup", "user": "domain-admins"}),
    )),
    V3(id="sssd-v3-0003", tool="sssd", kind="followup", turns=(
        Turn(user_input="user rpatel says their group membership looks stale, look them up", tool="sssd", operation="id_lookup",
             args={"operation": "id_lookup", "user": "rpatel"}),
        Turn(user_input="ok, flush the sssd cache", tool="sssd", operation="cache_flush",
             args={"operation": "cache_flush"}),
    )),
    V3(id="sssd-v3-0004", tool="sssd", kind="followup", turns=(
        Turn(user_input="list the realms currently enrolled or discoverable on this box", tool="sssd", operation="realm_list",
             args={"operation": "realm_list"}),
        Turn(user_input="yes, join us to corp.example.com", tool="sssd", operation="realm_join",
             args={"operation": "realm_join", "domain": "corp.example.com"}),
    )),
    V3(id="sssd-v3-0005", tool="sssd", kind="followup", turns=(
        Turn(user_input="enroll this host into ad.internal.net", tool="sssd", operation="realm_join",
             args={"operation": "realm_join", "domain": "ad.internal.net"}),
        Turn(user_input="no, use the other domain instead, ad2.internal.net", tool="sssd", operation="realm_join",
             args={"operation": "realm_join", "domain": "ad2.internal.net"}),
    )),
    V3(id="sssd-v3-0006", tool="sssd", kind="followup", turns=(
        Turn(user_input="leave the corp.example.com domain, we're decommissioning this box", tool="sssd", operation="realm_leave",
             args={"operation": "realm_leave", "domain": "corp.example.com"}),
        Turn(user_input="yes, go ahead", tool="sssd", operation="realm_leave",
             args={"operation": "realm_leave", "domain": "corp.example.com"}),
    )),
    V3(id="sssd-v3-0007", tool="sssd", kind="followup", turns=(
        Turn(user_input="flush the identity cache, logins are returning stale UIDs", tool="sssd", operation="cache_flush",
             args={"operation": "cache_flush"}),
        Turn(user_input="also look up user ecarter to confirm it's fresh", tool="sssd", operation="id_lookup",
             args={"operation": "id_lookup", "user": "ecarter"}),
    )),
    V3(id="sssd-v3-0008", tool="sssd", kind="followup", turns=(
        Turn(user_input="show sssd daemon status", tool="sssd", operation="status",
             args={"operation": "status"}),
        Turn(user_input="it's down, what happened, pull the recent journal entries for it", tool="logs", operation="tail",
             args={"operation": "tail", "unit": "sssd.service", "lines": 100}),
    )),
    V3(id="sssd-v3-0009", tool="sssd", kind="followup", turns=(
        Turn(user_input="list enrolled realms on this server", tool="sssd", operation="realm_list",
             args={"operation": "realm_list"}),
        Turn(user_input="also leave corp.example.com, it's the wrong domain now", tool="sssd", operation="realm_leave",
             args={"operation": "realm_leave", "domain": "corp.example.com"}),
        Turn(user_input="and then join it to newcorp.example.com instead", tool="sssd", operation="realm_join",
             args={"operation": "realm_join", "domain": "newcorp.example.com"}),
    )),
    V3(id="sssd-v3-0010", tool="sssd", kind="question", turns=(
        Turn(user_input="look up user twalsh through sssd", tool="sssd", operation="id_lookup",
             args={"operation": "id_lookup", "user": "twalsh"}),
        Turn(user_input="what does it mean that the UID it returned doesn't match what's in /etc/passwd",
             answer="sssd is resolving the identity from the domain directory, not the local passwd file, so a mismatch usually means the local account is stale or was created separately from the domain-joined one. Flushing the cache or checking for a duplicate local account will usually clear it up."),
    )),
    V3(id="sssd-v3-0011", tool="sssd", kind="question", turns=(
        Turn(user_input="flush all sssd caches", tool="sssd", operation="cache_flush",
             args={"operation": "cache_flush"}),
        Turn(user_input="what happened to active logins after that",
             answer="cache_flush just clears cached identity and lookup data with sss_cache -E, it doesn't kill active sessions. The next lookup for any user just re-fetches fresh data from the domain controller instead of using the stale cached copy."),
    )),
    V3(id="sssd-v3-0012", tool="sssd", kind="question", turns=(
        Turn(user_input="leave the domain oldcorp.example.com", tool="sssd", operation="realm_leave",
             args={"operation": "realm_leave", "domain": "oldcorp.example.com"}),
        Turn(user_input="why did that get flagged as destructive",
             answer="Leaving the realm removes this host's domain trust relationship, so every domain account immediately loses the ability to log in here until it's rejoined. Only local accounts still work in the meantime, which is why it needs explicit confirmation."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("sssd", SCENARIOS_V3)
