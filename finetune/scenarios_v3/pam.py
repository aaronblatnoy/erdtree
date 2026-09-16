"""finetune/scenarios_v3/pam.py — corpus v3 multi-turn scenarios for 'pam'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="pam-v3-0001", tool="pam", kind="followup", turns=(
        Turn(user_input="show the pam config for sshd", tool="pam", operation="pamd_audit", args={"operation": "pamd_audit", "service": "sshd"}),
        Turn(user_input="now the same for sudo", tool="pam", operation="pamd_audit", args={"operation": "pamd_audit", "service": "sudo"}),
    )),
    V3(id="pam-v3-0002", tool="pam", kind="followup", turns=(
        Turn(user_input="check faillock status for user jdoe", tool="pam", operation="faillock_status", args={"operation": "faillock_status", "user": "jdoe"}),
        Turn(user_input="and asmith too", tool="pam", operation="faillock_status", args={"operation": "faillock_status", "user": "asmith"}),
    )),
    V3(id="pam-v3-0003", tool="pam", kind="followup", turns=(
        Turn(user_input="pull up faillock counts for the whole box", tool="pam", operation="faillock_status", args={"operation": "faillock_status"}),
        Turn(user_input="that jdoe entry looks locked out, reset his tally", tool="pam", operation="faillock_reset", args={"operation": "faillock_reset", "user": "jdoe"}),
    )),
    V3(id="pam-v3-0004", tool="pam", kind="followup", turns=(
        Turn(user_input="reset the failure tally for mrivera", tool="pam", operation="faillock_reset", args={"operation": "faillock_reset", "user": "mrivera"}),
        Turn(user_input="yes, do it for all users while we're at it", tool="pam", operation="faillock_reset", args={"operation": "faillock_reset"}),
    )),
    V3(id="pam-v3-0005", tool="pam", kind="followup", turns=(
        Turn(user_input="enable the pwquality profile", tool="pam", operation="pam_auth_update", args={"operation": "pam_auth_update", "profile": "pwquality", "action": "enable"}),
        Turn(user_input="actually disable it instead, we need to test something first", tool="pam", operation="pam_auth_update", args={"operation": "pam_auth_update", "profile": "pwquality", "action": "disable"}),
    )),
    V3(id="pam-v3-0006", tool="pam", kind="followup", turns=(
        Turn(user_input="enable mkhomedir so new logins get a home directory", tool="pam", operation="pam_auth_update", args={"operation": "pam_auth_update", "profile": "mkhomedir", "action": "enable"}),
        Turn(user_input="also enable faillock while you're there", tool="pam", operation="pam_auth_update", args={"operation": "pam_auth_update", "profile": "faillock", "action": "enable"}),
    )),
    V3(id="pam-v3-0007", tool="pam", kind="followup", turns=(
        Turn(user_input="audit the login pam config", tool="pam", operation="pamd_audit", args={"operation": "pamd_audit", "service": "login"}),
        Turn(user_input="also check which accounts are locked right now", tool="pam", operation="faillock_status", args={"operation": "faillock_status"}),
    )),
    V3(id="pam-v3-0008", tool="pam", kind="followup", turns=(
        Turn(user_input="show faillock status for user tking", tool="pam", operation="faillock_status", args={"operation": "faillock_status", "user": "tking"}),
        Turn(user_input="ok reset that", tool="pam", operation="faillock_reset", args={"operation": "faillock_reset", "user": "tking"}),
        Turn(user_input="confirm it cleared", tool="pam", operation="faillock_status", args={"operation": "faillock_status", "user": "tking"}),
    )),
    V3(id="pam-v3-0009", tool="pam", kind="followup", turns=(
        Turn(user_input="show the sshd pam stack", tool="pam", operation="pamd_audit", args={"operation": "pamd_audit", "service": "sshd"}),
        Turn(user_input="also enable faillock there since it's missing", tool="pam", operation="pam_auth_update", args={"operation": "pam_auth_update", "profile": "faillock", "action": "enable"}),
        Turn(user_input="show me that updated config again", tool="pam", operation="pamd_audit", args={"operation": "pamd_audit", "service": "sshd"}),
    )),
    V3(id="pam-v3-0010", tool="pam", kind="question", turns=(
        Turn(user_input="check faillock status for user bpatel", tool="pam", operation="faillock_status", args={"operation": "faillock_status", "user": "bpatel"}),
        Turn(user_input="what does that tally mean for his ability to log in", answer="If bpatel's failure count has hit the deny threshold, faillock is actively blocking new authentication attempts until either the unlock timeout elapses or someone resets the tally. Below the threshold his logins still succeed, but each bad attempt moves him closer to a lockout."),
    )),
    V3(id="pam-v3-0011", tool="pam", kind="question", turns=(
        Turn(user_input="show the pam config for sudo", tool="pam", operation="pamd_audit", args={"operation": "pamd_audit", "service": "sudo"}),
        Turn(user_input="why did that config reference pam_faillock twice", answer="One entry runs on the way in to record and check the failure count (auth phase), the other runs after successful authentication to reset it (account phase). Both are needed — dropping either breaks either the lockout or the auto-reset behavior."),
    )),
    V3(id="pam-v3-0012", tool="pam", kind="question", turns=(
        Turn(user_input="enable the pwquality profile", tool="pam", operation="pam_auth_update", args={"operation": "pam_auth_update", "profile": "pwquality", "action": "enable"}),
        Turn(user_input="what should I check before trusting that change", answer="Open a second, separate login session before logging out of this one and confirm a normal user can still authenticate. A bad pwquality rule can reject every password including your own, so never verify from the only session you have open."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("pam", SCENARIOS_V3)
