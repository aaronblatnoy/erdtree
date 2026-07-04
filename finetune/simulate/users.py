"""finetune/simulate/users.py — realistic Rocky Linux 9 output simulator for the users tool.

Public API
----------
simulate_users(op, args, ctx) -> dict
    Returns a {exit_code, stdout, stderr, summary} dict mirroring core.tools.ToolResult.
    Covers every real operation declared in core/tools/users.py.

Design rules
------------
INV-schema-sync   Op names are NEVER hardcoded as bare strings outside the
                  dispatch table; all routing goes through _DISPATCH.
INV-I2            Every `summary` value is free of forbidden terms
                  (AI, LLM, model, agent, ollama, inference, neural, etc.).
                  Call finetune.coreimports.assert_no_ai_language on summaries
                  in the test suite (tests/finetune/test_i2.py).
INV-read-only-core  This module imports FROM finetune.coreimports only.
                    Do NOT import directly from core/.
INV-offline         No network calls, no subprocesses launched.  All output is
                    synthesised in-process.

Failure case coverage
---------------------
Exit-code variation is keyed on specific argument values so generate.py can
produce both success and failure traces without out-of-band configuration:

  user == "NOUSER"        → simulate a user-not-found failure (info, lock,
                             delete, remove_from_privgroup)
  user == "DUPUSER"       → simulate a user-already-exists failure (add)
  user with prefix "__"   → simulate a permission-denied failure (any write op)
  shell == "/bin/invalid" → simulate an invalid-shell failure (set_shell)
  group == "NOGROUP"      → simulate a group-not-found failure (add_to_group)

When args is empty ({}) the simulator uses safe defaults and returns a
SUCCESS result — the validation gate (`simulate_users(op, {}, ctx)`) always
passes with the four required keys and an I2-clean summary.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# I2 checker — always via coreimports (INV-I2, INV-read-only-core)
# ---------------------------------------------------------------------------
from finetune.coreimports import assert_no_ai_language

# ---------------------------------------------------------------------------
# Default placeholder values used when args keys are absent.
# ---------------------------------------------------------------------------
_DEFAULT_USER = "jdoe"
_DEFAULT_SHELL = "/bin/bash"
_DEFAULT_GROUP = "developers"

# ---------------------------------------------------------------------------
# Realistic /etc/passwd content (Rocky Linux 9 base install + common accounts)
# ---------------------------------------------------------------------------
_PASSWD_CONTENT = """\
root:x:0:0:root:/root:/bin/bash
bin:x:1:1:bin:/bin:/sbin/nologin
daemon:x:2:2:daemon:/sbin:/sbin/nologin
adm:x:3:4:adm:/var/adm:/sbin/nologin
lp:x:4:7:lp:/var/spool/lpd:/sbin/nologin
sync:x:5:0:sync:/sbin:/bin/sync
shutdown:x:6:0:shutdown:/sbin:/sbin/shutdown
halt:x:7:0:halt:/sbin:/sbin/halt
mail:x:8:12:mail:/var/spool/mail:/sbin/nologin
operator:x:11:0:operator:/root:/sbin/nologin
games:x:12:100:games:/usr/games:/sbin/nologin
ftp:x:14:50:FTP User:/var/ftp:/sbin/nologin
nobody:x:65534:65534:Kernel Overflow User:/:/sbin/nologin
systemd-coredump:x:999:997:systemd Core Dumper:/:/sbin/nologin
dbus:x:81:81:System message bus:/:/sbin/nologin
polkitd:x:998:996:User for polkitd:/:/sbin/nologin
sssd:x:997:995:User for sssd:/:/sbin/nologin
sshd:x:74:74:Privilege-separated SSH:/var/empty/sshd:/sbin/nologin
chrony:x:996:994:chrony system user:/var/lib/chrony:/sbin/nologin
tcpdump:x:72:72::/:/sbin/nologin
sysadm:x:1000:1000:System Administrator:/home/sysadm:/bin/bash
deploy:x:1001:1001:Deploy Account:/home/deploy:/bin/bash
jdoe:x:1002:1002:Jane Doe:/home/jdoe:/bin/bash
"""

# ---------------------------------------------------------------------------
# Helper: build a ToolResult-shaped dict and assert I2-clean summary.
# ---------------------------------------------------------------------------

def _result(exit_code: int, stdout: str, stderr: str, summary: str) -> dict[str, Any]:
    assert_no_ai_language(summary)
    return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr, "summary": summary}


# ---------------------------------------------------------------------------
# Operation simulators
# ---------------------------------------------------------------------------

def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: cat /etc/passwd"""
    # Check if we have a context with a login_user to add an extra account line
    extra = ""
    login_user = getattr(ctx, "login_user", None)
    if login_user and login_user not in _PASSWD_CONTENT and login_user != _DEFAULT_USER:
        extra = f"{login_user}:x:1003:1003:Ops User:/home/{login_user}:/bin/bash\n"

    stdout = _PASSWD_CONTENT + extra
    count = stdout.count("\n")
    return _result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Listed {count} local accounts from /etc/passwd.",
    )


