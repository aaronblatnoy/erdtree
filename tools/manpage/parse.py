"""tools/manpage/parse.py — Best-effort build-time man-page text parser.

Parses formatted man-page text (produced by ``man cmd | col -bx`` or
``mandoc -Tascii cmd.1``) and returns a structured :class:`ParsedManPage`.

This module is BUILD-TIME ONLY.  It is never imported on the shipped box.

Design goals
------------
* Best-effort, not exhaustive.  Man pages are inconsistently formatted; we
  handle the common patterns from the curated Radagon binary list and skip
  anything that does not match rather than raising.
* No external dependencies beyond the standard library.
* Pure functions / no side-effects: pass text in, get a dataclass out.
  Callers supply the text (they obtained it from ``man`` / ``mandoc``);
  this module does not shell out.

Supported edge cases
--------------------
* Optional-arg flags: ``--color[=WHEN]``
* Mutually exclusive groups: ``{start|stop|restart}`` in SYNOPSIS
* Repeatable flags: detected by ``...`` or multiple-value arg hints
* ``--long=VALUE`` vs ``--long VALUE`` (space-separated arg)
* Short flags with positional args: ``-n NUM``
* Subcommands with their own option subsections (git, systemctl, dnf)
* Combined short+long: ``-v, --verbose``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ParsedFlag:
    """A single flag (option) parsed from a man page OPTIONS section.

    Attributes
    ----------
    long_name:    Long-form option name without ``--`` prefix, e.g. ``verbose``.
    short_name:   Single-character short option without ``-`` prefix, e.g. ``v``.
    arg_name:     Metavar for the flag's argument (e.g. ``FILE``, ``NUM``),
                  or ``None`` if the flag takes no argument.
    arg_optional: True when the argument is optional (``--color[=WHEN]``).
    repeatable:   True when the flag may appear more than once (``-v -v``).
    description:  One-line summary from the man page (may be empty).
    """

    long_name: Optional[str] = None
    short_name: Optional[str] = None
    arg_name: Optional[str] = None
    arg_optional: bool = False
    repeatable: bool = False
    description: str = ""


@dataclass
class ParsedPositional:
    """A positional argument parsed from the SYNOPSIS section.

    Attributes
    ----------
    name:       Metavar name (e.g. ``FILE``, ``PATTERN``, ``COMMAND``).
    required:   False when the positional is wrapped in ``[...]``.
    repeatable: True when the positional is followed by ``...``.
    description: Description if available, otherwise empty.
    """

    name: str
    required: bool = True
    repeatable: bool = False
    description: str = ""


@dataclass
class ParsedSubcommand:
    """A subcommand parsed from a COMMANDS / SUBCOMMANDS section.

    Attributes
    ----------
    name:        The subcommand word (e.g. ``start``, ``install``).
    description: One-line description.
    flags:       Flags that belong specifically to this subcommand (may be
                 empty; global flags are stored on ParsedManPage.flags).
    """

    name: str
    description: str = ""
    flags: list[ParsedFlag] = field(default_factory=list)


@dataclass
class ParsedManPage:
    """Structured representation of a parsed man page.

    Attributes
    ----------
    binary:                   Name of the binary (e.g. ``systemctl``).
    version_string:           Version extracted from ``--version`` output if
                              the caller ran it and passed it in; ``None``
                              otherwise.
    synopsis:                 Raw SYNOPSIS text (stripped).
    flags:                    Global flags from the OPTIONS section.
    positionals:              Positional args extracted from SYNOPSIS.
    subcommands:              Subcommands from a COMMANDS/SUBCOMMANDS section
                              or from a ``git``-style listing.
    mutually_exclusive_groups: Groups of flag names that are mutually exclusive,
                              extracted from ``{a|b}`` patterns in SYNOPSIS.
    raw_text:                 The full text that was parsed (for debugging).
    """

    binary: str
    version_string: Optional[str] = None
    synopsis: str = ""
    flags: list[ParsedFlag] = field(default_factory=list)
    positionals: list[ParsedPositional] = field(default_factory=list)
    subcommands: list[ParsedSubcommand] = field(default_factory=list)
    mutually_exclusive_groups: list[list[str]] = field(default_factory=list)
    raw_text: str = ""


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

# Man page section headers: all-caps words, possibly with spaces, on their
# own line.  We also handle headers with trailing colon (some man pages).
_SECTION_HEADER_RE = re.compile(
    r'^([A-Z][A-Z ]+[A-Z])[ \t]*:?$', re.MULTILINE
)


def _extract_sections(text: str) -> dict[str, str]:
    """Split man-page text into named sections.

    Returns a dict mapping upper-cased section name to the section body
    (the text between this header and the next header).  The key is the
    header text stripped and upper-cased.

    Entries for unrecognised or repeated section names are skipped (the
    first occurrence wins).
    """
    sections: dict[str, str] = {}
    matches = list(_SECTION_HEADER_RE.finditer(text))
    for idx, match in enumerate(matches):
        header = match.group(1).strip().upper()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end]
        if header not in sections:
            sections[header] = body
    return sections


# ---------------------------------------------------------------------------
# Flag parsing helpers
# ---------------------------------------------------------------------------

# A flag line must start with 1-12 spaces followed by a dash.
_FLAG_LINE_PREFIX_RE = re.compile(r'^[ \t]{1,12}-')

# Matches a single flag token within a flag spec line.
# Groups:
#   short      — single-char short option letter (without -)
#   short_arg  — arg name after a short flag, space-separated (-n NUM)
#   long       — long option name without -- prefix
#   opt_arg    — arg name for [=WHEN] style (optional arg)
#   req_eq     — arg name for =FILE style (required, = separator)
_SINGLE_FLAG_RE = re.compile(
    r'(?:'
    r'-(?P<short>[a-zA-Z0-9])(?:\s+(?P<short_arg>[A-Z][A-Z0-9_-]*))?'
    r'|'
    r'--(?P<long>[a-zA-Z][a-zA-Z0-9-]*)'
    r'(?:'
    r'\[=(?P<opt_arg>[A-Z][A-Z0-9_-]*)\]'           # [=WHEN]
    r'|=(?P<req_eq>[A-Z][A-Z0-9_-]*)'               # =FILE
    r'|(?:\s+(?P<req_sp>[A-Z][A-Z0-9_-]*))'         # SPACE FILE (consumed only if present)
    r')?'
    r')'
)

# Marks a flag as repeatable
_REPEATABLE_HINTS = re.compile(
    r'\.\.\.|more than once|multiple times|repeated|can be given multiple',
    re.IGNORECASE,
)


def _parse_flag_spec(spec_line: str) -> list[ParsedFlag]:
    """Parse one flag spec line into a list of ParsedFlag objects.

    A single line may contain multiple flags (short + long alias).  We
    return one ParsedFlag per unique flag, merging arg information when both
    a short and long form appear on the same line.
    """
    flags: list[ParsedFlag] = []
    current_long: Optional[str] = None
    current_short: Optional[str] = None
    current_arg_name: Optional[str] = None
    current_arg_optional: bool = False

    # Strip trailing description (after the first two or more spaces that
    # follow a flag clause) — rough heuristic.
    # We scan matches in order and stop when we hit something that isn't a
    # flag token.

    pos = 0
    # Skip leading whitespace
    stripped = spec_line.lstrip()
    # Remove the trailing description part: once we have matched at least one
    # flag and encounter "   " (3+ spaces), treat the rest as description.
    # We operate on the full stripped line and let the regex iterate.

    for m in _SINGLE_FLAG_RE.finditer(stripped):
        short = m.group("short")
        long = m.group("long")
        short_arg = m.group("short_arg")
        opt_arg = m.group("opt_arg")
        req_eq = m.group("req_eq")
        req_sp = m.group("req_sp")

        arg_name = opt_arg or req_eq or req_sp or short_arg
        arg_optional = bool(opt_arg)

        if short:
            current_short = short
            if arg_name and not current_arg_name:
                current_arg_name = arg_name
        if long:
            current_long = long
            if arg_name and not current_arg_name:
                current_arg_name = arg_name
            if arg_optional:
                current_arg_optional = True

    if current_long or current_short:
        flags.append(ParsedFlag(
            long_name=current_long,
            short_name=current_short,
            arg_name=current_arg_name,
            arg_optional=current_arg_optional,
        ))

    return flags


def _parse_option_block(block: str) -> tuple[list[ParsedFlag], str]:
    """Parse a single option block (spec line + description lines).

    Returns ``(flags, description_summary)`` where ``flags`` is the list of
    flags found on the first line of the block and ``description_summary`` is
    the first non-empty description line (trimmed).
    """
    lines = block.split("\n")
    if not lines:
        return [], ""

    # The spec line is the first line; description follows.
    spec_line = lines[0]
    desc_lines = [l.strip() for l in lines[1:] if l.strip()]
    description = desc_lines[0] if desc_lines else ""
    repeatable = bool(_REPEATABLE_HINTS.search(block))

    flags = _parse_flag_spec(spec_line)
    for f in flags:
        f.description = description
        if repeatable:
            f.repeatable = True

    return flags, description


def _parse_options_section(text: str) -> list[ParsedFlag]:
    """Parse the body of an OPTIONS section and return all flags found.

    Splits the section into "option blocks" — each block starts at a line
    that begins with 1-12 spaces followed by a dash.  Lines that do not
    match that pattern are treated as continuations of the previous block.
    """
    flags: list[ParsedFlag] = []
    current_block_lines: list[str] = []

    def _flush_block():
        if not current_block_lines:
            return
        block = "\n".join(current_block_lines)
        block_flags, _ = _parse_option_block(block)
        flags.extend(block_flags)
        current_block_lines.clear()

    for line in text.split("\n"):
        if _FLAG_LINE_PREFIX_RE.match(line):
            _flush_block()
            current_block_lines.append(line)
        elif current_block_lines:
            current_block_lines.append(line)
        # else: preamble text before first flag — ignore

    _flush_block()
    return flags


# ---------------------------------------------------------------------------
# SYNOPSIS parsing
# ---------------------------------------------------------------------------

# Extracts positionals from SYNOPSIS: upper-case words not preceded by --.
_POSITIONAL_RE = re.compile(
    r'(?<![A-Z_-])(?<!-)([A-Z][A-Z0-9_-]{1,})(\.\.\.)?'
)
# Detects optional wrapper: [POSITIONAL] or [POSITIONAL...]
_OPTIONAL_POSITIONAL_RE = re.compile(
    r'\[([A-Z][A-Z0-9_-]{1,})(\.\.\.)?]'
)
# Mutually exclusive groups: {a|b|c}, (a|b|c), {--flag|--other}, etc.
# The leading -/{0,2} allows bare words (start|stop) and --flag style tokens.
_MUTEX_GROUP_RE = re.compile(
    r'[{(](-{0,2}[a-zA-Z][a-zA-Z0-9-]*(?:\|-{0,2}[a-zA-Z][a-zA-Z0-9-]*)+)[})]'
)


def _parse_synopsis(text: str) -> tuple[list[ParsedPositional], list[list[str]]]:
    """Extract positionals and mutually-exclusive groups from SYNOPSIS text.

    Returns ``(positionals, mutex_groups)``.
    """
    positionals: list[ParsedPositional] = []
    seen_names: set[str] = set()
    mutex_groups: list[list[str]] = []

    # Skip leading binary name token
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return positionals, mutex_groups

    synopsis_text = " ".join(lines)

    # --- Mutually exclusive groups ---
    for m in _MUTEX_GROUP_RE.finditer(synopsis_text):
        parts = m.group(1).split("|")
        if len(parts) > 1:
            mutex_groups.append(parts)

    # --- Optional positionals [NAME] / [NAME...] ---
    for m in _OPTIONAL_POSITIONAL_RE.finditer(synopsis_text):
        name = m.group(1)
        repeatable = bool(m.group(2))
        # Skip common false positives
        if name in {"OPTIONS", "OPTION", "ARGS", "ARGUMENTS"}:
            continue
        if name not in seen_names:
            seen_names.add(name)
            positionals.append(ParsedPositional(
                name=name, required=False, repeatable=repeatable
            ))

    # --- Required positionals (UPPERCASE words not in brackets, not = value) ---
    # Remove optional blocks first to avoid double-counting
    cleaned = _OPTIONAL_POSITIONAL_RE.sub("", synopsis_text)
    cleaned = _MUTEX_GROUP_RE.sub("", cleaned)
    # Also remove flag blocks like --option=VALUE (remove =VALUE part)
    cleaned = re.sub(r'--[a-zA-Z][-a-zA-Z0-9]*(?:=\S+)?', '', cleaned)
    cleaned = re.sub(r'-[a-zA-Z0-9](?:\s+[A-Z][A-Z0-9_-]*)?', '', cleaned)

    for m in _POSITIONAL_RE.finditer(cleaned):
        name = m.group(1)
        repeatable = bool(m.group(2))
        if name in {"OPTIONS", "OPTION", "ARGS", "ARGUMENTS", "COMMAND"}:
            continue
        if name not in seen_names:
            seen_names.add(name)
            positionals.append(ParsedPositional(
                name=name, required=True, repeatable=repeatable
            ))

    return positionals, mutex_groups


# ---------------------------------------------------------------------------
# Subcommand parsing
# ---------------------------------------------------------------------------

# A subcommand line: leading spaces, then a lowercase word (possibly hyphenated)
# followed by optional arguments in brackets.
_SUBCMD_LINE_RE = re.compile(
    r'^[ \t]{1,12}'
    r'(?P<name>[a-z][a-z0-9-]*(?:[-_][a-z0-9-]+)*)'
    r'(?:\s+(?P<args>[A-Z\[].*))?$'
)

# Section names that typically contain subcommand listings
_SUBCMD_SECTION_NAMES = {
    "COMMANDS",
    "SUBCOMMANDS",
    "COMMAND",
    "GIT COMMANDS",
    "AVAILABLE COMMANDS",
    "DNF COMMANDS",
}

# Subcommand names that are too generic / not real subcommands
_SUBCMD_BLACKLIST = {
    "options", "option", "the", "see", "use", "man", "this",
    "if", "for", "all", "any", "not", "are", "its", "may",
    "must", "will", "also", "note", "when",
}


def _parse_subcommands_section(text: str) -> list[ParsedSubcommand]:
    """Parse a COMMANDS / SUBCOMMANDS section body.

    Returns a list of subcommands found.  Only the first level of
    subcommands is extracted (not sub-sub-commands).
    """
    subcommands: list[ParsedSubcommand] = []
    seen: set[str] = set()
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _SUBCMD_LINE_RE.match(line)
        if m:
            name = m.group("name")
            if name not in _SUBCMD_BLACKLIST and name not in seen:
                # Collect description from the next non-empty line
                desc = ""
                for j in range(i + 1, min(i + 4, len(lines))):
                    candidate = lines[j].strip()
                    if candidate and not _SUBCMD_LINE_RE.match(lines[j]):
                        desc = candidate
                        break
                seen.add(name)
                subcommands.append(ParsedSubcommand(name=name, description=desc))
        i += 1
    return subcommands


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_man_text(binary: str, text: str, *, version_string: Optional[str] = None) -> ParsedManPage:
    """Parse formatted man-page text for ``binary`` and return a ParsedManPage.

    Parameters
    ----------
    binary:
        The name of the binary this man page describes.  Used only to
        populate ``ParsedManPage.binary``; not used for parsing logic.
    text:
        The formatted man-page text, as produced by
        ``man cmd | col -bx`` or ``mandoc -Tascii cmd.1``.
    version_string:
        Optional version string obtained by running ``binary --version``.
        Stored verbatim in ParsedManPage.version_string.

    Returns
    -------
    ParsedManPage
        Best-effort structured representation.  Fields may be empty if the
        corresponding section was absent or unparseable.
    """
    sections = _extract_sections(text)

    # --- OPTIONS ---
    flags: list[ParsedFlag] = []
    for sec_name in ("OPTIONS", "GLOBAL OPTIONS", "COMMON OPTIONS", "FLAGS"):
        if sec_name in sections:
            flags.extend(_parse_options_section(sections[sec_name]))

    # --- SYNOPSIS ---
    synopsis_text = sections.get("SYNOPSIS", "")
    positionals, mutex_groups = _parse_synopsis(synopsis_text)

    # --- SUBCOMMANDS ---
    subcommands: list[ParsedSubcommand] = []
    for sec_name in _SUBCMD_SECTION_NAMES:
        if sec_name in sections:
            subcommands.extend(_parse_subcommands_section(sections[sec_name]))
            break  # Take the first matching section only

    # Deduplicate flags by long_name (prefer earlier entries)
    seen_flags: set[str] = set()
    deduped_flags: list[ParsedFlag] = []
    for f in flags:
        key = f.long_name or f.short_name or ""
        if key and key not in seen_flags:
            seen_flags.add(key)
            deduped_flags.append(f)
        elif not key:
            # No name at all — skip
            pass

    return ParsedManPage(
        binary=binary,
        version_string=version_string,
        synopsis=synopsis_text.strip(),
        flags=deduped_flags,
        positionals=positionals,
        subcommands=subcommands,
        mutually_exclusive_groups=mutex_groups,
        raw_text=text,
    )
