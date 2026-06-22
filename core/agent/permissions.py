"""Permission seam — the hard safety gate before any operation executes.

This module is pure logic: it takes a proposed operation (the literal command
line that would run, plus the surrounding execution context) and classifies it
into one of three risk classes, then derives the gate that MUST be satisfied
before the operation may run.

Design contract (load-bearing — see plan invariant I3):

  - READ        -> ALLOW           : runs immediately, no confirmation.
  - WRITE       -> CONFIRM         : a plain yes/no confirmation is required.
  - DESTRUCTIVE -> CONFIRM_TYPED   : the user must type a literal word IN FULL.
                                     Never auto-confirmed. Never run
                                     non-interactively.

Hard rules enforced here, by construction:

  * Default-deny on ambiguity. An operation whose shape we cannot positively
    recognize as a read is treated as at least a WRITE. An operation that looks
    even partly destructive is treated as DESTRUCTIVE. We never under-gate.
  * A destructive operation can NEVER be auto-confirmed and can NEVER run in a
    non-interactive context. If there is no human at a TTY who can type the
    literal word, the gate's outcome is REFUSE, not "assume yes".
  * The gate carries no AI/LLM/agent/model language in any human-facing string
    (invariant I2): reasons read as plain Linux safety messages.

Nothing in here talks to a model, a network, a tier, or the filesystem. It is
fully testable on any host.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class OpClass(str, Enum):
    """Risk classification of an operation."""

    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class Gate(str, Enum):
    """The gate that must be satisfied before the operation may execute."""

    ALLOW = "allow"  # run now, no confirmation
    CONFIRM = "confirm"  # plain yes/no confirmation
    CONFIRM_TYPED = "confirm_typed"  # type the literal word in full
    REFUSE = "refuse"  # cannot proceed in this context (e.g. non-interactive destructive)


# The exact word a human must type IN FULL to clear a destructive gate.
# Chosen to be unambiguous, unlikely to be typed by accident, and never a
# default-accepted value (an empty line / "y" / "yes" must NOT clear it).
DESTRUCTIVE_CONFIRM_WORD = "DESTROY"


@dataclass(frozen=True)
class ExecContext:
    """The environment the operation would execute in.

    interactive:  True iff a human is present at a TTY and can be prompted and
                  can type a literal word. When False, destructive operations
                  are REFUSED outright — there is no one to confirm.
    remote:       True iff the operation targets a remote/headless host where a
                  mistake cannot be physically recovered (raises the stakes on
                  reboot/power/network/lockout operations).
    """

    interactive: bool = True
    remote: bool = False


@dataclass(frozen=True)
class Decision:
    """The result of classifying an operation."""

    op_class: OpClass
    gate: Gate
    reason: str
    # True only when the operation may run with NO human interaction at all.
    # By construction this is True ONLY for ALLOW (read) decisions.
    auto_ok: bool = field(default=False)

    @property
    def requires_typed_word(self) -> bool:
        return self.gate is Gate.CONFIRM_TYPED

    @property
    def confirm_word(self) -> str | None:
        return DESTRUCTIVE_CONFIRM_WORD if self.gate is Gate.CONFIRM_TYPED else None


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------
#
# These patterns are matched against the full command string (and, where it
# matters, the tokenized argv). They are intentionally broad: a false positive
# (over-gating a safe op) is a minor annoyance; a false negative (under-gating a
# destructive op) is catastrophic on a live box. We err toward MORE gating.

# Commands whose ONLY documented effect is to read state. Matched on argv[0]
# (after resolving a leading path, e.g. /usr/bin/ls -> ls). If a "read" command
# is invoked with a writing flag, the write/destructive rules below still win,
# because we test destructive -> write -> read in that order.
_READ_COMMANDS = frozenset(
    {
        "ls", "cat", "less", "more", "head", "tail", "stat", "file", "find",
        "grep", "egrep", "fgrep", "rg", "awk", "sed", "cut", "sort", "uniq",
        "wc", "tr", "df", "du", "free", "uptime", "uname", "hostname", "whoami",
        "id", "groups", "date", "cal", "echo", "printf", "pwd", "which",
        "whereis", "type", "env", "printenv", "ps", "top", "htop", "pgrep",
        "lsof", "ss", "netstat", "ip", "ping", "dig", "host", "nslookup",
        "traceroute", "lsblk", "blkid", "lscpu", "lsmem", "lspci", "lsusb",
        "lsmod", "dmesg", "journalctl", "rpm", "dnf", "dpkg", "apt", "man",
        "info", "history", "alias", "git", "systemctl", "service", "mount",
        "readlink", "realpath", "dirname", "basename", "md5sum", "sha256sum",
        "cmp", "diff", "tree", "getfacl", "getcap", "sestatus", "getenforce",
        "firewall-cmd", "nmcli", "ethtool", "smartctl", "sensors", "vmstat",
        "iostat", "mpstat", "sar", "tcpdump", "watch", "tee", "xargs",
    }
)

# Sub-verbs that turn an otherwise-readable command into a write or worse.
# Maps argv[0] -> {verb -> OpClass}. Anything not listed for a known command
# falls through to the default-deny shaping below.
_SUBCOMMAND_CLASS = {
    "systemctl": {
        # read
        "status": OpClass.READ, "is-active": OpClass.READ,
        "is-enabled": OpClass.READ, "is-failed": OpClass.READ,
        "list-units": OpClass.READ, "list-unit-files": OpClass.READ,
        "show": OpClass.READ, "cat": OpClass.READ, "get-default": OpClass.READ,
        # write
        "start": OpClass.WRITE, "stop": OpClass.WRITE,
        "restart": OpClass.WRITE, "reload": OpClass.WRITE,
        "enable": OpClass.WRITE, "disable": OpClass.WRITE,
        "mask": OpClass.WRITE, "unmask": OpClass.WRITE,
        "set-property": OpClass.WRITE, "daemon-reload": OpClass.WRITE,
        # destructive: changing the boot target or power state of a box
        "isolate": OpClass.DESTRUCTIVE, "set-default": OpClass.DESTRUCTIVE,
        "poweroff": OpClass.DESTRUCTIVE, "reboot": OpClass.DESTRUCTIVE,
        "halt": OpClass.DESTRUCTIVE, "kexec": OpClass.DESTRUCTIVE,
        "emergency": OpClass.DESTRUCTIVE, "rescue": OpClass.DESTRUCTIVE,
    },
    "dnf": {
        "list": OpClass.READ, "info": OpClass.READ, "search": OpClass.READ,
        "repolist": OpClass.READ, "check-update": OpClass.READ,
        "provides": OpClass.READ, "history": OpClass.READ, "repoquery": OpClass.READ,
        "install": OpClass.WRITE, "reinstall": OpClass.WRITE,
        "downgrade": OpClass.WRITE, "update": OpClass.WRITE,
        "upgrade": OpClass.WRITE, "mark": OpClass.WRITE,
        # removals can cascade (kernel/ssh/sudo) -> destructive by default
        "remove": OpClass.DESTRUCTIVE, "erase": OpClass.DESTRUCTIVE,
        "autoremove": OpClass.DESTRUCTIVE, "distro-sync": OpClass.DESTRUCTIVE,
    },
    "firewall-cmd": {
        # read
        "--list-all": OpClass.READ, "--list-services": OpClass.READ,
        "--list-ports": OpClass.READ, "--get-zones": OpClass.READ,
        "--state": OpClass.READ, "--get-default-zone": OpClass.READ,
        "--query-service": OpClass.READ,
    },
    "git": {
        "status": OpClass.READ, "log": OpClass.READ, "diff": OpClass.READ,
        "show": OpClass.READ, "branch": OpClass.READ, "remote": OpClass.READ,
        "fetch": OpClass.READ, "blame": OpClass.READ, "config": OpClass.READ,
    },
    "mount": {},  # bare `mount` lists; `mount <dev> <pt>` handled as write below
    "ip": {
        "addr": OpClass.READ, "a": OpClass.READ, "link": OpClass.READ,
        "route": OpClass.READ, "r": OpClass.READ, "neigh": OpClass.READ,
    },
}

# ---------------------------------------------------------------------------
# Argv-aware destructive constants (the primary, tokenized taxonomy)
# ---------------------------------------------------------------------------
#
# The classifier below TOKENIZES each (sub-)command into argv and reasons over
# normalized flags and operand paths. These constants drive that argv-aware
# logic. The whole-string regex table that follows is a SECONDARY net (fork
# bombs, redirections, and anything the tokenizer cannot see); argv logic is
# authoritative and runs first.

# Critical files: clobbering/removing any of these can break boot, auth, or
# remote access. Matched against operand paths (exact, or trailing-slash dir).
_CRITICAL_FILES = frozenset(
    {
        "/etc/ssh/sshd_config",
        "/etc/fstab", "/etc/passwd", "/etc/shadow", "/etc/sudoers",
        "/etc/gshadow", "/etc/group", "/etc/hosts", "/etc/resolv.conf",
        "/etc/crypttab", "/etc/default/grub",
        "/boot/grub2/grub.cfg", "/boot/grub/grub.cfg",
    }
)
# Directory prefixes whose recursive deletion is catastrophic regardless of
# flags being forced.
_SYSTEM_PATH_PREFIXES = (
    "/", "/etc", "/boot", "/bin", "/sbin", "/lib", "/lib64", "/usr",
    "/var", "/home", "/root", "/opt", "/srv", "/dev", "/proc", "/sys",
    "/run", "~", "$HOME",
)
# Block-device path prefixes — writing to / truncating these destroys data.
_BLOCK_DEV_PREFIXES = ("/dev/sd", "/dev/nvme", "/dev/vd", "/dev/hd",
                       "/dev/mapper", "/dev/disk", "/dev/md", "/dev/dm-",
                       "/dev/loop")
# Commands that clobber (overwrite) their destination file. (cmd -> reason verb)
_CLOBBER_COMMANDS = frozenset({"tee", "cp", "mv", "dd", "install", "truncate", "ln"})
# Programs whose mere invocation is destructive (device/data/boot wipers).
_DESTRUCTIVE_PROGRAMS: dict[str, str] = {
    "mkfs": "creating a filesystem erases the target device",
    "mke2fs": "creating a filesystem erases the target device",
    "wipefs": "wiping filesystem signatures destroys the volume",
    "blkdiscard": "discarding all blocks erases the device",
    "shred": "shred irreversibly overwrites data",
    "fdisk": "partition operations can make a disk unbootable",
    "gdisk": "partition operations can make a disk unbootable",
    "sgdisk": "partition operations can make a disk unbootable",
    "cfdisk": "partition operations can make a disk unbootable",
    "parted": "partition operations can make a disk unbootable",
    "sfdisk": "partition operations can make a disk unbootable",
    "partx": "partition operations can make a disk unbootable",
    "cryptsetup": "encryption operations can make a disk unreadable",
    "pvremove": "removing LVM volumes destroys their data",
    "vgremove": "removing LVM volumes destroys their data",
    "lvremove": "removing LVM volumes destroys their data",
    "lvreduce": "shrinking an LVM volume can destroy data",
    "grub-install": "reinstalling the bootloader can make the host unbootable",
    "grub2-install": "reinstalling the bootloader can make the host unbootable",
    "userdel": "deleting a user can lock out access",
    "deluser": "deleting a user can lock out access",
    "chpasswd": "bulk password change can lock out access",
}
# Power/boot-state verbs (bare commands).
_POWER_PROGRAMS = frozenset(
    {"reboot", "shutdown", "poweroff", "halt", "telinit", "kexec"}
)
# systemctl sub-verbs that change power/boot state.
_SYSTEMCTL_POWER = frozenset(
    {"reboot", "poweroff", "halt", "kexec", "emergency", "rescue",
     "isolate", "set-default"}
)
# Critical units whose stop/disable/mask is a lockout.
_CRITICAL_UNIT_RE = re.compile(r"\b(?:ssh|sshd|firewalld|nftables|iptables)\b")
# login shells that disable a login.
_NOLOGIN_RE = re.compile(r"/(?:usr/)?s?bin/(?:nologin|false)$")
# Privileged groups whose deletion removes sudo.
_PRIV_GROUPS = frozenset({"wheel", "sudo", "root", "adm"})

# Explicit destructive taxonomy — SECONDARY whole-string net. The argv-aware
# logic above is authoritative; these catch shapes the tokenizer cannot see
# (fork bombs, raw redirections onto devices/critical files). Any match =>
# DESTRUCTIVE.
_DESTRUCTIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # raw block writes via redirection
    (re.compile(r">\s*/dev/(?:sd|nvme|vd|hd|mapper|disk|md|dm-|loop)\w*"),
     "redirecting output onto a block device destroys it"),
    # zpool destroy
    (re.compile(r"\bzpool\s+(?:destroy|labelclear)\b"), "destroying a zpool erases its data"),
    # truncating critical system files via redirection
    (re.compile(r">\s*/etc/(?:fstab|passwd|shadow|sudoers|gshadow|group|hosts)\b"),
     "truncating a critical system file can break boot or access"),
    (re.compile(r">\s*/etc/ssh/sshd_config\b"), "truncating sshd_config can lock you out"),
    # SELinux disable
    (re.compile(r"\bsetenforce\s+0\b"), "disabling SELinux enforcement changes the host's security posture"),
    # fork bomb
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"), "fork bomb will exhaust the host"),
)

# Shapes that indicate a WRITE (mutation) but not in the destructive taxonomy.
# Used as part of default-deny: if it's not a known read and not destructive but
# it clearly mutates state, it is at least a WRITE. If we can't even tell, the
# shaping rule below still floors it at WRITE.
_WRITE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:cp|mv|ln|touch|mkdir|rmdir|install|rsync|truncate)\b"),
    re.compile(r"\b(?:chmod|chown|chgrp|chattr|setfacl|setcap)\b"),
    re.compile(r"\b(?:useradd|usermod|groupadd|chsh|chage)\b"),
    re.compile(r"(?<!/)\bpasswd\b(?:\s|$)"),  # the passwd command, not the /etc/passwd path
    re.compile(r"\brm\b"),  # any rm not caught as destructive is still a write
    re.compile(r"\bip\b\s+\w+\s+(?:add|del|delete|change|replace|flush|set)\b"),
    re.compile(r"\b(?:tee|dd)\b"),
    re.compile(r"\b(?:tar|unzip|gunzip|gzip|xz|zstd)\b"),
    re.compile(r"\bgit\b.*\b(?:commit|push|merge|rebase|reset|checkout|clean|stash|pull|clone|init|add)\b"),
    re.compile(r"\b(?:mount|umount|swapon|swapoff)\b"),
    re.compile(r"\b(?:ip|nmcli|firewall-cmd|iptables|nft|ufw)\b"),  # network mutation verbs land here unless destructive matched first
    re.compile(r">>?"),  # any output redirection that wasn't caught as destructive
)


# Specific mutating shapes that must override a read-classified sub-verb of a
# sub-command-aware command (e.g. `ip addr add` where `addr` alone reads).
# Deliberately narrow: only output redirection and explicit add/del/change verbs.
_SUBCMD_OVERRIDE_WRITE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r">>?"),
    re.compile(r"\bip\b\s+\w+\s+(?:add|del|delete|change|replace|flush|set)\b"),
    re.compile(r"\bnmcli\b.*\b(?:add|modify|delete|up|down|edit)\b"),
    re.compile(
        r"\bfirewall-cmd\b.*--(?:add|remove|set|change|reload|complete-reload|runtime-to-permanent)\b"
    ),
)


def _argv0(token: str) -> str:
    """Strip a leading path and any env-var prefix from argv[0]."""
    return token.rsplit("/", 1)[-1]


def _tokenize(command: str) -> Sequence[str]:
    try:
        return shlex.split(command, comments=False, posix=True)
    except ValueError:
        # Unparseable quoting => we cannot reason about it safely.
        return []


# Wrappers that prefix a real command. The value maps each wrapper to the set
# of option flags that CONSUME the following token (so we skip the option-arg
# and land on the wrapped verb, e.g. `nice -n 10 rm -rf /` -> `rm -rf /`).
_PREFIX_WRAPPERS: dict[str, frozenset[str]] = {
    "sudo": frozenset({"-u", "-g", "-U", "-h", "-p", "-C", "-r", "-t"}),
    "doas": frozenset({"-u", "-C"}),
    "env": frozenset({"-u", "-C", "-S"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "ionice": frozenset({"-c", "-n", "-p", "-P", "-u"}),
    "nohup": frozenset(),
    "time": frozenset({"-o", "-f", "--format", "--output"}),
    "command": frozenset(),
    "exec": frozenset({"-a"}),
    "stdbuf": frozenset({"-i", "-o", "-e"}),
    "setsid": frozenset(),
    "timeout": frozenset({"-s", "--signal", "-k", "--kill-after"}),
    "xargs": frozenset({"-I", "-n", "-P", "-d", "-a", "-E", "-s", "-L", "--replace",
                        "--max-args", "--max-procs", "--delimiter", "--max-lines"}),
    "watch": frozenset({"-n", "-d", "--interval"}),
}


def _strip_env_prefix(tokens: Sequence[str]) -> Sequence[str]:
    """Drop leading privilege/scheduling wrappers (sudo, env, nice -n N, xargs
    -n1, timeout 5s, ...) and VAR=val assignments so we see the wrapped verb.

    Wrapper OPTION-ARGUMENTS are consumed too (e.g. `nice -n 10` skips both),
    and a wrapper's own positional like `timeout 5s` / `xargs -0` is skipped so
    a destructive wrapped command (`timeout 5 rm -rf /`, `xargs rm -rf`) is
    never hidden behind the wrapper.
    """
    out = list(tokens)
    while out:
        head = _argv0(out[0])
        if head in _PREFIX_WRAPPERS and "=" not in out[0]:
            consume = _PREFIX_WRAPPERS[head]
            out = out[1:]
            # skip this wrapper's own flags / option-args / leading positionals
            # (durations, replace-strings) until we reach a non-flag that looks
            # like a command verb.
            while out:
                t = out[0]
                base = t.split("=", 1)[0]
                if t.startswith("-"):
                    out = out[1:]
                    if base in consume and out:
                        out = out[1:]  # option takes a separate argument
                    continue
                # timeout's first positional is a DURATION, not the verb.
                if head == "timeout" and re.fullmatch(r"\d+(?:\.\d+)?[smhd]?", t):
                    out = out[1:]
                    continue
                break
            continue
        if "=" in head and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", out[0]):
            out = out[1:]
            continue
        break
    return out


def _has_pipeline_or_chain(command: str) -> bool:
    """True if the command contains a pipe, chain, subshell, or redirection that
    means we cannot reason about it as a single simple verb."""
    return bool(re.search(r"[|;&]|\$\(|`|&&|\|\|", command))


# ---------------------------------------------------------------------------
# Argv flag / operand normalization
# ---------------------------------------------------------------------------

def _split_subcommands(command: str) -> list[str]:
    """Split a command line into independently-classifiable sub-commands on the
    shell operators that sequence/connect separate programs ( | ; & && || ).

    This is a SAFETY split, not a faithful shell parse: we only need each
    program's argv to survive intact so the most-severe sub-command wins. We do
    NOT split inside quotes (we scan the shlex-respecting way) — a crude but
    conservative regex split is acceptable because a false split can only
    produce MORE sub-commands to classify (never fewer), and every fragment is
    re-floored at WRITE by default-deny.

    Command SUBSTITUTIONS — $(...) and `...` — are ALSO surfaced as independent
    sub-commands so a destructive verb hidden inside one (`echo $(rm -rf /etc)`,
    `` `reboot` ``) is tokenized and escalated rather than slipping to the WRITE
    floor. We extract the inner text and classify it on its own; the outer text
    (with the substitution removed) is still classified too. A nested/unbalanced
    substitution we cannot extract leaves the raw fragment in place, which only
    ever yields MORE gating, never less.
    """
    # Pull out command-substitution bodies first: $(...) and `...`. We keep both
    # the inner body AND the residual outer text (substitution blanked out) so
    # neither side can hide a verb from classification.
    inner: list[str] = []
    for m in re.finditer(r"\$\(([^()]*)\)", command):
        inner.append(m.group(1))
    for m in re.finditer(r"`([^`]*)`", command):
        inner.append(m.group(1))
    residual = re.sub(r"\$\([^()]*\)", " ", command)
    residual = re.sub(r"`[^`]*`", " ", residual)

    # Replace shell operators with a sentinel, but leave redirections attached
    # to their command so the redirect-target logic can see them.
    parts = re.split(r"\|\||&&|[|;&\n]", residual)
    for body in inner:
        parts.extend(re.split(r"\|\||&&|[|;&\n]", body))
    return [p.strip() for p in parts if p.strip()]


def _flag_letters(tokens: Sequence[str]) -> set[str]:
    """Collect every short-flag letter and long-flag name from argv.

    Normalizes combined/split/uppercase forms so that -rf, -fr, -r -f, -Rf,
    -fR, -f -R, --recursive --force all yield the same set. Short flags are
    lowercased into single letters; long flags are kept as --name.
    """
    out: set[str] = set()
    for t in tokens:
        if t == "--" or not t.startswith("-") or t == "-":
            continue
        if t.startswith("--"):
            out.add(t.split("=", 1)[0].lower())
        else:
            for ch in t[1:]:
                out.add(ch.lower())
    return out


def _operands(tokens: Sequence[str]) -> list[str]:
    """Non-flag positional arguments (operands) of a command's argv[1:]."""
    out: list[str] = []
    saw_ddash = False
    for t in tokens[1:]:
        if t == "--":
            saw_ddash = True
            continue
        if not saw_ddash and t.startswith("-") and t != "-":
            continue
        out.append(t)
    return out


