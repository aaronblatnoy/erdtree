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

    # ROUND-2 HARDENING: command-substitution evasion. A destructive verb hidden
    # inside $(...) or `...` previously slipped to the WRITE floor because the
    # substitution body was never tokenized. The body MUST be surfaced and
    # escalated. (Outer benign text like `echo`/`x=` must not mask the inner op.)
    "$(rm -rf /etc)",
    "`reboot`",
    "echo $(rm -rf /home)",
    "echo `mkfs.ext4 /dev/sdb`",
    "foo `rm -rf /var`",
    "x=$(mkfs.ext4 /dev/sdb)",
    "result=$(dd if=/dev/zero of=/dev/sda)",
    "echo $(systemctl poweroff)",
    "log $(userdel -r admin)",

    # ROUND-2: gpasswd --delete=user / -d=user form (user absorbed into the flag
    # token, leaving only the privileged GROUP as an operand). Removing a user
    # from wheel/sudo/adm strips sudo — an admin lockout that previously slipped.
    "gpasswd --delete=admin wheel",
    "gpasswd -d=admin sudo",
    "gpasswd --delete=operator adm",
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


def test_command_substitution_does_not_hide_destructive():
    # A destructive verb inside $(...) or `...` must be tokenized and escalated,
    # not slip to the WRITE floor.
    for cmd in ("$(rm -rf /etc)", "`reboot`", "echo $(rm -rf /home)",
                "echo `mkfs.ext4 /dev/sdb`"):
        assert classify(cmd).op_class is OpClass.DESTRUCTIVE, cmd


def test_benign_command_substitution_is_not_over_escalated():
    # Surfacing substitution bodies must not flag a read substitution as
    # destructive. A pure read body stays READ; a VAR= assignment floors at WRITE.
    assert classify("echo $(date)").op_class is OpClass.READ
    assert classify("echo `hostname`").op_class is OpClass.READ
    assert classify("files=$(ls /tmp)").op_class in (OpClass.WRITE,)


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


# ---------------------------------------------------------------------------
# RHEL-9 TOOL SURFACE (Phase 1 taxonomy extension): per-verb READ/WRITE/
# DESTRUCTIVE boundaries for every new manifest tool.
#
# Each triple is (read_sibling, write_sibling, destructive_form). The read must
# ALLOW, the write must CONFIRM (interactive) / REFUSE (non-interactive), and the
# destructive form must gate on the typed word interactively AND be REFUSED with
# no human present. This is the load-bearing boundary contract: a missed
# destructive verb ships an under-gated op that can destroy a live box.
# ---------------------------------------------------------------------------

