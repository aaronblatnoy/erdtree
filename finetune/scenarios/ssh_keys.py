"""finetune/scenarios/ssh_keys.py — Scenario corpus for the 'ssh_keys' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  keygen                 WRITE       — generate a new SSH key pair
  authorized_keys_list   READ        — list entries in authorized_keys
  authorized_keys_add    WRITE       — append a public key to authorized_keys
  authorized_keys_remove DESTRUCTIVE — remove a key from authorized_keys (lockout risk)
  known_hosts_list       READ        — list entries in known_hosts
  known_hosts_remove     WRITE       — remove a host entry from known_hosts
  sshd_config_audit      READ        — dump effective sshd configuration

Coverage targets
----------------
  >= 40 entries total across all 7 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach the
  explicit-confirm gate for lockout-risk operations.

INV-schema-sync:  permission_class for each entry is derived from the LIVE
  registry via finetune.coreimports, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass — field names and order are EXACT for Phase-13 JOIN.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Scenario:
    id: str
    tool: str
    operation: str
    permission_class: OpClass
    complexity: Literal["single", "multi", "diagnostic"]
    user_input: str
    notes: str


# ---------------------------------------------------------------------------
# Live permission-class lookup — INV-schema-sync
# ---------------------------------------------------------------------------

def _pc(op: str) -> OpClass:
    """Return the live permission class for an ssh_keys operation."""
    return registry.get("ssh_keys").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # keygen  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="ssh_keys-keygen-0001",
        tool="ssh_keys",
        operation="keygen",
        permission_class=_pc("keygen"),
        complexity="single",
        user_input="generate a new ed25519 SSH key for the deploy user at /home/deploy/.ssh/id_ed25519",
        notes="Basic key generation for a service account.",
    ),
    Scenario(
        id="ssh_keys-keygen-0002",
        tool="ssh_keys",
        operation="keygen",
        permission_class=_pc("keygen"),
        complexity="single",
        user_input="create a 4096-bit RSA key pair at /root/.ssh/id_rsa for automated backups",
        notes="RSA key for backup automation; higher bit count for legacy compatibility.",
    ),
    Scenario(
        id="ssh_keys-keygen-0003",
        tool="ssh_keys",
        operation="keygen",
        permission_class=_pc("keygen"),
        complexity="single",
        user_input="generate an SSH key for the jenkins user at /home/jenkins/.ssh/jenkins_ci_key",
        notes="CI/CD service account key generation.",
    ),
    Scenario(
        id="ssh_keys-keygen-0004",
        tool="ssh_keys",
        operation="keygen",
        permission_class=_pc("keygen"),
        complexity="multi",
        user_input="generate an ed25519 key at /home/ansible/.ssh/id_ed25519 and then add the public key to the authorized_keys of the target server",
        notes="Multi-step: key generation followed by authorized_keys distribution.",
    ),
    Scenario(
        id="ssh_keys-keygen-0005",
        tool="ssh_keys",
        operation="keygen",
        permission_class=_pc("keygen"),
        complexity="diagnostic",
        user_input="the CI pipeline can't authenticate to the build server — generate a fresh key pair for the ci-runner user at /home/ci-runner/.ssh/id_ed25519",
        notes="Diagnostic-triggered WRITE: rotate compromised or expired key.",
    ),
    Scenario(
        id="ssh_keys-keygen-0006",
        tool="ssh_keys",
        operation="keygen",
        permission_class=_pc("keygen"),
        complexity="single",
        user_input="create an ecdsa key for the monitoring user at /home/monitor/.ssh/id_ecdsa",
        notes="ECDSA key for a monitoring service account.",
    ),
    Scenario(
        id="ssh_keys-keygen-0007",
        tool="ssh_keys",
        operation="keygen",
        permission_class=_pc("keygen"),
        complexity="multi",
        user_input="generate a new RSA key at /home/admin/.ssh/id_rsa and show me the fingerprint afterwards",
        notes="Multi-step: generate key then list to verify fingerprint.",
    ),

    # =========================================================================
    # authorized_keys_list  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="ssh_keys-authorized_keys_list-0001",
        tool="ssh_keys",
        operation="authorized_keys_list",
        permission_class=_pc("authorized_keys_list"),
        complexity="single",
        user_input="show me what keys are in root's authorized_keys",
        notes="Basic listing of root's authorized keys.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_list-0002",
        tool="ssh_keys",
        operation="authorized_keys_list",
        permission_class=_pc("authorized_keys_list"),
        complexity="single",
        user_input="list all authorized SSH keys for the deploy user",
        notes="Service account authorized key audit.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_list-0003",
        tool="ssh_keys",
        operation="authorized_keys_list",
        permission_class=_pc("authorized_keys_list"),
        complexity="single",
        user_input="what public keys are allowed to log in as the admin user?",
        notes="Access review for the admin account.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_list-0004",
        tool="ssh_keys",
        operation="authorized_keys_list",
        permission_class=_pc("authorized_keys_list"),
        complexity="diagnostic",
        user_input="someone can't SSH into the server as the 'appuser' — show me their authorized_keys to check if the right key is there",
        notes="Diagnostic: authorized_keys inspection to troubleshoot login failure.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_list-0005",
        tool="ssh_keys",
        operation="authorized_keys_list",
        permission_class=_pc("authorized_keys_list"),
        complexity="multi",
        user_input="list the authorized keys for the jenkins user and check if there are any expired or test keys that should be removed",
        notes="Multi-step: list then review for stale entries.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_list-0006",
        tool="ssh_keys",
        operation="authorized_keys_list",
        permission_class=_pc("authorized_keys_list"),
        complexity="diagnostic",
        user_input="security audit requires listing all keys that can log in as root",
        notes="Compliance: privileged account key enumeration.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_list-0007",
        tool="ssh_keys",
        operation="authorized_keys_list",
        permission_class=_pc("authorized_keys_list"),
        complexity="single",
        user_input="show the contents of the ansible user's authorized_keys file",
        notes="Automation account key review.",
    ),

    # =========================================================================
    # authorized_keys_add  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="ssh_keys-authorized_keys_add-0001",
        tool="ssh_keys",
        operation="authorized_keys_add",
        permission_class=_pc("authorized_keys_add"),
        complexity="single",
        user_input="add the developer's public key to the deploy user's authorized_keys so they can deploy from their workstation",
        notes="WRITE: grant SSH access for a developer to a service account.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_add-0002",
        tool="ssh_keys",
        operation="authorized_keys_add",
        permission_class=_pc("authorized_keys_add"),
        complexity="single",
        user_input="add the CI server's public key to root's authorized_keys for automated deployments",
        notes="WRITE: grant CI/CD system SSH access to root.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_add-0003",
        tool="ssh_keys",
        operation="authorized_keys_add",
        permission_class=_pc("authorized_keys_add"),
        complexity="single",
        user_input="allow the new sysadmin to log in as the admin user by adding their key",
        notes="WRITE: onboarding a new administrator.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_add-0004",
        tool="ssh_keys",
        operation="authorized_keys_add",
        permission_class=_pc("authorized_keys_add"),
        complexity="multi",
        user_input="add the backup server's key to the backup user's authorized_keys and then verify it was added correctly",
        notes="Multi-step: add key then list to confirm.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_add-0005",
        tool="ssh_keys",
        operation="authorized_keys_add",
        permission_class=_pc("authorized_keys_add"),
        complexity="diagnostic",
        user_input="the monitoring agent can't connect — add its SSH key to the monitor user's authorized_keys",
        notes="Diagnostic-triggered WRITE: fix SSH access for a broken monitoring agent.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_add-0006",
        tool="ssh_keys",
        operation="authorized_keys_add",
        permission_class=_pc("authorized_keys_add"),
        complexity="single",
        user_input="add the ops team's shared key to the appuser account",
        notes="WRITE: shared ops key for service account access.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_add-0007",
        tool="ssh_keys",
        operation="authorized_keys_add",
        permission_class=_pc("authorized_keys_add"),
        complexity="multi",
        user_input="add the new bastion host's key to root's authorized_keys and then show the full authorized_keys file",
        notes="Multi-step: add bastion key then audit full contents.",
    ),

    # =========================================================================
    # authorized_keys_remove  (DESTRUCTIVE) — 7 entries
    # =========================================================================

    Scenario(
        id="ssh_keys-authorized_keys_remove-0001",
        tool="ssh_keys",
        operation="authorized_keys_remove",
        permission_class=_pc("authorized_keys_remove"),
        complexity="single",
        user_input="remove the terminated employee's SSH key from the deploy user's authorized_keys — their comment is 'jdoe@workstation'",
        notes="DESTRUCTIVE: offboarding — key removal can lock out the user permanently.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_remove-0002",
        tool="ssh_keys",
        operation="authorized_keys_remove",
        permission_class=_pc("authorized_keys_remove"),
        complexity="single",
        user_input="remove the old CI server's key from root's authorized_keys; the key comment is 'ci-old@jenkins'",
        notes="DESTRUCTIVE: decommissioning legacy CI system access.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_remove-0003",
        tool="ssh_keys",
        operation="authorized_keys_remove",
        permission_class=_pc("authorized_keys_remove"),
        complexity="single",
        user_input="the security team says to revoke the key 'contractor@external-firm' from the appuser authorized_keys immediately",
        notes="DESTRUCTIVE: emergency key revocation on security team order.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_remove-0004",
        tool="ssh_keys",
        operation="authorized_keys_remove",
        permission_class=_pc("authorized_keys_remove"),
        complexity="multi",
        user_input="remove the compromised key 'backup-old@backup01' from root's authorized_keys and then verify it is gone",
        notes="DESTRUCTIVE: compromised key revocation with confirmation step.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_remove-0005",
        tool="ssh_keys",
        operation="authorized_keys_remove",
        permission_class=_pc("authorized_keys_remove"),
        complexity="diagnostic",
        user_input="the penetration test found an unauthorized key 'unknown@attacker' in the admin user's authorized_keys — remove it now",
        notes="DESTRUCTIVE: incident response — unauthorized key removal.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_remove-0006",
        tool="ssh_keys",
        operation="authorized_keys_remove",
        permission_class=_pc("authorized_keys_remove"),
        complexity="single",
        user_input="remove all keys with the comment 'temp-access' from the deploy user's authorized_keys",
        notes="DESTRUCTIVE: bulk removal of temporary access keys after project end.",
    ),
    Scenario(
        id="ssh_keys-authorized_keys_remove-0007",
        tool="ssh_keys",
        operation="authorized_keys_remove",
        permission_class=_pc("authorized_keys_remove"),
        complexity="multi",
        user_input="list the authorized keys for the ansible user, then remove the one labeled 'ansible-old@control-node', and verify the result",
        notes="DESTRUCTIVE: multi-step key rotation — list, remove, confirm.",
    ),

    # =========================================================================
    # known_hosts_list  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="ssh_keys-known_hosts_list-0001",
        tool="ssh_keys",
        operation="known_hosts_list",
        permission_class=_pc("known_hosts_list"),
        complexity="single",
        user_input="show me the known_hosts entries for root",
        notes="Basic listing of root's known_hosts.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_list-0002",
        tool="ssh_keys",
        operation="known_hosts_list",
        permission_class=_pc("known_hosts_list"),
        complexity="single",
        user_input="what hosts does the deploy user already trust?",
        notes="Service account known_hosts review.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_list-0003",
        tool="ssh_keys",
        operation="known_hosts_list",
        permission_class=_pc("known_hosts_list"),
        complexity="diagnostic",
        user_input="the deploy script keeps getting 'host key verification failed' — show me what's in the deploy user's known_hosts",
        notes="Diagnostic: known_hosts inspection for SSH host key mismatch.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_list-0004",
        tool="ssh_keys",
        operation="known_hosts_list",
        permission_class=_pc("known_hosts_list"),
        complexity="multi",
        user_input="list the known_hosts for the ansible user and check if prod-db01.example.com is already trusted",
        notes="Multi-step: list then search for a specific host.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_list-0005",
        tool="ssh_keys",
        operation="known_hosts_list",
        permission_class=_pc("known_hosts_list"),
        complexity="single",
        user_input="show the known hosts file for the admin user — I want to see all trusted servers",
        notes="Admin account known_hosts audit.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_list-0006",
        tool="ssh_keys",
        operation="known_hosts_list",
        permission_class=_pc("known_hosts_list"),
        complexity="diagnostic",
        user_input="the backup script is failing with host key errors — check the backup user's known_hosts to see if the target host has an outdated entry",
        notes="Diagnostic: stale host key entry causing backup failures.",
    ),

    # =========================================================================
    # known_hosts_remove  (WRITE) — 6 entries
    # =========================================================================

    Scenario(
        id="ssh_keys-known_hosts_remove-0001",
        tool="ssh_keys",
        operation="known_hosts_remove",
        permission_class=_pc("known_hosts_remove"),
        complexity="single",
        user_input="remove the old entry for 'prod-db01.example.com' from root's known_hosts — the server was rebuilt and has a new key",
        notes="WRITE: clear stale host key after server rebuild.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_remove-0002",
        tool="ssh_keys",
        operation="known_hosts_remove",
        permission_class=_pc("known_hosts_remove"),
        complexity="single",
        user_input="the staging server IP changed — remove '10.0.0.50' from the deploy user's known_hosts",
        notes="WRITE: clear IP-based known_hosts entry after server migration.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_remove-0003",
        tool="ssh_keys",
        operation="known_hosts_remove",
        permission_class=_pc("known_hosts_remove"),
        complexity="diagnostic",
        user_input="the ansible playbook is failing with REMOTE HOST IDENTIFICATION HAS CHANGED — remove 'app01.example.com' from root's known_hosts",
        notes="Diagnostic-triggered WRITE: resolve host key mismatch blocking automation.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_remove-0004",
        tool="ssh_keys",
        operation="known_hosts_remove",
        permission_class=_pc("known_hosts_remove"),
        complexity="multi",
        user_input="remove the stale known_hosts entry for 'backup.internal' from the backup user and then try connecting again",
        notes="Multi-step: remove stale entry then re-establish connection.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_remove-0005",
        tool="ssh_keys",
        operation="known_hosts_remove",
        permission_class=_pc("known_hosts_remove"),
        complexity="single",
        user_input="clear the known_hosts entry for 'git.company.com' for the jenkins user — the git server was migrated to new hardware",
        notes="WRITE: post-migration known_hosts cleanup for CI user.",
    ),
    Scenario(
        id="ssh_keys-known_hosts_remove-0006",
        tool="ssh_keys",
        operation="known_hosts_remove",
        permission_class=_pc("known_hosts_remove"),
        complexity="multi",
        user_input="list the ansible user's known_hosts, then remove any entry for '192.168.1.100' since that IP was reassigned",
        notes="Multi-step: audit then remove reassigned IP from known_hosts.",
    ),

    # =========================================================================
    # sshd_config_audit  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="ssh_keys-sshd_config_audit-0001",
        tool="ssh_keys",
        operation="sshd_config_audit",
        permission_class=_pc("sshd_config_audit"),
        complexity="single",
        user_input="show me the current sshd configuration on this server",
        notes="Basic sshd config dump for review.",
    ),
    Scenario(
        id="ssh_keys-sshd_config_audit-0002",
        tool="ssh_keys",
        operation="sshd_config_audit",
        permission_class=_pc("sshd_config_audit"),
        complexity="single",
        user_input="is password authentication enabled in sshd?",
        notes="READ: check PasswordAuthentication setting.",
    ),
    Scenario(
        id="ssh_keys-sshd_config_audit-0003",
        tool="ssh_keys",
        operation="sshd_config_audit",
        permission_class=_pc("sshd_config_audit"),
        complexity="single",
        user_input="what port is sshd listening on?",
        notes="READ: verify SSH port for firewall planning.",
    ),
    Scenario(
        id="ssh_keys-sshd_config_audit-0004",
        tool="ssh_keys",
        operation="sshd_config_audit",
        permission_class=_pc("sshd_config_audit"),
        complexity="diagnostic",
        user_input="users are getting locked out after too many failed attempts — check the sshd config to see what MaxAuthTries and LoginGraceTime are set to",
        notes="Diagnostic: audit sshd settings for lockout-related parameters.",
    ),
    Scenario(
        id="ssh_keys-sshd_config_audit-0005",
        tool="ssh_keys",
        operation="sshd_config_audit",
        permission_class=_pc("sshd_config_audit"),
        complexity="multi",
        user_input="audit the sshd configuration and flag any settings that don't follow CIS benchmark recommendations",
        notes="Multi-step: dump config and cross-reference security standards.",
    ),
    Scenario(
        id="ssh_keys-sshd_config_audit-0006",
        tool="ssh_keys",
        operation="sshd_config_audit",
        permission_class=_pc("sshd_config_audit"),
        complexity="diagnostic",
        user_input="the security scanner flagged that root login might be enabled over SSH — check the actual effective sshd settings",
        notes="Diagnostic: verify PermitRootLogin effective value via sshd -T.",
    ),
    Scenario(
        id="ssh_keys-sshd_config_audit-0007",
        tool="ssh_keys",
        operation="sshd_config_audit",
        permission_class=_pc("sshd_config_audit"),
        complexity="multi",
        user_input="dump the full sshd configuration and check whether X11 forwarding and agent forwarding are disabled",
        notes="Multi-step: audit sshd config for forwarding settings per hardening guide.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("ssh_keys").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "ssh_keys", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("ssh_keys").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
