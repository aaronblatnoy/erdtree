"""finetune/scenarios_v3/crypto_policies.py — corpus v3 multi-turn scenarios for 'crypto_policies'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="crypto_policies-v3-0001", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="what crypto policy is active on this box", tool="crypto_policies", operation="get", args={"operation": "get"}),
        Turn(user_input="ok, what other policies could I switch to", tool="crypto_policies", operation="list", args={"operation": "list"}),
    )),
    V3(id="crypto_policies-v3-0002", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="list the available crypto policy profiles", tool="crypto_policies", operation="list", args={"operation": "list"}),
        Turn(user_input="switch to the FUTURE one", tool="crypto_policies", operation="set", args={"operation": "set", "policy": "FUTURE"}),
    )),
    V3(id="crypto_policies-v3-0003", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="apply the LEGACY crypto policy, we have an old scanner that needs weaker ciphers", tool="crypto_policies", operation="set", args={"operation": "set", "policy": "LEGACY"}),
        Turn(user_input="undo that, put it back to DEFAULT", tool="crypto_policies", operation="set", args={"operation": "set", "policy": "DEFAULT"}),
    )),
    V3(id="crypto_policies-v3-0004", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="is FIPS mode on right now", tool="crypto_policies", operation="fips-status", args={"operation": "fips-status"}),
        Turn(user_input="go ahead and enable it then", tool="crypto_policies", operation="fips-enable", args={"operation": "fips-enable"}),
    )),
    V3(id="crypto_policies-v3-0005", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="check current FIPS status on db02", tool="crypto_policies", operation="fips-status", args={"operation": "fips-status"}),
        Turn(user_input="also show me the active crypto policy while we're at it", tool="crypto_policies", operation="get", args={"operation": "get"}),
    )),
    V3(id="crypto_policies-v3-0006", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="set the crypto policy to FIPS for the compliance audit", tool="crypto_policies", operation="set", args={"operation": "set", "policy": "FIPS"}),
        Turn(user_input="yes, and enable FIPS mode too since we're already here", tool="crypto_policies", operation="fips-enable", args={"operation": "fips-enable"}),
    )),
    V3(id="crypto_policies-v3-0007", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="what's the currently active crypto policy on the jump host", tool="crypto_policies", operation="get", args={"operation": "get"}),
        Turn(user_input="no, use FUTURE instead of whatever that was", tool="crypto_policies", operation="set", args={"operation": "set", "policy": "FUTURE"}),
    )),
    V3(id="crypto_policies-v3-0008", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="pull up the list of crypto policy names we can pick from", tool="crypto_policies", operation="list", args={"operation": "list"}),
        Turn(user_input="set it to LEGACY for now", tool="crypto_policies", operation="set", args={"operation": "set", "policy": "LEGACY"}),
        Turn(user_input="actually, do FIPS instead of that", tool="crypto_policies", operation="set", args={"operation": "set", "policy": "FIPS"}),
    )),
    V3(id="crypto_policies-v3-0009", tool="crypto_policies", kind="followup", turns=(
        Turn(user_input="enable FIPS mode on this host", tool="crypto_policies", operation="fips-enable", args={"operation": "fips-enable"}),
        Turn(user_input="now confirm the crypto policy switched over to FIPS", tool="crypto_policies", operation="get", args={"operation": "get"}),
        Turn(user_input="also double check FIPS status shows enabled too", tool="crypto_policies", operation="fips-status", args={"operation": "fips-status"}),
    )),
    V3(id="crypto_policies-v3-0010", tool="crypto_policies", kind="question", turns=(
        Turn(user_input="check whether FIPS mode is enabled on this server", tool="crypto_policies", operation="fips-status", args={"operation": "fips-status"}),
        Turn(user_input="what does that result actually mean for us", answer="It reports whether the kernel and OpenSSL are currently running in FIPS 140 mode.\nIf it shows disabled, the box is using the regular crypto stack, not the validated FIPS modules.\nA prior fips-enable call only takes effect after a reboot, so this can lag until then."),
    )),
    V3(id="crypto_policies-v3-0011", tool="crypto_policies", kind="question", turns=(
        Turn(user_input="apply the FIPS crypto policy on this host", tool="crypto_policies", operation="set", args={"operation": "set", "policy": "FIPS"}),
        Turn(user_input="after that, do I need anything else", answer="Setting the policy alone doesn't flip the kernel into FIPS mode.\nRun fips-enable and then reboot the host for FIPS 140 mode to actually take effect.\nUntil the reboot, fips-status will keep reporting the old state."),
    )),
    V3(id="crypto_policies-v3-0012", tool="crypto_policies", kind="question", turns=(
        Turn(user_input="show the current crypto policy on the load balancer", tool="crypto_policies", operation="get", args={"operation": "get"}),
        Turn(user_input="is that a safe setting for a public-facing box", answer="DEFAULT is a reasonable, broadly-compatible baseline for a public-facing host.\nFUTURE tightens things further by dropping weaker ciphers and shorter key sizes.\nOnly drop to LEGACY if you have a specific client that can't negotiate anything stronger."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("crypto_policies", SCENARIOS_V3)