RHEL_VERB_BOUNDARIES = [
    # --- selinux ---
    ("getsebool httpd_can_network_connect",
     "setsebool httpd_can_network_connect on",
     "semanage fcontext -d '/web(/.*)?'"),
    ("semanage port -l",
     "semanage port -a -t http_port_t -p tcp 8080",
     "semanage port -d -p tcp 8080"),
    ("semanage fcontext -l",
     "semanage fcontext -a -t httpd_sys_content_t '/web(/.*)?'",
     "semanage user -d testuser"),
    # --- audit ---
    ("auditctl -l",
     "auditctl -a always,exit -F arch=b64 -S execve -k exec",
     "auditctl -D"),
    ("auditctl -s",
     "auditctl -w /etc/passwd -p wa -k identity",
     "auditctl -d always,exit -F arch=b64 -S execve"),
    ("auditctl -l",
     "auditctl -e 1",
     "auditctl -e 0"),
    # --- lvm ---
    ("pvdisplay",
     "pvcreate /dev/sdb1",
     "pvremove /dev/sdb1"),
    ("vgdisplay",
     "vgcreate vg0 /dev/sdb1",
     "vgremove vg0"),
    ("lvdisplay vg0/data",
     "lvcreate -n data -L 10G vg0",
     "lvremove -y /dev/vg0/data"),
    ("lvs",
     "lvextend -L +5G /dev/vg0/data",
     "lvreduce -L 5G /dev/vg0/data"),
    # --- stratis ---
    ("stratis pool list",
     "stratis pool create pool1 /dev/sdb",
     "stratis pool destroy pool1"),
    ("stratis filesystem list",
     "stratis filesystem create pool1 fs1",
     "stratis filesystem destroy pool1 fs1"),
    # --- nfs ---
    ("showmount -e localhost",
     "exportfs -a",
     "exportfs -u client:/srv/share"),
    ("exportfs",
     "exportfs -r",
     "exportfs -ua"),
    # --- samba ---
    ("testparm -s",
     "smbpasswd -a deploy",
     "smbpasswd -x deploy"),
    # --- nmcli / bond ---
    ("nmcli connection show",
     "nmcli connection modify eth0 ipv4.method manual",
     "nmcli connection delete eth0"),
    ("nmcli device status",
     "nmcli connection add type ethernet ifname eth1",
     "nmcli device disconnect eth0"),
    # --- routing ---
    ("ip route show",
     "ip route add 10.0.0.0/24 via 192.168.1.1",
     "ip route del default"),
    ("ip route show",
     "ip rule add from 10.0.0.0/24 table 100",
     "ip rule flush"),
    ("ip route show table main",
     "ip route add default via 192.168.1.1",
     "ip route flush table main"),
    # --- nftables ---
    ("nft list ruleset",
     "nft add rule inet filter input tcp dport 22 accept",
     "nft flush ruleset"),
    # --- podman ---
    ("podman ps -a",
     "podman run -d nginx",
     "podman rm -f web"),
    ("podman images",
     "podman pull nginx",
     "podman rmi nginx"),
    ("podman inspect web",
     "podman stop web",
     "podman rm web"),
    # --- buildah ---
    ("buildah images",
     "buildah from alpine",
     "buildah rm working-container"),
    ("buildah inspect img",
     "buildah commit working-container img",
     "buildah rmi localhost/img"),
    # --- virsh ---
    ("virsh list --all",
     "virsh start vm1",
     "virsh destroy vm1"),
    ("virsh dominfo vm1",
     "virsh define vm1.xml",
     "virsh undefine vm1"),
    ("virsh pool-list",
     "virsh pool-define pool.xml",
     "virsh pool-destroy default"),
    ("virsh domstate vm1",
     "virsh shutdown vm1",
     "virsh undefine vm1 --remove-all-storage"),
    # --- cron ---
    ("crontab -l",
     "crontab -e",
     "crontab -r"),
    ("crontab -l",
     "crontab /tmp/newcron",
     "crontab -r -u deploy"),
    # --- at ---
    ("atq",
     "at now + 1 hour",
     "atrm 5"),
    ("at -l",
     "at now + 2 hours",
     "at -r 5"),
    # --- sysctl ---
    ("sysctl -a",
     "sysctl -w vm.swappiness=10",
     "sysctl -w kernel.panic=10"),
    ("sysctl vm.swappiness",
     "sysctl net.core.somaxconn=1024",
     "sysctl kernel.modules_disabled=1"),
    # --- kernel_modules ---
    ("lsmod",
     "modprobe nvme",
     "rmmod xfs"),
    ("modinfo xfs",
     "modprobe -a xfs",
     "modprobe -r nvme"),
    # --- grub ---
    ("grubby --info=ALL",
     "grubby --set-default=/boot/vmlinuz-5.14",
     "grubby --remove-kernel=/boot/vmlinuz-5.14"),
    ("grubby --default-kernel",
     "grubby --update-kernel=ALL --args=quiet",
     "grub2-mkconfig -o /boot/grub2/grub.cfg"),
    # --- subscription ---
    ("subscription-manager status",
     "subscription-manager register --username user",
     "subscription-manager unregister"),
    ("subscription-manager list",
     "subscription-manager repos --enable=rhel-9-server",
     "subscription-manager remove --all"),
    # --- postgresql ---
    ("psql -c 'SELECT count(*) FROM users'",
     "psql -c 'INSERT INTO t VALUES (1)'",
     "psql -c 'DROP DATABASE production'"),
    ("pg_isready",
     "createdb staging",
     "dropdb production"),
    ("psql -c 'SELECT 1'",
     "psql -c 'UPDATE t SET x=1'",
     "psql -c 'TRUNCATE TABLE events'"),
    ("psql -c 'EXPLAIN SELECT 1'",
     "createuser deploy",
     "dropuser deploy"),
    ("psql -c 'SHOW work_mem'",
     "psql -c 'GRANT SELECT ON t TO deploy'",
     "psql -d app -c 'ALTER TABLE t DROP COLUMN c'"),
    # --- mariadb ---
    ("mysqladmin status",
     "mysqladmin flush-hosts",
     "mysqladmin drop production"),
    ("mysql -e 'SELECT 1'",
     "mysql -e 'INSERT INTO t VALUES (1)'",
     "mysql -e 'DROP TABLE events'"),
    ("mysql -e 'SHOW DATABASES'",
     "mysql -e 'UPDATE t SET x=1'",
     "mysql -e 'DELETE FROM users'"),
    ("mariadb -e 'SELECT 1'",
     "mariadb -e 'CREATE TABLE t (id INT)'",
     "mariadb -e 'TRUNCATE logs'"),
    # --- rsync ---
    ("rsync -n /src/ /dst/",
     "rsync -a /src/ /dst/",
     "rsync --delete /src/ /dst/"),
    ("rsync --dry-run /src/ /dst/",
     "rsync /src/ /dst/",
     "rsync -a --delete-after /src/ /dst/"),
    # --- restic ---
    ("restic snapshots",
     "restic backup /srv/data",
     "restic forget --prune"),
    ("restic ls latest",
     "restic forget --keep-last 5",
     "restic prune"),
    ("restic stats",
     "restic restore latest --target /restore",
     "restic forget --keep-last 5 --prune"),
    # --- sssd / realm ---
    ("realm list",
     "realm join ad.example.com",
     "realm leave ad.example.com"),
]

