"""finetune/scenarios/packages.py — Scenario corpus for the 'packages' tool.

Operations and permission classes are derived LIVE from the registry via
finetune.coreimports so this file tracks core/ drift automatically
(INV-schema-sync).  Do NOT hardcode op names, arg names, or permission_class
literals — always use the registry-derived helpers defined below.

The Scenario dataclass is defined locally here with the EXACT field names
required by the Phase 1 spec.  The Phase 1 join step (scenarios/__init__.py)
will import this class and unify all per-tool modules under a single canonical
definition; keeping field names exactly as specified is load-bearing.

Operator user_input strings are NOT asserted I2-clean (plan §1, risks row).
Only assistant content and simulate summaries require the I2 gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Core registry seam — INV-schema-sync: all op/permission data comes from here.
# ---------------------------------------------------------------------------
from finetune.coreimports import registry, OpClass  # noqa: E402

# ---------------------------------------------------------------------------
# Scenario dataclass — field names are load-bearing (join step imports them).
# ---------------------------------------------------------------------------

Complexity = Literal["single", "multi", "diagnostic"]


@dataclass(frozen=True)
class Scenario:
    """One training scenario seed.

    id              Unique corpus id, prefixed with the tool name.
    tool            Registered tool name (always 'packages' in this module).
    operation       Real op name from the tool's OpSpec registry entry.
    permission_class  Live-derived OpClass from the registry — NEVER hardcoded.
    complexity      'single' | 'multi' | 'diagnostic'
    user_input      Natural English an operator would type at the prompt.
    notes           Authoring note (not emitted into traces).
    """

    id: str
    tool: str
    operation: str
    permission_class: OpClass
    complexity: Complexity
    user_input: str
    notes: str = ""


# ---------------------------------------------------------------------------
# Live permission-class helper — INV-schema-sync enforcement point.
# Calling _pc(op) at module load time binds to the registry's declared class;
# if core/ changes an op's class, this module picks it up on next import.
# ---------------------------------------------------------------------------

def _pc(op_name: str) -> OpClass:
    """Return the live-declared OpClass for a packages operation."""
    spec = registry.get("packages")
    if spec is None:
        raise RuntimeError(
            "packages tool not found in registry — ensure coreimports side-effect "
            "imports have run before this module is loaded."
        )
    op_spec = spec.ops.get(op_name)
    if op_spec is None:
        raise RuntimeError(
            f"packages tool has no operation '{op_name}' in registry. "
            "If core/ renamed or removed this op, update this module to match."
        )
    return op_spec.permission_class


# ---------------------------------------------------------------------------
# Scenario corpus — 62 entries across all 5 real ops and 3 complexities.
#
# Op distribution:
#   search  (READ)        — 12 scenarios
#   info    (READ)        — 12 scenarios
#   install (WRITE)       — 14 scenarios
#   update  (WRITE)       — 12 scenarios
#   remove  (DESTRUCTIVE) — 12 scenarios
#                           ─────────────
#                     Total  62
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # search — READ — 12 scenarios
    # =========================================================================

    Scenario(
        id="packages-search-0001",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="single",
        user_input="search for a web server package",
        notes="common entry-level search; expects httpd/nginx results",
    ),
    Scenario(
        id="packages-search-0002",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="single",
        user_input="find a package that provides the nmap command",
        notes="searching by command/tool name rather than package name",
    ),
    Scenario(
        id="packages-search-0003",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="single",
        user_input="what postgresql packages are available?",
        notes="database package discovery",
    ),
    Scenario(
        id="packages-search-0004",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="single",
        user_input="look up python3 packages in the repos",
        notes="language runtime discovery; expects multiple results",
    ),
    Scenario(
        id="packages-search-0005",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="single",
        user_input="search for a package containing the ss utility",
        notes="network diagnostics package lookup",
    ),
    Scenario(
        id="packages-search-0006",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="single",
        user_input="find packages related to disk monitoring",
        notes="storage/disk tooling discovery — expects smartmontools, hdparm etc.",
    ),
    Scenario(
        id="packages-search-0007",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="multi",
        user_input="I need a container runtime — what packages are available, and then show me details on the most likely one?",
        notes="multi-step: search then info; teaches search → info chaining",
    ),
    Scenario(
        id="packages-search-0008",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="multi",
        user_input="search for firewall management packages and then install whichever one is recommended for RHEL",
        notes="multi-step: search → install; teach confirm-before-install gate follows",
    ),
    Scenario(
        id="packages-search-0009",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="multi",
        user_input="find any kernel debug packages available and tell me the latest version",
        notes="search + info chaining for version discovery",
    ),
    Scenario(
        id="packages-search-0010",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="diagnostic",
        user_input="my strace command is missing — which package installs it?",
        notes="diagnostic: missing binary → search to identify provider package",
    ),
    Scenario(
        id="packages-search-0011",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="diagnostic",
        user_input="the lsof tool is not found on this server — what package should I install?",
        notes="diagnostic: missing tool → package search",
    ),
    Scenario(
        id="packages-search-0012",
        tool="packages",
        operation="search",
        permission_class=_pc("search"),
        complexity="diagnostic",
        user_input="I cannot find a SNMP daemon anywhere — search the repos to see if one exists",
        notes="diagnostic: service unavailable → search to determine installability",
    ),

    # =========================================================================
    # info — READ — 12 scenarios
    # =========================================================================

    Scenario(
        id="packages-info-0001",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="show me the details for the nginx package",
        notes="basic info lookup for a common web server package",
    ),
    Scenario(
        id="packages-info-0002",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what version of openssh-server is in the repos?",
        notes="version discovery for a security-critical package",
    ),
    Scenario(
        id="packages-info-0003",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="give me the package description for postgresql15-server",
        notes="detailed description for DB package evaluation",
    ),
    Scenario(
        id="packages-info-0004",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="how big is the kernel-headers package?",
        notes="size query; useful before installing on space-constrained systems",
    ),
    Scenario(
        id="packages-info-0005",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="check if firewalld is available in the package repos",
        notes="availability check for a firewall management package",
    ),
    Scenario(
        id="packages-info-0006",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="single",
        user_input="what repository does the htop package come from?",
        notes="repo source discovery for compliance auditing",
    ),
    Scenario(
        id="packages-info-0007",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="I want to install rsyslog — first show me the info, then if it looks reasonable go ahead and install it",
        notes="multi-step: info → conditional install; confirm gate expected",
    ),
    Scenario(
        id="packages-info-0008",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="look up info for both bind and unbound, then tell me which is a better choice for a caching DNS server",
        notes="multi-step: info × 2 → recommendation; teaches parallel info calls",
    ),
    Scenario(
        id="packages-info-0009",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="multi",
        user_input="check the size and version of the java-17-openjdk package, and if it is under 200 MB install it",
        notes="multi-step: info → conditional install based on size",
    ),
    Scenario(
        id="packages-info-0010",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="I need to know if the version of curl in the repos has the HTTP/2 fix — get me the full package info",
        notes="diagnostic: version/feature check to determine patch status",
    ),
    Scenario(
        id="packages-info-0011",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="show me info for the openssl package — I need to check if it is patched for the recent CVE",
        notes="diagnostic: security patch verification via package metadata",
    ),
    Scenario(
        id="packages-info-0012",
        tool="packages",
        operation="info",
        permission_class=_pc("info"),
        complexity="diagnostic",
        user_input="something keeps requiring libpq — get me the info for the libpq package to understand what provides it",
        notes="diagnostic: dependency investigation via info",
    ),

    # =========================================================================
    # install — WRITE — 14 scenarios
    # =========================================================================

    Scenario(
        id="packages-install-0001",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install nginx",
        notes="canonical single-package install; confirm gate required",
    ),
    Scenario(
        id="packages-install-0002",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install the htop package",
        notes="monitoring utility install; teaches WRITE gate pattern",
    ),
    Scenario(
        id="packages-install-0003",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="get me the git package",
        notes="developer tooling install; common sysadmin request",
    ),
    Scenario(
        id="packages-install-0004",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="set up postgresql15-server on this box",
        notes="database server install; implies service setup follows",
    ),
    Scenario(
        id="packages-install-0005",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install vim-enhanced and tmux",
        notes="multi-package single-op install; both packages in one call",
    ),
    Scenario(
        id="packages-install-0006",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="add the firewalld package to this system",
        notes="firewall management install; security hardening scenario",
    ),
    Scenario(
        id="packages-install-0007",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="single",
        user_input="install the EPEL release package",
        notes="repo enablement; prerequisite for many third-party packages",
    ),
    Scenario(
        id="packages-install-0008",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="multi",
        user_input="install nginx, then check whether the nginx service started successfully",
        notes="multi-step: install → services status; teaches cross-tool chaining",
    ),
    Scenario(
        id="packages-install-0009",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="multi",
        user_input="set up a LAMP stack — install httpd, mariadb-server, and php",
        notes="multi-package install for a classic web stack; WRITE × 1 call",
    ),
    Scenario(
        id="packages-install-0010",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="multi",
        user_input="install the auditd package and then enable and start the service",
        notes="security hardening: install → enable/start; cross-tool chain",
    ),
    Scenario(
        id="packages-install-0011",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="multi",
        user_input="add fail2ban and rsyslog, then verify both are in the installed package list",
        notes="multi-package install + verification; common hardening sequence",
    ),
    Scenario(
        id="packages-install-0012",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="diagnostic",
        user_input="the journalctl binary is missing — install whatever package provides it",
        notes="diagnostic: missing binary → install resolution; systemd-related",
    ),
    Scenario(
        id="packages-install-0013",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="diagnostic",
        user_input="sysstat is not installed and I need iostat — install it now",
        notes="diagnostic: missing performance tool → install fix",
    ),
    Scenario(
        id="packages-install-0014",
        tool="packages",
        operation="install",
        permission_class=_pc("install"),
        complexity="diagnostic",
        user_input="the server is missing curl, wget, and tcpdump — install all three to restore standard tooling",
        notes="diagnostic: baseline tool restoration; multiple missing utilities",
    ),

    # =========================================================================
    # update — WRITE — 12 scenarios
    # =========================================================================

    Scenario(
        id="packages-update-0001",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="update the nginx package to the latest version",
        notes="targeted single-package update; WRITE gate required",
    ),
    Scenario(
        id="packages-update-0002",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="run a full system update",
        notes="full system upgrade; empty packages list triggers update-all path",
    ),
    Scenario(
        id="packages-update-0003",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="update openssl to the latest available version",
        notes="security-critical package update; common post-CVE action",
    ),
    Scenario(
        id="packages-update-0004",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="bring the openssh-server package up to date",
        notes="SSH server patch; security hardening scenario",
    ),
    Scenario(
        id="packages-update-0005",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="update only the python3 and python3-pip packages",
        notes="targeted language runtime update; two packages in one call",
    ),
    Scenario(
        id="packages-update-0006",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="single",
        user_input="patch the kernel to the latest version in the repos",
        notes="kernel update; WRITE class even though kernel is critical",
    ),
    Scenario(
        id="packages-update-0007",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="multi",
        user_input="update postgresql15-server, then restart the database service",
        notes="multi-step: update → service restart; teaches cross-tool sequence",
    ),
    Scenario(
        id="packages-update-0008",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="multi",
        user_input="do a full system update and then reboot the machine",
        notes="multi-step: full update → reboot; teaches WRITE then DESTRUCTIVE confirm",
    ),
    Scenario(
        id="packages-update-0009",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="multi",
        user_input="update the httpd package and verify the service is still running after",
        notes="multi-step: update → status check; in-place update validation",
    ),
    Scenario(
        id="packages-update-0010",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="diagnostic",
        user_input="a CVE was published for glibc — patch it immediately",
        notes="diagnostic: CVE-driven emergency update; security response scenario",
    ),
    Scenario(
        id="packages-update-0011",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="diagnostic",
        user_input="the installed curl version has a known TLS bug — update it to the patched version",
        notes="diagnostic: known-bad version → targeted package update",
    ),
    Scenario(
        id="packages-update-0012",
        tool="packages",
        operation="update",
        permission_class=_pc("update"),
        complexity="diagnostic",
        user_input="several packages are showing as out of date on the security scan — run a full update to address them",
        notes="diagnostic: compliance scan finding → full system update remediation",
    ),

    # =========================================================================
    # remove — DESTRUCTIVE — 12 scenarios
    # =========================================================================

    Scenario(
        id="packages-remove-0001",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="remove the telnet package from this server",
        notes="security hardening: remove insecure legacy tool; DESTRUCTIVE gate",
    ),
    Scenario(
        id="packages-remove-0002",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="uninstall rsh-server — it should not be on this box",
        notes="security hardening: remove legacy remote shell server",
    ),
    Scenario(
        id="packages-remove-0003",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="get rid of the httpd package, I am switching to nginx",
        notes="service replacement: remove old web server; DESTRUCTIVE cascade check",
    ),
    Scenario(
        id="packages-remove-0004",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="remove bind-utils from the server",
        notes="cleanup: remove DNS utility package; typical hardening step",
    ),
    Scenario(
        id="packages-remove-0005",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="uninstall the ftp package — plain FTP is not allowed by policy",
        notes="compliance: remove policy-prohibited protocol package",
    ),
    Scenario(
        id="packages-remove-0006",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="remove nfs-utils and rpcbind, we do not use NFS here",
        notes="attack surface reduction: remove unused network service packages",
    ),
    Scenario(
        id="packages-remove-0007",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="multi",
        user_input="stop the httpd service and then remove the httpd package entirely",
        notes="multi-step: services stop → package remove; proper service teardown",
    ),
    Scenario(
        id="packages-remove-0008",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="multi",
        user_input="remove the old java-11-openjdk package and install java-17-openjdk instead",
        notes="multi-step: remove → install; version migration scenario",
    ),
    Scenario(
        id="packages-remove-0009",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="multi",
        user_input="harden this box by removing sendmail, talk, and ntalk",
        notes="security hardening multi-remove: strip unneeded legacy services",
    ),
    Scenario(
        id="packages-remove-0010",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="diagnostic",
        user_input="the security scanner flagged xinetd as a risk — remove it",
        notes="diagnostic: scanner-driven removal; hardening response",
    ),
    Scenario(
        id="packages-remove-0011",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="diagnostic",
        user_input="snmpd is running but we never configured it — remove the package to eliminate the attack surface",
        notes="diagnostic: unexpected running service → package removal remediation",
    ),
    Scenario(
        id="packages-remove-0012",
        tool="packages",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="diagnostic",
        user_input="the compliance audit says tftp-server must not be installed — verify it is gone or remove it",
        notes="diagnostic: compliance audit finding → remove if present",
    ),
]

# ---------------------------------------------------------------------------
# Module-level validation (runs at import time for fast feedback).
# Checks that every Scenario references a real op of the packages tool and
# that the declared permission_class matches the live registry.
# ---------------------------------------------------------------------------

def _validate() -> None:
    spec = registry.get("packages")
    if spec is None:
        raise RuntimeError("packages tool not registered — coreimports side-effect imports missing")

    seen_ids: set[str] = set()
    for s in SCENARIOS:
        # Unique id check
        if s.id in seen_ids:
            raise ValueError(f"Duplicate scenario id: {s.id!r}")
        seen_ids.add(s.id)

        # Real operation check
        if s.operation not in spec.ops:
            raise ValueError(
                f"Scenario {s.id!r} references non-existent operation "
                f"{s.operation!r} on tool 'packages'. Real ops: {list(spec.ops)}"
            )

        # Permission class consistency check
        live_pc = spec.ops[s.operation].permission_class
        if s.permission_class is not live_pc:
            raise ValueError(
                f"Scenario {s.id!r}: permission_class {s.permission_class!r} "
                f"does not match live registry value {live_pc!r} for op {s.operation!r}. "
                "Update the scenario or fix the registry."
            )

        # Tool name check
        if s.tool != "packages":
            raise ValueError(
                f"Scenario {s.id!r} has tool={s.tool!r}; expected 'packages'"
            )

    # Count check
    if len(SCENARIOS) < 60:
        raise ValueError(
            f"packages scenario corpus has only {len(SCENARIOS)} entries; "
            "Phase 1 requires >= 60 per tool."
        )


_validate()
