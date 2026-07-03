"""
core/agent/pipeline/intent.py

Intent classifier: given a natural-language user request, identify the most
likely (tool, operation) pair from the registered tool specs, or signal that
no confident match was found.

Public API
----------
    classify_intent(
        user_input, snapshot_text, registry, *, embedder=None, responder=None
    ) -> IntentResult

IntentResult is either:
  * IntentMatch  — a ranked (tool, operation) candidate with a coarse confidence
                   score (0.0-1.0) and an optional list of runner-up candidates.
  * NoConfidentMatch — no candidate crossed the confidence threshold; the caller
                       should fall back to the native or fallback path.

Two backends, one injected interface (Assumption A3 from the plan)
------------------------------------------------------------------
(a) Embedding backend  — embedding similarity over op descriptions using a
    sqlite-vec index, or (in tests) a stub embedder that returns pre-seeded
    vectors. Chosen when ``embedder`` is supplied. No generation round-trip.
(b) Model backend      — a narrow, single-turn model call to pick the best
    (tool, op) from a bounded candidate list. Chosen when ``responder`` is
    supplied and ``embedder`` is None.

In production exactly one backend is injected; in tests the stub embedder
is always used (no network, no Ollama required).

Confidence scoring (coarse, per plan Assumption A2)
----------------------------------------------------
For the embedding backend: cosine similarity distance + margin (gap between
best and runner-up similarity). For the model backend: a hard 1.0 when the
model picks a recognised candidate, 0.0 otherwise.

Top-K tie-breaking
------------------
When two ops have near-identical descriptions (similarity gap < TIE_MARGIN)
both are returned as candidates in ``top_k``; the assembler's required-slot
fit disambiguates downstream.

Design invariants
-----------------
I1  No egress. The model backend only calls the injected responder (localhost
    Ollama). The embedding backend only calls the injected embedder.
I2  No AI/LLM/model/agent language in any user-facing string.
I3  This module NEVER calls permissions.classify — intent classification
    produces a candidate, not a dispatch decision.
I4  Audit is the caller's concern; this module has NO side effects on the
    audit log.
I6  No tier/product names anywhere in this file.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.tools import ToolRegistry

# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------

#: Minimum confidence required to emit IntentMatch (vs NoConfidentMatch).
#: Calibrated on the bench set (Phase 5). Tunable via the embedder/tests.
CONFIDENCE_THRESHOLD: float = 0.30

#: Similarity gap below which two candidates are considered "tied" and both
#: returned in top_k so the assembler can disambiguate by slot fit.
TIE_MARGIN: float = 0.05

#: Maximum number of top-K candidates to return when there are ties.
TOP_K_MAX: int = 5


# ---------------------------------------------------------------------------
# Candidate space
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OpCandidate:
    """One (tool, operation) pair from the registry with its description text."""

    tool: str
    operation: str
    description: str   # concatenated tool.description + " — " + op.description


def _build_candidate_space(registry: ToolRegistry) -> list[OpCandidate]:
    """Build the full candidate list from the registry's tool/op descriptions.

    Each (tool, op) pair becomes one candidate whose description text is:
        "<tool description> — <op description>"

    This gives the embedder/model enough context to distinguish, e.g.,
    "services restart" from "processes kill" even when the raw op names clash.
    """
    candidates: list[OpCandidate] = []
    for tool_name in registry.list_tools():
        spec = registry.get(tool_name)
        if spec is None:
            continue
        tool_desc = spec.description or tool_name
        for op_name, op_spec in spec.ops.items():
            op_desc = op_spec.description or op_name
            full_desc = f"{tool_desc} — {op_desc}"
            candidates.append(
                OpCandidate(
                    tool=tool_name,
                    operation=op_name,
                    description=full_desc,
                )
            )
    return candidates


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IntentMatch:
    """A confident (tool, operation) match with coarse confidence.

    Attributes
    ----------
    tool:       Registered tool name.
    operation:  Op name within the tool.
    confidence: Coarse score in [0.0, 1.0]. Synthesised from match distance
                and margin to the runner-up (A2 — not logprobs).
    top_k:      All candidates whose similarity is within TIE_MARGIN of the
                best; includes the best itself as the first entry. When two
                ops have near-identical descriptions the assembler uses
                required-slot fit to disambiguate.
    """

    tool: str
    operation: str
    confidence: float
    top_k: list["IntentMatch"] = field(default_factory=list)


@dataclass(frozen=True)
class NoConfidentMatch:
    """No candidate exceeded the confidence threshold.

    The caller should escalate to the native path, ask for clarification, or
    activate the fallback.

    Attributes
    ----------
    best_tool:      Best candidate tool found (may be empty).
    best_operation: Best candidate operation found (may be empty).
    best_score:     The highest confidence reached (below threshold).
    reason:         A concise, I2-clean explanation.
    """

    best_tool: str = ""
    best_operation: str = ""
    best_score: float = 0.0
    reason: str = ""


# The public return type.
IntentResult = IntentMatch | NoConfidentMatch


# ---------------------------------------------------------------------------
# Embedder interface (injected; tests supply a stub)
# ---------------------------------------------------------------------------

# An embedder is any callable that takes a string and returns a list of floats.
# The embedding backend uses ONE call per query (the user_input) and ONE call
# per candidate at index-build time (or accepts pre-built vectors).
#
# Stub contract for tests:
#   embedder(text: str) -> list[float]
#   The stub must return vectors of equal length for all inputs.

Embedder = Callable[[str], list[float]]

# A responder is the same model-call interface used elsewhere in the pipeline.
Responder = Callable[[list[dict], list[dict]], Any]


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors. Returns 0.0 on zero norms."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Backend (a): embedding similarity
# ---------------------------------------------------------------------------

def _classify_via_embedder(
    user_input: str,
    snapshot_text: str,
    candidates: list[OpCandidate],
    embedder: Embedder,
) -> IntentResult:
    """Embedding-similarity backend.

    Embeds the query (user_input) and each candidate description, then ranks
    by cosine similarity. Computes a coarse confidence from the best score and
    the margin to the runner-up.

    No generation call is made — this is pure retrieval (A3).
    """
    if not candidates:
        return NoConfidentMatch(reason="no operations are registered")

    # Embed the query. Prepend a brief context string so the embedding captures
    # the system state (e.g. "running on rocky linux: restart nginx").
    query_text = user_input
    if snapshot_text:
        # Keep it short: just the raw user request. The snapshot_text helps the
        # model backend but is noise for embedding similarity over op descriptions.
        query_text = user_input

    query_vec = embedder(query_text)

    # Score each candidate.
    scored: list[tuple[float, OpCandidate]] = []
    for cand in candidates:
        cand_vec = embedder(cand.description)
        sim = _cosine(query_vec, cand_vec)
        scored.append((sim, cand))

    # Sort descending by similarity.
    scored.sort(key=lambda t: t[0], reverse=True)

    best_sim, best_cand = scored[0]
    runner_up_sim = scored[1][0] if len(scored) > 1 else 0.0

    # Coarse confidence: scaled best similarity, discounted by proximity of runner-up.
    margin = best_sim - runner_up_sim
    confidence = _compute_confidence(best_sim, margin)

    if confidence < CONFIDENCE_THRESHOLD:
        return NoConfidentMatch(
            best_tool=best_cand.tool,
            best_operation=best_cand.operation,
            best_score=confidence,
            reason=(
                f"best match {best_cand.tool}.{best_cand.operation!r} "
                f"scored {confidence:.2f}, below threshold {CONFIDENCE_THRESHOLD:.2f}"
            ),
        )

    # Collect top-K tied candidates.
    top_k_matches: list[IntentMatch] = []
    for i, (sim, cand) in enumerate(scored[:TOP_K_MAX]):
        gap = best_sim - sim
        if gap > TIE_MARGIN:
            break
        next_sim = scored[i + 1][0] if i + 1 < len(scored) else 0.0
        cand_margin = sim - next_sim
        top_k_matches.append(
            IntentMatch(
                tool=cand.tool,
                operation=cand.operation,
                confidence=_compute_confidence(sim, cand_margin),
                top_k=[],
            )
        )

    return IntentMatch(
        tool=best_cand.tool,
        operation=best_cand.operation,
        confidence=confidence,
        top_k=top_k_matches,
    )


def _compute_confidence(sim: float, margin: float) -> float:
    """Coarse confidence from cosine similarity and runner-up margin.

    We do not have logprobs (A2). This formula is deliberately simple:
      confidence = sim * (1 + margin_bonus)
    where margin_bonus is a small uplift for a clear winner.

    The result is clamped to [0.0, 1.0].
    """
    margin_bonus = min(margin * 0.5, 0.15)
    raw = sim * (1.0 + margin_bonus)
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# Backend (b): narrow model call
# ---------------------------------------------------------------------------

# The prompt template for the model backend. I2-clean: no AI/LLM/model language.
_MODEL_BACKEND_SYSTEM = (
    "You are a command classifier. "
    "Given a user request, respond with EXACTLY the (tool, operation) pair "
    "that best matches — no other text. Format: tool_name.operation_name"
)


def _classify_via_model(
    user_input: str,
    snapshot_text: str,
    candidates: list[OpCandidate],
    responder: Responder,
) -> IntentResult:
    """Narrow model-call backend.

    Builds a compact prompt listing the available (tool, operation) pairs and
    their descriptions, then asks the model to pick one. This is a single, very
    narrow generation call — the model only needs to pick from a closed list,
    not generate a full tool-call JSON (A3).

    No embedding is computed.
    """
    if not candidates:
        return NoConfidentMatch(reason="no operations are registered")

    # Build the candidate list for the prompt.
    lines: list[str] = []
    for cand in candidates:
        lines.append(f"  {cand.tool}.{cand.operation}: {cand.description}")
    candidate_block = "\n".join(lines)

    context_note = ""
    if snapshot_text:
        # Trim to avoid bloating the narrow prompt.
        trimmed = snapshot_text[:300].strip()
        context_note = f"\n\nSystem context (brief):\n{trimmed}"

    user_prompt = (
        f"User request: {user_input}{context_note}\n\n"
        f"Available operations:\n{candidate_block}\n\n"
        "Reply with exactly one entry from the list above in the form "
        "tool_name.operation_name — nothing else."
    )

    messages = [{"role": "user", "content": user_prompt}]
    tools: list[dict] = []  # narrow call — no tool schema needed

    try:
        response = responder(messages, tools)
    except Exception:
        return NoConfidentMatch(reason="classification call failed")

    raw_text: str = ""
    if hasattr(response, "content"):
        raw_text = (response.content or "").strip()
    elif isinstance(response, str):
        raw_text = response.strip()

    # Parse "tool.operation" from the response.
    match = re.match(r"^([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)$", raw_text)
    if not match:
        return NoConfidentMatch(
            reason=f"classification response could not be parsed: {raw_text!r}"
        )

    tool_name, op_name = match.group(1), match.group(2)

    # Validate the response is a real (tool, op) pair.
    valid = {(c.tool, c.operation) for c in candidates}
    if (tool_name, op_name) not in valid:
        return NoConfidentMatch(
            best_tool=tool_name,
            best_operation=op_name,
            best_score=0.0,
            reason=(
                f"classification returned {tool_name}.{op_name!r}, "
                "which is not a registered operation"
            ),
        )

    # Model backend returns a binary confidence: 1.0 when the candidate is valid.
    return IntentMatch(
        tool=tool_name,
        operation=op_name,
        confidence=1.0,
        top_k=[IntentMatch(tool=tool_name, operation=op_name, confidence=1.0, top_k=[])],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_intent(
    user_input: str,
    snapshot_text: str,
    registry: ToolRegistry,
    *,
    embedder: Optional[Embedder] = None,
    responder: Optional[Responder] = None,
) -> IntentResult:
    """Classify a natural-language request into a (tool, operation) candidate.

    Parameters
    ----------
    user_input:    The raw English request from the user.
    snapshot_text: The current system-context snapshot (injected context). Used
                   as additional signal for the model backend; largely ignored
                   by the embedding backend (op descriptions don't change with
                   system state).
    registry:      The ToolRegistry to build the candidate space from.
    embedder:      Optional embedding callable (text -> list[float]). When
                   supplied, the embedding-similarity backend is used. Tests
                   supply a deterministic stub so the embedding path is fully
                   dev-host testable without network access.
    responder:     Optional model-call callable (messages, tools) -> response.
                   Used when ``embedder`` is None. Ignored when ``embedder``
                   is supplied (the embedding backend is preferred — no round-
                   trip generation cost).

    Returns
    -------
    IntentMatch    — a confident (tool, operation) candidate with coarse
                     confidence and optional top-K ties.
    NoConfidentMatch — no candidate exceeded the threshold; the caller should
                       escalate or fall back.

    Invariants
    ----------
    I1  All inference calls go through the injected embedder/responder only
        (localhost Ollama in production; stubs in tests).
    I2  No AI/LLM/model/agent language appears in any string returned to the
        user or in log/audit fields written by this function.
    I3  This function NEVER calls permissions.classify.
    I4  This function writes NO audit records.
    """
    if not user_input or not user_input.strip():
        return NoConfidentMatch(reason="empty input")

    candidates = _build_candidate_space(registry)

    if not candidates:
        return NoConfidentMatch(reason="no operations are registered")

    if embedder is not None:
        return _classify_via_embedder(user_input, snapshot_text, candidates, embedder)

    if responder is not None:
        return _classify_via_model(user_input, snapshot_text, candidates, responder)

    # No backend injected: return NoConfidentMatch so the caller escalates
    # gracefully rather than crashing.
    return NoConfidentMatch(
        reason="no classification backend available (no embedder or responder injected)"
    )
