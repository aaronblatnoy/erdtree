"""tools/manpage/generate_schemas.py — Man-page schema generator and boot-time loader.

This module has two responsibilities:

BUILD TIME (developer / CI only):
    Convert :class:`~tools.manpage.parse.ParsedManPage` objects into the frozen
    ``OpSpec``/``ArgSpec`` shape and write the versioned JSON artifact at
    ``models/schemas/manpages.vN.json``.  Run as::

        python -m tools.manpage.generate_schemas --output models/schemas/manpages.v1.json

BOOT TIME (on the shipped box):
    :func:`load_into_registry` reads the pre-built JSON artifact and registers
    the described tools into a :class:`core.tools.ToolRegistry` as ALWAYS-GATED
    (minimum ``WRITE`` permission class, regardless of the natural class stored
    in the JSON).  It also performs NEVRA/``--version`` drift detection: if the
    installed binary's version differs from the pinned version, the tool is
    registered with all ops forced to at least ``WRITE`` and its description is
    annotated ``[unverified]``.

Invariants
----------
I1  No egress — this module never calls an external network.
I2  No AI/LLM/model/agent language in any user-facing string.
I3  Generated tools land on the WRITE floor; destructive shapes stay DESTRUCTIVE.
I6  No tier/product names appear in generated descriptions.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

# Absolute path to the default artifact, relative to this file's package root.
_DEFAULT_ARTIFACT = (
    Path(__file__).resolve().parent.parent.parent
    / "models" / "schemas" / "manpages.v1.json"
)


# ---------------------------------------------------------------------------
# Type string <-> Python type mapping  (JSON-safe)
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[str, type] = {
    "str": str,
    "int": int,
    "bool": bool,
    "list": list,
}
_TYPE_REVERSE: dict[type, str] = {v: k for k, v in _TYPE_MAP.items()}


def _type_to_str(t: type) -> str:
    return _TYPE_REVERSE.get(t, "str")


def _str_to_type(s: str) -> type:
    return _TYPE_MAP.get(s, str)


# ---------------------------------------------------------------------------
# Permission class helpers
# ---------------------------------------------------------------------------

# Import lazily so this module can be imported from pure-Python builds that
# may not have the full core package on sys.path (e.g. offline schema regen).
try:
    from core.agent.permissions import OpClass
    from core.tools import (
        ArgSpec,
        OpSpec,
        ToolResult,
        ToolSpec,
        run_subprocess,
    )
    _CORE_AVAILABLE = True
except ImportError:
    _CORE_AVAILABLE = False
    OpClass = None  # type: ignore[assignment]

_PERM_STR_MAP = {
    "read": "read",
    "write": "write",
    "destructive": "destructive",
}


def _opclass_from_str(s: str):  # returns OpClass or str depending on availability
    if _CORE_AVAILABLE:
        return OpClass(s)
    return s


def _opclass_to_str(oc) -> str:
    if _CORE_AVAILABLE and isinstance(oc, OpClass):
        return oc.value
    return str(oc)


# ---------------------------------------------------------------------------
# Permission class heuristic
# ---------------------------------------------------------------------------

# Keywords in op names that indicate destructive operations.
_DESTRUCTIVE_KEYWORDS = re.compile(
    r'\b(remove|delete|destroy|wipe|format|mkfs|rm|purge|erase|fdisk|parted'
    r'|userdel|groupdel|dd|nuke|truncate|drop)\b',
    re.IGNORECASE,
)
# Keywords in op names that indicate read-only operations.
_READ_KEYWORDS = re.compile(
    r'\b(status|list|show|get|query|check|info|ls|cat|grep|find|ps|top|ss'
    r'|stat|df|du|lsblk|log|journal|read|view|display|print|help|version)\b',
    re.IGNORECASE,
)


def _infer_permission_class(op_name: str, description: str = "") -> str:
    """Infer a permission class string from an op name + description.

    Returns one of ``"read"``, ``"write"``, or ``"destructive"``.
    The result is a NATURAL class; the loader upgrades ``"read"`` -> ``"write"``
    when registering man-page tools (ALWAYS-GATED floor).
    """
    combined = f"{op_name} {description}".lower()
    if _DESTRUCTIVE_KEYWORDS.search(combined):
        return "destructive"
    if _READ_KEYWORDS.search(op_name):
        return "read"
    return "write"


# ---------------------------------------------------------------------------
# Schema dict shape (what goes into/comes from the JSON artifact)
# ---------------------------------------------------------------------------

@dataclass
class ArgEntry:
    """JSON-serialisable arg descriptor."""
    name: str
    type: str           # "str" | "int" | "bool" | "list"
    required: bool = False
    description: str = ""
    default: Any = None


@dataclass
class OpEntry:
    """JSON-serialisable op descriptor."""
    op_name: str
    permission_class: str   # "read" | "write" | "destructive"
    description: str = ""
    args: list[ArgEntry] = field(default_factory=list)


@dataclass
class ToolEntry:
    """JSON-serialisable tool descriptor."""
    binary: str
    version_pin: str            # e.g. "255" or "2.43.0"
    version_source: str         # "--version" or "rpm-q"
    version_pattern: str        # regex to extract version from --version output
    description: str = ""
    ops: list[OpEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ParsedManPage -> schema dict conversion
# ---------------------------------------------------------------------------

def parsed_to_schema(
    parsed,                     # ParsedManPage
    curated_ops: Optional[list[OpEntry]] = None,
) -> ToolEntry:
    """Convert a :class:`~tools.manpage.parse.ParsedManPage` to a ToolEntry.

    ``curated_ops`` may be supplied to override the auto-generated ops list
    (used for the pre-curated artifact).  When absent, ops are synthesized
    from the parsed subcommands (one op per subcommand) or from a single
    ``_main`` op (no subcommands).

    The natural permission class is inferred heuristically; the loader
    upgrades ``"read"`` to ``"write"`` when registering (ALWAYS-GATED floor).
    """
    if curated_ops is not None:
        ops = curated_ops
    elif parsed.subcommands:
        ops = []
        for sc in parsed.subcommands:
            perm = _infer_permission_class(sc.name, sc.description)
            args = [
                ArgEntry(
                    name=_flag_to_arg_name(f),
                    type="bool" if f.arg_name is None else _infer_arg_type(f.arg_name),
                    required=False,
                    description=f.description,
                    default=False if f.arg_name is None else None,
                )
                for f in (parsed.flags + sc.flags)
            ]
            ops.append(OpEntry(
                op_name=sc.name,
                permission_class=perm,
                description=sc.description,
                args=args,
            ))
    else:
        # Flat tool: one _main op, all flags become args
        perm = _infer_permission_class(parsed.binary)
        args = [
            ArgEntry(
                name=_flag_to_arg_name(f),
                type="bool" if f.arg_name is None else _infer_arg_type(f.arg_name),
                required=False,
                description=f.description,
                default=False if f.arg_name is None else None,
            )
            for f in parsed.flags
        ]
        ops = [OpEntry(op_name="_main", permission_class=perm, args=args)]

    return ToolEntry(
        binary=parsed.binary,
        version_pin="",
        version_source="--version",
        version_pattern=r"(\d+\.\d+)",
        description=f"Man-page derived schema for {parsed.binary}",
        ops=ops,
    )


def _flag_to_arg_name(flag) -> str:
    """Derive a Python-identifier arg name from a ParsedFlag."""
    if flag.long_name:
        return flag.long_name.replace("-", "_")
    if flag.short_name:
        return f"opt_{flag.short_name}"
    return "unknown"


def _infer_arg_type(arg_name: Optional[str]) -> str:
    """Infer JSON arg type string from metavar name."""
    if arg_name is None:
        return "bool"
    upper = arg_name.upper()
    if upper in {"NUM", "N", "COUNT", "SIZE", "PORT", "LINES", "SECONDS"}:
        return "int"
    if upper in {"FILES", "PATHS", "UNITS", "SERVICES", "PACKAGES"}:
        return "list"
    return "str"


# ---------------------------------------------------------------------------
# Artifact I/O
# ---------------------------------------------------------------------------

def emit_artifact(
    tool_entries: dict[str, ToolEntry],
    output_path: Path | str,
    *,
    schema_version: int = 1,
) -> None:
    """Serialize ``tool_entries`` to the versioned JSON artifact.

    Parameters
    ----------
    tool_entries:
        Mapping of logical tool name -> ToolEntry.
    output_path:
        Destination path for the JSON file.
    schema_version:
        Integer schema version embedded in the file (default 1).
    """
    import datetime

    doc = {
        "schema_version": schema_version,
        "generated_at": datetime.date.today().isoformat(),
        "description": (
            "Curated man-page derived tool schemas for Radagon sysadmin "
            "binaries. Build-time artifact; never parsed at runtime on the "
            "shipped box."
        ),
        "tools": {},
    }
    for name, entry in tool_entries.items():
        doc["tools"][name] = {
            "binary": entry.binary,
            "version_pin": entry.version_pin,
            "version_source": entry.version_source,
            "version_pattern": entry.version_pattern,
            "description": entry.description,
            "ops": [
                {
                    "op_name": op.op_name,
                    "permission_class": op.permission_class,
                    "description": op.description,
                    "args": [
                        {
                            "name": arg.name,
                            "type": arg.type,
                            "required": arg.required,
                            "description": arg.description,
                            "default": arg.default,
                        }
                        for arg in op.args
                    ],
                }
                for op in entry.ops
            ],
        }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def load_artifact(artifact_path: Path | str | None = None) -> dict:
    """Load and return the raw JSON artifact as a dict.

    Raises :class:`FileNotFoundError` if the artifact is missing.
    """
    path = Path(artifact_path) if artifact_path else _DEFAULT_ARTIFACT
    if not path.exists():
        raise FileNotFoundError(f"Man-page schema artifact not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------

def detect_version(binary: str, *, version_pattern: str = r"(\d+[\.\d]*)") -> Optional[str]:
    """Run ``binary --version`` and extract the version string.

    Returns the first regex match group from the output, or ``None`` if the
    binary is not found or the pattern does not match.

    This is a READ operation and never modifies system state.  It is called
    at boot time with a short timeout to avoid blocking startup.
    """
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout + result.stderr
        m = re.search(version_pattern, output)
        if m:
            return m.group(1)
        # Fallback: first number-like token on first line
        first_line = output.split("\n")[0] if output else ""
        m2 = re.search(r"(\d+[\.\d]*)", first_line)
        return m2.group(1) if m2 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def version_matches(pinned: str, detected: Optional[str]) -> bool:
    """Return True if the detected version is compatible with the pinned version.

    The comparison is prefix-based: the detected version must START WITH the
    pinned prefix.  This means ``pinned="255"`` matches ``detected="255.1.2"``.
    An absent detected version (binary not found) never matches.
    """
    if detected is None or not pinned:
        return False
    # Exact match or prefix match (e.g. "255" matches "255.2")
    return detected == pinned or detected.startswith(pinned + ".")


# ---------------------------------------------------------------------------
# ToolSpec factory from a schema entry dict
# ---------------------------------------------------------------------------

def _make_execute(binary: str, has_subcommands: bool) -> Callable:
    """Return a generic execute callable for a man-page-derived ToolSpec.

    The callable constructs a minimal argv from the binary name, optional
    subcommand op name, and provided args.  This is intentionally conservative:
    it only adds flags that the caller explicitly sets to non-default values.
    Boolean args are rendered as bare ``--flag``; string/int args are rendered
    as ``--flag VALUE``; list args are rendered as repeated ``--flag ITEM``.

    Since all man-page tools are ALWAYS-GATED, this execute function will only
    be called after the permission gate has confirmed the operation.
    """
    def execute(op: str, args: dict[str, Any]) -> ToolResult:  # type: ignore[name-defined]
        cmd = [binary]
        if has_subcommands and op != "_main":
            cmd.append(op)
        for key, value in args.items():
            flag = "--" + key.replace("_", "-")
            if isinstance(value, bool):
                if value:
                    cmd.append(flag)
            elif isinstance(value, list):
                for item in value:
                    cmd.extend([flag, str(item)])
            elif value is not None:
                cmd.extend([flag, str(value)])
        return run_subprocess(cmd)  # type: ignore[name-defined]
    return execute


def schema_entry_to_toolspec(
    name: str,
    entry: dict,
    *,
    unverified: bool = False,
) -> "ToolSpec":  # type: ignore[name-defined]
    """Build a :class:`core.tools.ToolSpec` from a JSON schema entry dict.

    Parameters
    ----------
    name:
        Logical tool name (registry key).
    entry:
        The ``tools[name]`` sub-dict from the JSON artifact.
    unverified:
        If ``True``, all READ ops are upgraded to WRITE (version drift
        detected — tool schema may not match the installed binary).

    The ALWAYS-GATED rule is enforced here: ``"read"`` permission classes
    are always upgraded to ``"write"`` for man-page tools, regardless of
    ``unverified``.  ``"destructive"`` is never downgraded.
    """
    if not _CORE_AVAILABLE:
        raise RuntimeError(
            "core package not available — cannot build ToolSpec. "
            "This function is for runtime use only."
        )

    binary = entry["binary"]
    description = entry.get("description", f"man-page tool: {binary}")
    if unverified:
        description = f"[unverified] {description}"

    has_subcommands = any(
        op["op_name"] != "_main" for op in entry.get("ops", [])
    )

    ops: dict[str, OpSpec] = {}  # type: ignore[name-defined]
    for op_dict in entry.get("ops", []):
        op_name = op_dict["op_name"]
        natural_class_str = op_dict.get("permission_class", "write")

        # ALWAYS-GATED: floor is WRITE.  Destructive is never downgraded,
        # even on version mismatch (unverified=True).
        if natural_class_str == "destructive":
            effective_class = OpClass.DESTRUCTIVE  # type: ignore[union-attr]
        else:
            # "read" and "write" both land at WRITE (always-gated floor).
            effective_class = OpClass.WRITE  # type: ignore[union-attr]

        args_list: list[ArgSpec] = []  # type: ignore[name-defined]
        for arg_dict in op_dict.get("args", []):
            args_list.append(ArgSpec(  # type: ignore[name-defined]
                name=arg_dict["name"],
                type=_str_to_type(arg_dict.get("type", "str")),
                required=arg_dict.get("required", False),
                description=arg_dict.get("description", ""),
                default=arg_dict.get("default", None),
            ))

        ops[op_name] = OpSpec(  # type: ignore[name-defined]
            op_name=op_name,
            permission_class=effective_class,
            args=args_list,
            description=op_dict.get("description", ""),
        )

    execute = _make_execute(binary, has_subcommands)

    return ToolSpec(  # type: ignore[name-defined]
        name=name,
        ops=ops,
        execute=execute,
        description=description,
    )


# ---------------------------------------------------------------------------
# Boot-time registry loader
# ---------------------------------------------------------------------------

def load_into_registry(
    registry,
    artifact_path: Path | str | None = None,
    *,
    verify_versions: bool = True,
    skip_on_error: bool = True,
) -> list[str]:
    """Load man-page-derived tool schemas into *registry* from the JSON artifact.

    Each tool is registered ALWAYS-GATED (minimum WRITE).  If ``verify_versions``
    is True (default), the installed binary's ``--version`` output is compared
    to the pinned version; mismatches cause the tool to be registered as
    ``[unverified]`` with all ops forced to at least WRITE.

    Parameters
    ----------
    registry:
        A :class:`core.tools.ToolRegistry` instance.
    artifact_path:
        Path to the JSON artifact.  Defaults to ``models/schemas/manpages.v1.json``
        relative to the repo root.
    verify_versions:
        Whether to run drift detection.  Set to ``False`` in tests to avoid
        shelling out.
    skip_on_error:
        If ``True`` (default), silently skip tools that fail to load (e.g.
        duplicate registration) rather than raising.

    Returns
    -------
    list[str]
        Names of successfully registered tools.
    """
    artifact = load_artifact(artifact_path)
    registered: list[str] = []

    for tool_name, entry in artifact.get("tools", {}).items():
        try:
            unverified = False
            if verify_versions:
                pinned = entry.get("version_pin", "")
                pattern = entry.get("version_pattern", r"(\d+[\.\d]*)")
                binary = entry.get("binary", tool_name)
                detected = detect_version(binary, version_pattern=pattern)
                if pinned and not version_matches(pinned, detected):
                    unverified = True

            spec = schema_entry_to_toolspec(tool_name, entry, unverified=unverified)
            registry.register(spec)
            registered.append(tool_name)
        except Exception:
            if not skip_on_error:
                raise

    return registered


# ---------------------------------------------------------------------------
# Curated artifact builder  (developer / CI entrypoint)
# ---------------------------------------------------------------------------

def build_curated_artifact(output_path: Path | str) -> None:
    """Write the curated man-page artifact without running actual man commands.

    In CI / offline environments we cannot shell out to ``man``.  The curated
    artifact is hand-reviewed and checked in; this function re-generates it
    from the embedded curated data below.

    Run via::

        python -m tools.manpage.generate_schemas --output models/schemas/manpages.v1.json
    """
    # The curated data is stored in manpages.v1.json and is the authoritative
    # source.  This function is a no-op placeholder so the CLI entry-point
    # works; the real artifact is checked in.
    print(
        f"Curated artifact is already checked in at {_DEFAULT_ARTIFACT}. "
        "To regenerate from live man pages, install mandoc and run "
        "tools.manpage.generate_schemas --from-live."
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate or inspect the man-page schema artifact."
    )
    parser.add_argument(
        "--output",
        default=str(_DEFAULT_ARTIFACT),
        help="Output path for the artifact (default: models/schemas/manpages.v1.json)",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print the loaded artifact to stdout instead of writing.",
    )
    ns = parser.parse_args()

    if ns.inspect:
        data = load_artifact(ns.output)
        print(json.dumps(data, indent=2))
    else:
        build_curated_artifact(ns.output)
