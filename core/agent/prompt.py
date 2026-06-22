"""
core/agent/prompt.py

Prompt assembly for the agent loop.

Design contract (load-bearing — see plan invariants I2, I5, I6):

  I2  No AI/LLM/model/agent/agentic language in ANY user-facing string.
      The system prompt speaks as a capable Linux command interface, not as
      an AI assistant.  Words like "AI", "LLM", "model", "agent", "neural"
      are FORBIDDEN in every string produced here.

  I5  Fresh system context is ALWAYS injected.  The caller supplies a
      SystemSnapshot (core/context/snapshot.py) or a compatible object; this
      module serialises it and prepends it to the system prompt.  The user
      never has to explain their environment.

  I6  This module is tier-agnostic.  It accepts a tier_prompt string provided
      by the caller (loaded by core/agent/tier.py in Phase 9); it has no
      knowledge of tier names or product names.

Wire format: OpenAI Chat Completions messages array (0002 §1 / §4).
Frozen contract: docs/decisions/0002-tool-call-protocol.md.

TOOL SCHEMA FORMAT: build_tool_list() takes the tool registry's schema
representation (list of dicts with "name", "description", "parameters")
and converts them into the 0002 §1 format:
  {"type": "function", "function": {"name", "description", "parameters"}}

The assembled messages array is ready to pass directly to OllamaClient.chat()
/ OllamaClient.stream().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ------------------------------------------------------------------ #
# Invariant: ensure no AI language leaks into the house system prompt #
# ------------------------------------------------------------------ #
# These are the forbidden terms (I2).  They are checked by the unit
# test and by _assert_no_ai_language() called on every assembled prompt.
_FORBIDDEN_AI_TERMS = frozenset({
    "ai", "artificial intelligence",
    "llm", "large language model",
    "model",         # context-dependent but forbidden in user-visible strings
    "agent",
    "neural", "neural network",
    "machine learning",
    "gpt",
    "ollama",        # the engine is invisible to users
    "inference",
})

# Regex pattern built from forbidden terms (whole-word, case-insensitive)
import re as _re
_AI_PATTERN = _re.compile(
    r"\b(" + "|".join(_re.escape(t) for t in _FORBIDDEN_AI_TERMS) + r")\b",
    _re.IGNORECASE,
)


def _assert_no_ai_language(text: str, label: str = "prompt") -> None:
    """Raise ValueError if any I2-forbidden term appears in *text*."""
    match = _AI_PATTERN.search(text)
    if match:
        raise ValueError(
            f"I2 violation in {label!r}: found forbidden term "
            f"{match.group()!r} at position {match.start()}. "
            "No AI/LLM/model/agent language may appear in user-facing strings."
        )


# ------------------------------------------------------------------ #
# House system prompt                                                  #
# ------------------------------------------------------------------ #

# The house prompt is written in a no-hedge, direct voice.
# It never mentions AI, LLMs, agents, or models (I2).
# It is tier-agnostic (I6) — tier-specific personality text is
# appended separately via the tier_prompt argument.
# It references the CONTEXT BLOCK that will be prepended at assembly
# time so the system knows its environment is always current (I5).
_HOUSE_SYSTEM_PROMPT = """\
You are the command interface for this Linux system.

Your job is to translate the operator's plain-English requests into \
precise shell operations and carry them out safely, using only the \
tools available to you.

Rules you follow without exception:
- You ALWAYS reply in English, even when the operator writes in another \
language.  Every response, summary, and message you produce is in English.
- You NEVER run a write or destructive operation without the operator's \
explicit confirmation.
- You NEVER guess at a command — if you are not certain, ask before acting.
- You NEVER explain yourself as software or describe your capabilities; \
you simply do the work.
- Your responses are terse and accurate.  No apologies.  No hedging.  \
No filler sentences.
- When you describe a result, you describe it as a Linux operator would: \
exit codes, service states, package names, log lines — concrete and exact.
- If you cannot carry out a request with the tools available, you say \
so plainly and stop.

