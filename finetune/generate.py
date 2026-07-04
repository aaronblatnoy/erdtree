"""finetune/generate.py — the async generation driver + CLI (Phase 5).

Turns the fixture layers (scenarios / context / simulate) plus the LLM seam
(llm.py) and the pure format converter (convert.py) into a stream of
0002-conformant ShareGPT/messages training records, one JSONL line each.

Flow per scenario (plan §1 / PHASE 5)
-------------------------------------
1. ``make_context(tier, seed)`` -> live Rocky-9 ``snapshot_text``.
2. Build the REAL messages via ``assemble_messages(PromptConfig(...))`` — the
   house prompt (INV-house-prompt) and tool-use discipline are injected by
   core; we NEVER hand-write the system string.  Tools come LIVE from the
   registry (INV-schema-sync) via ``live_tool_list()``.
3. ``backend.complete(...)`` -> Anthropic-shaped ``tool_use`` block(s).  Convert
   (convert.py) to the OpenAI assistant tool-call turn.  For non-READ ops
   (WRITE/DESTRUCTIVE per the op's OpClass) MODEL THE CONFIRM TURN *before* the
   executing call (INV-permission-fidelity / CLAUDE.md invariant 3): a synthetic
   confirmation prompt + the operator's confirmation ("yes" for WRITE, the typed
   word "DESTROY" for DESTRUCTIVE) so the trace teaches the gate.
4. ``simulate(tool, op, args, ctx)`` -> ToolResult; convert to ``role:"tool"``.
5. ``backend.complete(...)`` again with the tool result appended -> the final
   English answer; convert to an assistant content turn; assert I2-clean.
6. On a MISS (prose where a tool was required, or invalid arguments), follow
   0002 §5: append the router re-ask and retry ONCE; if still a MISS, DROP the
   trace and log it (never emit a broken record).
7. Append each complete record as one JSONL line (never hold the whole corpus
   in memory).  ``--resume`` counts existing lines and skips already-produced
   scenario ids.  ``asyncio.Semaphore(K)`` bounds concurrency; a tqdm bar tracks
   progress.

INVARIANTS THREADED HERE
------------------------
INV-schema-sync   Tool schemas / op names / permission classes come LIVE from
                  finetune.coreimports + the Scenario's registry-derived
                  ``permission_class`` — nothing is hardcoded.
INV-house-prompt  The system prompt is produced by ``assemble_messages`` (core).
INV-I2            Every assistant ``content`` string (confirm prompt + final
                  answer) is asserted I2-clean; the snapshot is asserted clean
                  by context.py.  Operator/user_input text is NOT asserted.
INV-0002          Records go through convert.py verbatim: ``arguments`` is a
                  JSON-encoded STRING, ``content`` is None on tool-call turns,
                  ``tool`` messages correlate by ``tool_call_id``.
INV-offline       FakeBackend is the DEFAULT for build/validate/smoke — no
                  network, no ``anthropic`` install, no ANTHROPIC_API_KEY.
INV-read-only-core  Only imports via finetune.* seams; never mutates core/.
A4                tier changes ONLY tier_prompt + context depth + a meta field —
                  never the trace STRUCTURE.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from finetune import convert, coreimports
from finetune.context import make_context
from finetune.llm import make_backend
from finetune.scenarios import ALL_SCENARIOS, Scenario
from finetune.simulate import simulate

try:  # tqdm is a build-time dep; degrade gracefully if absent.
    from tqdm import tqdm
except Exception:  # noqa: BLE001
    tqdm = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Defaults / constants                                                        #
# --------------------------------------------------------------------------- #

DEFAULT_OUT = "finetune/data/traces.jsonl"
DEFAULT_MODEL = "claude-sonnet-4-6"   # exact id, no date suffix (plan A2)
DEFAULT_CONCURRENCY = 5
TIERS = ("marika", "radagon")

# Tier addendum text (A4: tier only nudges persona/context depth, never
# structure).  These strings are injected as PromptConfig.tier_prompt, which
# assemble_messages asserts I2-clean — so they must contain no forbidden term.
TIER_PROMPTS = {
    "radagon": (
        "You run in a data center. Prioritize uptime, security, and precise, "
        "auditable operations. Prefer the least disruptive action that resolves "
        "the request."
    ),
    "marika": (
        "You run on a personal Linux machine. Keep operations simple and "
        "explain outcomes plainly for a single operator."
    ),
}

# Confirmation the operator types back at the gate.  Operator text — NOT
# asserted I2-clean.  DESTRUCTIVE requires the literal typed word (mirrors
# permissions.DESTRUCTIVE_CONFIRM_WORD); WRITE takes a plain "yes".
_CONFIRM_WORD = {"write": "yes", "destructive": "DESTROY"}

# Synthetic confirmation PROMPT the assistant shows before executing a non-READ
# op.  These ARE assistant content and MUST be I2-clean (asserted at emit time).
_CONFIRM_PROMPT = {
    "write": (
        "This changes the system. Reply yes to proceed, or no to cancel."
    ),
    "destructive": (
        "This is a destructive change and cannot be undone. Type DESTROY to "
        "proceed, or anything else to cancel."
    ),
}

# 0002 §5 re-ask wording (adopted from the frozen contract): appended as a
# follow-up turn when the model answers with prose / invalid arguments where a
# valid tool call was required, then the model is retried ONCE.
_REASK = (
    "That request requires a tool call with valid arguments: {detail}. "
    "Rewrite the input so it satisfies the expected schema and call the tool."
)


# --------------------------------------------------------------------------- #
# Small block helpers (blocks are ToolUseBlock / TextBlock or plain dicts)     #
# --------------------------------------------------------------------------- #

def _btype(block: Any) -> Optional[str]:
    if isinstance(block, dict):
        return block.get("type")
    return getattr(block, "type", None)


def _bfield(block: Any, name: str, default: Any = None) -> Any:
    if isinstance(block, dict):
        return block.get(name, default)
    return getattr(block, name, default)


def _tool_use_blocks(blocks: Iterable[Any]) -> list[Any]:
    return [b for b in blocks if _btype(b) == "tool_use"]


def _text_from(blocks: Iterable[Any]) -> str:
    return "".join(_bfield(b, "text", "") or "" for b in blocks if _btype(b) == "text")


# --------------------------------------------------------------------------- #
# Stratified selection (plan §0 coverage targets, PHASE 5 step 1)             #
# --------------------------------------------------------------------------- #

def stratified_selection(
    scenarios: list[Scenario],
    n: int,
    seed: int,
) -> list[Scenario]:
    """Pick ``n`` scenarios meeting the §0 coverage floors.

    Guarantees (as far as the pool allows):
      * each of the 11 tools appears (round-robin across tools),
      * each permission class (READ/WRITE/DESTRUCTIVE) appears above a floor,
      * each complexity (single/multi/diagnostic) appears above a floor.

    Deterministic in ``seed``.  Selection is unique by scenario id; if ``n``
    exceeds the unique pool it cycles, tagging repeats so ids stay unique
    (keeps ``--resume`` correct).
    """
    rng = random.Random(seed)
    pool = list(scenarios)
    rng.shuffle(pool)

    selected: list[Scenario] = []
    seen: set[str] = set()

    def _take(pred, count: int) -> None:
        added = 0
        for s in pool:
            if added >= count or len(selected) >= n:
                break
            if s.id in seen:
                continue
            if pred(s):
                selected.append(s)
                seen.add(s.id)
                added += 1

    # Floor per stratum: at least 1, scaled gently with n.
    floor = max(1, n // 20)

    # Guarantee permission-class coverage (WRITE/DESTRUCTIVE are the rare ones).
    for opc in (
        coreimports.OpClass.READ,
        coreimports.OpClass.WRITE,
        coreimports.OpClass.DESTRUCTIVE,
    ):
        _take(lambda s, _o=opc: s.permission_class == _o, floor)

    # Guarantee complexity coverage.
    for cx in ("single", "multi", "diagnostic"):
        _take(lambda s, _c=cx: s.complexity == _c, floor)

    # Fill the remainder round-robin by tool for balanced tool coverage.
    by_tool: dict[str, list[Scenario]] = {}
    for s in pool:
        by_tool.setdefault(s.tool, []).append(s)
    tool_order = sorted(by_tool)
    cursor = {t: 0 for t in tool_order}

    while len(selected) < n:
        progressed = False
        for t in tool_order:
            if len(selected) >= n:
                break
            lst = by_tool[t]
            while cursor[t] < len(lst) and lst[cursor[t]].id in seen:
                cursor[t] += 1
            if cursor[t] < len(lst):
                s = lst[cursor[t]]
                cursor[t] += 1
                selected.append(s)
                seen.add(s.id)
                progressed = True
        if not progressed:
            break  # unique pool exhausted

    # If asked for more than the unique pool holds, cycle with suffixed ids so
    # every emitted record still has a unique, resumable scenario_id.
    if len(selected) < n and selected:
        base = list(selected)
        i = 0
        dup = 0
        while len(selected) < n:
            src = base[i % len(base)]
            i += 1
            if i % len(base) == 0:
                dup += 1
            # Rebuild as a fresh Scenario with a unique id (frozen dataclass).
            selected.append(
                Scenario(
                    id=f"{src.id}-rep{dup + 1}",
                    tool=src.tool,
                    operation=src.operation,
                    permission_class=src.permission_class,
                    complexity=src.complexity,
                    user_input=src.user_input,
                    notes=src.notes,
                )
            )

    return selected[:n]


# --------------------------------------------------------------------------- #
# Resume support                                                              #
# --------------------------------------------------------------------------- #

def _existing_ids(path: str) -> tuple[set[str], int]:
    """Return (already-produced scenario ids, line count) for ``--resume``."""
    ids: set[str] = set()
    count = 0
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                count += 1
                try:
                    rec = json.loads(line)
                    sid = rec.get("meta", {}).get("scenario_id")
                    if sid:
                        ids.add(sid)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return ids, count


# --------------------------------------------------------------------------- #
# One trace                                                                    #
# --------------------------------------------------------------------------- #

@dataclass
class TraceOutcome:
    record: Optional[dict]
    dropped: bool
    reason: str = ""


async def _complete_tool_use(
    backend: Any,
    convo: list[dict],
    tools: list[dict],
    scenario: Scenario,
) -> tuple[Optional[list[Any]], Optional[dict], Optional[str]]:
    """First model turn: obtain a VALID tool_use, honoring the §5 re-ask ONCE.

    Returns (tool_use_blocks, validated_args, operation) or (None, None, None)
    on an unrecoverable MISS.
    """
    spec = coreimports.registry.get(scenario.tool)

    async def _try(messages: list[dict]) -> tuple[Optional[list[Any]], Optional[dict], Optional[str], str]:
        resp = await backend.complete(messages, tools, tool_choice="auto")
        blocks = resp.get("content_blocks", [])
        tus = _tool_use_blocks(blocks)
        if not tus:
            return None, None, None, "no tool_use block (prose where a tool was required)"
        block = tus[0]  # A6: single tool call per turn
        raw_args = _bfield(block, "input", {}) or {}
        try:
            operation, rest = coreimports.validate_arguments(spec, raw_args)
        except ValueError as exc:
            return None, None, None, str(exc)
        return tus, rest, operation, ""

    tus, rest, operation, detail = await _try(convo)
    if tus is not None:
        return tus, rest, operation

    # §5: append the router re-ask and retry ONCE.
    reask = {"role": "user", "content": _REASK.format(detail=detail)}
    tus, rest, operation, detail = await _try([*convo, reask])
    if tus is not None:
        return tus, rest, operation
    return None, None, None


async def generate_trace(
    scenario: Scenario,
    tier: str,
    seed: int,
    backend_name: str,
    model: str,
) -> TraceOutcome:
    """Produce one complete record for ``scenario`` (or a drop outcome)."""
    snapshot = make_context(tier, seed)
    tier_prompt = TIER_PROMPTS[tier]
    tools = coreimports.live_tool_list()

    cfg = coreimports.PromptConfig(
        tier_prompt=tier_prompt,
        snapshot_text=snapshot,
        user_input=scenario.user_input,
        tools=tools,
        tool_choice="auto",
    )
    base = coreimports.assemble_messages(cfg)  # [system, user]
    system_msg = base[0]
    user_msg = base[1] if len(base) > 1 else {"role": "user", "content": scenario.user_input}

    backend = make_backend(backend_name, scenario=scenario, model=model)

    # --- Turn 1: the tool call (with §5 re-ask on MISS) --------------------- #
    tus, op_args, operation = await _complete_tool_use(backend, list(base), tools, scenario)
    if tus is None:
        return TraceOutcome(None, True, "MISS after re-ask: no valid tool call")

    tool = scenario.tool
    opc = scenario.permission_class  # registry-derived OpClass (INV-schema-sync)

    # --- Assemble the conversation turns (after the system message) --------- #
    turns: list[dict] = [user_msg]

    # INV-permission-fidelity: model the confirm-before-execute gate for
    # non-READ ops so the trace teaches the gate (CLAUDE.md invariant 3).
    if opc != coreimports.OpClass.READ:
        cls = opc.value  # "write" | "destructive"
        confirm_prompt = _CONFIRM_PROMPT[cls]
        coreimports.assert_no_ai_language(confirm_prompt, "confirm_prompt")
        turns.append(convert.assistant_text_to_openai(confirm_prompt))
        turns.append({"role": "user", "content": _CONFIRM_WORD[cls]})

    assistant_tool_turn = convert.anthropic_tool_use_to_openai_tool_calls(tus)
    turns.append(assistant_tool_turn)

    tool_use_id = assistant_tool_turn["tool_calls"][0]["id"]

    # --- Turn 2 setup: simulate the tool result ---------------------------- #
    result = simulate(tool, operation, op_args, snapshot)
    # summaries are guaranteed I2-clean by simulate/; assert defensively.
    coreimports.assert_no_ai_language(str(result.get("summary", "")), "simulate.summary")
    tool_msg = convert.anthropic_tool_result_to_openai_tool_msg(tool_use_id, result)
    turns.append(tool_msg)

    # --- Turn 2: the final English answer ----------------------------------- #
    followup = [system_msg, *turns]  # includes the role:"tool" msg -> Fake ends turn
    final_text = ""
    for attempt in range(2):  # regenerate once on an I2 violation
        resp = await backend.complete(followup, tools, tool_choice="auto")
        candidate = _text_from(resp.get("content_blocks", []))
        if not candidate.strip():
            continue
        try:
            coreimports.assert_no_ai_language(candidate, "final_answer")
        except ValueError:
            continue  # regenerate
        final_text = candidate
        break

    if not final_text.strip():
        return TraceOutcome(None, True, "no I2-clean final answer produced")

    turns.append(convert.assistant_text_to_openai(final_text))

    meta = {
        "tier": tier,
        "scenario_id": scenario.id,
        "tool": tool,
        "operation": operation,
        "permission_class": opc.value,
        "complexity": scenario.complexity,
    }
    record = convert.assemble_record(system_msg["content"], tools, turns, meta)
    return TraceOutcome(record, False)


# --------------------------------------------------------------------------- #
# Driver                                                                       #
# --------------------------------------------------------------------------- #

async def run(args: argparse.Namespace) -> int:
    import os

    selection = stratified_selection(ALL_SCENARIOS, args.n, args.seed)

    done_ids, existing = ({}, 0)
    if args.resume:
        done_ids, existing = _existing_ids(args.out)
    else:
        done_ids = set()

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)

    # Scenarios still to produce (skip already-emitted ids on resume).
    todo = [s for s in selection if s.id not in done_ids]

    write_lock = asyncio.Lock()
    sem = asyncio.Semaphore(max(1, args.concurrency))

    written = 0
    dropped = 0
    open_mode = "a" if args.resume else "w"
    fh = open(args.out, open_mode, encoding="utf-8")

    bar = tqdm(total=len(todo), desc="generate", unit="rec") if tqdm else None

    async def worker(idx: int, scenario: Scenario) -> None:
        nonlocal written, dropped
        async with sem:
            try:
                outcome = await generate_trace(
                    scenario,
                    args.tier,
                    args.seed + idx,
                    args.backend,
                    args.claude_model,
                )
            except Exception as exc:  # noqa: BLE001
                dropped += 1
                sys.stderr.write(f"[drop] {scenario.id}: {type(exc).__name__}: {exc}\n")
                if bar:
                    bar.update(1)
                return

            if outcome.dropped or outcome.record is None:
                dropped += 1
                sys.stderr.write(f"[drop] {scenario.id}: {outcome.reason}\n")
            else:
                line = json.dumps(outcome.record, separators=(",", ":"), ensure_ascii=False)
                async with write_lock:
                    fh.write(line + "\n")
                    fh.flush()
                    written += 1
            if bar:
                bar.update(1)

    try:
        await asyncio.gather(*(worker(i, s) for i, s in enumerate(todo)))
    finally:
        fh.close()
        if bar:
            bar.close()

    total_lines = existing + written
    # Coverage summary over the just-selected set (best-effort; validate.py is
    # the authoritative gate).
    tools_seen = sorted({s.tool for s in selection})
    classes_seen = sorted({s.permission_class.value for s in selection})
    complexities_seen = sorted({s.complexity for s in selection})
    sys.stderr.write(
        f"[summary] backend={args.backend} tier={args.tier} "
        f"written={written} dropped={dropped} total_lines={total_lines} "
        f"tools={len(tools_seen)} classes={classes_seen} "
        f"complexities={complexities_seen} out={args.out}\n"
    )
    print(
        f"OK wrote {written} record(s) (total {total_lines}) to {args.out} "
        f"[dropped {dropped}]"
    )
    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m finetune.generate",
        description=(
            "Generate 0002-conformant ShareGPT/messages fine-tune traces "
            "(offline Fake backend by default; --backend anthropic for real runs)."
        ),
    )
    p.add_argument("--n", type=int, required=True, help="Total number of traces to target.")
    p.add_argument("--tier", choices=TIERS, default="radagon", help="Tier (persona/context depth + meta only).")
    p.add_argument("--out", default=DEFAULT_OUT, help=f"Output JSONL path (default {DEFAULT_OUT}).")
    p.add_argument("--resume", action="store_true", help="Append; skip already-produced scenario ids.")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Max concurrent traces.")
    p.add_argument("--backend", choices=("fake", "anthropic"), default="anthropic",
                   help="LLM backend. 'fake' is offline/no-key (default for smoke/CI); "
                        "'anthropic' is the real run.")
    p.add_argument("--claude-model", dest="claude_model", default=DEFAULT_MODEL,
                   help=f"Anthropic model id (default {DEFAULT_MODEL}).")
    p.add_argument("--seed", type=int, default=0, help="Deterministic selection/context seed.")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.n <= 0:
        sys.stderr.write("--n must be positive\n")
        return 2
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
