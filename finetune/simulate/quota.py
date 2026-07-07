"""finetune/simulate/quota.py — Rocky Linux 9 output simulator for the 'quota' tool.

Public API
----------
simulate_quota(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/quota.py
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system-context str from make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Realistic Rocky-9 quota output formats (repquota block device table, quota
  per-user report, quotaon/off confirmation lines, quotacheck scan output).
* Exit codes follow real binary conventions:
    0  — success
    1  — general failure (quota not enabled, user not found, binary error)
  127  — binary not found (quota-utils package not installed)
* Failure triggers are deterministic: filesystems containing "notfound",
  "nodev", "noexist" or users containing "nouser", "invalid" hit error paths.
  A hash-based ~15% scatter adds variety.

I2 compliance
-------------
All `summary` strings are I2-clean.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports (avoids circular deps).
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
    """Extract hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _fs_not_found(filesystem: str) -> bool:
    """Deterministically decide if a filesystem should trigger a not-found error."""
    lower = filesystem.lower()
    for tok in ("notfound", "nodev", "noexist", "missing", "bogus", "fake"):
        if tok in lower:
            return True
    # Hash-based scatter (~15%)
    h = int(hashlib.md5(filesystem.encode()).hexdigest(), 16)
    return h % 20 == 0


def _user_not_found(username: str) -> bool:
    """Deterministically decide if a username should trigger a not-found error."""
    lower = username.lower()
    for tok in ("nouser", "invalid", "notfound", "bogus", "ghost"):
        if tok in lower:
            return True
    h = int(hashlib.md5(username.encode()).hexdigest(), 16)
    return h % 20 == 0


def _quota_not_enabled(filesystem: str) -> bool:
    """Deterministically decide if quotas appear disabled on a filesystem."""
    h = int(hashlib.md5((filesystem + "quota").encode()).hexdigest(), 16)
    return h % 15 == 0


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_repquota(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    filesystem = args.get("filesystem", "-a")
    host = _hostname(ctx)

    if filesystem != "-a" and _fs_not_found(filesystem):
        stderr = f"quotactl() system call failed while getting info on {filesystem}: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to retrieve quota report for '{filesystem}': filesystem not found or quotas not configured.",
        )

    if filesystem == "-a":
        fs_header = "/home"
        fs_desc = "all quota-enabled filesystems"
    else:
        fs_header = filesystem
        fs_desc = f"'{filesystem}'"

    stdout = (
        f"*** Report for user quotas on device {fs_header}\n"
        f"Block grace time: 7days; Inode grace time: 7days\n"
        f"                        Block limits                File limits\n"
        f"User            used    soft    hard  grace    used  soft  hard  grace\n"
        f"----------------------------------------------------------------------\n"
        f"root      --      36       0       0              3     0     0\n"
        f"alice     --  102400  512000  614400           1024  5000  6000\n"
        f"bob       --  307200  512000  614400           2048  5000  6000\n"
        f"charlie   +-  512100  512000  614400  6days    5001  5000  6000  6days\n"
        f"dave      --   81920  512000  614400            820  5000  6000\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Quota report for {fs_desc} retrieved.",
    )


def _sim_quota_user(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    username = args.get("username", "unknown")

    if _user_not_found(username):
        stderr = f"quota: No filesystem specified.\nquota: {username}: user does not exist.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to retrieve quota for user '{username}': user does not exist.",
        )

    # Check if over quota (hash scatter)
    h = int(hashlib.md5((username + "over").encode()).hexdigest(), 16)
    over = h % 10 == 0

    used_blocks = 102400 + (sum(ord(c) for c in username) % 409600)
    soft_blocks = 512000
    hard_blocks = 614400

    if over:
        grace = "6days"
        block_flag = "+"
    else:
        grace = ""
        block_flag = "-"

    stdout = (
        f"Disk quotas for user {username} (uid {1000 + (sum(ord(c) for c in username) % 1000)}):\n"
        f"     Filesystem  blocks   quota   limit   grace   files   quota   limit   grace\n"
        f"          /home  {used_blocks:>6}  {soft_blocks}  {hard_blocks}  {grace:>6}    1024    5000    6000\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Quota information for user '{username}' retrieved.",
    )


