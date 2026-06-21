"""Tests for the permission seam (core/agent/permissions.py).

These are pure-logic tests — no model, no network, no Linux required. They are
fully green on any host.

The load-bearing assertions (plan invariant I3, success criterion SC5):

  * Read ops -> ALLOW, instant, auto_ok.
  * Write ops -> CONFIRM (interactive) / REFUSE (non-interactive), never auto.
  * A CURATED DESTRUCTIVE CORPUS is ALWAYS classified DESTRUCTIVE, is ALWAYS
    gated behind a typed literal word, and is NEVER auto-confirmable.
  * Destructive ops are REFUSED non-interactively (no one to type the word).
  * Default-deny: an unknown shape is at least a WRITE, never a silent ALLOW.
  * Only the literal confirm word typed IN FULL clears a destructive gate; an
    empty line / "y" / "yes" / a partial word does NOT.
"""

from __future__ import annotations

import pytest

from core.agent.permissions import (
    DESTRUCTIVE_CONFIRM_WORD,
    Decision,
    ExecContext,
    Gate,
    OpClass,
    classify,
    confirms_destructive,
    is_auto_confirmable,
)


# ---------------------------------------------------------------------------
# Corpora
# ---------------------------------------------------------------------------

READ_CORPUS = [
    "ls -la /var/log",
    "cat /etc/os-release",
    "df -h",
    "free -m",
    "uptime",
    "uname -a",
    "ps aux",
    "ss -tlnp",
    "journalctl -u nginx --since today",
    "systemctl status nginx",
    "systemctl is-active sshd",
    "systemctl list-units --type=service",
    "dnf list installed",
    "dnf info postgresql",
    "dnf search nginx",
    "rpm -qa",
    "ip addr show",
    "ip route",
    "firewall-cmd --list-all",
    "git status",
    "git log --oneline -10",
    "grep -r ERROR /var/log/messages",
    "journalctl -p err -b",
    "find / -name '*.conf'",
    "getenforce",
    "sestatus",
    "lsblk",
    "smartctl -a /dev/sda",
    # read-only pipeline
    "journalctl -u sshd | grep Failed",
    "ps aux | grep ollama | grep -v grep",
    "cat /etc/passwd | wc -l",
    "/usr/bin/df -h",  # leading path resolves to df
    # ROUND-1: benign wrapped reads — wrappers must not over-gate a wrapped read
    "nice -n 5 ls /tmp",
    "timeout 5 ls /",
    "cat x | xargs echo",
    "xargs -n1 echo",
]

WRITE_CORPUS = [
    "systemctl restart nginx",
    "systemctl start postgresql",
    "systemctl stop nginx",
    "systemctl enable sshd",
    "systemctl disable cups",
    "systemctl reload nginx",
    "dnf install postgresql-server",
    "dnf update",
    "dnf upgrade nginx",
    "cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak",
    "mv /tmp/a /tmp/b",
    "mkdir -p /srv/data",
    "chmod 644 /etc/motd",
    "chown nginx:nginx /var/www",
    "useradd deploy",
    "touch /etc/cron.d/job",
    "ln -s /opt/app/current /opt/app/live",
    "echo 'tuned' >> /etc/sysctl.conf",
    "git commit -m 'x'",
    "git push origin main",
    "tar -czf backup.tgz /srv/data",
    "ip addr add 10.0.0.5/24 dev eth0",
    "nmcli connection up eth0",
    "mount /dev/sdb1 /mnt",
    # unknown verb -> default-deny to write
    "frobnicate --all",
    "some-vendor-tool deploy",
    # ROUND-1: explicit NOT-destructive guards — these must stay WRITE so the
    # broadened taxonomy does not over-gate routine ops. (-L lock is destructive
    # but -l rename is not; forced delete of a NON-system path is a write; adding
    # a firewall rule is a write; truncating/dd to a regular file is a write.)
    "usermod -l newname oldname",
    "usermod -aG docker deploy",
    "rm -f /tmp/scratch",
    "rm /tmp/scratch",
    "iptables -A INPUT -p tcp --dport 22 -j ACCEPT",
    "truncate -s 100M /tmp/disk.img",
    "dd if=/dev/zero of=/tmp/disk.img bs=1M count=10",
    "groupdel testers",
    "passwd deploy",
    # adding/removing a user to a NON-privileged group is a routine write;
    # adding to wheel is also fine (granting, not lockout).
    "gpasswd -d deploy docker",
    "gpasswd -a deploy wheel",
    "usermod -aG wheel deploy",
]

