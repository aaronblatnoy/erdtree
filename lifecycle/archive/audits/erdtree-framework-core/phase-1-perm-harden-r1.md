# Phase 1 — Permission Seam Hardening (Round 1)

**File under audit:** `core/agent/permissions.py` (safety keystone)
**Tests:** `tests/test_permissions.py`
**Invariant:** CLAUDE.md I3 — destructive ops require a literal-word typed confirmation, never auto-confirmed, never run non-interactively.
**Date:** 2026-06-21
**Result:** PASS — all findings now gated DESTRUCTIVE; all tests green.

## Root cause (confirmed before fix)

The original classifier used **regex-on-raw-string** flag detection. It did NOT
tokenize argv or normalize flags, so any non-canonical flag form (split,
uppercase, reordered) and any file-clobber-instead-of-redirect escaped the
destructive net and fell through to WRITE (a mere yes/no confirm). Verified by
probe before the fix — every seed finding classified as `write`:

```
write  iptables -F / --flush / ip6tables -F
write  nft flush table <fam> <name> / nft delete table ...
write  kill -9 -1 / killall -9 -1            (dead regex: \b-9\b\b-1\b never matched)
write  rm -r -f /etc, rm -fR, rm -Rf, rm -f -R, rm -R /etc, sudo rm -r /home/user
write  tee|cp|mv|dd over /etc/ssh/sshd_config
write  tee /etc/fstab, cp /dev/null /etc/passwd, mv x /etc/shadow, dd of=/etc/sudoers
write  chpasswd, usermod -p "" root, deluser admin
write  dbus-send / busctl ... login1 Reboot/PowerOff
write  truncate -s 0 /dev/sdb
```

## Re-architecture (MANDATE items 1–4)

1. **Tokenize argv + most-severe sub-command.** `_classify_command` now
   `_split_subcommands` on `| ; & && ||`, classifies EACH sub-command via
   `_classify_single`, and returns the **most severe** class. A destructive step
   anywhere in a pipeline/chain escalates the whole line.
2. **Normalize flags.** `_flag_letters` decomposes combined/split/uppercase
   short flags into a single lowercased set so `-rf == -fr == -r -f == -Rf ==
   -fR == -f -R == --recursive --force`. Case-sensitive flags that need it
   (`-L` lock vs `-l` rename; `-F` flush) are matched against raw flag tokens.
3. **Argv-aware destructive layer** (`_classify_argv`) runs FIRST and is
   authoritative; it understands operand paths (`_targets_system_path`,
   `_targets_critical_file`, `_targets_block_device`), clobber commands
   (tee/cp/mv/dd/install/truncate), wipers/partitioners/LVM/bootloader, power
   verbs + `systemctl`/`dbus-send`/`busctl` reboot, firewall flush (iptables/
   ip6tables/nft named-table/ufw), mass kill (`-1`), and admin lockout.
4. **Wrapper unwrapping.** `_strip_env_prefix` now consumes wrapper option-args
   and positionals (`nice -n 10`, `ionice -c 3`, `timeout 5s`, `xargs -0`,
   `watch -n 1`, `stdbuf`) so a wrapped destructive command is never hidden.
5. **Default-deny preserved:** unknown/destructive-shaped-but-unrecognized →
   WRITE floor at minimum; destructive → CONFIRM_TYPED (interactive) / REFUSE
   (non-interactive). Public API (`classify`, `Decision`, `ExecContext`, `Gate`,
   `OpClass`, `confirms_destructive`, `is_auto_confirmable`,
   `DESTRUCTIVE_CONFIRM_WORD`) unchanged.

The whole-string regex table is retained only as a SECONDARY net (raw
redirections onto devices/critical files, fork bombs).

## Findings — all now DESTRUCTIVE (post-fix probe, 0 failures)

| Finding | Before | After |
|---|---|---|
| iptables -F / --flush, ip6tables -F | write | **destructive** |
| nft flush/delete table <fam> <name> | write | **destructive** |
| kill -9 -1 / killall -9 -1 / pkill -9 -1 | write | **destructive** |
| rm -r -f / -fR / -Rf / -f -R / --recursive --force; rm -R /sys-path | write | **destructive** |
| tee/cp/mv/dd/install over /etc/ssh/sshd_config | write | **destructive** |
| clobber of /etc/fstab,passwd,shadow,sudoers (cp /dev/null, tee, mv, dd, truncate) | write | **destructive** |
| chpasswd; usermod -p "" root; usermod -L; deluser; userdel | write | **destructive** |
| dbus-send / busctl login1 Reboot/PowerOff; systemctl reboot/poweroff/halt | write | **destructive** |
| truncate -s 0 /dev/sdX; dd of=/dev/sdX; mkfs.* /dev/sdX | write | **destructive** |

Plus wrapper-evasion siblings caught: `nice -n 10 rm -fr /home`,
`cat x | xargs rm -rf`, `timeout 5 rm -rf /var`, `watch -n 1 systemctl reboot`,
`sudo env FOO=1 rm -Rf /var`.

## Over-gating guard (no false positives)

Routine ops correctly stay WRITE/READ: `usermod -l newname old` (rename),
`usermod -aG docker deploy`, `rm -f /tmp/scratch`, `iptables -A INPUT ...`,
`truncate -s 100M /tmp/disk.img`, `dd of=/tmp/img`, `groupdel testers`,
`passwd deploy`, `nice -n 5 ls`, `timeout 5 ls /`, `xargs -n1 echo`.

## Non-interactive behavior preserved

Every destructive case → `Gate.REFUSE` when `interactive=False`; never `auto_ok`.

## Test evidence (MANDATE item 5)

All new findings + split/uppercase/clobber/wrapper variants AND explicit
not-destructive guards added to `tests/test_permissions.py`. Existing cases stay
green.

```
$ python3 -m pytest tests/test_permissions.py -q
789 passed in 0.36s

$ python3 -m pytest tests/ -q
865 passed, 2 skipped in 0.41s
```

(Destructive corpus grew from the original canonical set to include every
finding above; permission-test count rose 427 → 789.)

## Verdict

**passed = true.** All findings are gated DESTRUCTIVE (typed-word confirmation,
REFUSE non-interactive), no benign op over-gated, full suite green. Touched only
`core/agent/permissions.py` and `tests/test_permissions.py`.