RHEL_READ_SIBLINGS = sorted({r for r, _, _ in RHEL_VERB_BOUNDARIES})
RHEL_WRITE_SIBLINGS = sorted({w for _, w, _ in RHEL_VERB_BOUNDARIES})
RHEL_DESTRUCTIVE_SIBLINGS = sorted({d for _, _, d in RHEL_VERB_BOUNDARIES})


@pytest.mark.parametrize("cmd", RHEL_READ_SIBLINGS)
def test_rhel_read_sibling_is_allowed(cmd):
    d = classify(cmd)
    assert d.op_class is OpClass.READ, f"{cmd!r} should be READ, got {d.op_class} ({d.reason})"
    assert d.gate is Gate.ALLOW
    assert d.auto_ok is True
    # Reads stay ALLOW even with no human present.
    assert classify(cmd, ExecContext(interactive=False)).gate is Gate.ALLOW


@pytest.mark.parametrize("cmd", RHEL_WRITE_SIBLINGS)
def test_rhel_write_sibling_confirms_and_refuses(cmd):
    d = classify(cmd)
    assert d.op_class is OpClass.WRITE, f"{cmd!r} should be WRITE, got {d.op_class} ({d.reason})"
    assert d.gate is Gate.CONFIRM
    assert d.auto_ok is False
    assert is_auto_confirmable(d) is False
    # No human present -> a change cannot be confirmed -> REFUSE.
    assert classify(cmd, ExecContext(interactive=False)).gate is Gate.REFUSE


@pytest.mark.parametrize("cmd", RHEL_DESTRUCTIVE_SIBLINGS)
def test_rhel_destructive_form_gates_on_typed_word(cmd):
    d = classify(cmd, ExecContext(interactive=True))
    assert d.op_class is OpClass.DESTRUCTIVE, f"{cmd!r} MUST be DESTRUCTIVE, got {d.op_class} ({d.reason})"
    assert d.gate is Gate.CONFIRM_TYPED
    assert d.requires_typed_word is True
    assert d.confirm_word == DESTRUCTIVE_CONFIRM_WORD
    assert d.auto_ok is False


@pytest.mark.parametrize("cmd", RHEL_DESTRUCTIVE_SIBLINGS)
def test_rhel_destructive_is_refused_non_interactively(cmd):
    # I3: every destructive manifest verb is REFUSED with no human present —
    # never auto-run, in any context.
    for ctx in (ExecContext(interactive=False),
                ExecContext(interactive=False, remote=True)):
        d = classify(cmd, ctx)
        assert d.op_class is OpClass.DESTRUCTIVE
        assert d.gate is Gate.REFUSE, f"{cmd!r} must be REFUSED non-interactively"
        assert d.auto_ok is False
        assert is_auto_confirmable(d) is False


def test_rhel_boundary_triples_are_distinct_classes():
    """Every triple genuinely spans the three risk classes — proving the read
    sibling is not accidentally over-gated and the destructive form is not
    accidentally under-gated to the same class as its write sibling."""
    for read_cmd, write_cmd, dest_cmd in RHEL_VERB_BOUNDARIES:
        assert classify(read_cmd).op_class is OpClass.READ, read_cmd
        assert classify(write_cmd).op_class is OpClass.WRITE, write_cmd
        assert classify(dest_cmd).op_class is OpClass.DESTRUCTIVE, dest_cmd