# THE curated destructive corpus. Every entry MUST be DESTRUCTIVE, MUST gate on
# a typed word, and MUST be refused non-interactively. Add freely; the contract
# is that this set never shrinks in coverage.
DESTRUCTIVE_CORPUS = [
    # rm -rf family
    "rm -rf /",
    "rm -rf /*",
    "rm -rf /home/user",
    "rm -rf ~/projects",
    "rm -fr /var/lib/pgsql",
    "rm -r --force /etc/nginx",
    "rm --recursive --force /data",
    "sudo rm -rf /var",
    "rm -rf $HOME",
    # mkfs / wipe / shred
    "mkfs.ext4 /dev/sdb1",
    "mkfs -t xfs /dev/nvme0n1p2",
    "mke2fs /dev/sdc",
    "wipefs -a /dev/sda",
    "blkdiscard /dev/nvme0n1",
    "shred -n 3 -z /dev/sdb",
    # dd to block device
    "dd if=/dev/zero of=/dev/sda bs=1M",
    "dd if=image.iso of=/dev/sdb",
    "cat /dev/zero > /dev/sda",
    # partition / lvm / luks
    "fdisk /dev/sda",
    "parted /dev/sda mklabel gpt",
    "sgdisk --zap-all /dev/sda",
    "sfdisk /dev/sda < layout.txt",
    "lvremove -y /dev/vg0/data",
    "vgremove vg0",
    "pvremove /dev/sdb1",
    "cryptsetup luksFormat /dev/sdb1",
    "zpool destroy tank",
    # power / boot state (remote reboot etc.)
    "reboot",
    "shutdown -h now",
    "poweroff",
    "halt",
    "init 6",
    "systemctl reboot",
    "systemctl poweroff",
    "systemctl isolate rescue.target",
    "systemctl set-default emergency.target",
    # bootloader
    "grub2-install /dev/sda",
    "grub2-mkconfig -o /boot/grub2/grub.cfg",
    # user / access lockout
    "userdel -r admin",
    "groupdel wheel",
    "passwd -l root",
    "passwd root",
    "usermod -L deploy",
    "usermod -s /sbin/nologin admin",
    "chsh -s /usr/sbin/nologin admin",
    # SSH lockout
    "systemctl stop sshd",
    "systemctl disable sshd",
    "systemctl mask ssh",
    "rm /etc/ssh/sshd_config",
    "echo '' > /etc/ssh/sshd_config",
    "rm ~/.ssh/authorized_keys",
    # firewall lockout
    "iptables -P INPUT DROP",
    "nft flush ruleset",
    "ufw disable",
    "ufw reset",
    "firewall-cmd --panic-on",
    "systemctl stop firewalld",
    # critical system files
    "echo '' > /etc/fstab",
    "rm /etc/passwd",
    "rm /etc/sudoers",
    # SELinux
    "setenforce 0",
    # dnf removals (cascade risk)
    "dnf remove kernel",
    "dnf remove openssh-server",
    "dnf autoremove",
    # mass file deletion via find
    "find /var/log -type f -delete",
    "find / -name '*.bak' -exec rm {} ;",
    # truncating a critical system file
    "truncate -s 0 /etc/fstab",
    # fork bomb
    ":(){ :|:& };:",

    # ---------------------------------------------------------------------
    # ROUND-1 HARDENING: argv-tokenized flag-normalized destructive corpus.
    # Every one of these previously under-gated to WRITE (regex-on-raw-string
    # taxonomy that did not tokenize argv or normalize flags). They MUST all be
    # DESTRUCTIVE now. Keep canonical AND split/uppercase/clobber variants.
    # ---------------------------------------------------------------------

    # rm: recursive+forced in split / uppercase / separated forms
    "rm -r -f /etc",
    "rm -f -r /etc",
    "rm -R -F /etc",
    "rm -fR /home",
    "rm -Rf /etc",
    "rm -fr /var",
    "rm -rF /usr",
    "rm -f -R /etc",
    "rm --recursive --force /data",
    "rm --force --recursive /data",
    "sudo rm -r -f /home/user",
    # rm: recursive delete of a system path (no force flag)
    "rm -r /etc",
    "rm -R /home",
    "rm --recursive /usr",
    "sudo rm -r /var/lib",
    # rm: forced delete of a system path / critical file (no recursion)
    "rm -f /etc/fstab",
    "rm /etc/shadow",
    "rm /etc/ssh/sshd_config",

    # firewall flush -> lockout on default-DROP (all backends)
    "iptables -F",
    "iptables --flush",
    "iptables -F INPUT",
    "ip6tables -F",
    "ip6tables --flush",
    "iptables-legacy -F",
    "ip6tables-nft --flush",
    "sudo iptables -F",
    "iptables -P INPUT DROP",
    "iptables -P FORWARD DROP",

    # nft named-ruleset flush / delete (not just `flush ruleset`)
    "nft flush table inet filter",
    "nft flush table ip filter",
    "nft delete table inet filter",
    "nft delete table ip6 nat",
    "sudo nft flush table inet filter",

    # mass kill including init/sshd (word-boundary dead-code bug)
    "kill -9 -1",
    "killall -9 -1",
    "kill -KILL -1",
    "sudo kill -9 -1",
    "pkill -9 -1",

    # SSH lockout via file CLOBBER (not just `>` redirect)
    "tee /etc/ssh/sshd_config",
    "cp /dev/null /etc/ssh/sshd_config",
    "cp emptyfile /etc/ssh/sshd_config",
    "mv x /etc/ssh/sshd_config",
    "dd if=/dev/null of=/etc/ssh/sshd_config",
    "install -m 600 /dev/null /etc/ssh/sshd_config",

    # clobber of other critical files via cp /dev/null, tee, mv, dd
    "cp /dev/null /etc/fstab",
    "tee /etc/fstab",
    "tee /etc/passwd",
    "mv x /etc/shadow",
    "dd if=/dev/null of=/etc/sudoers",
    "cp /dev/null /etc/passwd",
    "truncate -s 0 /etc/passwd",

    # admin / root account lockout
    "chpasswd",
    'usermod -p "" root',
    "usermod -p '' root",
    "usermod -L root",
    "usermod --lock admin",
    "deluser admin",
    "userdel admin",
    "userdel -r deploy",
    # admin lockout via removal from a privileged (sudo) group
    "gpasswd -d admin wheel",
    "gpasswd --delete admin sudo",
    "gpasswd -d operator adm",

    # remote reboot/poweroff/halt via dbus-send / busctl / systemctl
    "dbus-send --system --print-reply --dest=org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager.Reboot boolean:true",
    "dbus-send --system --dest=org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager.PowerOff boolean:true",
    "busctl call org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager Reboot b true",
    "busctl call org.freedesktop.login1 /org/freedesktop/login1 org.freedesktop.login1.Manager PowerOff b true",
    "systemctl reboot",
    "systemctl poweroff",
    "systemctl halt",

    # write to a block device (truncate / dd / mkfs)
    "truncate -s 0 /dev/sdb",
    "truncate -s 0 /dev/nvme0n1",
    "dd if=/dev/zero of=/dev/sdb",
    "dd of=/dev/sda if=/dev/zero",
    "mkfs.xfs /dev/sdb1",

    # firewall service / nft ruleset disable siblings
    "nft flush ruleset",
    "ufw disable",
    "ufw reset",

    # ROUND-1: wrapper-evasion — scheduling/xargs/timeout wrappers must NOT hide
    # a wrapped destructive command (these previously fell through to WRITE
    # because the wrapper's option-args were not consumed / the wrapped verb was
    # an argument, not argv0).
    "nice -n 10 rm -fr /home",
    "ionice -c 3 rm -r /usr",
    "timeout 5 rm -rf /var",
    "timeout 5s mkfs.ext4 /dev/sdb",
    "cat x | xargs rm -rf",
    "cat x | xargs rm -rf /etc",
    "xargs -0 rm -rf /home",
    "watch -n 1 systemctl reboot",
    "stdbuf -o0 rm -rf /etc",
    "sudo env FOO=1 rm -Rf /var",
]


