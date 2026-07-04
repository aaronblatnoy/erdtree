"""finetune/scenarios/hardware.py — Scenario corpus for the 'hardware' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  cpu     READ  — processor topology and capability flags (lscpu)
  memory  READ  — RAM and swap usage summary (free -h)
  pci     READ  — PCI bus device list (lspci)
  usb     READ  — USB device list (lsusb)
  block   READ  — block device topology (lsblk)
  sensors READ  — hardware sensor readings: temperature, fan speed, voltage
  summary READ  — combined snapshot: cpu + memory + block

Coverage targets
----------------
  >= 60 entries total across all 7 operations.
  All three complexities represented: single | multi | diagnostic.
  ALL ops are READ — permission_class derived from the live registry.

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
# Compatible field names are EXACT so the P1 JOIN can unify without renames.
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
    """Return the live permission class for a hardware operation."""
    return registry.get("hardware").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # cpu  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="hardware-cpu-0001",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="single",
        user_input="show me the CPU information for this machine",
        notes="Basic CPU topology query.",
    ),
    Scenario(
        id="hardware-cpu-0002",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="single",
        user_input="how many CPU cores does this server have?",
        notes="Core count query — common capacity-planning question.",
    ),
    Scenario(
        id="hardware-cpu-0003",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="single",
        user_input="what processor is installed in this system?",
        notes="Identify processor model and vendor.",
    ),
    Scenario(
        id="hardware-cpu-0004",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="single",
        user_input="does this CPU support hardware virtualisation?",
        notes="Check for vmx/svm flags — hypervisor pre-flight check.",
    ),
    Scenario(
        id="hardware-cpu-0005",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="single",
        user_input="what is the CPU clock speed on this host?",
        notes="Clock speed / MHz query.",
    ),
    Scenario(
        id="hardware-cpu-0006",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="multi",
        user_input="show the CPU topology and tell me how many physical sockets are populated",
        notes="Multi-step: retrieve lscpu output then interpret socket count.",
    ),
    Scenario(
        id="hardware-cpu-0007",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="diagnostic",
        user_input="the workload is CPU-bound — show the processor topology so I can see if NUMA is a factor",
        notes="Diagnostic: NUMA topology analysis for a performance issue.",
    ),
    Scenario(
        id="hardware-cpu-0008",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="diagnostic",
        user_input="we need to verify this host can run KVM — check the CPU flags",
        notes="Diagnostic: verify hardware-virtualisation capability before enabling KVM.",
    ),
    Scenario(
        id="hardware-cpu-0009",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="multi",
        user_input="get the CPU details and then confirm the architecture matches our x86_64 baseline",
        notes="Multi-step: retrieve CPU info then validate architecture.",
    ),
    Scenario(
        id="hardware-cpu-0010",
        tool="hardware",
        operation="cpu",
        permission_class=_pc("cpu"),
        complexity="single",
        user_input="show me lscpu output for this server",
        notes="Direct lscpu-style topology query.",
    ),

    # =========================================================================
    # memory  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="hardware-memory-0001",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="single",
        user_input="how much RAM does this server have?",
        notes="Total memory query — capacity check.",
    ),
    Scenario(
        id="hardware-memory-0002",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="single",
        user_input="show me the current memory usage",
        notes="Live RAM and swap utilisation.",
    ),
    Scenario(
        id="hardware-memory-0003",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="single",
        user_input="is the server running low on memory?",
        notes="Simple low-memory check.",
    ),
    Scenario(
        id="hardware-memory-0004",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="single",
        user_input="what is the swap usage on this machine?",
        notes="Swap utilisation — indicates memory pressure.",
    ),
    Scenario(
        id="hardware-memory-0005",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="diagnostic",
        user_input="the server is sluggish — check how much free RAM is available",
        notes="Diagnostic: memory availability check during performance investigation.",
    ),
    Scenario(
        id="hardware-memory-0006",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="multi",
        user_input="show the memory usage and tell me what percentage of RAM is currently in use",
        notes="Multi-step: retrieve memory stats then calculate utilisation percentage.",
    ),
    Scenario(
        id="hardware-memory-0007",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="diagnostic",
        user_input="the OOM killer fired last night — show me the current memory situation",
        notes="Diagnostic: post-OOM memory review.",
    ),
    Scenario(
        id="hardware-memory-0008",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="single",
        user_input="display RAM and swap stats for this host",
        notes="Combined RAM/swap status query.",
    ),
    Scenario(
        id="hardware-memory-0009",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="multi",
        user_input="check memory usage and flag if swap is being actively used",
        notes="Multi-step: retrieve memory then interpret swap activity.",
    ),
    Scenario(
        id="hardware-memory-0010",
        tool="hardware",
        operation="memory",
        permission_class=_pc("memory"),
        complexity="diagnostic",
        user_input="postgresql is crashing — check whether this host is out of memory",
        notes="Diagnostic: rule out memory exhaustion as crash cause.",
    ),

    # =========================================================================
    # pci  (READ) — 9 entries
    # =========================================================================

    Scenario(
        id="hardware-pci-0001",
        tool="hardware",
        operation="pci",
        permission_class=_pc("pci"),
        complexity="single",
        user_input="list all PCI devices on this server",
        notes="Full PCI bus enumeration.",
    ),
    Scenario(
        id="hardware-pci-0002",
        tool="hardware",
        operation="pci",
        permission_class=_pc("pci"),
        complexity="single",
        user_input="what network cards are installed?",
        notes="NIC identification via PCI listing.",
    ),
    Scenario(
        id="hardware-pci-0003",
        tool="hardware",
        operation="pci",
        permission_class=_pc("pci"),
        complexity="single",
        user_input="show me the GPU devices on this host",
        notes="GPU identification via PCI listing.",
    ),
    Scenario(
        id="hardware-pci-0004",
        tool="hardware",
        operation="pci",
        permission_class=_pc("pci"),
        complexity="single",
        user_input="does this server have any RAID controllers?",
        notes="RAID controller identification via PCI scan.",
    ),
    Scenario(
        id="hardware-pci-0005",
        tool="hardware",
        operation="pci",
        permission_class=_pc("pci"),
        complexity="diagnostic",
        user_input="the 10GbE interface disappeared after a reboot — check what PCI network devices are visible",
        notes="Diagnostic: missing NIC troubleshooting via PCI enumeration.",
    ),
    Scenario(
        id="hardware-pci-0006",
        tool="hardware",
        operation="pci",
        permission_class=_pc("pci"),
        complexity="multi",
        user_input="list PCI devices and identify any storage controllers that might be relevant to our disk setup",
        notes="Multi-step: enumerate PCI then filter for storage controllers.",
    ),
    Scenario(
        id="hardware-pci-0007",
        tool="hardware",
        operation="pci",
        permission_class=_pc("pci"),
        complexity="single",
        user_input="show PCI bus devices so I can confirm the HBA is recognised",
        notes="HBA (host bus adapter) presence check.",
    ),
    Scenario(
        id="hardware-pci-0008",
        tool="hardware",
        operation="pci",
        permission_class=_pc("pci"),
        complexity="diagnostic",
        user_input="we added a new PCIe card — verify the OS can see it",
        notes="Diagnostic: confirm new hardware is visible after installation.",
    ),
    Scenario(
        id="hardware-pci-0009",
        tool="hardware",
        operation="pci",
        permission_class=_pc("pci"),
        complexity="single",
        user_input="enumerate PCI devices on this machine",
        notes="General PCI inventory.",
    ),

    # =========================================================================
    # usb  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="hardware-usb-0001",
        tool="hardware",
        operation="usb",
        permission_class=_pc("usb"),
        complexity="single",
        user_input="list all USB devices connected to this server",
        notes="Full USB device enumeration.",
    ),
    Scenario(
        id="hardware-usb-0002",
        tool="hardware",
        operation="usb",
        permission_class=_pc("usb"),
        complexity="single",
        user_input="is there anything plugged into the USB ports?",
        notes="USB presence check — unexpected device audit.",
    ),
    Scenario(
        id="hardware-usb-0003",
        tool="hardware",
        operation="usb",
        permission_class=_pc("usb"),
        complexity="diagnostic",
        user_input="the USB security key for two-factor auth is not responding — check if the OS sees the device",
        notes="Diagnostic: USB device not recognised — check visibility.",
    ),
    Scenario(
        id="hardware-usb-0004",
        tool="hardware",
        operation="usb",
        permission_class=_pc("usb"),
        complexity="single",
        user_input="show me what USB devices lsusb reports",
        notes="Raw lsusb output.",
    ),
    Scenario(
        id="hardware-usb-0005",
        tool="hardware",
        operation="usb",
        permission_class=_pc("usb"),
        complexity="multi",
        user_input="list USB devices and check whether any unauthorised storage devices are connected",
        notes="Multi-step: enumerate USB then flag any mass-storage devices — security audit.",
    ),
    Scenario(
        id="hardware-usb-0006",
        tool="hardware",
        operation="usb",
        permission_class=_pc("usb"),
        complexity="diagnostic",
        user_input="a USB-to-serial adapter was just plugged in — verify it shows up",
        notes="Diagnostic: confirm new USB peripheral is detected.",
    ),
    Scenario(
        id="hardware-usb-0007",
        tool="hardware",
        operation="usb",
        permission_class=_pc("usb"),
        complexity="single",
        user_input="how many USB devices are attached to this server right now?",
        notes="USB device count.",
    ),
    Scenario(
        id="hardware-usb-0008",
        tool="hardware",
        operation="usb",
        permission_class=_pc("usb"),
        complexity="diagnostic",
        user_input="security policy requires no USB mass storage on production hosts — check what is plugged in",
        notes="Security-hardening diagnostic: USB mass storage compliance check.",
    ),

    # =========================================================================
    # block  (READ) — 9 entries
    # =========================================================================

    Scenario(
        id="hardware-block-0001",
        tool="hardware",
        operation="block",
        permission_class=_pc("block"),
        complexity="single",
        user_input="show me the block device layout for this server",
        notes="Full block device topology.",
    ),
    Scenario(
        id="hardware-block-0002",
        tool="hardware",
        operation="block",
        permission_class=_pc("block"),
        complexity="single",
        user_input="what disks are installed in this machine?",
        notes="Physical disk inventory.",
    ),
    Scenario(
        id="hardware-block-0003",
        tool="hardware",
        operation="block",
        permission_class=_pc("block"),
        complexity="single",
        user_input="show me the partition layout",
        notes="Partition scheme overview.",
    ),
    Scenario(
        id="hardware-block-0004",
        tool="hardware",
        operation="block",
        permission_class=_pc("block"),
        complexity="diagnostic",
        user_input="the / filesystem is nearly full — show the block device list so I can find what disk it is on",
        notes="Diagnostic: identify which disk backs the root filesystem.",
    ),
    Scenario(
        id="hardware-block-0005",
        tool="hardware",
        operation="block",
        permission_class=_pc("block"),
        complexity="multi",
        user_input="list block devices and confirm the data volume is mounted at /data",
        notes="Multi-step: retrieve block layout then verify expected mount point.",
    ),
    Scenario(
        id="hardware-block-0006",
        tool="hardware",
        operation="block",
        permission_class=_pc("block"),
        complexity="single",
        user_input="how many drives are in this server and what are their sizes?",
        notes="Drive count and capacity summary.",
    ),
    Scenario(
        id="hardware-block-0007",
        tool="hardware",
        operation="block",
        permission_class=_pc("block"),
        complexity="diagnostic",
        user_input="a new disk was hot-plugged — verify the kernel has picked it up",
        notes="Diagnostic: confirm newly attached disk is visible as a block device.",
    ),
    Scenario(
        id="hardware-block-0008",
        tool="hardware",
        operation="block",
        permission_class=_pc("block"),
        complexity="multi",
        user_input="show the block device topology and flag any block devices that are not mounted",
        notes="Multi-step: enumerate block devices then identify unmounted ones.",
    ),
    Scenario(
        id="hardware-block-0009",
        tool="hardware",
        operation="block",
        permission_class=_pc("block"),
        complexity="single",
        user_input="list the block devices along with their filesystem types and mount points",
        notes="Block topology with filesystem and mount detail.",
    ),

    # =========================================================================
    # sensors  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="hardware-sensors-0001",
        tool="hardware",
        operation="sensors",
        permission_class=_pc("sensors"),
        complexity="single",
        user_input="what are the current CPU temperatures?",
        notes="CPU temperature check via sensors.",
    ),
    Scenario(
        id="hardware-sensors-0002",
        tool="hardware",
        operation="sensors",
        permission_class=_pc("sensors"),
        complexity="single",
        user_input="show me the hardware sensor readings",
        notes="Full sensor output.",
    ),
    Scenario(
        id="hardware-sensors-0003",
        tool="hardware",
        operation="sensors",
        permission_class=_pc("sensors"),
        complexity="diagnostic",
        user_input="the server is throttling under load — check the thermal readings",
        notes="Diagnostic: verify thermal throttling hypothesis via sensor data.",
    ),
    Scenario(
        id="hardware-sensors-0004",
        tool="hardware",
        operation="sensors",
        permission_class=_pc("sensors"),
        complexity="single",
        user_input="are the fans running at the right speed?",
        notes="Fan speed check.",
    ),
    Scenario(
        id="hardware-sensors-0005",
        tool="hardware",
        operation="sensors",
        permission_class=_pc("sensors"),
        complexity="diagnostic",
        user_input="the datacenter monitoring says this host is running hot — pull the sensor data",
        notes="Diagnostic: thermal incident response via sensor readings.",
    ),
    Scenario(
        id="hardware-sensors-0006",
        tool="hardware",
        operation="sensors",
        permission_class=_pc("sensors"),
        complexity="multi",
        user_input="show the sensor readings and flag any temperatures above 80 degrees",
        notes="Multi-step: retrieve sensor data then identify high-temperature entries.",
    ),
    Scenario(
        id="hardware-sensors-0007",
        tool="hardware",
        operation="sensors",
        permission_class=_pc("sensors"),
        complexity="single",
        user_input="check the voltage readings on this server",
        notes="Voltage sensor check.",
    ),
    Scenario(
        id="hardware-sensors-0008",
        tool="hardware",
        operation="sensors",
        permission_class=_pc("sensors"),
        complexity="diagnostic",
        user_input="the system logged a thermal warning overnight — show the current sensor state",
        notes="Diagnostic: thermal warning follow-up via live sensor readings.",
    ),

    # =========================================================================
    # summary  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="hardware-summary-0001",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="single",
        user_input="give me a full hardware overview of this server",
        notes="Combined CPU + memory + block snapshot.",
    ),
    Scenario(
        id="hardware-summary-0002",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="single",
        user_input="what hardware does this machine have?",
        notes="High-level hardware inventory question.",
    ),
    Scenario(
        id="hardware-summary-0003",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="single",
        user_input="show me a hardware summary for this host",
        notes="Hardware summary — onboarding or documentation task.",
    ),
    Scenario(
        id="hardware-summary-0004",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="diagnostic",
        user_input="I need to assess this server before migrating workloads onto it — give me a hardware snapshot",
        notes="Diagnostic: pre-migration hardware capacity assessment.",
    ),
    Scenario(
        id="hardware-summary-0005",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="multi",
        user_input="get a hardware snapshot and tell me if the CPU and RAM are sufficient for our database workload",
        notes="Multi-step: retrieve summary then evaluate suitability for a specific workload.",
    ),
    Scenario(
        id="hardware-summary-0006",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="single",
        user_input="document the hardware configuration of this node",
        notes="Hardware documentation task.",
    ),
    Scenario(
        id="hardware-summary-0007",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="diagnostic",
        user_input="performance is unexpectedly poor — get a full hardware snapshot so we can check resource capacity",
        notes="Diagnostic: hardware baseline during performance investigation.",
    ),
    Scenario(
        id="hardware-summary-0008",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="multi",
        user_input="pull a hardware summary and then confirm whether the storage topology matches our expected layout",
        notes="Multi-step: retrieve summary then validate block device layout.",
    ),
    Scenario(
        id="hardware-summary-0009",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="single",
        user_input="I just inherited this server — show me what it is made of",
        notes="Quick hardware inventory for a newly managed host.",
    ),
    Scenario(
        id="hardware-summary-0010",
        tool="hardware",
        operation="summary",
        permission_class=_pc("summary"),
        complexity="diagnostic",
        user_input="the VM sizing team needs the hardware spec of this bare-metal host — pull the full snapshot",
        notes="Diagnostic: hardware inventory for capacity planning and VM sizing.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("hardware").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "hardware", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("hardware").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 60, f"Need >= 60 scenarios, got {len(SCENARIOS)}"
