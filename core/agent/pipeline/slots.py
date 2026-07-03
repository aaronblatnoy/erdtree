"""
core/agent/pipeline/slots.py

Deterministic-first slot extraction with parallel model workers for genuinely
fuzzy slots.

Public API
----------
    extract_slots(
        user_input, snapshot_text, tool, operation, needed_slots,
        registry, *, responder=None, max_workers=4
    ) -> dict[str, Any]

Design
------
DETERMINISTIC FIRST (closed-world, no model call):
    For each needed slot, a narrow regex + closed-world lookup against the
    injected system context (snapshot_text) is tried first.  A deterministic
    match is accepted ONLY when the candidate value is PRESENT in the injected
    context — this prevents regex over-matching invented values.  Unmatched
    slots fall through to the model worker layer.

FUZZY WORKERS (model, parallel, capped):
    Each unresolved slot after the deterministic pass gets exactly ONE narrow
    model call: the original sentence + a single focused question -> one value
    or null.  Workers run in a ThreadPoolExecutor capped by max_workers (and by
    the Phase-0 concurrency finding that Ollama may serialize on 2-GPU hardware;
    the cap keeps the queue shallow).

NULL / UNRESOLVED:
    If a worker returns null (or the responder is absent), the slot is left
    absent in the returned dict.  The assembler (Phase 2) decides what to do
    with missing slots (required -> Unresolved; optional w/ default -> apply
    default).

Invariants
----------
I1  No egress: the only external call is the injected responder (localhost
    Ollama).  If responder is None, the model worker layer is skipped entirely
    and only deterministic slots are returned.
I2  No AI/LLM/model/agent language in any user-facing or log string.
I4  This module does NOT write audit records; audit is the caller's concern
    (the spine in repl.py handles I4).
I6  No tier/product names anywhere in this module.

Thread-safety
-------------
Each worker call is independent.  The responder callable is assumed to be
thread-safe (Ollama HTTP is stateless per request).  The returned dict is
assembled after all futures resolve — no shared mutable state.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional

from core.tools import ToolRegistry

# ---------------------------------------------------------------------------
# Type alias for the injected responder (mirrors strategy.py / repl.py).
# We cannot import from repl.py without a circular import.
# ---------------------------------------------------------------------------
Responder = Callable[[list[dict], list[dict]], Any]

# ---------------------------------------------------------------------------
# Slot-type hints that guide the deterministic resolver.
# These are the ArgSpec.type / ArgSpec.name patterns we can resolve
# closed-world from the system context snapshot.
# ---------------------------------------------------------------------------

# Names of slots that carry systemd unit names.
_UNIT_SLOT_NAMES: frozenset[str] = frozenset({"unit", "service", "unit_name"})

# Names of slots that carry package names.
_PKG_SLOT_NAMES: frozenset[str] = frozenset({"package", "pkg", "package_name"})

# Names of slots that carry filesystem paths.
_PATH_SLOT_NAMES: frozenset[str] = frozenset({"path", "file", "directory", "dir", "target"})

# Names of slots that carry block-device paths.
_DEVICE_SLOT_NAMES: frozenset[str] = frozenset({"device", "block_device", "dev"})

# Names of slots that carry TCP/UDP port numbers.
_PORT_SLOT_NAMES: frozenset[str] = frozenset({"port", "local_port"})

# Names of slots that carry network interface names.
_IFACE_SLOT_NAMES: frozenset[str] = frozenset({"interface", "iface", "network_interface"})


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

def _extract_words_from_input(user_input: str) -> list[str]:
    """Return the space-separated tokens from the user sentence."""
    return user_input.split()


def _find_in_snapshot(candidate: str, snapshot_text: str) -> bool:
    """Return True iff the candidate string appears literally in the snapshot."""
    return candidate in snapshot_text


# ---------------------------------------------------------------------------
# Deterministic resolvers (one per slot family)
# ---------------------------------------------------------------------------

def _resolve_unit(user_input: str, snapshot_text: str) -> Optional[str]:
    """Extract a systemd unit name from the user sentence if it appears in the
    snapshot (closed-world: active_services / failed_services / inactive_services
    are listed there)."""
    # Systemd unit names look like "name" or "name.service" / "name.timer" etc.
    pattern = re.compile(
        r"\b([A-Za-z0-9_@\-]+(?:\.(?:service|socket|timer|target|path|mount|slice|scope))?)\b"
    )
    for m in pattern.finditer(user_input):
        candidate = m.group(1)
        # Only accept if the candidate (with or without .service) appears in
        # the injected context snapshot (closed-world).
        if _find_in_snapshot(candidate, snapshot_text):
            return candidate
        # Also try without suffix.
        bare = candidate.split(".")[0]
        if bare != candidate and _find_in_snapshot(bare, snapshot_text):
            return bare
    return None


# Common English words / shell verbs that can appear in a snapshot's metadata
# text but are never package names.  Keeping this list narrow — only words
# that the package-name regex would wrongly match against snapshot prose like
# "Packages installed: 512" or "Active services (3): nginx".
_PKG_STOP_WORDS: frozenset[str] = frozenset({
    "install", "installed", "remove", "purge", "update", "upgrade",
    "packages", "package", "the", "a", "an", "on", "in", "at", "is",
    "are", "was", "were", "for", "of", "to", "and", "or", "not",
    "with", "all", "any", "no", "yes", "true", "false",
    "active", "failed", "inactive", "services", "service",
    "disks", "ports", "listening", "host", "os", "cpu", "memory",
})


def _resolve_package(user_input: str, snapshot_text: str) -> Optional[str]:
    """Extract a package name if it appears in the installed-packages list in
    the snapshot."""
    words = _extract_words_from_input(user_input)
    for word in words:
        # Strip common punctuation suffixes.
        word = word.rstrip(".,;:!?").lower()
        if not word or word in _PKG_STOP_WORDS:
            continue
        if _find_in_snapshot(word, snapshot_text):
            return word
    return None


def _resolve_path(user_input: str, snapshot_text: str) -> Optional[str]:
    """Extract an absolute filesystem path from the sentence if it appears in
    the snapshot (mount points or recent audit lines)."""
    pattern = re.compile(r"(/[A-Za-z0-9_./@\-]+)")
    for m in pattern.finditer(user_input):
        candidate = m.group(1)
        if _find_in_snapshot(candidate, snapshot_text):
            return candidate
    return None


def _resolve_device(user_input: str, snapshot_text: str) -> Optional[str]:
    """Extract a block device path (e.g. /dev/sda) if it appears in the
    snapshot (disk entries list devices)."""
    pattern = re.compile(r"(/dev/[A-Za-z0-9_]+)")
    for m in pattern.finditer(user_input):
        candidate = m.group(1)
        if _find_in_snapshot(candidate, snapshot_text):
            return candidate
    return None


def _resolve_port(user_input: str, snapshot_text: str) -> Optional[int]:
    """Extract a port number from the sentence if it appears as a listening
    port in the snapshot."""
    pattern = re.compile(r"\b(\d{1,5})\b")
    for m in pattern.finditer(user_input):
        candidate_str = m.group(1)
        port = int(candidate_str)
        if 1 <= port <= 65535:
            # Closed-world: only accept ports that appear in the snapshot.
            if _find_in_snapshot(candidate_str, snapshot_text):
                return port
    return None


def _resolve_interface(user_input: str, snapshot_text: str) -> Optional[str]:
    """Extract a network interface name (e.g. eth0, ens3, wlan0) if it
    appears in the snapshot."""
    # Common interface name patterns.
    pattern = re.compile(
        r"\b(eth\d+|ens\d+|enp\d+s\d+|wlan\d+|wlp\d+s\d+|lo|bond\d+|br[A-Za-z0-9\-]+|virbr\d+)\b"
    )
    for m in pattern.finditer(user_input):
        candidate = m.group(1)
        if _find_in_snapshot(candidate, snapshot_text):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Deterministic dispatch table
# ---------------------------------------------------------------------------

def _deterministic_resolve(
    slot_name: str,
    slot_type: type,
    user_input: str,
    snapshot_text: str,
) -> tuple[bool, Any]:
    """Try to resolve one slot deterministically.

    Returns (resolved: bool, value: Any).
    If resolved is False, value is None and the slot should go to a worker.
    """
    name_lower = slot_name.lower()

    if name_lower in _DEVICE_SLOT_NAMES:
        # Device before path so /dev/sda doesn't match the generic path resolver.
        val = _resolve_device(user_input, snapshot_text)
        if val is not None:
            return True, val

    if name_lower in _PATH_SLOT_NAMES:
        val = _resolve_path(user_input, snapshot_text)
        if val is not None:
            return True, val

    if name_lower in _UNIT_SLOT_NAMES:
        val = _resolve_unit(user_input, snapshot_text)
        if val is not None:
            return True, val

    if name_lower in _PKG_SLOT_NAMES:
        val = _resolve_package(user_input, snapshot_text)
        if val is not None:
            return True, val

    if name_lower in _PORT_SLOT_NAMES and slot_type is int:
        val = _resolve_port(user_input, snapshot_text)
        if val is not None:
            return True, val

    if name_lower in _IFACE_SLOT_NAMES:
        val = _resolve_interface(user_input, snapshot_text)
        if val is not None:
            return True, val

    return False, None


# ---------------------------------------------------------------------------
# Model worker (one per fuzzy slot)
# ---------------------------------------------------------------------------

_WORKER_TOOL_SCHEMA: list[dict] = []  # slot workers use plain messages, no tool calls


def _ask_model_for_slot(
    slot_name: str,
    slot_type: type,
    user_input: str,
    responder: Responder,
) -> Any:
    """Call the injected responder with a single focused question for one slot.

    Returns the extracted value (coerced to slot_type if possible) or None if
    the model cannot determine a value.

    The question is intentionally narrow — one slot, one answer — so a small
    base model can answer reliably without multi-slot reasoning.

    I2: no AI/LLM/model/agent language in the question string.
    I1: responder is the localhost Ollama instance — no external calls.
    """
    type_hint = _type_hint_for(slot_type)
    question = (
        f"In this request: \"{user_input}\"\n"
        f"What is the value for '{slot_name}'? "
        f"Reply with ONLY the {type_hint} value, or the word null if not specified."
    )
    messages: list[dict] = [{"role": "user", "content": question}]
    try:
        response = responder(messages, _WORKER_TOOL_SCHEMA)
        raw = (getattr(response, "content", None) or "").strip()
    except Exception:
        return None

    if not raw or raw.lower() in {"null", "none", "n/a", "unknown", "not specified", "not mentioned"}:
        return None

    # Attempt coercion to the declared slot type.
    return _coerce(raw, slot_type)


def _type_hint_for(slot_type: type) -> str:
    """Return a plain-English type label for the narrow question (I2-clean)."""
    if slot_type is int:
        return "integer"
    if slot_type is bool:
        return "true or false"
    if slot_type is list:
        return "comma-separated list"
    return "text"


def _coerce(raw: str, slot_type: type) -> Any:
    """Best-effort coercion of a raw model answer to the declared slot type.

    Returns None on failure rather than raising, so a bad answer degrades to
    'unresolved' rather than crashing the pipeline.
    """
    try:
        if slot_type is int:
            # Strip trailing punctuation that a model might include.
            return int(re.sub(r"[^\d\-]", "", raw))
        if slot_type is bool:
            return raw.lower() in {"true", "yes", "1", "on"}
        if slot_type is list:
            return [item.strip() for item in raw.split(",") if item.strip()]
        # Default: string.
        return str(raw)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_slots(
    user_input: str,
    snapshot_text: str,
    tool: str,
    operation: str,
    needed_slots: list[tuple[str, type]],
    registry: ToolRegistry,
    *,
    responder: Optional[Responder] = None,
    max_workers: int = 4,
) -> dict[str, Any]:
    """Extract slot values for (tool, operation) from a natural-language sentence.

    Parameters
    ----------
    user_input:
        The original user sentence (untransformed — passed verbatim to workers).
    snapshot_text:
        The injected system context snapshot as a plain string.  The
        deterministic resolver performs closed-world lookups against this text.
    tool:
        Registered tool name (used for context; not dispatched here).
    operation:
        Operation name within the tool (used for context; not dispatched here).
    needed_slots:
        List of (slot_name, slot_type) pairs to extract.  Typically built from
        the Unresolved.missing list returned by the assembler, together with
        ArgSpec.type.
    registry:
        The ToolRegistry; used to look up ArgSpec.type for each slot if not
        already known.  (The caller may pass an empty list for needed_slots if
        the assembler already resolved the spec.)
    responder:
        The injected model callable (messages, tools) -> response.  If None,
        the model worker layer is entirely skipped — only deterministic slots
        are returned (useful for tests and for READ ops where a model round-trip
        is unnecessary).
    max_workers:
        Maximum number of concurrent model worker threads.  Should reflect the
        Phase-0 finding: on hardware where Ollama serializes, set to 1.

    Returns
    -------
    dict[str, Any] mapping slot_name -> resolved_value for every slot that
    could be resolved.  Slots that could not be resolved are absent from the
    dict (not present with value None) so the assembler's required-slot check
    works by key presence.

    Invariants
    ----------
    I1  Only calls the injected responder (localhost Ollama); no other egress.
    I2  No AI/LLM/model/agent strings exposed to the user.
    I6  No tier/product names.
    """
    result: dict[str, Any] = {}
    fuzzy_slots: list[tuple[str, type]] = []

    # ------------------------------------------------------------------
    # Pass 1: deterministic resolver (closed-world, no model call)
    # ------------------------------------------------------------------
    for slot_name, slot_type in needed_slots:
        resolved, value = _deterministic_resolve(
            slot_name, slot_type, user_input, snapshot_text
        )
        if resolved and value is not None:
            result[slot_name] = value
        else:
            fuzzy_slots.append((slot_name, slot_type))

    # ------------------------------------------------------------------
    # Pass 2: model workers for genuinely fuzzy slots
    # ------------------------------------------------------------------
    if fuzzy_slots and responder is not None:
        # Cap concurrency by both max_workers and the number of fuzzy slots.
        pool_size = min(max_workers, len(fuzzy_slots))
        with ThreadPoolExecutor(max_workers=pool_size) as pool:
            future_to_slot: dict[Any, tuple[str, type]] = {
                pool.submit(
                    _ask_model_for_slot,
                    slot_name,
                    slot_type,
                    user_input,
                    responder,
                ): (slot_name, slot_type)
                for slot_name, slot_type in fuzzy_slots
            }
            for future in as_completed(future_to_slot):
                slot_name, _ = future_to_slot[future]
                try:
                    value = future.result()
                except Exception:
                    value = None
                if value is not None:
                    result[slot_name] = value
                # Null / exception -> slot absent from result (unresolved)

    return result
