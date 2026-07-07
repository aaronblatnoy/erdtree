"""finetune/simulate/httpd.py — Rocky Linux 9 output simulator for the 'httpd' tool.

Public API
----------
simulate_httpd(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 7 real operations declared in core/tools/httpd.py
    args : dict of op arguments (may be {} — all httpd ops have no required args)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Checked via isinstance; both forms are supported.

Realism model
-------------
* Exit codes mirror real apachectl / systemctl / curl behaviour on Rocky 9.
* stdout/stderr reflect actual Rocky 9 httpd output format.
* Failure triggers use a hash-based deterministic scatter for variety,
  plus explicit "failure" keyword detection.

I2 compliance
-------------
All `summary` strings are I2-clean. No AI/LLM/model/agent language.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports (to avoid circular deps when
__init__.py imports simulate modules before coreimports is fully settled).
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _httpd_is_running(ctx: Any) -> bool:
    """Return True if httpd appears to be running in the given context."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return any("httpd" in s or "apache" in s.lower() for s in active)
    if isinstance(ctx, str):
        return "httpd" in ctx or "apache2" in ctx
    return False


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-web.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-web"


def _httpd_should_fail(seed: str) -> bool:
    """Deterministic failure scatter (~12%)."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return h % 8 == 0


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

def _sim_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """apachectl status — display httpd server status."""
    host = _hostname(ctx)
    running = _httpd_is_running(ctx)

    if _httpd_should_fail("status-notrunning") and not running:
        stderr = (
            "AH00558: httpd: Could not reliably determine the server's fully "
            "qualified domain name, using 127.0.0.1. Set the 'ServerName' "
            "directive globally to suppress this message\n"
            "httpd (no pid file) not running\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Apache HTTP Server does not appear to be running.",
        )

    if running:
        stdout = (
            f"● httpd.service - The Apache HTTP Server\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/httpd.service; enabled; preset: disabled)\n"
            f"    Drop-In: /usr/lib/systemd/system/httpd.service.d\n"
            f"             └─php-fpm.conf\n"
            f"     Active: active (running) since Thu 2026-07-03 00:01:04 UTC; 8h 34min ago\n"
            f"       Docs: man:httpd.service(8)\n"
            f"   Main PID: 1234 (httpd)\n"
            f"     Status: \"Total requests: 14872; Idle/Busy workers 99/1;Requests/sec: 0.482; "
            f"Bytes served/sec: 14.1kB/sec\"\n"
            f"      Tasks: 278 (limit: 23168)\n"
            f"     Memory: 43.8M\n"
            f"        CPU: 1m 12.456s\n"
            f"     CGroup: /system.slice/httpd.service\n"
            f"             ├─1234 /usr/sbin/httpd -DFOREGROUND\n"
            f"             ├─1240 /usr/sbin/httpd -DFOREGROUND\n"
            f"             ├─1241 /usr/sbin/httpd -DFOREGROUND\n"
            f"             └─1242 /usr/sbin/httpd -DFOREGROUND\n"
            f"\n"
            f"Jul 03 00:01:04 {host} systemd[1]: Started The Apache HTTP Server.\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="Apache HTTP Server is active and running.",
        )
    else:
        stdout = (
            f"○ httpd.service - The Apache HTTP Server\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/httpd.service; disabled; preset: disabled)\n"
            f"     Active: inactive (dead)\n"
        )
        return _make_result(
            exit_code=3,
            stdout=stdout,
            stderr="",
            summary="Apache HTTP Server is loaded but currently inactive.",
        )


def _sim_configtest(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """apachectl configtest — validate Apache configuration syntax."""
    if _httpd_should_fail("configtest-syntax"):
        stderr = (
            "AH00558: httpd: Could not reliably determine the server's fully "
            "qualified domain name, using 127.0.0.1. Set the 'ServerName' "
            "directive globally to suppress this message\n"
            "AH00526: Syntax error on line 143 of /etc/httpd/conf.d/vhosts.conf:\n"
            "Invalid command 'SSLCertificateFilee', perhaps misspelled or defined by a module "
            "not included in the server configuration\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Apache configuration syntax check failed; a directive error was found in the configuration files.",
        )

    stderr = (
        "AH00558: httpd: Could not reliably determine the server's fully "
        "qualified domain name, using 127.0.0.1. Set the 'ServerName' "
        "directive globally to suppress this message\n"
        "Syntax OK\n"
    )
    return _make_result(
        exit_code=0,
        stdout="",
        stderr=stderr,
        summary="Apache configuration syntax is valid (Syntax OK).",
    )


def _sim_start(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """systemctl start httpd — start the Apache HTTP Server."""
    host = _hostname(ctx)
    running = _httpd_is_running(ctx)

    if running:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Apache HTTP Server was already running; start command completed without error.",
        )

    if _httpd_should_fail("start-fail"):
        stderr = (
            "Job for httpd.service failed because the control process exited with error code.\n"
            "See 'systemctl status httpd.service' and 'journalctl -xeu httpd.service' for details.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to start Apache HTTP Server; the control process exited with an error.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="Apache HTTP Server started.",
    )


def _sim_stop(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """systemctl stop httpd — stop the Apache HTTP Server."""
    running = _httpd_is_running(ctx)

    if not running:
        return _make_result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Apache HTTP Server was already inactive; stop command completed without error.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="Apache HTTP Server stopped.",
    )


def _sim_restart(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """systemctl restart httpd — restart the Apache HTTP Server."""
    if _httpd_should_fail("restart-fail"):
        stderr = (
            "Job for httpd.service failed because the control process exited with error code.\n"
            "See 'systemctl status httpd.service' and 'journalctl -xeu httpd.service' for details.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to restart Apache HTTP Server; check the configuration for errors.",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary="Apache HTTP Server restarted.",
    )


def _sim_vhost_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """apachectl -S — list configured virtual hosts."""
    host = _hostname(ctx)

    if _httpd_should_fail("vhost-fail"):
        stderr = (
            "AH00558: httpd: Could not reliably determine the server's fully "
            "qualified domain name, using 127.0.0.1.\n"
            "AH00526: Syntax error on line 12 of /etc/httpd/conf.d/ssl.conf:\n"
            "SSLCertificateFile: file '/etc/pki/tls/certs/localhost.crt' does not exist "
            "or is empty\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to retrieve virtual host list; Apache configuration has an error.",
        )

    stdout = (
        f"VirtualHost configuration:\n"
        f"*:80                   is a NameVirtualHost\n"
        f"         default server {host}.example.com (/etc/httpd/conf.d/welcome.conf:10)\n"
        f"         port 80 namevhost {host}.example.com (/etc/httpd/conf.d/vhosts.conf:5)\n"
        f"                 alias www.example.com\n"
        f"         port 80 namevhost api.example.com (/etc/httpd/conf.d/vhosts.conf:20)\n"
        f"*:443                  is a NameVirtualHost\n"
        f"         default server {host}.example.com (/etc/httpd/conf.d/ssl.conf:58)\n"
        f"         port 443 namevhost {host}.example.com (/etc/httpd/conf.d/ssl.conf:58)\n"
        f"ServerRoot: \"/etc/httpd\"\n"
        f"Main DocumentRoot: \"/var/www/html\"\n"
        f"Main ErrorLog: \"/etc/httpd/logs/error_log\"\n"
        f"Mutex default: dir=\"/run/httpd/\" mechanism=default\n"
        f"PidFile: \"/run/httpd/httpd.pid\"\n"
        f"Define: DUMP_VHOSTS\n"
        f"Define: DUMP_RUN_CFG\n"
        f"User: name=\"apache\" id=48\n"
        f"Group: name=\"apache\" id=48\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Virtual host listing retrieved; 2 port binding(s) found.",
    )


def _sim_mod_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """curl http://127.0.0.1/server-status?auto — fetch live mod_status metrics."""
    running = _httpd_is_running(ctx)

    if not running or _httpd_should_fail("modstatus-fail"):
        stderr = (
            "curl: (7) Failed to connect to 127.0.0.1 port 80 after 0 ms: "
            "Connection refused\n"
        )
        return _make_result(
            exit_code=7,
            stdout="",
            stderr=stderr,
            summary=(
                "Failed to retrieve mod_status metrics from 127.0.0.1; "
                "ensure mod_status is enabled and httpd is running."
            ),
        )

    stdout = (
        "localhost\n"
        "ServerVersion: Apache/2.4.57 (Rocky Linux)\n"
        "ServerMPM: prefork\n"
        "Server Built: Jul  3 2025 00:00:00\n"
        "CurrentTime: Thursday, 03-Jul-2026 10:30:00 UTC\n"
        "RestartTime: Thursday, 03-Jul-2026 00:01:04 UTC\n"
        "ParentServerConfigGeneration: 1\n"
        "ParentServerMPMGeneration: 0\n"
        "ServerUptimeSeconds: 37736\n"
        "ServerUptime: 10 hours 28 minutes 56 seconds\n"
        "Load1: 0.08\n"
        "Load5: 0.04\n"
        "Load15: 0.01\n"
        "Total Accesses: 14872\n"
        "Total kBytes: 58240\n"
        "Total Duration: 7441\n"
        "CPUUser: 2.3\n"
        "CPUSystem: 0.45\n"
        "CPUChildrenUser: 0\n"
        "CPUChildrenSystem: 0\n"
        "CPULoad: .007292\n"
        "Uptime: 37736\n"
        "ReqPerSec: .394\n"
        "BytesPerSec: 1580\n"
        "BytesPerReq: 4010\n"
        "DurationPerReq: .5\n"
        "BusyWorkers: 1\n"
        "IdleWorkers: 99\n"
        "Scoreboard: _________________________...________________________W\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="Apache mod_status metrics retrieved from the local server.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "status":     _sim_status,
    "configtest": _sim_configtest,
    "start":      _sim_start,
    "stop":       _sim_stop,
    "restart":    _sim_restart,
    "vhost_list": _sim_vhost_list,
    "mod_status": _sim_mod_status,
}


def simulate_httpd(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'httpd' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 7 real ops declared in the
           httpd ToolSpec (status, configtest, start, stop, restart,
           vhost_list, mod_status).
    args : argument dict (all httpd ops have no required args; pass {} freely).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'active_services' list and 'hostname'.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present. summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_httpd: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
