"""finetune/scenarios/rpm.py — Scenario corpus for the 'rpm' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  query_info   READ   — show metadata for an installed package (rpm -qi)
  query_files  READ   — list files owned by an installed package (rpm -ql)
  query_file   READ   — identify which package owns a given file path (rpm -qf)
  verify       READ   — verify installed package file integrity (rpm -V / -Va)
  checksig     READ   — verify GPG signature of an RPM file (rpm --checksig)
  install      WRITE  — install an RPM package file (rpm -ivh)
  rpm2cpio     READ   — extract cpio payload from an RPM file (rpm2cpio)

Coverage targets
----------------
  >= 40 entries total across all 7 operations.
  All three complexities represented: single | multi | diagnostic.
  WRITE scenarios are honestly labeled (permission_class from registry)
  so downstream traces teach the confirm-before-write gate.

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
# Scenario dataclass
# Compatible field names are EXACT so the Phase-13 JOIN can unify without renames.
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
    """Return the live permission class for an rpm operation."""
    return registry.get("rpm").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # query_info  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="rpm-query_info-0001",
        tool="rpm",
        operation="query_info",
        permission_class=_pc("query_info"),
        complexity="single",
        user_input="show me the details of the openssl-libs package",
        notes="Basic package metadata query — version, build date, vendor.",
    ),
    Scenario(
        id="rpm-query_info-0002",
        tool="rpm",
        operation="query_info",
        permission_class=_pc("query_info"),
        complexity="single",
        user_input="what version of bash is installed on this system?",
        notes="Checking the installed bash version via rpm metadata.",
    ),
    Scenario(
        id="rpm-query_info-0003",
        tool="rpm",
        operation="query_info",
        permission_class=_pc("query_info"),
        complexity="single",
        user_input="give me the package info for kernel",
        notes="Querying the running kernel package metadata.",
    ),
    Scenario(
        id="rpm-query_info-0004",
        tool="rpm",
        operation="query_info",
        permission_class=_pc("query_info"),
        complexity="single",
        user_input="when was glibc installed on this server?",
        notes="Finding the install date for the core C library package.",
    ),
    Scenario(
        id="rpm-query_info-0005",
        tool="rpm",
        operation="query_info",
        permission_class=_pc("query_info"),
        complexity="single",
        user_input="show rpm metadata for python3",
        notes="Checking the installed Python 3 package.",
    ),
    Scenario(
        id="rpm-query_info-0006",
        tool="rpm",
        operation="query_info",
        permission_class=_pc("query_info"),
        complexity="diagnostic",
        user_input="check what version of openssh-server is installed — we need to know if it is patched against the recent CVE",
        notes="Security audit: verifying the installed SSH server package version against a CVE.",
    ),
    Scenario(
        id="rpm-query_info-0007",
        tool="rpm",
        operation="query_info",
        permission_class=_pc("query_info"),
        complexity="multi",
        user_input="look up the installed version of curl and tell me if it is older than 7.76.0",
        notes="Multi-step: query package info then evaluate version string.",
    ),
    Scenario(
        id="rpm-query_info-0008",
        tool="rpm",
        operation="query_info",
        permission_class=_pc("query_info"),
        complexity="single",
        user_input="who is the vendor for the installed selinux-policy package?",
        notes="Checking the vendor field on an SELinux policy package.",
    ),

    # =========================================================================
    # query_files  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="rpm-query_files-0001",
        tool="rpm",
        operation="query_files",
        permission_class=_pc("query_files"),
        complexity="single",
        user_input="list all files installed by the nginx package",
        notes="Enumerate every file shipped by the nginx RPM.",
    ),
    Scenario(
        id="rpm-query_files-0002",
        tool="rpm",
        operation="query_files",
        permission_class=_pc("query_files"),
        complexity="single",
        user_input="show me which files belong to the openssl package",
        notes="File list for the openssl package — useful for auditing.",
    ),
    Scenario(
        id="rpm-query_files-0003",
        tool="rpm",
        operation="query_files",
        permission_class=_pc("query_files"),
        complexity="diagnostic",
        user_input="I cannot find the httpd binary — which files does the httpd package install and where are they?",
        notes="Diagnostic: locate a missing binary by querying the package file list.",
    ),
    Scenario(
        id="rpm-query_files-0004",
        tool="rpm",
        operation="query_files",
        permission_class=_pc("query_files"),
        complexity="single",
        user_input="list every file that came with the sudo package",
        notes="Checking what sudo installs for a security review.",
    ),
    Scenario(
        id="rpm-query_files-0005",
        tool="rpm",
        operation="query_files",
        permission_class=_pc("query_files"),
        complexity="multi",
        user_input="get the file list for the bind package and show me which config files it includes",
        notes="Multi-step: file list then filter for config paths.",
    ),
    Scenario(
        id="rpm-query_files-0006",
        tool="rpm",
        operation="query_files",
        permission_class=_pc("query_files"),
        complexity="single",
        user_input="what files does the coreutils package own?",
        notes="Auditing the coreutils package file ownership.",
    ),
    Scenario(
        id="rpm-query_files-0007",
        tool="rpm",
        operation="query_files",
        permission_class=_pc("query_files"),
        complexity="diagnostic",
        user_input="the /usr/lib64 directory looks cluttered — show which files in it belong to the glibc package",
        notes="Diagnostic: identify glibc-owned libraries in /usr/lib64.",
    ),

    # =========================================================================
    # query_file  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="rpm-query_file-0001",
        tool="rpm",
        operation="query_file",
        permission_class=_pc("query_file"),
        complexity="single",
        user_input="which package owns /usr/bin/bash?",
        notes="Identify the RPM package that installed the bash binary.",
    ),
    Scenario(
        id="rpm-query_file-0002",
        tool="rpm",
        operation="query_file",
        permission_class=_pc("query_file"),
        complexity="single",
        user_input="what package does /etc/ssh/sshd_config belong to?",
        notes="Tracing an SSH config file back to its package.",
    ),
    Scenario(
        id="rpm-query_file-0003",
        tool="rpm",
        operation="query_file",
        permission_class=_pc("query_file"),
        complexity="diagnostic",
        user_input="/usr/bin/python3 changed unexpectedly — find out which package owns it",
        notes="Diagnostic: correlate a changed file to its owning package for integrity review.",
    ),
    Scenario(
        id="rpm-query_file-0004",
        tool="rpm",
        operation="query_file",
        permission_class=_pc("query_file"),
        complexity="single",
        user_input="who installed /usr/sbin/sshd?",
        notes="Tracing the sshd binary back to its package.",
    ),
    Scenario(
        id="rpm-query_file-0005",
        tool="rpm",
        operation="query_file",
        permission_class=_pc("query_file"),
        complexity="multi",
        user_input="find out which package owns /usr/lib64/libssl.so.3 and then show its full package info",
        notes="Multi-step: file owner query followed by package info.",
    ),
    Scenario(
        id="rpm-query_file-0006",
        tool="rpm",
        operation="query_file",
        permission_class=_pc("query_file"),
        complexity="single",
        user_input="which package provides /usr/bin/curl?",
        notes="Identifying the package that ships the curl binary.",
    ),
    Scenario(
        id="rpm-query_file-0007",
        tool="rpm",
        operation="query_file",
        permission_class=_pc("query_file"),
        complexity="diagnostic",
        user_input="the audit report flagged /etc/pam.d/common-auth as modified — which package installed it?",
        notes="Diagnostic: tracing a flagged config file to its package for remediation.",
    ),

    # =========================================================================
    # verify  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="rpm-verify-0001",
        tool="rpm",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="single",
        user_input="verify the integrity of the openssh-server package",
        notes="Check that openssh-server files match the RPM database.",
    ),
    Scenario(
        id="rpm-verify-0002",
        tool="rpm",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="single",
        user_input="run an integrity check on all installed packages",
        notes="Full system package integrity audit — rpm -Va.",
    ),
    Scenario(
        id="rpm-verify-0003",
        tool="rpm",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="diagnostic",
        user_input="the system might have been compromised — verify all packages to see if any files were changed",
        notes="Incident response: full package verification to detect unauthorized file modifications.",
    ),
    Scenario(
        id="rpm-verify-0004",
        tool="rpm",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="single",
        user_input="check if any files in the sudo package have been modified since install",
        notes="Security check: sudo binary and config file integrity.",
    ),
    Scenario(
        id="rpm-verify-0005",
        tool="rpm",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="multi",
        user_input="verify the kernel package integrity and then show me any files that differ",
        notes="Multi-step: verify kernel package then analyse discrepancy output.",
    ),
    Scenario(
        id="rpm-verify-0006",
        tool="rpm",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="diagnostic",
        user_input="our compliance scanner says openssl may have been tampered with — run rpm verify on it",
        notes="Diagnostic: compliance-triggered package verification for openssl.",
    ),
    Scenario(
        id="rpm-verify-0007",
        tool="rpm",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="single",
        user_input="verify that the glibc package files have not been altered",
        notes="Integrity check for the core C library package.",
    ),

    # =========================================================================
    # checksig  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="rpm-checksig-0001",
        tool="rpm",
        operation="checksig",
        permission_class=_pc("checksig"),
        complexity="single",
        user_input="verify the GPG signature on /tmp/mypackage-1.0.x86_64.rpm before installing it",
        notes="Signature check before installation — security best practice.",
    ),
    Scenario(
        id="rpm-checksig-0002",
        tool="rpm",
        operation="checksig",
        permission_class=_pc("checksig"),
        complexity="single",
        user_input="check if /home/admin/updates/kernel-5.14.0-1.el9.rpm is signed correctly",
        notes="Verifying a downloaded kernel update RPM signature.",
    ),
    Scenario(
        id="rpm-checksig-0003",
        tool="rpm",
        operation="checksig",
        permission_class=_pc("checksig"),
        complexity="diagnostic",
        user_input="the vendor sent us an RPM at /opt/vendor/agent.rpm — check its signature before we install it",
        notes="Diagnostic: validating a third-party RPM signature before deployment.",
    ),
    Scenario(
        id="rpm-checksig-0004",
        tool="rpm",
        operation="checksig",
        permission_class=_pc("checksig"),
        complexity="multi",
        user_input="verify the signature of /tmp/custom-app-2.0.rpm and if it passes, install it",
        notes="Multi-step: checksig then conditional install.",
    ),
    Scenario(
        id="rpm-checksig-0005",
        tool="rpm",
        operation="checksig",
        permission_class=_pc("checksig"),
        complexity="single",
        user_input="does /var/cache/dnf/updates/openssl-3.0.7.rpm have a valid signature?",
        notes="Signature check on a cached update RPM.",
    ),
    Scenario(
        id="rpm-checksig-0006",
        tool="rpm",
        operation="checksig",
        permission_class=_pc("checksig"),
        complexity="diagnostic",
        user_input="security audit requires we confirm the signature on every RPM in /opt/staging before deployment",
        notes="Batch checksig pattern — first file as the pilot check.",
    ),

    # =========================================================================
    # install  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="rpm-install-0001",
        tool="rpm",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install the RPM file at /tmp/myapp-1.0.x86_64.rpm",
        notes="WRITE: direct RPM install from a local file.",
    ),
    Scenario(
        id="rpm-install-0002",
        tool="rpm",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install /home/admin/patches/security-fix-1.2.rpm directly via rpm",
        notes="WRITE: install a security patch RPM bypassing dnf for speed.",
    ),
    Scenario(
        id="rpm-install-0003",
        tool="rpm",
        operation="install",
        permission_class=_pc("install"),
        complexity="multi",
        user_input="first check the signature on /opt/vendor/agent-3.0.rpm then install it if the signature is valid",
        notes="Multi-step WRITE: checksig gating an install.",
    ),
    Scenario(
        id="rpm-install-0004",
        tool="rpm",
        operation="install",
        permission_class=_pc("install"),
        complexity="diagnostic",
        user_input="dnf is unavailable and we need to install /var/cache/kernel-update.rpm immediately",
        notes="Diagnostic-triggered WRITE: emergency install when dnf is not accessible.",
    ),
    Scenario(
        id="rpm-install-0005",
        tool="rpm",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install the custom monitoring agent RPM at /opt/monitoring/agent-2.1.rpm",
        notes="WRITE: installing a third-party monitoring agent.",
    ),
    Scenario(
        id="rpm-install-0006",
        tool="rpm",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="use rpm to install /tmp/offline-update.rpm on this air-gapped server",
        notes="WRITE: offline installation on a network-isolated host.",
    ),
    Scenario(
        id="rpm-install-0007",
        tool="rpm",
        operation="install",
        permission_class=_pc("install"),
        complexity="multi",
        user_input="install /tmp/newpkg-1.0.rpm and then verify the package was installed correctly",
        notes="Multi-step WRITE: install then query_info verification.",
    ),
    Scenario(
        id="rpm-install-0008",
        tool="rpm",
        operation="install",
        permission_class=_pc("install"),
        complexity="diagnostic",
        user_input="the app is broken after the last update — re-install the original RPM from /backup/app-old.rpm",
        notes="Diagnostic-triggered WRITE: reinstall from backup RPM to restore a broken application.",
    ),

    # =========================================================================
    # rpm2cpio  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="rpm-rpm2cpio-0001",
        tool="rpm",
        operation="rpm2cpio",
        permission_class=_pc("rpm2cpio"),
        complexity="single",
        user_input="extract the contents of /tmp/mypkg-1.0.x86_64.rpm using rpm2cpio",
        notes="Basic cpio payload extraction from an RPM file.",
    ),
    Scenario(
        id="rpm-rpm2cpio-0002",
        tool="rpm",
        operation="rpm2cpio",
        permission_class=_pc("rpm2cpio"),
        complexity="single",
        user_input="convert /opt/vendor/agent.rpm to cpio format so I can inspect its contents without installing",
        notes="Non-destructive RPM inspection via rpm2cpio.",
    ),
    Scenario(
        id="rpm-rpm2cpio-0003",
        tool="rpm",
        operation="rpm2cpio",
        permission_class=_pc("rpm2cpio"),
        complexity="diagnostic",
        user_input="I need to look at the config file shipped inside /tmp/newapp-2.0.rpm before installing it",
        notes="Diagnostic: inspect RPM contents before committing to installation.",
    ),
    Scenario(
        id="rpm-rpm2cpio-0004",
        tool="rpm",
        operation="rpm2cpio",
        permission_class=_pc("rpm2cpio"),
        complexity="multi",
        user_input="extract /var/cache/dnf/openssl-3.0.7.rpm with rpm2cpio and then look at the library files",
        notes="Multi-step: extract then inspect specific files from the payload.",
    ),
    Scenario(
        id="rpm-rpm2cpio-0005",
        tool="rpm",
        operation="rpm2cpio",
        permission_class=_pc("rpm2cpio"),
        complexity="single",
        user_input="pull the cpio archive out of /home/admin/test-package-1.0.noarch.rpm",
        notes="Extracting a noarch package payload for inspection.",
    ),
    Scenario(
        id="rpm-rpm2cpio-0006",
        tool="rpm",
        operation="rpm2cpio",
        permission_class=_pc("rpm2cpio"),
        complexity="diagnostic",
        user_input="the RPM database seems corrupt — recover the binary from /backup/bash-5.1.rpm using rpm2cpio",
        notes="Diagnostic: extracting a binary from an RPM backup to recover from database corruption.",
    ),
    Scenario(
        id="rpm-rpm2cpio-0007",
        tool="rpm",
        operation="rpm2cpio",
        permission_class=_pc("rpm2cpio"),
        complexity="multi",
        user_input="extract the cpio payload from /tmp/security-patch.rpm and verify the checksums of the extracted files",
        notes="Multi-step: extract then checksum verification of the payload.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("rpm").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "rpm", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("rpm").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
