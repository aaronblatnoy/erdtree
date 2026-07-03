"""tests/test_manpage_parser.py — Phase 9 man-page parser + schema generator tests.

Coverage
--------
1.  parse_man_text() extracts simple flags from an OPTIONS section.
2.  parse_man_text() handles flags with required args (--long=VAL, -n NUM).
3.  parse_man_text() handles flags with optional args (--color[=WHEN]).
4.  parse_man_text() handles combined short+long flags (-v, --verbose).
5.  parse_man_text() extracts subcommands from a COMMANDS section.
6.  parse_man_text() extracts mutually-exclusive groups from SYNOPSIS.
7.  parse_man_text() extracts positionals from SYNOPSIS.
8.  parse_man_text() deduplicates flags that appear more than once.
9.  parse_man_text() handles empty / minimal man page text gracefully.
10. schema_entry_to_toolspec() builds a valid ToolSpec with WRITE floor
    (even for ops declared "read" in the JSON).
11. schema_entry_to_toolspec() keeps DESTRUCTIVE as DESTRUCTIVE.
12. schema_entry_to_toolspec() marks unverified tools and upgrades READ->WRITE.
13. load_artifact() loads the checked-in manpages.v1.json without error.
14. Artifact contains expected tool names (systemctl, dnf, git, etc.).
15. All ops in the artifact have a permission_class that is one of the valid
    values ("read", "write", "destructive").
16. version_matches() behaves correctly for prefix-match and mismatch cases.
17. Registering a tool from the artifact produces a ToolSpec accepted by the
    ToolRegistry; the loaded op's effective permission_class is >= WRITE.
18. A version mismatch (detected < pinned prefix) marks the tool [unverified]
    and still registers successfully.

Invariants under test
---------------------
I3  generated tools land on the WRITE floor (no ALLOW auto-run for man-page ops).
I6  no tier/product name appears in tool descriptions or op names.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the modules under test
# ---------------------------------------------------------------------------

from tools.manpage.parse import (
    ParsedFlag,
    ParsedManPage,
    ParsedPositional,
    ParsedSubcommand,
    parse_man_text,
    _extract_sections,
    _parse_options_section,
    _parse_synopsis,
    _parse_subcommands_section,
)
from tools.manpage.generate_schemas import (
    load_artifact,
    schema_entry_to_toolspec,
    version_matches,
)
from core.tools import ArgSpec, OpSpec, ToolRegistry, ToolSpec
from core.agent.permissions import OpClass

# ---------------------------------------------------------------------------
# Fixtures / sample texts
# ---------------------------------------------------------------------------

SIMPLE_OPTIONS_TEXT = """\
NAME
    grep - print lines matching a pattern

SYNOPSIS
    grep [OPTIONS] PATTERN [FILE...]

OPTIONS
    -i, --ignore-case
        Ignore case distinctions in PATTERN and FILE.

    -n, --line-number
        Prefix each line of output with the line number.

    -r, --recursive
        Read all files under each directory, recursively.

    -l, --files-with-matches
        Print the name of each file that contains a match.
"""

OPTIONS_WITH_ARGS_TEXT = """\
NAME
    tail - output the last part of files

SYNOPSIS
    tail [OPTION]... [FILE]...

OPTIONS
    -n NUM, --lines=NUM
        Output the last NUM lines, instead of the last 10.

    -c BYTES, --bytes=BYTES
        Output the last BYTES bytes.

    --color[=WHEN]
        Colorize the output. WHEN can be 'always', 'never', or 'auto'.

    -f, --follow
        Output appended data as the file grows.
"""

SUBCOMMANDS_TEXT = """\
NAME
    systemctl - Control the systemd system and service manager

SYNOPSIS
    systemctl [OPTIONS...] COMMAND [UNIT...]

COMMANDS
    start UNIT...
        Start (activate) one or more units specified on the command line.

    stop UNIT...
        Stop (deactivate) one or more units specified on the command line.

    restart UNIT...
        Stop and then start one or more units.

    status [UNIT...|PID...]
        Show terse runtime status information about one or more units.

    enable UNIT...
        Enable one or more unit files.

    disable UNIT...
        Disable one or more unit files.