def _norm_path(p: str) -> str:
    """Normalize a path operand for comparison: strip a trailing slash and a
    trailing '/*' glob, but preserve a bare '/'."""
    p = p.strip()
    if p.endswith("/*"):
        p = p[:-2] or "/"
    if len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/") or "/"
    return p


def _is_recursive(flags: set[str], long_ok: bool = True) -> bool:
    return "r" in flags or (long_ok and "--recursive" in flags)


def _is_forced(flags: set[str]) -> bool:
    return "f" in flags or "--force" in flags


def _targets_system_path(operands: Sequence[str]) -> bool:
    for raw in operands:
        p = _norm_path(raw)
        if p in _SYSTEM_PATH_PREFIXES:
            return True
        for pre in _SYSTEM_PATH_PREFIXES:
            if pre in ("/", "~", "$HOME"):
                continue
            if p == pre or p.startswith(pre + "/"):
                return True
    return False


def _targets_critical_file(operands: Sequence[str]) -> bool:
    for raw in operands:
        p = _norm_path(raw)
        if p in _CRITICAL_FILES:
            return True
    return False


def _targets_block_device(operands: Sequence[str]) -> bool:
    for raw in operands:
        p = _norm_path(raw)
        if p.startswith(_BLOCK_DEV_PREFIXES):
            return True
    return False


