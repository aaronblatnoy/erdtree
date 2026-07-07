"""finetune/simulate/ssh_keys.py — Rocky Linux 9 output simulator for the 'ssh_keys' tool.

Public API
----------
simulate_ssh_keys(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 7 real operations declared in core/tools/ssh_keys.py
    args : dict of op arguments (may be {} for all-optional ops; defaults applied)
    ctx  : system context string from make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism
-------
* Exit codes match real OpenSSH / sed behaviour on Rocky Linux 9:
    0  — success
    1  — generic failure (file not found, permission denied, parse error)
   127 — binary not found (e.g. sshd not installed)
* stdout/stderr shapes match actual ssh-keygen, cat, sed, and sshd -T output.
* Failure branches are deterministic: absent file, missing binary, bad user
  triggers hash-based scatter for variety (same technique as services.py).

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent/neural language).

INV-read-only-core: imports NOTHING from core/ or finetune.coreimports.
The ToolResult shape is mirrored as a plain dict.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _hostname(ctx: Any) -> str:
    """Extract a short hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _ak_path(user: str) -> str:
    if user == "root":
        return "/root/.ssh/authorized_keys"
    return f"/home/{user}/.ssh/authorized_keys"


def _kh_path(user: str) -> str:
    if user == "root":
        return "/root/.ssh/known_hosts"
    return f"/home/{user}/.ssh/known_hosts"


def _file_missing(user: str, salt: str = "") -> bool:
    """Deterministically decide if the SSH file should be simulated as missing.

    Triggers: user contains 'noexist', 'missing', 'bogus', 'notfound', 'fail';
    or a hash-based ~15% scatter for realistic failure variety.
    """
    lower = user.lower() + salt.lower()
    for tok in ("noexist", "missing", "bogus", "notfound", "fail", "broken"):
        if tok in lower:
            return True
    h = int(hashlib.md5(lower.encode()).hexdigest(), 16)
    return h % 20 == 0


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_keygen(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    path = args.get("path", "/root/.ssh/id_ed25519")
    key_type = str(args.get("key_type") or "ed25519")
    bits_raw = args.get("bits")
    bits = int(bits_raw) if bits_raw is not None else 4096
    host = _hostname(ctx)

    # Simulate failure if path looks problematic
    if any(tok in path.lower() for tok in ("noexist", "missing", "fail", "/bad/")):
        stderr = (
            f"Saving key \"{path}\" failed: No such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to generate SSH key pair at '{path}'; directory does not exist.",
        )

    # Hash-based failure scatter (~10%)
    h = int(hashlib.md5(path.encode()).hexdigest(), 16)
    if h % 10 == 0:
        stderr = f"Saving key \"{path}\" failed: Permission denied\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to generate SSH key pair at '{path}' (exit 1).",
        )

    if key_type == "ed25519":
        key_block = "[ED25519 256]"
        fingerprint = f"SHA256:{hashlib.sha256(path.encode()).hexdigest()[:43]}"
    elif key_type == "ecdsa":
        key_block = f"[ECDSA {min(bits, 521)}]"
        fingerprint = f"SHA256:{hashlib.sha256(path.encode()).hexdigest()[:43]}"
    else:
        key_block = f"[RSA {bits}]"
        fingerprint = f"SHA256:{hashlib.sha256(path.encode()).hexdigest()[:43]}"

    stdout = (
        f"Generating public/private {key_type} key pair.\n"
        f"Your identification has been saved in {path}\n"
        f"Your public key has been saved in {path}.pub\n"
        f"The key fingerprint is:\n"
        f"{fingerprint} {host}\n"
        f"The key's randomart image is:\n"
        f"+--{key_block}--+\n"
        f"|       .o+E     |\n"
        f"|       .o .     |\n"
        f"|      . +.      |\n"
        f"|     . =.o      |\n"
        f"|    o.oSo .     |\n"
        f"|   o =+o.o      |\n"
        f"|  . =.=+o.      |\n"
        f"|   o.oo+ooo     |\n"
        f"|    .+.=*+.     |\n"
        f"+-----------------+\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"SSH key pair generated at '{path}' (type={key_type}, bits={bits}).",
    )


def _sim_authorized_keys_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    user = str(args.get("user") or "root")
    path = _ak_path(user)

    if _file_missing(user):
        stderr = f"cat: {path}: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Could not read authorized_keys for user '{user}' (exit 1).",
        )

    # Build realistic authorized_keys content
    uid = sum(ord(c) for c in user) % 4
    keys = [
        f"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI{hashlib.md5((user+'k1').encode()).hexdigest()[:32]} deploy@ci-server",
        f"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB{hashlib.md5((user+'k2').encode()).hexdigest()[:32]} admin@workstation.example.com",
    ]
    if uid > 1:
        keys.append(
            f"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI{hashlib.md5((user+'k3').encode()).hexdigest()[:32]} backup@backup-host"
        )
    stdout = "\n".join(keys) + "\n"
    line_count = len(keys)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Retrieved {line_count} authorized key entries for user '{user}'.",
    )