OPTIONS
    -t, --type=TYPE
        Argument to list-units.

    --no-pager
        Do not pipe output into a pager.
"""

MUTEX_GROUP_TEXT = """\
NAME
    journalctl - Query the systemd journal

SYNOPSIS
    journalctl {--system|--user} [OPTIONS...] [MATCHES...]

OPTIONS
    --system
        Show messages from system services and the kernel.

    --user
        Show messages from services of current user.
"""

MINIMAL_TEXT = """\
"""


# ---------------------------------------------------------------------------
# 1. Simple flag extraction
# ---------------------------------------------------------------------------

def test_parse_simple_flags():
    """Parser extracts simple boolean flags from OPTIONS section."""
    page = parse_man_text("grep", SIMPLE_OPTIONS_TEXT)
    long_names = {f.long_name for f in page.flags}
    assert "ignore-case" in long_names, f"long_names={long_names}"
    assert "line-number" in long_names
    assert "recursive" in long_names
    assert "files-with-matches" in long_names


def test_parse_simple_flags_short_names():
    """Parser captures short flag names alongside long names."""
    page = parse_man_text("grep", SIMPLE_OPTIONS_TEXT)
    by_long = {f.long_name: f for f in page.flags if f.long_name}
    assert by_long["ignore-case"].short_name == "i"
    assert by_long["line-number"].short_name == "n"
    assert by_long["recursive"].short_name == "r"


# ---------------------------------------------------------------------------
# 2. Flags with required args
# ---------------------------------------------------------------------------

def test_parse_flag_required_eq_arg():
    """Parser extracts required args in --long=VALUE format."""
    page = parse_man_text("tail", OPTIONS_WITH_ARGS_TEXT)
    by_long = {f.long_name: f for f in page.flags if f.long_name}
    assert "lines" in by_long, f"flags={list(by_long)}"
    lines_flag = by_long["lines"]
    assert lines_flag.arg_name is not None
    assert not lines_flag.arg_optional


def test_parse_flag_required_short_arg():
    """Parser extracts required args on short flags (-n NUM)."""
    page = parse_man_text("tail", OPTIONS_WITH_ARGS_TEXT)
    # The -n NUM pair: short_name="n", arg_name="NUM"
    n_flags = [f for f in page.flags if f.short_name == "n"]
    assert n_flags, "Expected a flag with short_name='n'"
    # arg_name should be captured
    assert any(f.arg_name is not None for f in n_flags)


# ---------------------------------------------------------------------------
# 3. Optional-arg flags (--color[=WHEN])
# ---------------------------------------------------------------------------

def test_parse_optional_arg_flag():
    """Parser marks optional-arg flags correctly."""
    page = parse_man_text("tail", OPTIONS_WITH_ARGS_TEXT)
    by_long = {f.long_name: f for f in page.flags if f.long_name}
    assert "color" in by_long, f"flags={list(by_long)}"
    color = by_long["color"]
    assert color.arg_optional is True
    assert color.arg_name is not None  # e.g. "WHEN"


# ---------------------------------------------------------------------------
# 4. Combined short + long flags
# ---------------------------------------------------------------------------

def test_parse_combined_short_long():
    """Parser combines short and long form onto a single ParsedFlag."""
    page = parse_man_text("tail", OPTIONS_WITH_ARGS_TEXT)
    by_long = {f.long_name: f for f in page.flags if f.long_name}
    assert "follow" in by_long
    follow = by_long["follow"]
    assert follow.short_name == "f"


# ---------------------------------------------------------------------------
# 5. Subcommand extraction
# ---------------------------------------------------------------------------

def test_parse_subcommands():
    """Parser extracts subcommands from a COMMANDS section."""
    page = parse_man_text("systemctl", SUBCOMMANDS_TEXT)
    names = {s.name for s in page.subcommands}
    assert "start" in names, f"subcommands={names}"
    assert "stop" in names
    assert "restart" in names
    assert "status" in names
    assert "enable" in names
    assert "disable" in names


def test_parse_subcommand_descriptions():
    """Subcommands carry a non-empty description."""
    page = parse_man_text("systemctl", SUBCOMMANDS_TEXT)
    by_name = {s.name: s for s in page.subcommands}
    assert by_name["start"].description, "start should have a description"


# ---------------------------------------------------------------------------
# 6. Mutually exclusive groups
# ---------------------------------------------------------------------------

def test_parse_mutex_groups():
    """Parser extracts mutually-exclusive groups from SYNOPSIS."""
    page = parse_man_text("journalctl", MUTEX_GROUP_TEXT)
    all_groups = page.mutually_exclusive_groups
    assert any(
        set(g) == {"--system", "--user"} or set(g) == {"system", "user"}
        for g in all_groups
    ), f"mutex_groups={all_groups}"


# ---------------------------------------------------------------------------
# 7. Positional extraction
# ---------------------------------------------------------------------------

def test_parse_required_positionals():
    """SYNOPSIS UPPERCASE words become positionals."""
    page = parse_man_text("grep", SIMPLE_OPTIONS_TEXT)
    names = {p.name for p in page.positionals}
    assert "PATTERN" in names or "FILE" in names, f"positionals={names}"


def test_parse_optional_positionals():
    """SYNOPSIS [WORD] becomes an optional positional."""
    page = parse_man_text("grep", SIMPLE_OPTIONS_TEXT)
    optional = [p for p in page.positionals if not p.required]
    # [FILE...] should appear as optional+repeatable
    assert any(p.name == "FILE" for p in optional), (
        f"positionals={page.positionals}"
    )


# ---------------------------------------------------------------------------
# 8. Flag deduplication
# ---------------------------------------------------------------------------

def test_flag_deduplication():
    """Flags appearing twice are deduplicated."""
    # Plant a duplicate by repeating the OPTIONS section content
    duplicate_text = """\