def _classify_argv(tokens: Sequence[str], raw: str) -> tuple[OpClass, str] | None:
    """Argv-aware destructive detection for a single sub-command.

    Returns a (DESTRUCTIVE, reason) tuple when the tokenized argv is recognized
    as destructive, or None to let the caller fall through to the regex/sub-
    command/default-deny layers. Never returns READ/WRITE — this layer only
    *escalates*.
    """
    if not tokens:
        return None
    verb = _argv0(tokens[0])
    flags = _flag_letters(tokens)
    ops = _operands(tokens)

    # --- rm: recursive OR forced removal, and recursive deletes of system paths
    if verb == "rm":
        rec = _is_recursive(flags)
        forced = _is_forced(flags)
        if rec and forced:
            return OpClass.DESTRUCTIVE, "recursive forced file removal cannot be undone"
        if rec and _targets_system_path(ops):
            return OpClass.DESTRUCTIVE, "recursively removing a system path can destroy the system"
        if rec:
            # Any recursive delete is irreversible by construction.
            return OpClass.DESTRUCTIVE, "recursive file removal cannot be undone"
        if forced and _targets_system_path(ops):
            return OpClass.DESTRUCTIVE, "force-removing a system path can destroy the system"
        if _targets_critical_file(ops) or _targets_system_path(ops):
            return OpClass.DESTRUCTIVE, "removing a system path or critical file can break the host"
        if any("/etc/ssh/" in o or "authorized_keys" in o or "/.ssh" in o for o in ops):
            return OpClass.DESTRUCTIVE, "removing SSH keys/config can lock you out"
        # plain `rm file` falls through to WRITE.
        return None

    # --- file clobber over a critical file or block device (tee/cp/mv/dd/...)
    if verb in _CLOBBER_COMMANDS:
        # dd uses of=; others take the path as an operand. Gather all candidate
        # destination paths from both operands and of=/value tokens.
        targets = list(ops)
        for t in tokens:
            if t.startswith("of="):
                targets.append(t[3:])
        if _targets_critical_file(targets):
            return OpClass.DESTRUCTIVE, "overwriting a critical system file can break boot or access"
        if _targets_block_device(targets):
            return OpClass.DESTRUCTIVE, "writing to a block device can destroy data"

    # --- raw program wipers / partitioners / lvm / bootloader / userdel ...
    if verb in _DESTRUCTIVE_PROGRAMS:
        # mkfs.ext4 etc. arrive as the bare verb already (argv0 split on '.').
        return OpClass.DESTRUCTIVE, _DESTRUCTIVE_PROGRAMS[verb]
    # mkfs.<fstype> keeps the suffix in argv0; catch it explicitly.
    if verb.startswith("mkfs.") or verb.startswith("mkfs"):
        return OpClass.DESTRUCTIVE, "creating a filesystem erases the target device"

    # --- power / boot state
    if verb in _POWER_PROGRAMS:
        return OpClass.DESTRUCTIVE, "changing power state can drop a remote host"
    if verb == "init" and any(o in ("0", "6") for o in ops):
        return OpClass.DESTRUCTIVE, "changing runlevel can power off or reboot the host"
    if verb == "systemctl":
        sub = {_argv0(t) for t in tokens[1:] if not t.startswith("-")}
        if sub & _SYSTEMCTL_POWER:
            return OpClass.DESTRUCTIVE, "changing power/boot state can drop a remote host"
        if sub & {"stop", "disable", "mask"} and _CRITICAL_UNIT_RE.search(raw):
            return OpClass.DESTRUCTIVE, "stopping SSH/firewall on a remote host can lock you out"

    # --- remote reboot/poweroff via dbus / busctl
    if verb in ("dbus-send", "busctl", "gdbus"):
        if re.search(r"login1|systemd1", raw) and re.search(
            r"\b(?:Reboot|PowerOff|Halt|KExec|poweroff|reboot|halt)\b", raw
        ):
            return OpClass.DESTRUCTIVE, "remote power/boot control can drop the host"

    # --- mass kill of EVERY process (kill ... -1 / killall ... -1) — argv sees
    #     the -1 target cleanly, unlike the old word-boundary regex (dead code).
    if verb in ("kill", "killall", "pkill") and "-1" in tokens:
        return OpClass.DESTRUCTIVE, "killing every process can crash the host"

    # --- truncate of a block device or critical file
    if verb == "truncate":
        if _targets_block_device(ops) or _targets_critical_file(ops):
            return OpClass.DESTRUCTIVE, "truncating a device or critical file destroys data"

    # --- bootloader config rewrite
    if verb in ("grub-mkconfig", "grub2-mkconfig", "update-grub") and "-o" in flags:
        return OpClass.DESTRUCTIVE, "rewriting the bootloader config can make the host unbootable"
    if verb in ("grub-mkconfig", "grub2-mkconfig"):
        return OpClass.DESTRUCTIVE, "regenerating the bootloader config can make the host unbootable"

    # --- group deletion of a privileged group
    if verb == "groupdel" and any(o in _PRIV_GROUPS for o in ops):
        return OpClass.DESTRUCTIVE, "deleting a privileged group can remove all sudo access"

    # --- gpasswd -d/--delete <user> <privgroup>: removing a user from a
    #     privileged group (wheel/sudo/root/adm) strips their sudo access — an
    #     admin-lockout sibling of groupdel. ADDING (-a) is a plain write.
    if verb == "gpasswd":
        removing = any(t == "--delete" or t.startswith("--delete=")
                       or re.fullmatch(r"-[A-Za-z]*d[A-Za-z]*", t.split("=", 1)[0])
                       for t in tokens)
        # With `--delete=user` / `-d=user`, the user is absorbed into the flag
        # token and the only operand left is the GROUP, so also scan the raw
        # tokens (not just operands) for a privileged group name.
        priv_target = any(o in _PRIV_GROUPS for o in ops) or (
            removing and any(_argv0(t) in _PRIV_GROUPS for t in tokens[1:]
                             if not t.startswith("-"))
        )
        if removing and priv_target:
            return OpClass.DESTRUCTIVE, "removing a user from a privileged group can remove sudo access"

    # --- passwd lockout / root password change
    if verb == "passwd":
        if {"l", "--lock"} & flags:
            return OpClass.DESTRUCTIVE, "locking an account can lock out access"
        if any(o == "root" for o in ops):
            return OpClass.DESTRUCTIVE, "changing the root password can lock out access"

    # --- usermod: lock, blank root password, or shell-to-nologin
    if verb == "usermod":
        # CASE-SENSITIVE: -L (lock) is destructive, -l (rename) is not. Match the
        # raw short-flag tokens, not the lowercased normalized set.
        if any(re.fullmatch(r"-[A-Za-z]*L[A-Za-z]*", t) or t == "--lock" for t in tokens):
            return OpClass.DESTRUCTIVE, "locking an account can lock out access"
        # blank password on root: -p "" root  (empty password operand)
        if "-p" in tokens or "--password" in tokens:
            idx = None
            for i, t in enumerate(tokens):
                if t in ("-p", "--password"):
                    idx = i
                    break
            pw = tokens[idx + 1] if idx is not None and idx + 1 < len(tokens) else None
            if (pw == "" or pw == '""' or pw == "''") and any(o == "root" for o in ops):
                return OpClass.DESTRUCTIVE, "setting a blank root password can compromise the host"
            if pw is not None and any(o == "root" for o in ops):
                return OpClass.DESTRUCTIVE, "changing the root password hash can lock out access"
        if any(_NOLOGIN_RE.search(t) for t in tokens):
            return OpClass.DESTRUCTIVE, "disabling the login shell can lock out access"

    # --- chsh to a nologin shell
    if verb == "chsh" and any(_NOLOGIN_RE.search(t) for t in tokens):
        return OpClass.DESTRUCTIVE, "removing a login shell can lock out access"

    # --- iptables / ip6tables flush, default-drop policy
    if verb in ("iptables", "ip6tables", "iptables-legacy", "ip6tables-legacy",
                "iptables-nft", "ip6tables-nft"):
        # CASE-SENSITIVE: -F / --flush (flush ALL rules). Match raw flag tokens.
        if any(t == "--flush" or re.fullmatch(r"-[A-Za-z]*F[A-Za-z]*", t) for t in tokens):
            return OpClass.DESTRUCTIVE, "flushing all firewall rules can lock you out on a default-drop host"
        m = re.search(r"-P\s+\w+\s+DROP", raw)
        if m:
            return OpClass.DESTRUCTIVE, "a default-drop firewall policy can lock you out"

    # --- nft flush/delete ruleset OR named table
    if verb == "nft":
        if re.search(r"\b(?:flush|delete)\b.*\b(?:ruleset|table)\b", raw):
            return OpClass.DESTRUCTIVE, "flushing or deleting an nftables ruleset/table can lock you out"

    # --- ip link set <if> down: taking down a network interface can sever SSH access
    if verb == "ip":
        if re.search(r"\blink\b.*\bset\b.*\bdown\b", raw):
            return OpClass.DESTRUCTIVE, "bringing down a network interface can sever remote access"

    # --- ufw disable/reset
    if verb == "ufw" and any(o in ("disable", "reset") for o in ops):
        return OpClass.DESTRUCTIVE, "resetting the firewall can lock you out"

    # --- firewall-cmd panic
    if verb == "firewall-cmd" and "--panic-on" in tokens:
        return OpClass.DESTRUCTIVE, "firewall panic mode drops all traffic and can lock you out"

    # --- dnf removals (cascade risk) handled in sub-command map, but catch the
    #     argv form too so a pipeline/chain cannot smuggle it past.
    if verb == "dnf":
        sub = {t for t in tokens[1:] if not t.startswith("-")}
        if sub & {"remove", "erase", "autoremove", "distro-sync"}:
            return OpClass.DESTRUCTIVE, "removing packages can cascade into kernel/ssh/sudo"

    # --- zpool destroy
    if verb == "zpool" and any(o in ("destroy", "labelclear") for o in ops):
        return OpClass.DESTRUCTIVE, "destroying a zpool erases its data"

    # --- find -delete / -exec rm
    if verb == "find":
        if "-delete" in tokens:
            return OpClass.DESTRUCTIVE, "find -delete removes matching files irreversibly"
        if "-exec" in tokens and any(_argv0(t) == "rm" for t in tokens):
            return OpClass.DESTRUCTIVE, "find -exec rm removes matching files irreversibly"

    return None