def _sim_authorized_keys_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    key = args.get("key", "ssh-ed25519 AAAA... user@host")
    user = str(args.get("user") or "root")
    path = _ak_path(user)

    if _file_missing(user, "add"):
        stderr = f"tee: {path}: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to add key to authorized_keys for user '{user}' (exit 1).",
        )

    key_line = key.strip() + "\n"
    return _make_result(
        exit_code=0,
        stdout=key_line,
        stderr="",
        summary=f"Public key appended to authorized_keys for user '{user}'.",
    )


def _sim_authorized_keys_remove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    key_comment = args.get("key_comment", "user@host")
    user = str(args.get("user") or "root")
    path = _ak_path(user)

    if _file_missing(user, "remove"):
        stderr = f"sed: {path}: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to remove key '{key_comment}' from authorized_keys "
                f"for user '{user}' (exit 1)."
            ),
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=(
            f"Entries matching '{key_comment}' removed from authorized_keys "
            f"for user '{user}'."
        ),
    )


def _sim_known_hosts_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    user = str(args.get("user") or "root")
    path = _kh_path(user)

    if _file_missing(user, "kh"):
        stderr = f"cat: {path}: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Could not read known_hosts for user '{user}' (exit 1).",
        )

    # Build realistic known_hosts content
    host = _hostname(ctx)
    uid_hash = hashlib.md5(user.encode()).hexdigest()
    stdout = (
        f"git.example.com,192.168.10.5 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5{uid_hash[:24]}\n"
        f"backup.example.com,10.0.0.20 ssh-rsa AAAAB3NzaC1yc2EAAAA{uid_hash[:28]}\n"
        f"{host}.local,127.0.0.1 ecdsa-sha2-nistp256 AAAAE2VjZHNh{uid_hash[:20]}\n"
    )
    line_count = stdout.count("\n")
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Retrieved {line_count} known_hosts entries for user '{user}'.",
    )


def _sim_known_hosts_remove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    hostname = args.get("hostname", "example.com")
    user = str(args.get("user") or "root")
    path = _kh_path(user)

    if _file_missing(user, hostname):
        stderr = f"ssh-keygen: {path}: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to remove '{hostname}' from known_hosts for user '{user}' "
                f"(exit 1)."
            ),
        )

    # Simulate host not found case (hash-based ~20%)
    h = int(hashlib.md5((hostname + user).encode()).hexdigest(), 16)
    if h % 5 == 0:
        stdout = f"# Host {hostname} not found in {path}\n"
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Host '{hostname}' was not present in known_hosts for user '{user}'.",
        )

    stdout = (
        f"# Host {hostname} found: line 2\n"
        f"# Host {hostname} found: line 3\n"
    )
    stderr = f"# Updated {path} old new\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr=stderr,
        summary=f"Host '{hostname}' removed from known_hosts for user '{user}'.",
    )


def _sim_sshd_config_audit(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = _hostname(ctx)

    # Simulate sshd not installed in some contexts
    if isinstance(ctx, dict) and ctx.get("sshd_missing"):
        stderr = "bash: sshd: command not found\n"
        return _make_result(
            exit_code=127,
            stdout="",
            stderr=stderr,
            summary="sshd configuration audit failed; sshd binary not found (exit 127).",
        )

    # Realistic sshd -T output (subset of effective settings)
    stdout = (
        f"port 22\n"
        f"addressfamily any\n"
        f"listenaddress 0.0.0.0\n"
        f"listenaddress ::\n"
        f"usepam yes\n"
        f"logingracetime 60\n"
        f"x11forwarding no\n"
        f"maxauthtries 6\n"
        f"pubkeyauthentication yes\n"
        f"authorizedkeysfile .ssh/authorized_keys\n"
        f"hostbasedauthentication no\n"
        f"ignoreuserknownhosts no\n"
        f"ignorerhosts yes\n"
        f"permitemptypasswords no\n"
        f"challengeresponseauthentication no\n"
        f"kerberosauthentication no\n"
        f"kerberosorlocalpasswd yes\n"
        f"gssapiauthentication yes\n"
        f"gssapicleanupcredentials no\n"
        f"usedns no\n"
        f"pidfile /var/run/sshd.pid\n"
        f"xauthlocation /usr/bin/xauth\n"
        f"subsystem sftp /usr/libexec/openssh/sftp-server\n"
        f"maxstartups 10:30:100\n"
        f"permittunnel no\n"
        f"ipqos lowdelay throughput\n"
        f"rekeylimit 0 0\n"
        f"permitopen any\n"
        f"authorizationkeyscommand none\n"
        f"banner none\n"
        f"acceptenv LANG LC_*\n"
        f"printlastlog yes\n"
        f"passwordauthentication yes\n"
    )
    line_count = stdout.count("\n")
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"sshd configuration audit completed; {line_count} settings reported.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "keygen":                  _sim_keygen,
    "authorized_keys_list":    _sim_authorized_keys_list,
    "authorized_keys_add":     _sim_authorized_keys_add,
    "authorized_keys_remove":  _sim_authorized_keys_remove,
    "known_hosts_list":        _sim_known_hosts_list,
    "known_hosts_remove":      _sim_known_hosts_remove,
    "sshd_config_audit":       _sim_sshd_config_audit,
}


def simulate_ssh_keys(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'ssh_keys' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 7 real ops declared in
           core/tools/ssh_keys.py.
    args : argument dict (may be sparse; per-op defaults are applied).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict.

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
            f"simulate_ssh_keys: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
