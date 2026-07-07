"""finetune/simulate/nginx.py — Rocky Linux 9 output simulator for the 'nginx' tool.

Public API
----------
simulate_nginx(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/nginx.py
           (configtest, status, start, stop, restart, reload)
    args : dict of op arguments (may be {} for ops with no required args)
    ctx  : system context string produced by make_context(),
           OR a profile dict (same shape as finetune.context._PROFILES entries).
           Checked via isinstance; both forms are supported.

Realism model
-------------
* Exit codes mirror real nginx / systemctl behaviour:
    0  — success
    1  — operation failed (config syntax error, dependency error, etc.)
    3  — unit is loaded but inactive/failed  (systemctl status)
    5  — unit not found for control ops
* stdout/stderr reflect the actual Rocky 9 nginx and systemctl output formats.
* Failure triggers are deterministic: a hash-based ~15% scatter adds variety.
* ctx is used to decide whether nginx is currently active.

I2 compliance
-------------
All `summary` strings are I2-clean. No forbidden terms appear in any summary.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (to avoid circular deps).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nginx_is_active(ctx: Any) -> bool:
    """Return True if nginx appears to be running in the given context."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return any("nginx" in s for s in active)
    if isinstance(ctx, str):
        return "nginx" in ctx.lower()
    return False


def _nginx_has_failed(ctx: Any) -> bool:
    """Return True if nginx appears in the failed-services list."""
    if isinstance(ctx, dict):
        failed: list[str] = ctx.get("failed_services", [])
        return any("nginx" in s for s in failed)
    return False


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for use in realistic log lines."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _config_has_error(config: str) -> bool:
    """Deterministically decide if a config path should trigger a syntax error.

    Triggers: the token 'broken', 'bad', 'invalid', 'error', 'fail' appears
    in the lowercase path; OR a hash-based 15% scatter adds variety.
    """
    lower = config.lower()
    for tok in ("broken", "bad", "invalid", "error", "fail", "corrupt"):
        if tok in lower:
            return True
    h = int(hashlib.md5(config.encode()).hexdigest(), 16)
    return h % 20 == 0


def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_configtest(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    config: str = args.get("config", "")
    config_label = config if config else "default configuration"

    if config and _config_has_error(config):
        stderr = (
            f"nginx: [emerg] unexpected \";\" in {config}:42\n"
            f"nginx: configuration file {config} test failed\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"nginx configuration test failed for {config_label}: syntax error at line 42.",
        )

    # Success path — nginx -t writes to stderr on success (by design)
    cfg_path = config if config else "/etc/nginx/nginx.conf"
    stderr = (
        f"nginx: the configuration file {cfg_path} syntax is ok\n"
        f"nginx: configuration file {cfg_path} test is successful\n"
    )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr=stderr,
        summary=f"nginx configuration test passed for {config_label}.",
    )


def _sim_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)

    if _nginx_has_failed(ctx):
        stdout = (
            "● nginx.service - The nginx HTTP and reverse proxy server\n"
            "     Loaded: loaded (/usr/lib/systemd/system/nginx.service; enabled; preset: disabled)\n"
            "     Active: failed (Result: exit-code) since Fri 2026-07-03 04:12:33 UTC; 6h ago\n"
            "    Process: 14201 ExecStartPre=/usr/sbin/nginx -t (code=exited, status=1/FAILURE)\n"
            "   Main PID: 14201 (code=exited, status=1/FAILURE)\n"
            "\n"
            f"Jul 03 04:12:33 {host} systemd[1]: nginx.service: Control process exited with error code.\n"
            f"Jul 03 04:12:33 {host} nginx[14201]: nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)\n"
            f"Jul 03 04:12:33 {host} systemd[1]: Failed to start The nginx HTTP and reverse proxy server.\n"
        )
        return _make_result(
            exit_code=3,
            stdout=stdout,
            stderr="",
            summary="nginx.service is loaded but in a failed state.",
        )

    if _nginx_is_active(ctx):
        stdout = (
            "● nginx.service - The nginx HTTP and reverse proxy server\n"
            "     Loaded: loaded (/usr/lib/systemd/system/nginx.service; enabled; preset: disabled)\n"
            "     Active: active (running) since Fri 2026-07-03 00:01:04 UTC; 10h ago\n"
            "   Main PID: 2341 (nginx)\n"
            "     Status: \"Server is online\"\n"
            "      Tasks: 3 (limit: 23168)\n"
            "     Memory: 6.8M\n"
            "        CPU: 422ms\n"
            "     CGroup: /system.slice/nginx.service\n"
            "             ├─2341 \"nginx: master process /usr/sbin/nginx\"\n"
            "             └─2342 \"nginx: worker process\"\n"
            "\n"
            f"Jul 03 00:01:04 {host} systemd[1]: Started The nginx HTTP and reverse proxy server.\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="nginx.service is active and running.",
        )

    # Inactive / not started
    stdout = (
        "○ nginx.service - The nginx HTTP and reverse proxy server\n"
        "     Loaded: loaded (/usr/lib/systemd/system/nginx.service; disabled; preset: disabled)\n"
        "     Active: inactive (dead)\n"
    )
    return _make_result(
        exit_code=3,
        stdout=stdout,
        stderr="",
        summary="nginx.service is loaded but currently inactive.",
    )


def _sim_start(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    if _nginx_is_active(ctx):
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="nginx.service was already running; start command completed without error.",
        )

    # Hash-based failure scatter (~10%)
    h = int(hashlib.md5(b"nginx-start-scatter").hexdigest(), 16)
    if h % 10 == 0:
        host = _hostname(ctx)
        stderr = (
            "Job for nginx.service failed because the control process exited with error code.\n"
            "See 'systemctl status nginx.service' and 'journalctl -xeu nginx.service' for details.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to start nginx.service; the control process exited with an error.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="nginx.service started.",
    )


def _sim_stop(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    if not _nginx_is_active(ctx):
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="nginx.service was already inactive; stop command completed without error.",
        )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="nginx.service stopped.",
    )


def _sim_restart(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    # Hash-based failure scatter (~8%)
    h = int(hashlib.md5(b"nginx-restart-scatter").hexdigest(), 16)
    if h % 12 == 0:
        stderr = (
            "Job for nginx.service failed because the control process exited with error code.\n"
            "See 'systemctl status nginx.service' and 'journalctl -xeu nginx.service' for details.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to restart nginx.service; check the configuration for errors.",
        )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="nginx.service restarted.",
    )


def _sim_reload(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    if not _nginx_is_active(ctx):
        stderr = (
            "Failed to reload nginx.service: Unit nginx.service is not active.\n"
        )
        return _make_result(
            exit_code=5,
            stdout="",
            stderr=stderr,
            summary="Failed to reload nginx.service because the service is not running.",
        )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="nginx.service configuration reloaded without dropping connections.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "configtest": _sim_configtest,
    "status":     _sim_status,
    "start":      _sim_start,
    "stop":       _sim_stop,
    "restart":    _sim_restart,
    "reload":     _sim_reload,
}


def simulate_nginx(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'nginx' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in the
           nginx ToolSpec (configtest, status, start, stop, restart, reload).
    args : argument dict (may be sparse; defaults applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'active_services'/'failed_services' lists.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_nginx: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