The SYSTEM CONTEXT block below is a live snapshot of this host.  It was \
collected moments ago and reflects the current state of the system.  You \
do not need to ask the operator to describe their environment.
"""

# Sanity-check the house prompt itself at import time.
_assert_no_ai_language(_HOUSE_SYSTEM_PROMPT, "house system prompt")


# ------------------------------------------------------------------ #
# Public interface                                                     #
# ------------------------------------------------------------------ #

@dataclass
class PromptConfig:
    """
    All caller-supplied configuration for one prompt assembly call.

    Fields
    ------
    tier_prompt:     Tier-specific personality / instruction addendum.
                     Loaded by core/agent/tier.py (Phase 9); stubbed here
                     until that phase lands.  May be empty string.
    snapshot_text:   The output of SystemSnapshot.to_prompt_text() (I5).
                     Caller is responsible for calling to_prompt_text();
                     this keeps the prompt layer independent of the
                     snapshot internals.
    user_input:      The raw operator input for this turn.
    history:         Recent conversation turns as OpenAI messages.
                     Caller manages window / compaction (Phase 8).
    tools:           Pre-built tool list in 0002 §1 wire format.
                     Build with build_tool_list() below.
    tool_choice:     Wire value passed through to the model ("auto").
    """
    tier_prompt: str = ""
    snapshot_text: str = ""
    user_input: str = ""
    history: list[dict] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    tool_choice: str = "auto"


def build_tool_list(registry_schemas: list[dict]) -> list[dict]:
    """
    Convert tool-registry schema dicts into the 0002 §1 wire format.

    Each input dict must have at minimum:
      "name"        (str)  — tool identifier
      "description" (str)  — natural language description
      "parameters"  (dict) — JSON Schema draft-07 object

    Returns a list of:
      {"type": "function", "function": {"name", "description", "parameters"}}

    This is the format passed to OllamaClient via tools=[...] and matches
    the frozen contract in docs/decisions/0002 §1.
    """
    result = []
    for schema in registry_schemas:
        result.append({
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema["parameters"],
            },
        })
    return result


def assemble_messages(config: PromptConfig) -> list[dict]:
    """
    Assemble the full OpenAI-format messages list for one agent turn.

    Layout (per 0002 §1 / §4):
      1. system  — house prompt + tier prompt + live context block (I2/I5/I6)
      2. history — recent turns (caller manages window / compaction, Phase 8)
      3. user    — current operator input

    Returns
    -------
    list[dict]  OpenAI Chat Completions messages array, ready for
                OllamaClient.chat(messages, tools=config.tools).
    """
    # Build the system message
    system_parts: list[str] = [_HOUSE_SYSTEM_PROMPT]

    # Tier addendum (I6: tier text comes from outside; core/ is name-free)
    if config.tier_prompt.strip():
        _assert_no_ai_language(config.tier_prompt, "tier_prompt")
        system_parts.append(config.tier_prompt.strip())

    # Live system context (I5)
    if config.snapshot_text.strip():
        system_parts.append(
            "--- SYSTEM CONTEXT (live) ---\n"
            + config.snapshot_text.strip()
            + "\n--- END SYSTEM CONTEXT ---"
        )
    else:
        system_parts.append(
            "--- SYSTEM CONTEXT ---\n"
            "(Context collection unavailable for this turn.)\n"
            "--- END SYSTEM CONTEXT ---"
        )

    system_content = "\n\n".join(system_parts)

    messages: list[dict] = []

    # 1. System message
    messages.append({"role": "system", "content": system_content})

    # 2. Recent history (caller is responsible for not blowing the window)
    for turn in config.history:
        messages.append(turn)

    # 3. Current user input
    if config.user_input.strip():
        messages.append({"role": "user", "content": config.user_input.strip()})

    return messages


def assemble(
    user_input: str,
    snapshot_text: str,
    history: Optional[list[dict]] = None,
    tier_prompt: str = "",
    tools: Optional[list[dict]] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Convenience function: assemble messages + return (messages, tools).

    Suitable for callers that do not want to build a PromptConfig explicitly.

    Returns
    -------
    (messages, tools)
        messages: list[dict] — the assembled messages array
        tools:    list[dict] — the tools list (may be empty)
    """
    cfg = PromptConfig(
        tier_prompt=tier_prompt,
        snapshot_text=snapshot_text,
        user_input=user_input,
        history=history or [],
        tools=tools or [],
    )
    msgs = assemble_messages(cfg)
    return msgs, cfg.tools
