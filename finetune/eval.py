"""finetune/eval.py — score a served model on the held-out eval traces.

For each record in eval.jsonl, replay the conversation up to (not including)
the assistant TOOL-CALL turn, send it to an Ollama model with the record's own
tool list, and score the model's reply against the reference:

  tool        chosen function name == reference tool
  op          chosen operation     == reference operation
  valid       arguments validate through the LIVE router (coreimports)
  args        arguments == reference arguments exactly
  args_req    required arguments (for the reference op) match after
              normalisation (case, trailing slashes) — the fair strictness
  reask       when the first call fails validation, the router's re-ask text is
              fed back once (exactly what the product does) and the second
              attempt is scored as op2/valid2
  i2          any text the model emitted is free of forbidden terms

Tools are advertised the way the product advertises them: the per-request
selection from core.agent.toolselect (top-k + docs), not the full registry and
not the record's own list.  The model is NOT asked to request permission; the
runtime gate does that in code (tests/test_gate_invariant.py).

Usage (on black-sky, next to Ollama):
  python -m finetune.eval finetune/data/eval.jsonl --model marika-ft --model qwen2.5:3b
"""
from __future__ import annotations

import argparse, json, sys, time, urllib.request
from finetune import coreimports
from core.agent.toolselect import ToolSelector
from core.agent.router import reask_invalid_arguments
from core.agent.prompt import build_tool_list

_SELECTOR = ToolSelector(coreimports.registry)

OLLAMA = "http://127.0.0.1:11434/api/chat"


def chat(model: str, messages: list, tools: list, num_ctx: int) -> dict:
    body = json.dumps({"model": model, "messages": messages, "tools": tools, "stream": False,
                       "options": {"temperature": 0, "num_ctx": num_ctx}, "keep_alive": "10m"}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())["message"]


def split_record(rec: dict):
    msgs = rec["messages"]
    call_idx = next(i for i, m in enumerate(msgs) if m["role"] == "assistant" and m.get("tool_calls"))
    call = msgs[call_idx]["tool_calls"][0]["function"]
    ref_args = json.loads(call["arguments"]) if isinstance(call["arguments"], str) else call["arguments"]
    # system + the operator request only: v2 has no confirm exchange, and the
    # model is not expected to produce one.
    prefix = [{"role": m["role"], "content": m.get("content") or ""} for m in msgs[:2]]
    return prefix, call["name"], ref_args


def advertised_tools(user_input: str) -> list[dict]:
    names = _SELECTOR.select(user_input)
    return build_tool_list(coreimports.registry_schemas(coreimports.registry, names))


def i2_ok(text: str) -> bool:
    try:
        coreimports.assert_no_ai_language(text or "", "eval")
        return True
    except ValueError:
        return False


def _norm(v):
    if isinstance(v, str):
        v = v.strip().lower().rstrip("/") or "/"
        for suf in (".service", ".timer", ".socket"):
            if v.endswith(suf):
                v = v[: -len(suf)]
        return v
    if isinstance(v, list):
        return sorted(_norm(x) for x in v)
    return v


def _parse_call(m: dict):
    tcs = m.get("tool_calls") or []
    if not tcs:
        return None, None
    fn = tcs[0]["function"]
    args = fn.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    return fn.get("name"), args


def _judge(name, args, ref_tool, ref_args):
    out = {"tool": name == ref_tool, "op": False, "valid": False, "args": False, "args_req": False, "err": ""}
    ref_op = ref_args.get("operation")
    out["op"] = out["tool"] and args.get("operation") == ref_op
    spec = coreimports.registry.get(name) if name else None
    if spec is None:
        out["err"] = f"unknown tool {name!r}"
        return out
    if "operation" not in args and len(spec.ops) == 1:  # mirrors the router's single-op default
        args = {"operation": next(iter(spec.ops)), **args}
        out["op"] = out["tool"] and args.get("operation") == ref_op
    try:
        coreimports.validate_arguments(spec, dict(args))
        out["valid"] = True
    except ValueError as exc:
        out["err"] = str(exc)
    out["args"] = out["op"] and args == ref_args
    if out["op"]:
        req = {a.name for a in spec.ops[ref_op].args if a.required} | {"operation"}
        out["args_req"] = all(_norm(args.get(k)) == _norm(ref_args.get(k)) for k in req)
    return out


def score_one(model: str, rec: dict, num_ctx: int) -> dict:
    prefix, ref_tool, ref_args = split_record(rec)
    user_input = prefix[1]["content"]
    tools = advertised_tools(user_input)
    out = {"id": rec["meta"]["scenario_id"], "pc": rec["meta"]["permission_class"],
           "advertised": ref_tool in {t["function"]["name"] for t in tools},
           "called": False, "tool": False, "op": False, "valid": False, "args": False, "args_req": False,
           "reask": False, "op2": False, "valid2": False, "i2": True, "chosen": None}

    m = chat(model, prefix, tools, num_ctx)
    out["i2"] = i2_ok(m.get("content", ""))
    name, args = _parse_call(m)
    if name is None:
        return out
    out["called"] = True
    j = _judge(name, args, ref_tool, ref_args)
    out.update({k: j[k] for k in ("tool", "op", "valid", "args", "args_req")})
    out["chosen"] = f"{name}.{args.get('operation')}"
    out["op2"], out["valid2"] = out["op"], out["valid"]

    if not j["valid"] and coreimports.registry.get(name) is not None:
        # One product-faithful re-ask round (repl.py feeds the router's text back).
        out["reask"] = True
        call_id = "call_eval_1"
        msgs = prefix + [
            {"role": "assistant", "content": "", "tool_calls": [{"id": call_id, "type": "function",
              "function": {"name": name, "arguments": args}}]},
            {"role": "tool", "tool_call_id": call_id, "content": reask_invalid_arguments(name, j["err"])},
        ]
        m2 = chat(model, msgs, tools, num_ctx)
        out["i2"] = out["i2"] and i2_ok(m2.get("content", ""))
        n2, a2 = _parse_call(m2)
        if n2 is not None:
            j2 = _judge(n2, a2, ref_tool, ref_args)
            out["op2"], out["valid2"] = j2["op"], j2["valid"]
            out["chosen"] = f"{out['chosen']} -> {n2}.{a2.get('operation')}"
    return out


