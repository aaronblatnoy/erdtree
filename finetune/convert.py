"""finetune/convert.py — Anthropic <-> OpenAI/ShareGPT format converter.

THE CORRECTNESS CRUX of the finetune pipeline.  A subtle error here silently
poisons the ENTIRE corpus, so this module is PURE (no I/O, no network, no core/
imports, stdlib only) and exhaustively unit-tested (tests/finetune/test_convert.py).

What it does
------------
Claude speaks the Anthropic Messages shape: an assistant turn's ``content`` is a
list of typed blocks — ``tool_use`` blocks ({id, name, input(dict)}) and ``text``
blocks ({text}).  Erdtree's FROZEN wire format (docs/decisions/0002 §2/§3) is the
OpenAI Chat Completions / ShareGPT shape that Ollama presents and the trainer must
learn byte-for-byte.  This module maps one onto the other.

Load-bearing rules threaded here (do NOT relax):

  INV-0002 §2 — an assistant tool-call turn is
      {"role":"assistant","content":None,"tool_calls":[
         {"id":<verbatim>, "type":"function",
          "function":{"name":<tool>, "arguments":<JSON-ENCODED STRING>}}]}
    * ``function.arguments`` is a JSON-ENCODED **STRING**, never a nested object.
      This is THE classic poison bug — emit an object and every trace MISSes the
      live router.  We ``json.dumps`` the Anthropic input dict here, once.
    * ``content`` is ``None`` on a tool-call turn.
    * ids flow through VERBATIM: Claude's ``toolu_...`` id becomes both
      ``tool_calls[].id`` (§2) and the following ``tool`` message's
      ``tool_call_id`` (§3), preserving correlation (plan A5).

  INV-0002 §3 — a tool-result message is
      {"role":"tool","tool_call_id":<same id>,"content":<compact JSON body>}
    The structured result dict is emitted as compact JSON so the model reasons
    over exit code + summaries.

  Compact JSON everywhere: ``separators=(",",":")`` so the emitted strings match
  the frozen examples and stay small for the trainer.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Optional

# Compact-JSON separators — the frozen 0002 encoding (no spaces).
_COMPACT = (",", ":")


# --------------------------------------------------------------------------- #
# Block field access — tolerate both SDK objects and plain dicts.             #
# --------------------------------------------------------------------------- #
#
# AnthropicBackend returns the real SDK content blocks (attribute access:
# block.type / block.id / block.name / block.input / block.text).  FakeBackend
# returns lightweight dataclass blocks with the same attributes.  Tests may also
# hand-craft plain dicts.  We accept all three shapes so convert.py never cares
# where the block came from.

def _field(block: Any, name: str, default: Any = None) -> Any:
    if isinstance(block, dict):
        return block.get(name, default)
    return getattr(block, name, default)


def _block_type(block: Any) -> Optional[str]:
    return _field(block, "type")


# --------------------------------------------------------------------------- #
# 1. Anthropic tool_use block(s) -> OpenAI assistant tool_calls turn (0002 §2) #
# --------------------------------------------------------------------------- #

def anthropic_tool_use_to_openai_tool_calls(blocks: Iterable[Any]) -> dict:
    """Convert Anthropic ``tool_use`` content blocks into a §2 assistant turn.

    ``blocks`` is the Anthropic assistant ``content`` list (or just the
    ``tool_use`` blocks).  Only ``type == "tool_use"`` blocks are converted;
    any ``text`` blocks are ignored here (0002 §2: a tool-call turn carries
    ``content: null`` and no prose).

    Returns::

        {"role": "assistant",
         "content": None,
         "tool_calls": [
             {"id": tu.id, "type": "function",
              "function": {"name": tu.name,
                           "arguments": json.dumps(tu.input, compact)}}, ...]}

    The Anthropic input DICT becomes a JSON-ENCODED STRING in ``arguments`` —
    NOT a nested object (INV-0002 §2).  ids flow through VERBATIM.
    """
    tool_calls: list[dict] = []
    for block in blocks:
        if _block_type(block) != "tool_use":
            continue
        tu_id = _field(block, "id")
        tu_name = _field(block, "name")
        tu_input = _field(block, "input")
        if tu_input is None:
            tu_input = {}
        tool_calls.append({
            "id": tu_id,                       # VERBATIM — toolu_... carried through
            "type": "function",                # always "function" (0002 §2)
            "function": {
                "name": tu_name,
                # THE crux: dict -> JSON-ENCODED STRING, never a nested object.
                "arguments": json.dumps(tu_input, separators=_COMPACT),
            },
        })
    return {
        "role": "assistant",
        "content": None,                       # None on a tool-call turn (0002 §2)
        "tool_calls": tool_calls,
    }


# --------------------------------------------------------------------------- #
# 2. Tool result dict -> OpenAI role:"tool" message (0002 §3)                  #
# --------------------------------------------------------------------------- #

def anthropic_tool_result_to_openai_tool_msg(tool_use_id: str, result_dict: dict) -> dict:
    """Build the §3 ``role:"tool"`` result message correlating by id.

    ``tool_use_id`` MUST equal the ``id`` of the tool_use block that produced
    this result (correlation, 0002 §3).  ``result_dict`` is the structured tool
    result (e.g. {"exit_code","stdout","stderr","summary"}); it is emitted as a
    compact-JSON string body so the model can reason over it.
    """
    return {
        "role": "tool",
        "tool_call_id": tool_use_id,           # correlation key (0002 §3)
        "content": json.dumps(result_dict, separators=_COMPACT),
    }


# --------------------------------------------------------------------------- #
# 3. Plain assistant text -> OpenAI assistant message (English answer)         #
# --------------------------------------------------------------------------- #

def assistant_text_to_openai(text: str) -> dict:
    """A plain English assistant answer (0002 §2: content non-null, no tool_calls)."""
    return {"role": "assistant", "content": text}


# --------------------------------------------------------------------------- #
# 4. Final ShareGPT record assembly                                            #
# --------------------------------------------------------------------------- #

def assemble_record(
    system: str,
    tools: list[dict],
    messages: list[dict],
    meta: dict,
) -> dict:
    """Assemble the final ShareGPT/messages training record (plan §4).

    Parameters
    ----------
    system   : the fully-composed system string (HOUSE_SYSTEM_PROMPT + tier +
               live SYSTEM CONTEXT).  The caller composes it via the live
               ``assemble_messages`` / house prompt (INV-house-prompt) and is
               responsible for the I2 assert on it — convert.py stays pure.
    tools    : the 0002 §1 function list (from the LIVE registry) stored
               alongside the messages for trainer visibility.
    messages : the ordered conversation turns AFTER the system message
               (user / assistant-tool-call / tool / assistant-text ...), each
               already produced by the converters above.
    meta     : the per-record metadata block (tier, scenario_id, tool,
               operation, permission_class, ...).

    Returns the record shape::

        {"messages": [ {"role":"system", "content": system}, *messages ],
         "tools": tools,
         "meta": meta}
    """
    return {
        "messages": [{"role": "system", "content": system}, *messages],
        "tools": tools,
        "meta": meta,
    }