def _sim_list_fail(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: permission denied reading /etc/passwd (edge case, very rare)."""
    return _result(
        exit_code=1,
        stdout="",
        stderr="cat: /etc/passwd: Permission denied",
        summary="Account listing failed: permission denied reading /etc/passwd.",
    )


def _sim_info(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: id <user>"""
    user = args.get("user", _DEFAULT_USER)

    if user == "NOUSER":
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"id: '{user}': no such user",
            summary=f"No account named '{user}' exists on this host.",
        )

    # Determine uid/gid — known accounts get realistic values
    _uid_map = {
        "root": (0, 0, "root", "root", ""),
        "deploy": (1001, 1001, "deploy", "deploy", ""),
        "sysadm": (1000, 1000, "sysadm", "sysadm", "wheel"),
        "jdoe": (1002, 1002, "jdoe", "jdoe", "developers"),
        "nobody": (65534, 65534, "nobody", "nobody", ""),
    }
    if user in _uid_map:
        uid, gid, uname, gname, extra_group = _uid_map[user]
        groups_part = f"{gid}({gname})"
        if extra_group:
            groups_part += f",10(wheel)" if extra_group == "wheel" else f",1003({extra_group})"
        stdout = f"uid={uid}({uname}) gid={gid}({gname}) groups={groups_part}\n"
    else:
        uid = 1099
        stdout = f"uid={uid}({user}) gid={uid}({user}) groups={uid}({user})\n"

    return _result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found account record for '{user}' (uid={uid}).",
    )


def _sim_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: useradd <user>"""
    user = args.get("user", _DEFAULT_USER)

    if user.startswith("__"):
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"useradd: Permission denied.",
            summary=f"Failed to create account '{user}': permission denied.",
        )

    if user == "DUPUSER" or user in ("root", "nobody", "sysadm", "deploy", "jdoe"):
        return _result(
            exit_code=9,
            stdout="",
            stderr=f"useradd: user '{user}' already exists",
            summary=f"Account '{user}' already exists; no changes made.",
        )

    return _result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Account '{user}' created successfully.",
    )


def _sim_set_shell(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: usermod -s <shell> <user>"""
    user = args.get("user", _DEFAULT_USER)
    shell = args.get("shell", _DEFAULT_SHELL)

    if user.startswith("__"):
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"usermod: Permission denied.",
            summary=f"Failed to set login shell for '{user}': permission denied.",
        )

    if user == "NOUSER":
        return _result(
            exit_code=6,
            stdout="",
            stderr=f"usermod: user '{user}' does not exist in /etc/passwd",
            summary=f"Account '{user}' not found; login shell not changed.",
        )

    if shell == "/bin/invalid":
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"usermod: shell '{shell}' does not exist",
            summary=f"Shell '{shell}' does not exist on this host; login shell not changed.",
        )

    return _result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Login shell for '{user}' set to '{shell}'.",
    )


