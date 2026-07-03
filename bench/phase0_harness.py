"""
bench/phase0_harness.py — Phase-0 measurement harness (run on mossad only).

PURPOSE
-------
Measures three things required by the Phase-0 GO/NO-GO gate:

  1. Single-shot p50/p95 wall-clock of ONE tool-call turn per tier model.
  2. Whether Ollama on 2x3060 Ti decodes slot-workers CONCURRENTLY or serializes
     them.  Varies OLLAMA_NUM_PARALLEL in {1, 2, 4}; times K=3 and K=5 narrow
     calls issued in parallel threads vs serial.
  3. Whether the OpenAI-compat endpoint exposes usable logprobs.

USAGE (on mossad)
-----------------
  # Step 1: single-shot latency for each tier model
  python bench/phase0_harness.py --mode latency --model qwen2.5:3b-instruct-q4_K_M --n 20
  python bench/phase0_harness.py --mode latency --model qwen2.5:14b-instruct-q4_K_M --n 20

  # Step 2: slot-worker concurrency probe (repeat for each NUM_PARALLEL)
  OLLAMA_NUM_PARALLEL=1 python bench/phase0_harness.py --mode concurrency --model qwen2.5:3b-instruct-q4_K_M --k 3
  OLLAMA_NUM_PARALLEL=1 python bench/phase0_harness.py --mode concurrency --model qwen2.5:3b-instruct-q4_K_M --k 5
  OLLAMA_NUM_PARALLEL=2 python bench/phase0_harness.py --mode concurrency --model qwen2.5:3b-instruct-q4_K_M --k 3
  OLLAMA_NUM_PARALLEL=2 python bench/phase0_harness.py --mode concurrency --model qwen2.5:3b-instruct-q4_K_M --k 5
  OLLAMA_NUM_PARALLEL=4 python bench/phase0_harness.py --mode concurrency --model qwen2.5:3b-instruct-q4_K_M --k 3
  OLLAMA_NUM_PARALLEL=4 python bench/phase0_harness.py --mode concurrency --model qwen2.5:3b-instruct-q4_K_M --k 5

  # Step 3: logprob probe
  python bench/phase0_harness.py --mode logprobs --model qwen2.5:3b-instruct-q4_K_M

  # Or run all three modes at once:
  python bench/phase0_harness.py --mode all --model qwen2.5:3b-instruct-q4_K_M --n 20 --k 3 5

INVARIANTS
----------
  I1  No egress: only talks to localhost:11434 (OllamaClient asserts this).
  I6  No tier/product names: caller passes model tag; this module is agnostic.

OUTPUT
------
  JSON lines to stdout (one record per measurement event).  Paste into the
  measurements note.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Optional

# Ensure repo root is on path when run from bench/ or repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.model.ollama import OllamaClient, TierConfig  # noqa: E402

BASE_URL = "http://localhost:11434"

# ---------------------------------------------------------------------------
# Fixed narrow-question prompt used for all measurements.
# It is intentionally simple (one tool, one required slot) so latency is
# dominated by model decode, not schema complexity.
# ---------------------------------------------------------------------------

_SYSTEM_SNAPSHOT = (
    "Services: nginx (active), postgresql (inactive). "
    "Packages: nginx-1.24.0, postgresql-14.9. "
    "Kernel: 5.15.0. Arch: x86_64."
)

_USER_INPUT = "show me the status of nginx"

# Minimal tool schema (mirrors the frozen 0002 wire shape for services.status).
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "services",
            "description": "Manage system services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["status", "start", "stop", "restart", "enable", "disable"],
                    },
                    "unit": {"type": "string"},
                },
                "required": ["operation", "unit"],
            },
        },
    }
]

_MESSAGES = [
    {
        "role": "system",
        "content": (
            "You control a Linux system. Issue a tool call when the user asks for "
            "a system operation.  System state:\n" + _SYSTEM_SNAPSHOT
        ),
    },
    {"role": "user", "content": _USER_INPUT},
]

# A narrow slot-extraction question (one slot, no tool schema needed).
_SLOT_MESSAGES = [
    {
        "role": "system",
        "content": "You extract a single field from a user request. Reply with ONLY the value.",
    },
    {
        "role": "user",
        "content": 'User said: "show me the status of nginx". What is the service name? Reply with just the name.',
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_client(model: str) -> OllamaClient:
    config = TierConfig(BASE_URL, model)
    return OllamaClient(config)


def _single_turn(client: OllamaClient, *, use_tools: bool = True) -> tuple[float, str]:
    """Time one tool-call (or narrow text) turn.  Returns (elapsed_s, finish_reason)."""
    messages = _MESSAGES if use_tools else _SLOT_MESSAGES
    tools = _TOOLS if use_tools else None
    t0 = time.perf_counter()
    resp = client.chat(messages, tools=tools, tool_choice="auto")
    elapsed = time.perf_counter() - t0
    return elapsed, resp.finish_reason


# ---------------------------------------------------------------------------
# Mode 1: Single-shot latency
# ---------------------------------------------------------------------------

def measure_latency(model: str, n: int) -> dict:
    """Run N single-shot turns and record p50/p95."""
    client = _build_client(model)
    samples: list[float] = []
    for i in range(n):
        elapsed, reason = _single_turn(client)
        samples.append(elapsed)
        print(
            json.dumps({"event": "sample", "model": model, "i": i, "elapsed_s": round(elapsed, 3), "finish_reason": reason}),
            flush=True,
        )
    p50 = statistics.median(samples)
    p95 = statistics.quantiles(samples, n=20)[18] if len(samples) >= 20 else max(samples)
    result = {
        "event": "latency_summary",
        "model": model,
        "n": n,
        "p50_s": round(p50, 3),
        "p95_s": round(p95, 3),
        "mean_s": round(statistics.mean(samples), 3),
        "min_s": round(min(samples), 3),
        "max_s": round(max(samples), 3),
    }
    print(json.dumps(result), flush=True)
    return result


# ---------------------------------------------------------------------------
# Mode 2: Concurrency probe
# ---------------------------------------------------------------------------

def _time_serial(client: OllamaClient, k: int) -> float:
    """Run K narrow slot calls in serial; return total wall-clock."""
    t0 = time.perf_counter()
    for _ in range(k):
        _single_turn(client, use_tools=False)
    return time.perf_counter() - t0


def _time_parallel(client: OllamaClient, k: int) -> float:
    """Run K narrow slot calls in parallel threads; return total wall-clock."""
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=k) as pool:
        futs = [pool.submit(_single_turn, client, use_tools=False) for _ in range(k)]
        concurrent.futures.wait(futs)
    return time.perf_counter() - t0


def measure_concurrency(model: str, k_values: list[int], repeats: int = 3) -> list[dict]:
    """
    For each K in k_values, measure serial vs parallel K narrow calls.
    OLLAMA_NUM_PARALLEL is read from the environment (caller sets it).
    """
    num_parallel_env = os.environ.get("OLLAMA_NUM_PARALLEL", "?")
    client = _build_client(model)
    results = []
    for k in k_values:
        serial_times = []
        parallel_times = []
        for _ in range(repeats):
            serial_times.append(_time_serial(client, k))
            parallel_times.append(_time_parallel(client, k))
        s_med = statistics.median(serial_times)
        p_med = statistics.median(parallel_times)
        speedup = round(s_med / p_med, 3) if p_med > 0 else None
        rec = {
            "event": "concurrency",
            "model": model,
            "OLLAMA_NUM_PARALLEL": num_parallel_env,
            "k": k,
            "serial_median_s": round(s_med, 3),
            "parallel_median_s": round(p_med, 3),
            "speedup_ratio": speedup,
            "go_criterion_met": (speedup is not None and speedup > 1.3),
        }
        print(json.dumps(rec), flush=True)
        results.append(rec)
    return results


# ---------------------------------------------------------------------------
# Mode 3: Logprob probe
# ---------------------------------------------------------------------------

def probe_logprobs(model: str) -> dict:
    """
    Check whether /v1/chat/completions returns logprob data.
    Ollama >= 0.3.6 added partial logprob support; availability is model-dependent.

    We send a request with logprobs=true and top_logprobs=1, then inspect the
    raw response.  OllamaClient doesn't expose logprobs (it's not in 0002), so
    we use urllib directly here.
    """
    import json as _json
    import urllib.request

    body = {
        "model": model,
        "stream": False,
        "logprobs": True,
        "top_logprobs": 1,
        "messages": _MESSAGES[:1] + [{"role": "user", "content": "say hi"}],
    }
    data = _json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        raw = _json.loads(resp.read())
    except Exception as exc:
        result = {"event": "logprob_probe", "model": model, "error": str(exc), "logprobs_present": False}
        print(json.dumps(result), flush=True)
        return result

    choices = raw.get("choices") or []
    logprobs_field = None
    if choices:
        logprobs_field = choices[0].get("logprobs")

    result = {
        "event": "logprob_probe",
        "model": model,
        "logprobs_present": logprobs_field is not None,
        "logprobs_sample": logprobs_field if logprobs_field is not None else None,
        "raw_keys": list(raw.keys()),
    }
    print(json.dumps(result), flush=True)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="phase0_harness",
        description="Phase-0 latency + concurrency + logprob probe (mossad only).",
    )
    parser.add_argument("--mode", choices=["latency", "concurrency", "logprobs", "all"], default="all")
    parser.add_argument("--model", required=True, help="Pinned Ollama model tag (never :latest).")
    parser.add_argument("--n", type=int, default=20, help="Number of single-shot turns for latency mode.")
    parser.add_argument("--k", type=int, nargs="+", default=[3, 5], help="Slot-worker counts for concurrency mode.")
    parser.add_argument("--repeats", type=int, default=3, help="Repeats per (K, serial/parallel) cell.")
    args = parser.parse_args(argv)

    if args.mode in ("latency", "all"):
        measure_latency(args.model, args.n)

    if args.mode in ("concurrency", "all"):
        measure_concurrency(args.model, args.k, args.repeats)

    if args.mode in ("logprobs", "all"):
        probe_logprobs(args.model)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