def _sim_quotaon(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    filesystem = args.get("filesystem", "/home")

    if _fs_not_found(filesystem):
        stderr = f"quotaon: using {filesystem} as nfs mount: No such file or directory\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to enable quotas on '{filesystem}': filesystem not found.",
        )

    # Check if quota files exist (scatter)
    h = int(hashlib.md5((filesystem + "files").encode()).hexdigest(), 16)
    no_files = h % 12 == 0

    if no_files:
        stderr = (
            f"quotaon: {filesystem}: No quota files found. "
            f"Use quotacheck to create them.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to enable quotas on '{filesystem}': quota files not found. "
                "Run quotacheck first to create accounting files."
            ),
        )

    stdout = (
        f"/dev/sda3 [{filesystem}]: user quotas turned on\n"
        f"/dev/sda3 [{filesystem}]: group quotas turned on\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Quota enforcement enabled on '{filesystem}'.",
    )


def _sim_quotaoff(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    filesystem = args.get("filesystem", "/home")

    if _fs_not_found(filesystem):
        stderr = f"quotaoff: cannot find filesystem {filesystem}\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to disable quotas on '{filesystem}': filesystem not found.",
        )

    # Check if quotas were already off (scatter)
    h = int(hashlib.md5((filesystem + "off").encode()).hexdigest(), 16)
    already_off = h % 15 == 0

    if already_off:
        stderr = f"quotaoff: {filesystem}: quotas are not currently enabled\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to disable quotas on '{filesystem}': quotas are not currently enabled.",
        )

    stdout = (
        f"/dev/sda3 [{filesystem}]: user quotas turned off\n"
        f"/dev/sda3 [{filesystem}]: group quotas turned off\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Quota enforcement disabled on '{filesystem}'.",
    )


def _sim_quotacheck(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    filesystem = args.get("filesystem", "/home")

    if _fs_not_found(filesystem):
        stderr = f"quotacheck: Cannot find filesystem for path {filesystem}\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Quota check failed for '{filesystem}': filesystem not found.",
        )

    # Simulate busy filesystem (scatter)
    h = int(hashlib.md5((filesystem + "busy").encode()).hexdigest(), 16)
    busy = h % 18 == 0

    if busy:
        stderr = (
            f"quotacheck: WARNING - Quotafile {filesystem}/aquota.user was probably truncated. "
            f"Can not save quota settings!\n"
            f"quotacheck: Cannot remount filesystem mounted on {filesystem} read-only so counted values may not be right.\n"
        )
        stdout = (
            f"quotacheck: Scanning {filesystem} [/dev/sda3] done\n"
            f"quotacheck: Old file not found.\n"
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr=stderr,
            summary=f"Quota check for '{filesystem}' completed with warnings; filesystem was busy and counts may be inaccurate.",
        )

    stdout = (
        f"quotacheck: Scanning {filesystem} [/dev/sda3] done\n"
        f"quotacheck: Checked 2847 directories and 31204 files\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Quota check completed for '{filesystem}'; accounting files updated.",
    )


def _sim_edquota(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    username = args.get("username", "unknown")
    filesystem = args.get("filesystem", "/home")
    soft_blocks = args.get("soft_blocks", 0)
    hard_blocks = args.get("hard_blocks", 0)
    soft_inodes = args.get("soft_inodes", 0)
    hard_inodes = args.get("hard_inodes", 0)

    if _user_not_found(username):
        stderr = f"setquota: user {username} does not exist.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to set quota limits for user '{username}': user does not exist.",
        )

    if _fs_not_found(filesystem):
        stderr = f"setquota: {filesystem}: No such file or directory.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to set quota limits for user '{username}' on '{filesystem}': filesystem not found.",
        )

    # Check if quotas are enabled on that filesystem
    if _quota_not_enabled(filesystem):
        stderr = f"setquota: {filesystem}: Quota not enabled.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to set quota limits on '{filesystem}': quotas are not enabled on that filesystem. "
                "Run quotaon first."
            ),
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=(
            f"Quota limits set for user '{username}' on '{filesystem}': "
            f"blocks soft={soft_blocks} hard={hard_blocks}, "
            f"inodes soft={soft_inodes} hard={hard_inodes}."
        ),
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "repquota":   _sim_repquota,
    "quota_user": _sim_quota_user,
    "quotaon":    _sim_quotaon,
    "quotaoff":   _sim_quotaoff,
    "quotacheck": _sim_quotacheck,
    "edquota":    _sim_edquota,
}


def simulate_quota(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'quota' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in the
           quota ToolSpec (repquota, quota_user, quotaon, quotaoff,
           quotacheck, edquota).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either a snapshot_text str from make_context(),
           or a profile dict with a 'hostname' key.

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
            f"simulate_quota: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
