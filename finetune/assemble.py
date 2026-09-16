"""finetune/assemble.py — the deterministic GENUINE-LOOP judgment assembler.

This module is the *scoring* half of the GENUINE-LOOP subscription data
generator.  A separate fan-out of judgment agents decides, COLD from the user
prompt alone (label hidden — see the prompts-only shards written by
``finetune.shard``), which tool + operation the request needs, using the LIVE
registry.  Each such decision is emitted as a judgment record::

    {scenario_id, tool, operation, args, answer, confirm?}

where ``tool``/``operation`` are the CHOSEN (cold) values — they may or may not
match the scenario's TRUE label.  This module takes those judgments and:

  1. Looks the scenario up by id in ``finetune.scenarios.ALL_SCENARIOS`` to get
     its ``user_input`` and its TRUE label (used ONLY to SCORE, never as an
     input to the choice — GENUINE-LOOP).
  2. VALIDATES the CHOSEN tool/op/args against the LIVE router
     (``registry.get`` + ``coreimports.validate_arguments``).  A failure DROPS
     the record (logged) — never a MISS in the corpus.
  3. Determines the CHOSEN op's REAL permission class from the registry OpSpec
     (``ToolSpec.permission_class_for``).  This drives the confirm turn — NOT
     the scenario label.
  4. Builds the live system prompt + tool list exactly as ``generate.py`` does
     (``assemble_messages`` over the house prompt + ``make_context``).
  5. Simulates the CHOSEN call (``finetune.simulate.simulate``).
  6. Assembles a 0002-conformant ShareGPT/messages trace via the REAL
     ``convert.py`` helpers (INV-0002 string-args, confirm-before-write gate).
  7. Asserts the final answer is I2-clean (drop+log on violation).
  8. Streams one JSONL line per surviving record and reports the SELECTION
     AGREEMENT RATE (fraction where the cold choice matched the label).

CLI::

    python -m finetune.assemble \
        --judgments finetune/data/judgments \
        --out finetune/data/traces.jsonl \
        --tier radagon

Load-bearing invariants threaded here
-------------------------------------
GENUINE-LOOP   The label is used ONLY to score (``selection_match``); it is
               NEVER read to make or repair the tool/op choice.
INV-schema-sync  Tool spec, op set, and permission_class are derived LIVE from
               the registry (via finetune.coreimports) — nothing hardcoded.
INV-0002-string-args  The assistant tool-call turn goes through the real
               convert.py, so ``function.arguments`` is a JSON-ENCODED STRING,
               ``content`` is None, and the tool id correlates verbatim to the
               following role:"tool" message.
INV-confirm-gate  For every NON-READ chosen op the trace models the
               confirm-before-execute turn (a plain "yes" for WRITE; the typed
               destructive word for DESTRUCTIVE) BEFORE the executing call.
INV-house-prompt  The system prompt comes from the live ``assemble_messages``
               (core's _HOUSE_SYSTEM_PROMPT via coreimports), never hand-written.
INV-I2         The final answer is asserted clean by ``assert_no_ai_language``.
INV-offline    No network, no ANTHROPIC_API_KEY, stdlib + finetune seams only.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Iterator, Optional

from finetune import convert, coreimports
from finetune.context import make_context
from finetune.scenarios import ALL_SCENARIOS, Scenario
from finetune.simulate import simulate

# Reuse the SAME confirm/tier wording generate.py teaches, so the two producers
# never drift.  The confirm PROMPT is assistant content (I2-asserted below); the
# confirm WORD default is the operator's reply ("yes" for WRITE, the typed
# destructive word for DESTRUCTIVE — mirrors permissions.DESTRUCTIVE_CONFIRM_WORD).
from finetune.generate import TIER_PROMPTS, _CONFIRM_PROMPT, _CONFIRM_WORD


DEFAULT_JUDGMENTS = "finetune/data/judgments"
DEFAULT_OUT = "finetune/data/traces.jsonl"
TIERS = ("marika", "radagon")


# --------------------------------------------------------------------------- #
# Deterministic helpers                                                        #
# --------------------------------------------------------------------------- #

def _stable_seed(scenario_id: str) -> int:
    """A stable, process-independent seed from a scenario id.

    Python's built-in ``hash`` is salted per-process; we need the SAME context
    profile for a given scenario id across every run, so we hash explicitly.
    """
    digest = hashlib.md5(scenario_id.encode("utf-8")).hexdigest()
    return int(digest, 16)


def _tool_use_id(scenario_id: str) -> str:
    """A deterministic ``toolu_`` id for the tool_use block.

    convert.py carries this VERBATIM into both the assistant tool-call turn and
    the following role:"tool" message, preserving 0002 §2/§3 correlation.
    """
    return "toolu_" + hashlib.sha1(scenario_id.encode("utf-8")).hexdigest()[:24]


# --------------------------------------------------------------------------- #
# Judgment loading                                                            #
# --------------------------------------------------------------------------- #

def iter_judgments(path: str) -> Iterator[tuple[str, int, dict]]:
    """Yield (source_file, line_no, judgment_dict) for every judgment record.

    ``path`` may be a directory (all ``*.jsonl`` / ``*.json`` files, sorted) or
    a single file.  Blank lines are skipped; a line that is not a JSON object is
    surfaced as a parse error the caller drops+logs.
    """
    if os.path.isdir(path):
        files = sorted(
            set(glob.glob(os.path.join(path, "*.jsonl")))
            | set(glob.glob(os.path.join(path, "*.json")))
        )
    else:
        files = [path]

    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    yield fpath, line_no, {"__parse_error__": str(exc)}
                    continue
                yield fpath, line_no, rec


# --------------------------------------------------------------------------- #
# One record                                                                   #
# --------------------------------------------------------------------------- #

@dataclass
class AssembleOutcome:
    record: Optional[dict]
    dropped: bool
    reason: str = ""
    selection_match: bool = False


def _build_scenario_index(pool: str = "train") -> dict[str, Scenario]:
    if pool == "v2":
        from finetune.scenarios_v2 import load_all
        return {s.id: Scenario(id=s.id, tool=s.tool, operation=s.operation,
                               permission_class=coreimports.registry.get(s.tool).permission_class_for(s.operation),
                               complexity=s.complexity, user_input=s.user_input, notes=s.notes)
                for s in load_all()}
    from finetune.shard import pool_scenarios
    return {s.id: s for s in pool_scenarios(pool)}


def assemble_v3(scn, tier: str) -> AssembleOutcome:
    """Build a multi-turn trace for one corpus-v3 scenario.  Every tool turn is
    validated through the live router, simulated, and answered from the
    result; answer turns carry the authored English.  Tools advertised are the
    per-request selection for turn 1 plus every tool used in the record (the
    REPL pins tools already used in the conversation the same way)."""
    seed = _stable_seed(scn.id)
    snapshot = make_context(tier, seed)
    first = scn.turns[0]
    used = [t.tool for t in scn.turns if t.tool]
    global _SELECTOR
    if _SELECTOR is None:
        from core.agent.toolselect import ToolSelector
        _SELECTOR = ToolSelector(coreimports.registry)
    names = _SELECTOR.select(first.user_input, extra=used)
    tools = coreimports.build_tool_list(coreimports.registry_schemas(coreimports.registry, names))
    cfg = coreimports.PromptConfig(tier_prompt=TIER_PROMPTS[tier], snapshot_text=snapshot,
                                   user_input=first.user_input, tools=tools, tool_choice="auto")
    base = coreimports.assemble_messages(cfg)
    system_msg = base[0]
    turns: list[dict] = []
    last_tool, last_op, last_pc = None, None, "read"
    for i, t in enumerate(scn.turns):
        turns.append({"role": "user", "content": t.user_input})
        if t.tool is None:
            try:
                coreimports.assert_no_ai_language(t.answer, "answer_turn")
            except ValueError as exc:
                return AssembleOutcome(None, True, f"{scn.id}: answer turn failed I2: {exc}")
            turns.append(convert.assistant_text_to_openai(t.answer))
            continue
        spec = coreimports.registry.get(t.tool)
        try:
            operation, rest = coreimports.validate_arguments(spec, dict(t.args))
        except ValueError as exc:
            return AssembleOutcome(None, True, f"{scn.id} turn {i+1}: invalid call: {exc}")
        result = simulate(t.tool, operation, rest, snapshot)
        try:
            coreimports.assert_no_ai_language(str(result.get("summary", "")), "simulate.summary")
        except ValueError as exc:
            return AssembleOutcome(None, True, f"{scn.id} turn {i+1}: {exc}")
        tool_use_id = _tool_use_id(f"{scn.id}#{i}")
        block = {"type": "tool_use", "id": tool_use_id, "name": t.tool, "input": {"operation": operation, **rest}}
        call_turn = convert.anthropic_tool_use_to_openai_tool_calls([block])
        turns.append(call_turn)
        turns.append(convert.anthropic_tool_result_to_openai_tool_msg(call_turn["tool_calls"][0]["id"], result))
        answer = render_answer(result)
        try:
            coreimports.assert_no_ai_language(answer, "final_answer")
        except ValueError as exc:
            return AssembleOutcome(None, True, f"{scn.id} turn {i+1}: answer failed I2: {exc}")
        turns.append(convert.assistant_text_to_openai(answer))
        last_tool, last_op = t.tool, operation
        last_pc = (spec.permission_class_for(operation) or coreimports.OpClass.WRITE).value
    meta = {"tier": tier, "scenario_id": scn.id, "kind": scn.kind, "turns": len(scn.turns),
            "chosen_tool": last_tool, "chosen_operation": last_op, "permission_class": last_pc,
            "labeled_tool": scn.tool, "labeled_operation": last_op, "selection_match": True}
    record = convert.assemble_record(system_msg["content"], tools, turns, meta)
    return AssembleOutcome(record, False, selection_match=True)


def iter_v2_judgments() -> Iterator[tuple[str, int, dict]]:
    """Corpus v2 scenarios carry their own reference call and answer; expose
    them in the judgment shape so assemble_one is the single trace builder."""
    from finetune.scenarios_v2 import load_all
    for i, s in enumerate(load_all(), start=1):
        args = {k: v for k, v in s.args.items() if k != "operation"}
        yield "scenarios_v2", i, {"scenario_id": s.id, "tool": s.tool, "operation": s.operation,
                                   "args": args, "answer": s.answer}


_SELECTOR = None


def render_answer(result: dict) -> str:
    """The operator-facing answer, derived from the simulated result so the
    supervision never contradicts the tool output (17% of corpus v2 paired a
    failing result with a success answer).  Terse: outcome line, then at most
    six lines of real output."""
    code = int(result.get("exit_code", 0) or 0)
    summary = (result.get("summary") or "").strip()
    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    if code != 0:
        first_err = stderr.splitlines()[0].strip() if stderr else ""
        head = f"Failed (exit {code})"
        body = summary or first_err
        if first_err and first_err not in body:
            body = f"{body} {first_err}".strip()
        return f"{head}: {body}" if body else f"{head}."
    lines = [ln.rstrip() for ln in stdout.splitlines() if ln.strip()][:6]
    out = summary or "Done, exit code 0."
    if lines:
        out += "\n" + "\n".join(lines)
    return out


def _selected_tools(user_input: str, pin: str) -> list[dict]:
    """Advertise the per-request selection (core.agent.toolselect), exactly as
    the REPL does, with the chosen tool pinned so every op stays trainable."""
    global _SELECTOR
    if _SELECTOR is None:
        from core.agent.toolselect import ToolSelector
        _SELECTOR = ToolSelector(coreimports.registry)
    names = _SELECTOR.select(user_input, extra=[pin])
    return coreimports.build_tool_list(coreimports.registry_schemas(coreimports.registry, names))


def assemble_one(
    judgment: dict,
    tier: str,
    scenarios_by_id: dict[str, Scenario],
    *,
    confirm_turns: bool = True,
    select_tools: bool = False,
    ground_answers: bool = False,
) -> AssembleOutcome:
    """Assemble a single trace from one cold judgment, or return a drop."""
    if "__parse_error__" in judgment:
        return AssembleOutcome(None, True, f"unparseable judgment line: {judgment['__parse_error__']}")

    scenario_id = judgment.get("scenario_id")
    if not scenario_id:
        return AssembleOutcome(None, True, "judgment missing scenario_id")

    # 1. Look up the scenario (its user_input + TRUE label — label used ONLY to
    #    score below, NEVER to make or repair the choice).
    scenario = scenarios_by_id.get(scenario_id)
    if scenario is None:
        return AssembleOutcome(None, True, f"unknown scenario_id {scenario_id!r}")

    chosen_tool = judgment.get("tool")
    chosen_operation = judgment.get("operation")
    args = judgment.get("args") or {}
    answer = judgment.get("answer")

    if not chosen_tool or not chosen_operation:
        return AssembleOutcome(None, True, f"{scenario_id}: judgment missing tool/operation")
    if not isinstance(args, dict):
        return AssembleOutcome(None, True, f"{scenario_id}: args is not an object")
    if not isinstance(answer, str) or not answer.strip():
        return AssembleOutcome(None, True, f"{scenario_id}: judgment missing answer text")

    # 2. VALIDATE the COLD choice against the LIVE router.  A failure DROPS the
    #    record (never emit a MISS into the corpus).
    spec = coreimports.registry.get(chosen_tool)
    if spec is None:
        return AssembleOutcome(None, True, f"{scenario_id}: chosen tool {chosen_tool!r} not in live registry")
    try:
        operation, rest = coreimports.validate_arguments(
            spec, {"operation": chosen_operation, **args}
        )
    except ValueError as exc:
        return AssembleOutcome(None, True, f"{scenario_id}: invalid chosen call: {exc}")

    # 3. REAL permission class of the CHOSEN op from the registry OpSpec — this
    #    drives the confirm turn, NOT the scenario label.
    opc = spec.permission_class_for(operation) or coreimports.OpClass.WRITE

    # 4. Live system prompt + tool list, exactly as generate.py composes them.
    seed = _stable_seed(scenario_id)
    snapshot = make_context(tier, seed)
    tools = _selected_tools(scenario.user_input, chosen_tool) if select_tools else coreimports.live_tool_list()
    cfg = coreimports.PromptConfig(
        tier_prompt=TIER_PROMPTS[tier],
        snapshot_text=snapshot,
        user_input=scenario.user_input,
        tools=tools,
        tool_choice="auto",
    )
    base = coreimports.assemble_messages(cfg)  # [system, user]
    system_msg = base[0]
    user_msg = base[1] if len(base) > 1 else {"role": "user", "content": scenario.user_input}

    # 5. Simulate the CHOSEN call.
    result = simulate(chosen_tool, operation, rest, snapshot)
    coreimports.assert_no_ai_language(str(result.get("summary", "")), "simulate.summary")

    # 6. Assemble the trace via the REAL convert.py helpers.
    turns: list[dict] = [user_msg]

    # INV-confirm-gate: model the confirm-before-execute turn for NON-READ ops.
    if confirm_turns and opc != coreimports.OpClass.READ:
        cls = opc.value  # "write" | "destructive"
        confirm_prompt = _CONFIRM_PROMPT[cls]
        coreimports.assert_no_ai_language(confirm_prompt, "confirm_prompt")
        turns.append(convert.assistant_text_to_openai(confirm_prompt))
        confirm_reply = judgment.get("confirm") or _CONFIRM_WORD[cls]
        turns.append({"role": "user", "content": confirm_reply})

    # Assistant tool-call turn — arguments become a JSON-ENCODED STRING, content
    # None, id carried verbatim (INV-0002-string-args) — all via convert.py.
    tool_use_id = _tool_use_id(scenario_id)
    tool_use_block = {
        "type": "tool_use",
        "id": tool_use_id,
        "name": chosen_tool,
        "input": {"operation": operation, **rest},
    }
    assistant_tool_turn = convert.anthropic_tool_use_to_openai_tool_calls([tool_use_block])
    turns.append(assistant_tool_turn)

    correlated_id = assistant_tool_turn["tool_calls"][0]["id"]
    turns.append(convert.anthropic_tool_result_to_openai_tool_msg(correlated_id, result))

    # 7. Final English answer — derived from the simulated result when
    #    ground_answers is set; assert I2-clean (drop+log on violation).
    if ground_answers:
        answer = render_answer(result)
    try:
        coreimports.assert_no_ai_language(answer, "final_answer")
    except ValueError as exc:
        return AssembleOutcome(None, True, f"{scenario_id}: answer failed I2 check: {exc}")
    turns.append(convert.assistant_text_to_openai(answer))

    selection_match = (chosen_tool == scenario.tool and operation == scenario.operation)

    meta = {
        "tier": tier,
        "scenario_id": scenario_id,
        "chosen_tool": chosen_tool,
        "chosen_operation": operation,
        "permission_class": opc.value,
        "labeled_tool": scenario.tool,
        "labeled_operation": scenario.operation,
        "selection_match": selection_match,
    }
    record = convert.assemble_record(system_msg["content"], tools, turns, meta)
    return AssembleOutcome(record, False, selection_match=selection_match)


# --------------------------------------------------------------------------- #
# Driver                                                                       #
# --------------------------------------------------------------------------- #

def run(args: argparse.Namespace) -> int:
    scenarios_by_id = _build_scenario_index(getattr(args, "pool", "train"))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)

    assembled = 0
    matched = 0
    dropped = 0
    drop_reasons: dict[str, int] = {}

    def _short_reason(reason: str) -> str:
        # Bucket per-record reasons (which carry a scenario id) into a class.
        for key in (
            "unparseable judgment line",
            "missing scenario_id",
            "unknown scenario_id",
            "missing tool/operation",
            "args is not an object",
            "missing answer text",
            "not in live registry",
            "invalid chosen call",
            "answer failed I2 check",
        ):
            if key in reason:
                return key
        return "other"

    if args.pool == "v3":
        from finetune.scenarios_v3 import load_all as _load_v3
        n_ok = n_drop = 0
        with open(args.out, "a" if args.append else "w", encoding="utf-8") as out_fh:
            for scn in _load_v3():
                oc = assemble_v3(scn, args.tier)
                if oc.dropped:
                    n_drop += 1; print(f"[drop] {oc.reason}", file=sys.stderr); continue
                out_fh.write(json.dumps(oc.record, ensure_ascii=False) + "\n"); n_ok += 1
        print(f"OK assembled {n_ok} v3 trace(s) to {args.out} [dropped {n_drop}]")
        return 0 if n_ok else 1
    source = iter_v2_judgments() if args.pool == "v2" else iter_judgments(args.judgments)
    with open(args.out, "a" if args.append else "w", encoding="utf-8") as out_fh:
        for _fpath, _line_no, judgment in source:
            try:
                outcome = assemble_one(judgment, args.tier, scenarios_by_id,
                                       confirm_turns=not args.no_confirm, select_tools=args.select_tools,
                                       ground_answers=args.ground_answers)
            except Exception as exc:  # noqa: BLE001 — never let one bad record abort the stream
                dropped += 1
                bucket = f"exception:{type(exc).__name__}"
                drop_reasons[bucket] = drop_reasons.get(bucket, 0) + 1
                sys.stderr.write(f"[drop] {judgment.get('scenario_id', '?')}: {type(exc).__name__}: {exc}\n")
                continue

            if outcome.dropped or outcome.record is None:
                dropped += 1
                bucket = _short_reason(outcome.reason)
                drop_reasons[bucket] = drop_reasons.get(bucket, 0) + 1
                sys.stderr.write(f"[drop] {outcome.reason}\n")
                continue

            # Stream one JSONL line — never hold the whole corpus in memory.
            out_fh.write(json.dumps(outcome.record, separators=(",", ":"), ensure_ascii=False) + "\n")
            out_fh.flush()
            assembled += 1
            if outcome.selection_match:
                matched += 1

    rate = (matched / assembled) if assembled else 0.0
    reasons_str = ", ".join(f"{k}={v}" for k, v in sorted(drop_reasons.items())) or "none"
    sys.stderr.write(
        f"[summary] tier={args.tier} assembled={assembled} dropped={dropped} "
        f"drop_reasons=[{reasons_str}] selection_agreement={matched}/{assembled} "
        f"({rate:.3f}) out={args.out}\n"
    )
    print(
        f"OK assembled {assembled} trace(s) to {args.out} "
        f"[dropped {dropped}; drop_reasons: {reasons_str}]"
    )
    print(f"SELECTION AGREEMENT RATE: {matched}/{assembled} = {rate:.3f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m finetune.assemble",
        description=(
            "Deterministically assemble 0002-conformant ShareGPT/messages traces "
            "from COLD judgment records, scoring the cold tool/op choice against "
            "the hidden scenario label (offline; no network, no API key)."
        ),
    )
    p.add_argument("--judgments", default=DEFAULT_JUDGMENTS,
                   help=f"Judgments file or directory (default {DEFAULT_JUDGMENTS}).")
    p.add_argument("--out", default=DEFAULT_OUT,
                   help=f"Output JSONL path (default {DEFAULT_OUT}).")
    p.add_argument("--no-confirm", action="store_true",
                   help="Do not model the confirm exchange (corpus v2: the runtime gate asks, not the model).")
    p.add_argument("--select-tools", action="store_true",
                   help="Advertise the per-request tool selection (core.agent.toolselect) instead of all tools.")
    p.add_argument("--append", action="store_true", help="Append to --out instead of overwriting.")
    p.add_argument("--ground-answers", action="store_true",
                   help="Derive the final answer from the simulated tool result (corpus v3) instead of the authored text.")
    p.add_argument("--pool", choices=("train", "eval", "v2", "v3"), default="train",
                   help="Scenario pool the judgments refer to (eval = held-out EVAL_SCENARIOS).")
    p.add_argument("--tier", choices=TIERS, default="radagon",
                   help="Tier (persona/context depth + meta only; never structure).")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