_SEVERITY = {OpClass.READ: 0, OpClass.WRITE: 1, OpClass.DESTRUCTIVE: 2}


def _classify_command(command: str) -> tuple[OpClass, str]:
    """Pure shape classification of a command string.

    Tokenizes into argv, splits compound command lines into independently-
    classifiable sub-commands, classifies EACH, and returns the MOST SEVERE.
    Applies destructive -> write -> read precedence, then default-deny shaping.
    """
    full = command.strip()
    if not full:
        return OpClass.WRITE, "empty or unrecognized operation"

    # Split a compound line ( | ; & && || ) and surface command-substitution
    # bodies, then classify each fragment; the most severe fragment governs the
    # whole line. This means a hidden destructive step anywhere in a pipeline,
    # chain, or $(...)/`...` substitution escalates the entire line.
    subs = _split_subcommands(full)
    # Always classify the literal full line too, so a single simple command (no
    # operators, no substitution) is handled exactly as before, and so the
    # whole-string secondary nets see the original text. When substitution or
    # operators produced fragments, those fragments are the authoritative,
    # tokenizable views — a destructive body inside $(...) cannot hide behind the
    # WRITE floor that the un-tokenizable raw string would otherwise yield.
    candidates = list(subs)
    if full not in candidates:
        candidates.append(full)
    worst: tuple[OpClass, str] | None = None
    for sub in candidates:
        cls, reason = _classify_single(sub, full)
        if worst is None or _SEVERITY[cls] > _SEVERITY[worst[0]]:
            worst = (cls, reason)
            if cls is OpClass.DESTRUCTIVE:
                break
    assert worst is not None
    return worst