# ---------------------------------------------------------------------------
# Read ops: instant, auto, no confirmation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", READ_CORPUS)
def test_read_is_allowed_instantly(cmd):
    d = classify(cmd)
    assert d.op_class is OpClass.READ, f"{cmd!r} should be READ, got {d.op_class} ({d.reason})"
    assert d.gate is Gate.ALLOW
    assert d.auto_ok is True
    assert is_auto_confirmable(d) is True
    assert d.requires_typed_word is False


@pytest.mark.parametrize("cmd", READ_CORPUS)
def test_read_is_allowed_even_non_interactive(cmd):
    # Reads are safe to run with no human present.
    d = classify(cmd, ExecContext(interactive=False))
    assert d.gate is Gate.ALLOW
    assert d.auto_ok is True


# ---------------------------------------------------------------------------
# Write ops: confirm interactively, refuse non-interactively, never auto
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", WRITE_CORPUS)
def test_write_requires_confirmation(cmd):
    d = classify(cmd)
    assert d.op_class is OpClass.WRITE, f"{cmd!r} should be WRITE, got {d.op_class} ({d.reason})"
    assert d.gate is Gate.CONFIRM
    assert d.auto_ok is False
    assert is_auto_confirmable(d) is False
    assert d.requires_typed_word is False


@pytest.mark.parametrize("cmd", WRITE_CORPUS)
def test_write_is_refused_non_interactively(cmd):
    d = classify(cmd, ExecContext(interactive=False))
    assert d.op_class is OpClass.WRITE
    assert d.gate is Gate.REFUSE
    assert d.auto_ok is False