def test_sql_read_only_query_stays_read_but_any_doubt_is_write():
    # A clean single SELECT/SHOW/EXPLAIN reads; anything else biases to WRITE.
    assert classify("psql -c 'SELECT * FROM t'").op_class is OpClass.READ
    assert classify("mysql -e 'SHOW TABLES'").op_class is OpClass.READ
    # multiple statements -> cannot prove read-only -> WRITE
    assert classify("psql -c 'SELECT 1; SELECT 2'").op_class is OpClass.WRITE
    # file input cannot be inspected -> WRITE
    assert classify("psql -f migrate.sql").op_class is OpClass.WRITE
    assert classify("mysql --execute='CALL do_thing()'").op_class is OpClass.WRITE


def test_sql_destructive_verbs_escalate_regardless_of_client():
    for cmd in (
        "psql -c 'DROP TABLE t'",
        "psql -c 'delete from users'",       # lower-case still escalates
        "mysql -e 'TRUNCATE t'",
        "mariadb --execute='ALTER TABLE t DROP COLUMN c'",
        "psql -c 'SELECT 1' -c 'DROP DATABASE d'",  # second body is destructive
    ):
        assert classify(cmd).op_class is OpClass.DESTRUCTIVE, cmd
        assert classify(cmd, ExecContext(interactive=False)).gate is Gate.REFUSE, cmd


def test_sysctl_noncritical_write_is_write_critical_is_destructive():
    assert classify("sysctl -w vm.swappiness=10").op_class is OpClass.WRITE
    for key in ("kernel.panic", "kernel.sysrq", "kernel.core_pattern",
                "kernel.modules_disabled", "kernel.kexec_load_disabled"):
        assert classify(f"sysctl -w {key}=1").op_class is OpClass.DESTRUCTIVE, key
        assert classify(f"sysctl {key}=1").op_class is OpClass.DESTRUCTIVE, key


def test_podman_plain_rm_without_force_is_still_destructive():
    # The container is gone either way; -f is only the sharpest case.
    assert classify("podman rm mycontainer").op_class is OpClass.DESTRUCTIVE
    assert classify("podman container rm c1").op_class is OpClass.DESTRUCTIVE
    assert classify("podman rmi -f img").op_class is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Adversarial-review regression tests: F1 (podman noun-verb / prune),
# F2 (nmcli abbreviated delete/disconnect), F3 (rsync --del alias).
# ---------------------------------------------------------------------------

# F1 — CRITICAL: `podman <noun> prune` must be DESTRUCTIVE and must NOT auto-run.
@pytest.mark.parametrize("cmd", [
    "podman image prune -a -f",
    "podman image prune",
    "podman container prune",
    "podman volume prune",
    "podman network prune",
    "podman pod prune",
    "podman system prune",
    "podman system prune -a",
])
def test_f1_podman_prune_is_destructive_and_never_auto_runs(cmd):
    d = classify(cmd)
    assert d.op_class is OpClass.DESTRUCTIVE, f"{cmd!r} -> {d.op_class} ({d.reason})"
    assert d.gate is Gate.CONFIRM_TYPED
    assert d.auto_ok is False
    assert is_auto_confirmable(d) is False
    # Non-interactively a prune must REFUSE — never silently auto-run.
    non = classify(cmd, ExecContext(interactive=False))
    assert non.gate is Gate.REFUSE, f"{cmd!r} must REFUSE non-interactively"
    assert non.auto_ok is False


# F1 — the podman noun-verb grammar must classify on the VERB, not the noun.
@pytest.mark.parametrize("cmd,expected", [
    # image
    ("podman image ls", OpClass.READ),
    ("podman image inspect web", OpClass.READ),
    ("podman image history nginx", OpClass.READ),
    ("podman image pull nginx", OpClass.WRITE),
    ("podman image build .", OpClass.WRITE),
    ("podman image rm nginx", OpClass.DESTRUCTIVE),
    ("podman image rmi nginx", OpClass.DESTRUCTIVE),
    ("podman image prune", OpClass.DESTRUCTIVE),
    # container
    ("podman container ls", OpClass.READ),
    ("podman container inspect c1", OpClass.READ),
    ("podman container rm c1", OpClass.DESTRUCTIVE),
    ("podman container prune", OpClass.DESTRUCTIVE),
    # volume
    ("podman volume ls", OpClass.READ),
    ("podman volume inspect v1", OpClass.READ),
    ("podman volume rm v1", OpClass.DESTRUCTIVE),
    ("podman volume prune", OpClass.DESTRUCTIVE),
    # system
    ("podman system prune", OpClass.DESTRUCTIVE),
])
def test_f1_podman_noun_verb_resolves_on_verb(cmd, expected):
    got = classify(cmd).op_class
    assert got is expected, f"{cmd!r} -> {got} (expected {expected})"