NAME
    foo - test

OPTIONS
    -v, --verbose
        Increase verbosity.

    -v, --verbose
        Increase verbosity (duplicate).
"""
    page = parse_man_text("foo", duplicate_text)
    verbose_flags = [f for f in page.flags if f.long_name == "verbose"]
    assert len(verbose_flags) == 1, (
        f"Expected exactly 1 'verbose' flag after dedup, got {len(verbose_flags)}"
    )


# ---------------------------------------------------------------------------
# 9. Graceful handling of empty / minimal text
# ---------------------------------------------------------------------------

def test_parse_empty_text():
    """Parsing empty text returns an empty ParsedManPage without raising."""
    page = parse_man_text("unknown", MINIMAL_TEXT)
    assert isinstance(page, ParsedManPage)
    assert page.flags == []
    assert page.subcommands == []
    assert page.positionals == []


def test_parse_no_options_section():
    """A page with no OPTIONS section returns empty flags list."""
    text = "NAME\n    foo - a tool\n\nDESCRIPTION\n    Does stuff.\n"
    page = parse_man_text("foo", text)
    assert page.flags == []


# ---------------------------------------------------------------------------
# 10. schema_entry_to_toolspec — WRITE floor for "read" ops
# ---------------------------------------------------------------------------

def _make_minimal_entry(permission_class: str, op_name: str = "status") -> dict:
    return {
        "binary": "testbin",
        "version_pin": "1.0",
        "version_source": "--version",
        "version_pattern": r"(\d+\.\d+)",
        "description": "Test tool",
        "ops": [
            {
                "op_name": op_name,
                "permission_class": permission_class,
                "description": f"Test op ({permission_class})",
                "args": [
                    {
                        "name": "unit",
                        "type": "str",
                        "required": False,
                        "description": "unit arg",
                        "default": None,
                    }
                ],
            }
        ],
    }


def test_read_op_upgraded_to_write():
    """A 'read' permission_class in the JSON is upgraded to WRITE when loaded."""
    entry = _make_minimal_entry("read", "status")
    spec = schema_entry_to_toolspec("testbin", entry, unverified=False)
    op = spec.ops["status"]
    assert op.permission_class == OpClass.WRITE, (
        f"Expected WRITE floor for 'read' op, got {op.permission_class}"
    )


def test_write_op_stays_write():
    """A 'write' op stays WRITE."""
    entry = _make_minimal_entry("write", "start")
    spec = schema_entry_to_toolspec("testbin", entry, unverified=False)
    op = spec.ops["start"]
    assert op.permission_class == OpClass.WRITE


# ---------------------------------------------------------------------------
# 11. schema_entry_to_toolspec — DESTRUCTIVE stays DESTRUCTIVE
# ---------------------------------------------------------------------------

def test_destructive_op_stays_destructive():
    """A 'destructive' op is never downgraded."""
    entry = _make_minimal_entry("destructive", "remove")
    spec = schema_entry_to_toolspec("testbin", entry, unverified=False)
    op = spec.ops["remove"]
    assert op.permission_class == OpClass.DESTRUCTIVE, (
        f"Expected DESTRUCTIVE, got {op.permission_class}"
    )


# ---------------------------------------------------------------------------
# 12. Unverified tool — description annotated, READ upgraded
# ---------------------------------------------------------------------------

def test_unverified_tool_description():
    """Unverified tools carry [unverified] in their description."""
    entry = _make_minimal_entry("read")
    spec = schema_entry_to_toolspec("testbin", entry, unverified=True)
    assert "[unverified]" in spec.description, (
        f"Expected [unverified] in description: {spec.description!r}"
    )


def test_unverified_read_upgraded_to_write():
    """Unverified read ops are upgraded to WRITE."""
    entry = _make_minimal_entry("read")
    spec = schema_entry_to_toolspec("testbin", entry, unverified=True)
    op = list(spec.ops.values())[0]
    assert op.permission_class == OpClass.WRITE


def test_unverified_destructive_stays_destructive():
    """Unverified destructive ops stay DESTRUCTIVE."""
    entry = _make_minimal_entry("destructive")
    spec = schema_entry_to_toolspec("testbin", entry, unverified=True)
    op = list(spec.ops.values())[0]
    assert op.permission_class == OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# 13. load_artifact loads the checked-in artifact
# ---------------------------------------------------------------------------

def test_load_artifact_no_error():
    """load_artifact() loads the checked-in manpages.v1.json without raising."""
    data = load_artifact()
    assert isinstance(data, dict)
    assert "tools" in data
    assert "schema_version" in data


# ---------------------------------------------------------------------------
# 14. Artifact contains expected tool names
# ---------------------------------------------------------------------------

def test_artifact_contains_expected_tools():
    """The artifact covers the curated Radagon sysadmin binary list."""
    data = load_artifact()
    tools = set(data["tools"].keys())
    expected = {
        "systemctl", "dnf", "journalctl", "firewall-cmd",
        "ip", "useradd", "userdel", "git", "tar", "ps",
    }
    missing = expected - tools
    assert not missing, f"Missing tools in artifact: {missing}"


# ---------------------------------------------------------------------------
# 15. All artifact ops have valid permission_class
# ---------------------------------------------------------------------------

def test_artifact_permission_classes_valid():
    """Every op in the artifact declares a valid permission_class."""
    data = load_artifact()
    valid = {"read", "write", "destructive"}
    for tool_name, tool_data in data["tools"].items():
        for op in tool_data.get("ops", []):
            pc = op.get("permission_class")
            assert pc in valid, (
                f"Tool '{tool_name}' op '{op['op_name']}' has invalid "
                f"permission_class: {pc!r}"
            )


# ---------------------------------------------------------------------------
# 16. version_matches() prefix logic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pinned,detected,expected", [
    ("255", "255", True),
    ("255", "255.2", True),
    ("255", "255.2.3", True),
    ("4", "4.18.2", True),
    ("2", "2.43.0", True),
    ("255", "254", False),
    ("255", "256", False),
    ("255", None, False),
    ("", "255", False),           # empty pinned -> no match
    ("255", "2550", False),       # "255" should not match "2550"
])
def test_version_matches(pinned, detected, expected):
    assert version_matches(pinned, detected) == expected, (
        f"version_matches({pinned!r}, {detected!r}) expected {expected}"
    )


# ---------------------------------------------------------------------------
# 17. Registered tool from artifact has WRITE+ gate
# ---------------------------------------------------------------------------

def test_register_tool_from_artifact_write_floor():
    """Tools loaded from the artifact register with WRITE minimum gate."""
    data = load_artifact()
    # Pick systemctl — it has both read and write ops.
    entry = data["tools"]["systemctl"]
    spec = schema_entry_to_toolspec("systemctl", entry, unverified=False)

    # All ops must be >= WRITE (i.e. WRITE or DESTRUCTIVE)
    for op_name, op_spec in spec.ops.items():
        assert op_spec.permission_class in (OpClass.WRITE, OpClass.DESTRUCTIVE), (
            f"systemctl.{op_name} has permission_class={op_spec.permission_class}; "
            f"expected WRITE or DESTRUCTIVE (ALWAYS-GATED floor)"
        )


def test_register_tool_in_registry():
    """A tool built from the artifact registers cleanly in a ToolRegistry."""
    data = load_artifact()
    entry = data["tools"]["dnf"]
    spec = schema_entry_to_toolspec("dnf", entry, unverified=False)

    registry = ToolRegistry()
    registry.register(spec)  # must not raise
    assert "dnf" in registry.list_tools()


def test_registered_tool_op_accessible():
    """Registered tool ops are accessible via registry.permission_class_for."""
    data = load_artifact()
    entry = data["tools"]["dnf"]
    spec = schema_entry_to_toolspec("dnf", entry, unverified=False)

    registry = ToolRegistry()
    registry.register(spec)

    pc = registry.permission_class_for("dnf", "install")
    assert pc == OpClass.WRITE

    pc_remove = registry.permission_class_for("dnf", "remove")
    assert pc_remove == OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# 18. Version mismatch marks tool unverified and still registers
# ---------------------------------------------------------------------------

def test_version_mismatch_marks_unverified():
    """A fabricated version mismatch produces an [unverified] description."""
    entry = _make_minimal_entry("read", "status")
    # Simulate mismatch by passing unverified=True (what the loader does on drift)
    spec = schema_entry_to_toolspec("testbin", entry, unverified=True)
    assert "[unverified]" in spec.description

    # The tool still registers without error
    registry = ToolRegistry()
    registry.register(spec)
    assert "testbin" in registry.list_tools()


def test_version_mismatch_read_op_upgraded():
    """On version mismatch, a 'read' op is upgraded to WRITE (not ALLOW)."""
    entry = _make_minimal_entry("read", "status")
    spec = schema_entry_to_toolspec("testbin", entry, unverified=True)
    op = spec.ops["status"]
    assert op.permission_class in (OpClass.WRITE, OpClass.DESTRUCTIVE), (
        f"Expected WRITE+ after version mismatch, got {op.permission_class}"
    )


# ---------------------------------------------------------------------------
# I6: No tier/product names in descriptions
# ---------------------------------------------------------------------------

def test_no_tier_names_in_artifact_descriptions():
    """Artifact descriptions contain no tier/product names (I6)."""
    data = load_artifact()
    tier_names = re.compile(
        r'\b(Marika|Radagon|Radahn|Starscourge|Erdtree)\b', re.IGNORECASE
    )
    for tool_name, tool_data in data["tools"].items():
        desc = tool_data.get("description", "")
        assert not tier_names.search(desc), (
            f"Tier name found in tool '{tool_name}' description: {desc!r}"
        )
        for op in tool_data.get("ops", []):
            op_desc = op.get("description", "")
            assert not tier_names.search(op_desc), (
                f"Tier name found in tool '{tool_name}' op '{op['op_name']}' "
                f"description: {op_desc!r}"
            )


# ---------------------------------------------------------------------------
# ArgSpec types are correctly mapped
# ---------------------------------------------------------------------------

def test_argspec_types_mapped_correctly():
    """Bool/int/str/list type strings from JSON map to correct Python types."""
    data = load_artifact()
    # journalctl has int (lines), bool (follow), str (unit)
    entry = data["tools"]["journalctl"]
    spec = schema_entry_to_toolspec("journalctl", entry, unverified=False)
    op = spec.ops["_main"]
    by_name = {a.name: a for a in op.args}
    assert by_name["follow"].type is bool
    assert by_name["lines"].type is int
    assert by_name["unit"].type is str
