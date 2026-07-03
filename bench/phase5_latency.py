"""
bench/phase5_latency.py — Phase-5 CHECKPOINT B latency harness (mossad only).

Measures the two numbers the Phase-5 latency checkpoint requires
(runtime/audits/nl-pipeline/phase-5-latency.md):

  B1/B2  p50 of a COMMON op under `fast-then-decompose` vs `native` — these must
         be EQUAL, because decomposition never fires on the common (fast) path.
  B3     p50 of a HARD/compound op under decomposition — the escalation cost.

HOW IT MEASURES
---------------
It builds the REAL repl via ``core.agent.main.build_repl`` under the chosen
``ERDTREE_UNDERSTANDING`` mode and times ``run_turn(request)`` over N repeats,
reporting p50/p95/mean. The repl is built NON-INTERACTIVE, so any write/
destructive op the request maps to is REFUSED at the gate (no side effects on
the box) — but the understanding round-trip (the thing we are timing: the native
call, and on a miss the intent + slot calls) still happens in full. Reads run
normally (they are ALLOW). This isolates understanding latency without mutating
the host.

  I1  No egress beyond localhost Ollama (build_repl asserts loopback at the
      client). This harness opens no socket itself.
  I6  No tier/product names: the model tag comes from the environment
      (ERDTREE_MODEL / ERDTREE_TIER), read opaquely by main.AppConfig.

USAGE (on mossad, from the repo root)
-------------------------------------
  # B2 — native common-op p50
  ERDTREE_UNDERSTANDING=native \
    python bench/phase5_latency.py --request "restart nginx" --n 20

  # B1 — fast-then-decompose common-op p50 (must equal B2)
  ERDTREE_UNDERSTANDING=fast-then-decompose \
    python bench/phase5_latency.py --request "restart nginx" --n 20

  # B3 — hard-op escalation cost
  ERDTREE_UNDERSTANDING=fast-then-decompose \
    python bench/phase5_latency.py \
      --request "get the box's biggest cpu hog and calm it down a notch" --n 20

The ``--understanding`` flag, if given, overrides the env var for convenience.
Point ERDTREE_AUDIT_LOG at a temp path so the run is self-contained.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Optional

# Make ``core`` importable when run as ``python bench/phase5_latency.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile over a non-empty list (pct in [0, 100])."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[k]


def measure(request: str, n: int, understanding: Optional[str]) -> dict:
    """Time run_turn(request) over N repeats under the chosen understanding mode.

    Returns a summary dict with p50/p95/mean/min/max wall-clock seconds.
    """
    if understanding:
        os.environ["ERDTREE_UNDERSTANDING"] = understanding

    # Import AFTER the env is set so AppConfig.from_env picks up the mode.
    from core.agent.main import AppConfig, build_repl

    config = AppConfig.from_env(interactive=False)
    repl = build_repl(config)  # asserts localhost (I1)

    samples: list[float] = []
    for _ in range(max(1, n)):
        t0 = time.perf_counter()
        repl.run_turn(request)
        samples.append(time.perf_counter() - t0)

    return {
        "request": request,
        "understanding": os.environ.get("ERDTREE_UNDERSTANDING", "native"),
        "model": config.model,
        "n": len(samples),
        "p50_s": round(_percentile(samples, 50), 4),
        "p95_s": round(_percentile(samples, 95), 4),
        "mean_s": round(statistics.fmean(samples), 4),
        "min_s": round(min(samples), 4),
        "max_s": round(max(samples), 4),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="phase5_latency",
        description="Phase-5 CHECKPOINT B latency harness (mossad only).",
    )
    parser.add_argument("--request", required=True, help="The request to time.")
    parser.add_argument("--n", type=int, default=20, help="Repeats (default 20).")
    parser.add_argument(
        "--understanding",
        default=None,
        choices=["native", "decomposed", "fast-then-decompose"],
        help="Override ERDTREE_UNDERSTANDING for this run.",
    )
    parser.add_argument("--mode", default="turn", help="Reserved; only 'turn'.")
    args = parser.parse_args(argv)

    try:
        summary = measure(args.request, args.n, args.understanding)
    except ConnectionError:
        # No reachable local model — refuse to fabricate a number (bench honesty).
        print(
            "The local service is not reachable; no latency measured. "
            "Start it and re-run.",
            file=sys.stderr,
        )
        return 3

    print(json.dumps(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