# F1 — the benign siblings must be UNCHANGED (no over-gating from the noun skip).
@pytest.mark.parametrize("cmd,expected", [
    ("podman ps", OpClass.READ),
    ("podman ps -a", OpClass.READ),
    ("podman images", OpClass.READ),
    ("podman inspect web", OpClass.READ),
    ("podman pull nginx", OpClass.WRITE),
    ("podman run -d nginx", OpClass.WRITE),
    ("podman create nginx", OpClass.WRITE),
    ("podman rm web", OpClass.DESTRUCTIVE),
    ("podman rmi nginx", OpClass.DESTRUCTIVE),
    ("podman volume pull remote", OpClass.WRITE),  # noun-verb leak fix: was READ
])
def test_f1_podman_plain_forms_unchanged(cmd, expected):
    got = classify(cmd).op_class
    assert got is expected, f"{cmd!r} -> {got} (expected {expected})"


# F2 — nmcli abbreviated delete/disconnect must escalate to DESTRUCTIVE.
@pytest.mark.parametrize("cmd", [
    "nmcli con del home",
    "nmcli c del home",
    "nmcli conn del home",
    "nmcli connection del home",
    "nmcli connection delete home",
    "nmcli con delete home",
    "nmcli dev disc eth0",
    "nmcli device disc eth0",
    "nmcli device disconnect eth0",
    "nmcli d disc eth0",
])
def test_f2_nmcli_abbreviated_delete_disconnect_is_destructive(cmd):
    d = classify(cmd)
    assert d.op_class is OpClass.DESTRUCTIVE, f"{cmd!r} -> {d.op_class} ({d.reason})"
    assert d.gate is Gate.CONFIRM_TYPED
    assert classify(cmd, ExecContext(interactive=False)).gate is Gate.REFUSE


# F2 — benign nmcli siblings must NOT be over-gated by the prefix rule.
@pytest.mark.parametrize("cmd,expected", [
    ("nmcli con up eth0", OpClass.WRITE),
    ("nmcli con down eth0", OpClass.WRITE),
    ("nmcli connection modify eth0 ipv4.method manual", OpClass.WRITE),
    ("nmcli con show", OpClass.READ),
    ("nmcli con show d", OpClass.READ),
    ("nmcli connection show", OpClass.READ),
    ("nmcli device status", OpClass.READ),
])
def test_f2_nmcli_benign_siblings_not_overgated(cmd, expected):
    got = classify(cmd).op_class
    assert got is expected, f"{cmd!r} -> {got} (expected {expected})"


# F3 — rsync --del (alias for --delete-during) must be DESTRUCTIVE.
def test_f3_rsync_del_alias_is_destructive():
    d = classify("rsync --del /src/ /dst/")
    assert d.op_class is OpClass.DESTRUCTIVE, d.reason
    assert d.gate is Gate.CONFIRM_TYPED
    assert classify("rsync --del /src/ /dst/",
                    ExecContext(interactive=False)).gate is Gate.REFUSE
    # Full --delete and its variants stay DESTRUCTIVE too.
    assert classify("rsync --delete /src/ /dst/").op_class is OpClass.DESTRUCTIVE
    assert classify("rsync --delete-during /src/ /dst/").op_class is OpClass.DESTRUCTIVE


# F3 — negatives: --del must be matched EXACTLY, not swallow lookalike flags,
# and a plain rsync stays WRITE.
@pytest.mark.parametrize("cmd,expected", [
    ("rsync -a /src/ /dst/", OpClass.WRITE),
    ("rsync --delay-updates /src/ /dst/", OpClass.WRITE),  # NOT --del; lookalike
    ("rsync -n /src/ /dst/", OpClass.READ),                # plain dry-run reads
])
def test_f3_rsync_del_negatives(cmd, expected):
    got = classify(cmd).op_class
    assert got is expected, f"{cmd!r} -> {got} (expected {expected})"