# ---------------------------------------------------------------------------
# THE destructive corpus: always gated, never auto, refused non-interactively
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", DESTRUCTIVE_CORPUS)
def test_destructive_is_always_classified_destructive(cmd):
    d = classify(cmd)
    assert d.op_class is OpClass.DESTRUCTIVE, (
        f"{cmd!r} MUST be DESTRUCTIVE, got {d.op_class} ({d.reason})"
    )


@pytest.mark.parametrize("cmd", DESTRUCTIVE_CORPUS)
def test_destructive_gates_on_typed_word_when_interactive(cmd):
    d = classify(cmd, ExecContext(interactive=True))
    assert d.gate is Gate.CONFIRM_TYPED, f"{cmd!r} must gate on a typed word"
    assert d.requires_typed_word is True
    assert d.confirm_word == DESTRUCTIVE_CONFIRM_WORD


@pytest.mark.parametrize("cmd", DESTRUCTIVE_CORPUS)
def test_destructive_is_never_auto_confirmable(cmd):
    for ctx in (ExecContext(interactive=True), ExecContext(interactive=False),
                ExecContext(interactive=True, remote=True),
                ExecContext(interactive=False, remote=True)):
        d = classify(cmd, ctx)
        assert d.auto_ok is False, f"{cmd!r} must NEVER be auto-ok"
        assert is_auto_confirmable(d) is False, f"{cmd!r} must NEVER be auto-confirmable"