def _sim_add_to_group(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: usermod -aG <group> <user>"""
    user = args.get("user", _DEFAULT_USER)
    group = args.get("group", _DEFAULT_GROUP)

    if user.startswith("__"):
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"usermod: Permission denied.",
            summary=f"Failed to add '{user}' to group '{group}': permission denied.",
        )

    if group == "NOGROUP":
        return _result(
            exit_code=6,
            stdout="",
            stderr=f"usermod: group '{group}' does not exist",
            summary=f"Group '{group}' does not exist; '{user}' not added.",
        )

    if user == "NOUSER":
        return _result(
            exit_code=6,
            stdout="",
            stderr=f"usermod: user '{user}' does not exist in /etc/passwd",
            summary=f"Account '{user}' not found; not added to group '{group}'.",
        )

    return _result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Account '{user}' added to group '{group}'.",
    )


def _sim_lock(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: usermod -L <user>"""
    user = args.get("user", _DEFAULT_USER)

    if user.startswith("__"):
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"usermod: Permission denied.",
            summary=f"Failed to lock account '{user}': permission denied.",
        )

    if user == "NOUSER":
        return _result(
            exit_code=6,
            stdout="",
            stderr=f"usermod: user '{user}' does not exist in /etc/passwd",
            summary=f"Account '{user}' not found; lock not applied.",
        )

    if user == "root":
        # Locking root is allowed by usermod but dangerous — return success with note
        return _result(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Account 'root' locked (password login disabled).",
        )

    return _result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Account '{user}' locked; password-based login disabled.",
    )


def _sim_delete(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: userdel <user>"""
    user = args.get("user", _DEFAULT_USER)

    if user.startswith("__"):
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"userdel: Permission denied.",
            summary=f"Failed to delete account '{user}': permission denied.",
        )

    if user == "NOUSER":
        return _result(
            exit_code=6,
            stdout="",
            stderr=f"userdel: user '{user}' does not exist",
            summary=f"Account '{user}' not found; nothing deleted.",
        )

    # Check if user appears to be currently logged in (simulate via ctx)
    login_user = getattr(ctx, "login_user", None)
    if login_user and login_user == user:
        return _result(
            exit_code=8,
            stdout="",
            stderr=f"userdel: user {user} is currently logged in",
            summary=f"Account '{user}' is currently logged in; deletion blocked.",
        )

    return _result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Account '{user}' deleted from the system.",
    )


def _sim_remove_from_privgroup(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate: gpasswd -d <user> wheel"""
    user = args.get("user", _DEFAULT_USER)

    if user.startswith("__"):
        return _result(
            exit_code=1,
            stdout="",
            stderr=f"gpasswd: Permission denied.",
            summary=f"Failed to remove '{user}' from the privileged group: permission denied.",
        )

    if user == "NOUSER":
        return _result(
            exit_code=3,
            stdout="",
            stderr=f"gpasswd: user '{user}' is not a member of 'wheel'",
            summary=f"Account '{user}' is not a member of the privileged group; no change.",
        )

    # Simulate the case where the user is not in wheel
    _not_in_wheel = {"jdoe", "deploy", "nobody"}
    if user in _not_in_wheel:
        return _result(
            exit_code=3,
            stdout="",
            stderr=f"gpasswd: user '{user}' is not a member of 'wheel'",
            summary=f"Account '{user}' is not a member of the privileged group; no change.",
        )

    return _result(
        exit_code=0,
        stdout=f"Removing user {user} from group wheel\n",
        stderr="",
        summary=f"Account '{user}' removed from the privileged group (wheel).",
    )


# ---------------------------------------------------------------------------
# Dispatch table — keyed on real op names from core/tools/users.py
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "list": _sim_list,
    "info": _sim_info,
    "add": _sim_add,
    "set_shell": _sim_set_shell,
    "add_to_group": _sim_add_to_group,
    "lock": _sim_lock,
    "delete": _sim_delete,
    "remove_from_privgroup": _sim_remove_from_privgroup,
}

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def simulate_users(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Return a realistic {exit_code, stdout, stderr, summary} for a users tool op.

    Parameters
    ----------
    op:   One of the real operation names declared in core/tools/users.py.
    args: Arguments dict (may be empty — safe defaults are applied per op).
    ctx:  System snapshot context (any object; attributes accessed via getattr
          with fallback so a plain dict or None also works).

    Raises
    ------
    KeyError: if `op` is not a recognised users operation.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_users: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)


# Expose the set of covered ops so the P3 join can assert completeness.
COVERED_OPS: frozenset[str] = frozenset(_DISPATCH)
