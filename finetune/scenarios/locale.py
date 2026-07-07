"""finetune/scenarios/locale.py — Scenario corpus for the 'locale' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  localectl-status   READ   — show current locale and keymap
  set-locale         WRITE  — set the system locale
  set-keymap         WRITE  — set the system keyboard layout
  timedatectl-status READ   — show current date, time, timezone, NTP state
  set-timezone       WRITE  — set the system timezone
  set-ntp            WRITE  — enable or disable NTP synchronisation

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
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
# Compatible field names are EXACT so the P13 JOIN can unify without renames.
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
    """Return the live permission class for a locale operation."""
    return registry.get("locale").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # localectl-status  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="locale-localectl-status-0001",
        tool="locale",
        operation="localectl-status",
        permission_class=_pc("localectl-status"),
        complexity="single",
        user_input="what locale is this system using?",
        notes="Simple read: show current locale via localectl status.",
    ),
    Scenario(
        id="locale-localectl-status-0002",
        tool="locale",
        operation="localectl-status",
        permission_class=_pc("localectl-status"),
        complexity="single",
        user_input="show me the current keyboard layout and locale settings",
        notes="Inspect both locale and keymap from localectl status output.",
    ),
    Scenario(
        id="locale-localectl-status-0003",
        tool="locale",
        operation="localectl-status",
        permission_class=_pc("localectl-status"),
        complexity="single",
        user_input="what language is the system configured for?",
        notes="Locale check phrased as a language question.",
    ),
    Scenario(
        id="locale-localectl-status-0004",
        tool="locale",
        operation="localectl-status",
        permission_class=_pc("localectl-status"),
        complexity="diagnostic",
        user_input="a user is seeing garbled characters — check what locale the system is set to",
        notes="Diagnostic: locale mismatch may cause character encoding issues.",
    ),
    Scenario(
        id="locale-localectl-status-0005",
        tool="locale",
        operation="localectl-status",
        permission_class=_pc("localectl-status"),
        complexity="single",
        user_input="show the VC keymap and X11 layout",
        notes="Specifically asks for keyboard/X11 settings from localectl.",
    ),
    Scenario(
        id="locale-localectl-status-0006",
        tool="locale",
        operation="localectl-status",
        permission_class=_pc("localectl-status"),
        complexity="multi",
        user_input="check the current locale and then set it to en_US.UTF-8 if it is not already",
        notes="Multi-step: status check before deciding whether to write.",
    ),
    Scenario(
        id="locale-localectl-status-0007",
        tool="locale",
        operation="localectl-status",
        permission_class=_pc("localectl-status"),
        complexity="diagnostic",
        user_input="the application is printing question marks instead of special characters — what locale does localectl show?",
        notes="Diagnostic: encoding problem traced back to locale configuration.",
    ),
    Scenario(
        id="locale-localectl-status-0008",
        tool="locale",
        operation="localectl-status",
        permission_class=_pc("localectl-status"),
        complexity="single",
        user_input="run localectl status and show me the output",
        notes="Direct localectl status invocation request.",
    ),

    # =========================================================================
    # set-locale  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="locale-set-locale-0001",
        tool="locale",
        operation="set-locale",
        permission_class=_pc("set-locale"),
        complexity="single",
        user_input="set the system locale to en_US.UTF-8",
        notes="WRITE: set the most common US English locale.",
    ),
    Scenario(
        id="locale-set-locale-0002",
        tool="locale",
        operation="set-locale",
        permission_class=_pc("set-locale"),
        complexity="single",
        user_input="change the locale to de_DE.UTF-8 for our German-language deployment",
        notes="WRITE: switch to German locale for localised deployment.",
    ),
    Scenario(
        id="locale-set-locale-0003",
        tool="locale",
        operation="set-locale",
        permission_class=_pc("set-locale"),
        complexity="single",
        user_input="set LANG to fr_FR.UTF-8",
        notes="WRITE: set French locale using LANG= form.",
    ),
    Scenario(
        id="locale-set-locale-0004",
        tool="locale",
        operation="set-locale",
        permission_class=_pc("set-locale"),
        complexity="multi",
        user_input="set the locale to en_GB.UTF-8 and then confirm the change with localectl status",
        notes="Multi-step: set locale then verify.",
    ),
    Scenario(
        id="locale-set-locale-0005",
        tool="locale",
        operation="set-locale",
        permission_class=_pc("set-locale"),
        complexity="diagnostic",
        user_input="the system locale is still C.UTF-8 after the OS install — change it to en_US.UTF-8",
        notes="Diagnostic-triggered WRITE: correct a default post-install locale.",
    ),
    Scenario(
        id="locale-set-locale-0006",
        tool="locale",
        operation="set-locale",
        permission_class=_pc("set-locale"),
        complexity="single",
        user_input="configure the server to use the Japanese locale ja_JP.UTF-8",
        notes="WRITE: set Japanese locale for an Asia-Pacific server.",
    ),
    Scenario(
        id="locale-set-locale-0007",
        tool="locale",
        operation="set-locale",
        permission_class=_pc("set-locale"),
        complexity="single",
        user_input="set the system locale to es_ES.UTF-8",
        notes="WRITE: Spanish locale for a Spanish-language environment.",
    ),
    Scenario(
        id="locale-set-locale-0008",
        tool="locale",
        operation="set-locale",
        permission_class=_pc("set-locale"),
        complexity="multi",
        user_input="switch the locale to pt_BR.UTF-8 for the Brazilian office and verify it took effect",
        notes="Multi-step: set Brazilian Portuguese locale then confirm.",
    ),
    Scenario(
        id="locale-set-locale-0009",
        tool="locale",
        operation="set-locale",
        permission_class=_pc("set-locale"),
        complexity="diagnostic",
        user_input="users are seeing encoding errors — the locale might be set to C; change it to en_US.UTF-8",
        notes="Diagnostic: encoding error traced to minimal C locale; switch to UTF-8.",
    ),

    # =========================================================================
    # set-keymap  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="locale-set-keymap-0001",
        tool="locale",
        operation="set-keymap",
        permission_class=_pc("set-keymap"),
        complexity="single",
        user_input="set the keyboard layout to us",
        notes="WRITE: set US QWERTY keyboard layout.",
    ),
    Scenario(
        id="locale-set-keymap-0002",
        tool="locale",
        operation="set-keymap",
        permission_class=_pc("set-keymap"),
        complexity="single",
        user_input="change the keyboard map to de for a German keyboard",
        notes="WRITE: German keyboard layout for a German-locale server.",
    ),
    Scenario(
        id="locale-set-keymap-0003",
        tool="locale",
        operation="set-keymap",
        permission_class=_pc("set-keymap"),
        complexity="single",
        user_input="set the virtual console keymap to gb",
        notes="WRITE: UK keyboard layout.",
    ),
    Scenario(
        id="locale-set-keymap-0004",
        tool="locale",
        operation="set-keymap",
        permission_class=_pc("set-keymap"),
        complexity="multi",
        user_input="set the keyboard to fr and then check localectl status to confirm",
        notes="Multi-step: set French keyboard layout then verify.",
    ),
    Scenario(
        id="locale-set-keymap-0005",
        tool="locale",
        operation="set-keymap",
        permission_class=_pc("set-keymap"),
        complexity="diagnostic",
        user_input="the console is outputting the wrong characters when I type — set the keymap to us",
        notes="Diagnostic: incorrect key output points to wrong keymap setting.",
    ),
    Scenario(
        id="locale-set-keymap-0006",
        tool="locale",
        operation="set-keymap",
        permission_class=_pc("set-keymap"),
        complexity="single",
        user_input="configure the keyboard layout to dvorak",
        notes="WRITE: set Dvorak layout for a developer server.",
    ),
    Scenario(
        id="locale-set-keymap-0007",
        tool="locale",
        operation="set-keymap",
        permission_class=_pc("set-keymap"),
        complexity="single",
        user_input="set keymap to es for Spanish keyboard",
        notes="WRITE: Spanish keyboard layout.",
    ),
    Scenario(
        id="locale-set-keymap-0008",
        tool="locale",
        operation="set-keymap",
        permission_class=_pc("set-keymap"),
        complexity="multi",
        user_input="set the keyboard to it (Italian) and confirm it is listed in localectl status",
        notes="Multi-step: set Italian keyboard layout and verify.",
    ),

    # =========================================================================
    # timedatectl-status  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="locale-timedatectl-status-0001",
        tool="locale",
        operation="timedatectl-status",
        permission_class=_pc("timedatectl-status"),
        complexity="single",
        user_input="what timezone is this server in?",
        notes="Simple read: show timezone via timedatectl status.",
    ),
    Scenario(
        id="locale-timedatectl-status-0002",
        tool="locale",
        operation="timedatectl-status",
        permission_class=_pc("timedatectl-status"),
        complexity="single",
        user_input="show me the current date and time settings",
        notes="General time/date status check.",
    ),
    Scenario(
        id="locale-timedatectl-status-0003",
        tool="locale",
        operation="timedatectl-status",
        permission_class=_pc("timedatectl-status"),
        complexity="single",
        user_input="is NTP synchronisation enabled on this host?",
        notes="Check NTP state from timedatectl status output.",
    ),
    Scenario(
        id="locale-timedatectl-status-0004",
        tool="locale",
        operation="timedatectl-status",
        permission_class=_pc("timedatectl-status"),
        complexity="diagnostic",
        user_input="log timestamps are wrong — check the timezone and NTP sync status",
        notes="Diagnostic: wrong log times may indicate timezone misconfiguration or NTP drift.",
    ),
    Scenario(
        id="locale-timedatectl-status-0005",
        tool="locale",
        operation="timedatectl-status",
        permission_class=_pc("timedatectl-status"),
        complexity="single",
        user_input="run timedatectl status",
        notes="Direct timedatectl status invocation request.",
    ),
    Scenario(
        id="locale-timedatectl-status-0006",
        tool="locale",
        operation="timedatectl-status",
        permission_class=_pc("timedatectl-status"),
        complexity="multi",
        user_input="check if NTP is active and if not enable it",
        notes="Multi-step: read NTP state from status, then conditionally enable NTP.",
    ),
    Scenario(
        id="locale-timedatectl-status-0007",
        tool="locale",
        operation="timedatectl-status",
        permission_class=_pc("timedatectl-status"),
        complexity="diagnostic",
        user_input="cron jobs are running at the wrong time — what timezone is the system in?",
        notes="Diagnostic: cron schedule mismatch traced to unexpected timezone.",
    ),

    # =========================================================================
    # set-timezone  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="locale-set-timezone-0001",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("set-timezone"),
        complexity="single",
        user_input="set the timezone to UTC",
        notes="WRITE: set server timezone to UTC — best practice for servers.",
    ),
    Scenario(
        id="locale-set-timezone-0002",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("set-timezone"),
        complexity="single",
        user_input="change the timezone to America/New_York",
        notes="WRITE: set US Eastern timezone.",
    ),
    Scenario(
        id="locale-set-timezone-0003",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("set-timezone"),
        complexity="single",
        user_input="set the server time zone to Europe/London",
        notes="WRITE: UK timezone for a London-based server.",
    ),
    Scenario(
        id="locale-set-timezone-0004",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("set-timezone"),
        complexity="multi",
        user_input="set the timezone to Asia/Tokyo and then verify with timedatectl status",
        notes="Multi-step: set Japan Standard Time then confirm.",
    ),
    Scenario(
        id="locale-set-timezone-0005",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("set-timezone"),
        complexity="diagnostic",
        user_input="the cron jobs are running 5 hours off — set the timezone to America/Chicago",
        notes="Diagnostic-triggered WRITE: timezone offset error corrected.",
    ),
    Scenario(
        id="locale-set-timezone-0006",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("set-timezone"),
        complexity="single",
        user_input="configure this host to use the Australia/Sydney timezone",
        notes="WRITE: Australian Eastern timezone for a Sydney deployment.",
    ),
    Scenario(
        id="locale-set-timezone-0007",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("set-timezone"),
        complexity="single",
        user_input="change the time zone to Europe/Berlin",
        notes="WRITE: Central European timezone for a German data centre.",
    ),
    Scenario(
        id="locale-set-timezone-0008",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("set-timezone"),
        complexity="multi",
        user_input="set the timezone to America/Los_Angeles and check the current time afterwards",
        notes="Multi-step: set Pacific timezone then confirm current time.",
    ),
    Scenario(
        id="locale-set-timezone-0009",
        tool="locale",
        operation="set-timezone",
        permission_class=_pc("set-timezone"),
        complexity="diagnostic",
        user_input="SSL certificates are showing as expired even though they are not — check the timezone and set it to UTC",
        notes="Diagnostic: TLS errors caused by clock/timezone skew; fix by setting UTC.",
    ),

    # =========================================================================
    # set-ntp  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="locale-set-ntp-0001",
        tool="locale",
        operation="set-ntp",
        permission_class=_pc("set-ntp"),
        complexity="single",
        user_input="enable NTP synchronisation",
        notes="WRITE: turn on NTP — standard post-install hardening step.",
    ),
    Scenario(
        id="locale-set-ntp-0002",
        tool="locale",
        operation="set-ntp",
        permission_class=_pc("set-ntp"),
        complexity="single",
        user_input="disable NTP on this host so it syncs from an internal source",
        notes="WRITE: disable NTP to allow manual or internal-only time management.",
    ),
    Scenario(
        id="locale-set-ntp-0003",
        tool="locale",
        operation="set-ntp",
        permission_class=_pc("set-ntp"),
        complexity="single",
        user_input="turn on time synchronisation via NTP",
        notes="WRITE: enable NTP phrased as 'turn on time synchronisation'.",
    ),
    Scenario(
        id="locale-set-ntp-0004",
        tool="locale",
        operation="set-ntp",
        permission_class=_pc("set-ntp"),
        complexity="multi",
        user_input="enable NTP and then check timedatectl status to confirm it is syncing",
        notes="Multi-step: enable NTP then verify synchronisation state.",
    ),
    Scenario(
        id="locale-set-ntp-0005",
        tool="locale",
        operation="set-ntp",
        permission_class=_pc("set-ntp"),
        complexity="diagnostic",
        user_input="the clock is drifting — enable NTP to keep it in sync",
        notes="Diagnostic-triggered WRITE: enable NTP as remedy for clock drift.",
    ),
    Scenario(
        id="locale-set-ntp-0006",
        tool="locale",
        operation="set-ntp",
        permission_class=_pc("set-ntp"),
        complexity="single",
        user_input="switch off NTP so I can set the time manually",
        notes="WRITE: disable NTP before manual time adjustment.",
    ),
    Scenario(
        id="locale-set-ntp-0007",
        tool="locale",
        operation="set-ntp",
        permission_class=_pc("set-ntp"),
        complexity="multi",
        user_input="disable NTP, set the timezone to UTC, then re-enable NTP",
        notes="Multi-step: disable NTP, configure timezone, then re-enable NTP.",
    ),
    Scenario(
        id="locale-set-ntp-0008",
        tool="locale",
        operation="set-ntp",
        permission_class=_pc("set-ntp"),
        complexity="diagnostic",
        user_input="certificate validation is failing because the clock is wrong — make sure NTP is enabled",
        notes="Diagnostic: PKI failures caused by clock skew; enable NTP as fix.",
    ),
    Scenario(
        id="locale-set-ntp-0009",
        tool="locale",
        operation="set-ntp",
        permission_class=_pc("set-ntp"),
        complexity="single",
        user_input="enable automatic time sync via NTP for this server",
        notes="WRITE: enable NTP for automatic time synchronisation.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("locale").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "locale", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("locale").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