@pytest.mark.parametrize("cmd", DESTRUCTIVE_CORPUS)
def test_destructive_is_refused_non_interactively(cmd):
    # I3: never run a destructive op non-interactively.
    d = classify(cmd, ExecContext(interactive=False))
    assert d.gate is Gate.REFUSE, f"{cmd!r} must be REFUSED with no human present"
    assert d.op_class is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# The typed-word gate: only the literal word, in full, clears it
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["", " ", "y", "Y", "yes", "YES", "n", "no",
                                 "destroy", "DESTRO", "DESTROYED", "DESTROY now",
                                 "ok", "confirm", "1", "true", None,
                                 "  ", "\n"])
def test_non_literal_input_does_not_clear_destructive(bad):
    assert confirms_destructive(bad) is False


@pytest.mark.parametrize("good", ["DESTROY", " DESTROY", "DESTROY ", "  DESTROY  ", "\tDESTROY\n"])
def test_literal_word_in_full_clears_destructive(good):
    # Trimmed surrounding whitespace is tolerated; the WORD itself must be exact.
    assert confirms_destructive(good) is True


def test_empty_string_never_clears_gate():
    # The default-yes failure mode: a bare Enter must never proceed.
    assert confirms_destructive("") is False


# ---------------------------------------------------------------------------
# Default-deny on ambiguity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    "frobnicate",
    "totally-unknown-binary --go",
    "VAR=1 mysterytool",
    "sudo mysterytool",
    "",
    "   ",
])
def test_unknown_shape_floors_at_write_never_read(cmd):
    d = classify(cmd)
    assert d.op_class in (OpClass.WRITE, OpClass.DESTRUCTIVE)
    assert d.gate is not Gate.ALLOW
    assert d.auto_ok is False


def test_unparseable_quoting_is_not_a_read():
    d = classify('echo "unterminated')
    assert d.op_class is not OpClass.READ
    assert d.auto_ok is False


def test_read_command_with_write_redirection_becomes_write():
    # `echo` is a read verb, but redirecting output mutates state.
    d = classify("echo hacked > /etc/motd")
    assert d.op_class is OpClass.WRITE


def test_read_command_redirecting_to_block_device_is_destructive():
    d = classify("echo x > /dev/sda")
    assert d.op_class is OpClass.DESTRUCTIVE


def test_pipeline_with_hidden_write_is_write():
    d = classify("cat list.txt | xargs rm -f")
    # rm -f matches the destructive recursive/forced pattern? -f alone w/o -r:
    # the forced-removal branch matches -f, so this is destructive — which is
    # the SAFE answer. Accept either destructive or write, never read.
    assert d.op_class in (OpClass.WRITE, OpClass.DESTRUCTIVE)
    assert d.op_class is not OpClass.READ


def test_sudo_prefix_does_not_hide_destructive():
    assert classify("sudo rm -rf /etc").op_class is OpClass.DESTRUCTIVE


def test_env_prefix_does_not_hide_destructive():
    assert classify("FOO=bar mkfs.ext4 /dev/sdb1").op_class is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Whole-corpus safety invariant (the keystone assertion)
# ---------------------------------------------------------------------------

def test_no_destructive_op_is_ever_auto_confirmable():
    """SC5/I3: across the entire destructive corpus and every context, not one
    op is ever auto-confirmable and not one ever runs non-interactively."""
    for cmd in DESTRUCTIVE_CORPUS:
        for interactive in (True, False):
            for remote in (True, False):
                d = classify(cmd, ExecContext(interactive=interactive, remote=remote))
                assert d.op_class is OpClass.DESTRUCTIVE
                assert d.auto_ok is False
                assert is_auto_confirmable(d) is False
                if not interactive:
                    assert d.gate is Gate.REFUSE
                else:
                    assert d.gate is Gate.CONFIRM_TYPED


def test_decision_is_immutable():
    d = classify("ls")
    with pytest.raises(Exception):
        d.gate = Gate.REFUSE  # type: ignore[misc]