def _classify_single(command: str, full_line: str) -> tuple[OpClass, str]:
    """Classify ONE sub-command. `full_line` is the entire original line, used
    only for redirection/whole-string secondary patterns that may span the
    sub-command boundary."""
    stripped = command.strip()
    if not stripped:
        return OpClass.WRITE, "empty or unrecognized operation"

    tokens = _tokenize(stripped)

    # 1a) Argv-aware destructive detection (PRIMARY, authoritative). Strip the
    #     privilege/env prefix first so `sudo rm -rf /` is seen as `rm -rf /`.
    core_for_argv = _strip_env_prefix(tokens) if tokens else tokens
    argv_hit = _classify_argv(core_for_argv, stripped)
    if argv_hit is not None:
        return argv_hit

    # 1b) Secondary whole-string destructive net (redirections, fork bombs,
    #     things the tokenizer cannot represent). Check both this sub-command
    #     and the full line so a redirect target is never missed.
    for pattern, reason in _DESTRUCTIVE_PATTERNS:
        if pattern.search(stripped) or pattern.search(full_line):
            return OpClass.DESTRUCTIVE, reason

    if not tokens:
        # Unparseable quoting — we cannot prove it is safe. Default-deny: an
        # unknown write-shape floors at WRITE; if it also looks destructive we
        # already returned above, so WRITE is the safe floor here.
        return OpClass.WRITE, "unparseable command treated as a change for safety"

    core = _strip_env_prefix(tokens)
    if not core:
        return OpClass.WRITE, "no command verb found after privilege wrapper"

    verb = _argv0(core[0])

    # A pipeline / chain / command substitution can hide a mutation; only treat
    # the whole thing as a pure read if EVERY recognizable verb is read-only.
    if _has_pipeline_or_chain(stripped):
        # Destructive already excluded. If any write pattern appears, it's a
        # write; otherwise, if the lead verb is a pure read command and no write
        # pattern matched, allow it as read.
        for wp in _WRITE_PATTERNS:
            if wp.search(stripped):
                return OpClass.WRITE, "pipeline contains a state-changing step"
        if verb in _READ_COMMANDS and verb not in _SUBCOMMAND_CLASS:
            return OpClass.READ, "read-only pipeline"
        # Lead verb has sub-commands or is unknown -> fall through to default-deny.

    # 2) Sub-command-aware commands (systemctl, dnf, firewall-cmd, git, ip, ...).
    if verb in _SUBCOMMAND_CLASS:
        sub_map = _SUBCOMMAND_CLASS[verb]
        # A mutating shape (e.g. `ip addr add`, output redirection) must override
        # a read-classified sub-verb (`addr`): check these SPECIFIC mutating
        # shapes first so a read sub-verb can never mask a write. We do NOT run
        # the broad command-name write patterns here (they would mis-flag read
        # invocations of these very commands).
        for wp in _SUBCMD_OVERRIDE_WRITE_PATTERNS:
            if wp.search(stripped):
                return OpClass.WRITE, f"{verb} invoked with a state-changing operation"
        # find the first token that is a known sub-verb
        for tok in core[1:]:
            key = tok
            if key in sub_map:
                cls = sub_map[key]
                return cls, f"{verb} {key} classified as {cls.value}"
        # Known command, unknown/absent sub-verb:
        #   - bare read commands (e.g. `systemctl` alone lists units; `ip` alone)
        #     -> READ only if the command with no recognized mutating sub-verb is
        #        inherently a lister. We default-deny mutating-capable commands to
        #        WRITE when the sub-verb is unrecognized.
        if verb in _READ_COMMANDS:
            # Has write patterns? then write. Else treat bare invocation as read.
            for wp in _WRITE_PATTERNS:
                if wp.search(stripped):
                    return OpClass.WRITE, f"unrecognized {verb} operation treated as a change"
            return OpClass.READ, f"{verb} with no recognized changing operation"
        return OpClass.WRITE, f"unrecognized {verb} operation treated as a change"

    # 3) Plain read commands with no mutating flags/redirection.
    if verb in _READ_COMMANDS:
        for wp in _WRITE_PATTERNS:
            if wp.search(stripped):
                return OpClass.WRITE, f"{verb} invoked with a state-changing flag or redirection"
        return OpClass.READ, f"{verb} is a read-only operation"

    # 4) Known write shapes.
    for wp in _WRITE_PATTERNS:
        if wp.search(stripped):
            return OpClass.WRITE, "recognized state-changing operation"

    # 5) Default-deny: an unknown verb we cannot prove is a read is at least a
    #    WRITE. It never auto-runs. (Unknown DESTRUCTIVE shapes were caught in
    #    step 1; this floor catches everything else.)
    return OpClass.WRITE, "unrecognized operation treated as a change for safety"


