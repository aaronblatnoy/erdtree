"""finetune/shard.py — label-hidden shard planner (GENUINE-LOOP Task B).

Splits the full ``ALL_SCENARIOS`` id set into ~30-id, DOMAIN-DIVERSE shards
(round-robin, so consecutive same-tool scenarios land in different shards) and
writes, for each shard, a PROMPTS-ONLY jsonl that a judgment agent reads to
choose a tool + operation COLD.

Outputs (all under finetune/data/, which is gitignored):

  finetune/data/_shards.json
      {"tier": "radagon", "variants": 1, "shards": [[<id>, ...], ...]}

  finetune/data/prompts/shard-<i>.jsonl
      One line per scenario with ONLY {"scenario_id", "user_input"} — the TRUE
      tool / operation / permission_class label is HIDDEN ON PURPOSE so the
      generator must decide COLD (GENUINE-LOOP).  The label lives only in
      ALL_SCENARIOS and is used later, by the assembler, to SCORE the choice.

Also ensures finetune/data/{prompts,judgments}/ exist.

Run::

    python -m finetune.shard --tier radagon --shard-size 30
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Optional

from finetune.scenarios import ALL_SCENARIOS

DATA_DIR = "finetune/data"
PROMPTS_DIR = os.path.join(DATA_DIR, "prompts")
JUDGMENTS_DIR = os.path.join(DATA_DIR, "judgments")
SHARDS_JSON = os.path.join(DATA_DIR, "_shards.json")


def _round_robin_shards(ids: list[str], shard_size: int) -> list[list[str]]:
    """Split ``ids`` into round-robin buckets of ~``shard_size`` each.

    ``num_shards`` is chosen so each shard holds about ``shard_size`` ids; a
    round-robin assignment (id i -> shard i % num_shards) makes each shard
    domain-diverse because ALL_SCENARIOS is grouped by tool.
    """
    total = len(ids)
    num_shards = max(1, round(total / shard_size))
    shards: list[list[str]] = [[] for _ in range(num_shards)]
    for i, sid in enumerate(ids):
        shards[i % num_shards].append(sid)
    return shards


def build(tier: str, shard_size: int, variants: int = 1) -> dict:
    """Write _shards.json + per-shard prompts-only jsonl; return the plan dict."""
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    os.makedirs(JUDGMENTS_DIR, exist_ok=True)

    ids = [s.id for s in ALL_SCENARIOS]
    prompt_by_id = {s.id: s.user_input for s in ALL_SCENARIOS}

    shards = _round_robin_shards(ids, shard_size)

    # Per-shard prompts-only jsonl — NO tool, NO operation, NO permission_class.
    for i, shard_ids in enumerate(shards):
        path = os.path.join(PROMPTS_DIR, f"shard-{i}.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for sid in shard_ids:
                fh.write(
                    json.dumps(
                        {"scenario_id": sid, "user_input": prompt_by_id[sid]},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )

    plan = {"tier": tier, "variants": variants, "shards": shards}
    with open(SHARDS_JSON, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=2)

    return plan


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m finetune.shard",
        description="Write label-hidden, domain-diverse prompt shards for the GENUINE-LOOP generator.",
    )
    p.add_argument("--tier", choices=("marika", "radagon"), default="radagon")
    p.add_argument("--shard-size", type=int, default=30, help="Approx ids per shard (default 30).")
    p.add_argument("--variants", type=int, default=1)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    plan = build(args.tier, args.shard_size, args.variants)
    n_shards = len(plan["shards"])
    total = sum(len(s) for s in plan["shards"])
    print(
        f"OK wrote {SHARDS_JSON} + {n_shards} prompt shard(s) "
        f"({total} scenarios, tier={args.tier}, ~{args.shard_size}/shard)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