def score_multiturn(model: str, scn, num_ctx: int, tier: str = "radagon") -> dict:
    """Held-out FOLLOW-UP scoring.  Turn 1 is teacher-forced exactly as the
    runtime would record it (reference call, simulated result, answer derived
    from the result); the model is then asked for turn 2's call with that
    history in context.  Tools advertised = selection for turn 2's text plus
    the tool used in turn 1 (the REPL pins tools already used)."""
    from finetune.assemble import render_answer, _stable_seed
    from finetune.context import make_context
    from finetune.simulate import simulate
    from finetune.generate import TIER_PROMPTS

    t1, t2 = scn.turns[0], scn.turns[1]
    snapshot = make_context(tier, _stable_seed(scn.id))
    names = _SELECTOR.select(t2.user_input, extra=[t1.tool])
    tools = build_tool_list(coreimports.registry_schemas(coreimports.registry, names))
    cfg = coreimports.PromptConfig(tier_prompt=TIER_PROMPTS[tier], snapshot_text=snapshot,
                                   user_input=t1.user_input, tools=tools, tool_choice="auto")
    system_msg = coreimports.assemble_messages(cfg)[0]
    spec1 = coreimports.registry.get(t1.tool)
    op1, rest1 = coreimports.validate_arguments(spec1, dict(t1.args))
    res1 = simulate(t1.tool, op1, rest1, snapshot)
    payload = {"exit_code": res1.get("exit_code", 0), "stdout_summary": (res1.get("stdout") or "")[:512],
               "stderr_summary": (res1.get("stderr") or "")[:512], "summary": res1.get("summary", "")}
    msgs = [
        {"role": "system", "content": system_msg["content"]},
        {"role": "user", "content": t1.user_input},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call_t1", "type": "function",
            "function": {"name": t1.tool, "arguments": dict(t1.args)}}]},
        {"role": "tool", "tool_call_id": "call_t1", "content": json.dumps(payload)},
        {"role": "assistant", "content": render_answer(res1)},
        {"role": "user", "content": t2.user_input},
    ]
    out = {"id": scn.id, "pc": "followup", "advertised": t2.tool in names, "called": False, "tool": False,
           "op": False, "valid": False, "args": False, "args_req": False, "reask": False,
           "op2": False, "valid2": False, "i2": True, "chosen": None}
    m = chat(model, msgs, tools, num_ctx)
    out["i2"] = i2_ok(m.get("content", ""))
    name, args = _parse_call(m)
    if name is None:
        return out
    out["called"] = True
    j = _judge(name, args, t2.tool, dict(t2.args))
    out.update({k: j[k] for k in ("tool", "op", "valid", "args", "args_req")})
    out["op2"], out["valid2"] = out["op"], out["valid"]
    out["chosen"] = f"{name}.{args.get('operation')}"
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path"); p.add_argument("--model", action="append", required=True)
    p.add_argument("--num-ctx", type=int, default=16384); p.add_argument("--limit", type=int, default=0)
    p.add_argument("--out", default="finetune/data/eval_results.jsonl")
    p.add_argument("--multiturn", action="store_true",
                   help="Score the held-out follow-up pool (finetune/scenarios/eval_pool_multiturn.py); PATH is ignored.")
    a = p.parse_args(argv)
    if a.multiturn:
        from finetune.scenarios.eval_pool_multiturn import EVAL_MULTITURN
        recs = list(EVAL_MULTITURN)
    else:
        recs = [json.loads(l) for l in open(a.path)]
    if a.limit: recs = recs[:a.limit]
    summary = {}
    with open(a.out, "a") as fh:
        for model in a.model:
            rows, t0 = [], time.time()
            for i, rec in enumerate(recs, 1):
                try:
                    r = score_multiturn(model, rec, a.num_ctx) if a.multiturn else score_one(model, rec, a.num_ctx)
                except Exception as exc:
                    _id = rec.id if a.multiturn else rec["meta"]["scenario_id"]
                    r = {"id": _id, "pc": "followup" if a.multiturn else rec["meta"]["permission_class"], "error": str(exc)[:200]}
                r["model"] = model; rows.append(r); fh.write(json.dumps(r) + "\n"); fh.flush()
                print(f"[{model}] {i}/{len(recs)} {r['id']} adv={r.get('advertised')} op={r.get('op')} valid={r.get('valid')} op2={r.get('op2')} {r.get('chosen')}", file=sys.stderr)
            n = len(rows)
            def rate(k): return sum(bool(r.get(k)) for r in rows) / n
            summary[model] = {
                "n": n, "advertised": rate("advertised"), "called": rate("called"), "tool": rate("tool"),
                "op": rate("op"), "valid": rate("valid"), "args_req": rate("args_req"), "args_exact": rate("args"),
                "reask_used": rate("reask"), "op_after_reask": rate("op2"), "valid_after_reask": rate("valid2"),
                "i2_clean": rate("i2"), "errors": sum("error" in r for r in rows),
                "sec_per_record": (time.time() - t0) / n,
            }
            print(json.dumps({model: summary[model]}), file=sys.stderr)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