def classify(command: str, context: ExecContext | None = None) -> Decision:
    """Classify a proposed operation and derive its gate.

    Args:
        command: the literal command line that would execute.
        context: the execution environment. Defaults to an interactive,
                 non-remote session.

    Returns:
        A Decision with the op class, the gate that must be satisfied, a plain
        human reason, and auto_ok (True only for read/ALLOW).
    """
    ctx = context or ExecContext()
    op_class, reason = _classify_command(command)

    if op_class is OpClass.READ:
        return Decision(OpClass.READ, Gate.ALLOW, reason, auto_ok=True)

    if op_class is OpClass.WRITE:
        # Writes always need a human yes/no. Never auto-confirmed, even
        # interactively; never auto-run non-interactively.
        if not ctx.interactive:
            return Decision(
                OpClass.WRITE,
                Gate.REFUSE,
                f"{reason}; a change needs confirmation and no one is available to confirm",
                auto_ok=False,
            )
        return Decision(OpClass.WRITE, Gate.CONFIRM, reason, auto_ok=False)

    # DESTRUCTIVE.
    if not ctx.interactive:
        # I3: destructive operations are NEVER run non-interactively. There is
        # no one to type the literal word, so the only safe outcome is REFUSE.
        return Decision(
            OpClass.DESTRUCTIVE,
            Gate.REFUSE,
            f"{reason}; this cannot be done without a person present to confirm it in full",
            auto_ok=False,
        )
    return Decision(
        OpClass.DESTRUCTIVE,
        Gate.CONFIRM_TYPED,
        reason,
        auto_ok=False,
    )


def confirms_destructive(typed: str | None) -> bool:
    """Return True iff `typed` clears a destructive gate.

    Only the literal confirm word, typed IN FULL (case-sensitive, no surrounding
    whitespace beyond trim), clears the gate. An empty line, "y", "yes", "Y", a
    partial word, or anything else does NOT clear it. There is no default-yes.
    """
    if typed is None:
        return False
    return typed.strip() == DESTRUCTIVE_CONFIRM_WORD


def is_auto_confirmable(decision: Decision) -> bool:
    """True iff this decision may proceed with NO human interaction.

    By construction this is True ONLY for read/ALLOW. Writes and destructive
    operations are never auto-confirmable.
    """
    return decision.auto_ok and decision.gate is Gate.ALLOW
