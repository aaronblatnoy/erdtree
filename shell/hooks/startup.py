"""
shell/hooks/startup.py — pre-shell health check (Ollama reachable?).

This runs BEFORE the first prompt. Its job is to establish that the local
inference service is up and the configured model is loaded. If ANYTHING goes
wrong — service down, model not loaded, timeout, any exception — it returns a
failure result rather than raising, so the dead-man path in shell.py can take
over cleanly.

Design:
  - HTTP probe against Ollama's /api/tags endpoint (lightweight, no token cost).
  - Hard timeout: if Ollama doesn't respond within STARTUP_TIMEOUT_S seconds we
    treat it as down. A boot-time Ollama that's still pulling a model will be
    up but may not have the model ready — we check for the model in the tag list.
  - Returns a HealthResult (ok=True/False, message). The message is always
    plain English with no AI/LLM/model/agent language (I2).

I1: the ONLY network touch here is localhost:11434 — the local service. No
    external connections, ever.
I2: user-facing strings in messages never say "AI", "LLM", "model", "agent".
"""

from __future__ import annotations

import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

STARTUP_TIMEOUT_S = 5  # seconds before we give up and fall back to bash

_DEFAULT_BASE_URL = "http://localhost:11434"


@dataclass(frozen=True)
class HealthResult:
    ok: bool
    message: str  # plain English, I2-clean


def check(base_url: str | None = None, model: str | None = None) -> HealthResult:
    """Probe the local inference service and optionally verify *model* is loaded.

    Returns HealthResult(ok=True, ...) only if the service is reachable AND
    (when *model* is given) the model appears in the tag list.

    Never raises — all exceptions are caught and mapped to ok=False.
    """
    url = (base_url or os.environ.get("ERDTREE_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
    model_name = model or os.environ.get("ERDTREE_MODEL", "")

    try:
        tags_url = f"{url}/api/tags"
        req = urllib.request.Request(tags_url)
        with urllib.request.urlopen(req, timeout=STARTUP_TIMEOUT_S) as resp:
            if resp.status != 200:
                return HealthResult(
                    ok=False,
                    message=(
                        f"The system service responded with status {resp.status}. "
                        "It may still be starting up."
                    ),
                )
            import json
            data = json.loads(resp.read())
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
        # Don't surface internal names — just say the service is unavailable.
        return HealthResult(
            ok=False,
            message=(
                "The system service is not available right now. "
                "It may still be starting up, or it may need to be restarted."
            ),
        )
    except TimeoutError:
        return HealthResult(
            ok=False,
            message=(
                "The system service did not respond in time. "
                "It may still be starting up."
            ),
        )
    except OSError as exc:
        return HealthResult(
            ok=False,
            message=(
                "Could not connect to the system service. "
                "Check that it is running."
            ),
        )
    except Exception:  # noqa: BLE001 — catch-all so dead-man always fires
        return HealthResult(
            ok=False,
            message="The system service could not be reached.",
        )

    # Service is up. Optionally verify the configured model is present.
    if model_name:
        loaded = _model_is_loaded(data, model_name)
        if not loaded:
            return HealthResult(
                ok=False,
                message=(
                    "The system service is running but the required configuration "
                    "is not yet ready. It may still be loading."
                ),
            )

    return HealthResult(ok=True, message="")


def _model_is_loaded(tags_data: dict, model_name: str) -> bool:
    """Return True if *model_name* appears in the Ollama /api/tags response."""
    models = tags_data.get("models", [])
    for entry in models:
        name = entry.get("name", "")
        # Ollama names are "family:tag"; we match the exact configured string
        # or just the family if no tag was specified.
        if name == model_name or name.startswith(model_name + ":"):
            return True
    return False
