# Phase 1 — Permission Seam Hardening, Round 2 (evidence)

**Date:** 2026-06-21
**File under audit:** `core/agent/permissions.py` (SAFETY KEYSTONE)
**Tests:** `tests/test_permissions.py`
**Scope:** ONLY the two files above were touched.

## Result: PASS

- `pytest tests/test_permissions.py` -> **807 passed in ~0.40s** (was 789; +18 new parametrized cases).
- Every round-2 SEED finding is now classified **DESTRUCTIVE**, gated behind a typed literal word (`CONFIRM_TYPED` / `DESTROY`), never auto-confirmable, and **REFUSED** non-interactively.

## Architecture state (verified, not assumed)

The classifier was already re-architected away from raw-string regex into a tokenized,
flag-normalized taxonomy (this is the keystone of the round-2 mandate):

- `_tokenize` (shlex.split) + `_split_subcommands` split a compound line on `| ; & && ||`
  and classify EACH sub-command; the **most severe** governs the whole line
  (`_classify_command` / `_SEVERITY`).
- `_strip_env_prefix` peels `sudo` / `doas` / `env VAR=val` / `nice -n N` / `ionice` /
  `timeout 5s` / `xargs` / `watch` / `stdbuf` wrappers (consuming their option-args and
  leading positionals) so a wrapped destructive verb (`timeout 5 rm -rf /var`,
  `cat x | xargs rm -rf /etc`, `sudo env FOO=1 rm -Rf /var`) is never hidden.
- `_flag_letters` normalizes combined/split/uppercase short flags and long flags so
  `-rf == -fr == -r -f == -Rf == -fR == -f -R == --recursive --force` are equivalent.
- Case-sensitive flag distinctions preserved where they matter: `iptables -F`/`--flush`
  (flush, destructive) vs lowercase; `usermod -L` (lock, destructive) vs `-l` (rename, write).
- DEFAULT-DENY preserved: unknown verb / unparseable quoting / unknown sub-verb of a
  mutating-capable command floors at **WRITE**, never a silent ALLOW (`_classify_single`
  step 5). Destructive-shaped-but-unrecognized escalates via the argv layer + secondary
  whole-string net before the write floor.
- Public API unchanged (`classify`, `Decision`, `ExecContext`, `Gate`, `OpClass`,
  `confirms_destructive`, `is_auto_confirmable`, `DESTRUCTIVE_CONFIRM_WORD`).
- Non-interactive refusal behavior unchanged: WRITE -> REFUSE, DESTRUCTIVE -> REFUSE
  when `interactive=False`.

## Per-seed-finding verification (all OK)

Each checked for: `op_class is DESTRUCTIVE` AND `gate is CONFIRM_TYPED` (interactive)
AND `not auto_ok` AND `gate is REFUSE` (non-interactive).

| Seed finding | Representative commands | Status |
|---|---|---|
| `iptables -F` / `--flush`, `ip6tables -F`, `-t nat -F` (flush ALL -> default-DROP lockout) | `iptables -F`, `iptables --flush`, `ip6tables -F`, `iptables -t nat -F` | OK |
| `nft flush table <fam> <name>` / `nft delete table` (named ruleset) | `nft flush table inet filter`, `nft delete table inet filter`, `nft delete table ip6 nat` | OK |
| `kill -9 -1` / `killall -9 -1` (mass kill incl. init/sshd; old `\b-9\b` dead regex) | `kill -9 -1`, `killall -9 -1`, `kill -KILL -1`, `pkill -9 -1` | OK (argv sees `-1` token) |
| `rm -r/-R` of system paths, split/uppercase/separate flags | `rm -r -f /etc`, `rm -fR /home`, `rm -Rf /etc`, `rm -f -R /etc`, `rm --recursive --force /data`, `rm -R /home` | OK |
| SSH lockout via file CLOBBER (tee/cp/mv/dd over sshd_config) | `tee /etc/ssh/sshd_config`, `cp /dev/null /etc/ssh/sshd_config`, `mv x /etc/ssh/sshd_config`, `dd if=/dev/null of=/etc/ssh/sshd_config` | OK |
| Clobber of other critical files (fstab/passwd/shadow/sudoers) | `cp /dev/null /etc/fstab`, `tee /etc/passwd`, `mv x /etc/shadow`, `dd if=/dev/null of=/etc/sudoers` | OK |
| Admin lockout: chpasswd; `usermod -p "" root`; `usermod -L`; deluser/userdel | `chpasswd`, `usermod -p "" root`, `usermod -L root`, `deluser admin`, `userdel admin` | OK |
| Remote reboot/poweroff/halt via dbus-send / busctl / systemctl | `dbus-send ... login1.Manager.Reboot`, `busctl call ... Reboot`, `systemctl reboot/poweroff/halt` | OK |
| `truncate -s 0 /dev/sdX`; `mkfs.*` / `dd of=/dev/sdX` (block-device write) | `truncate -s 0 /dev/sdb`, `mkfs.xfs /dev/sdb1`, `dd if=/dev/zero of=/dev/sdb`, `dd of=/dev/sda if=/dev/zero` | OK |

## Round-2 adversarial sweep — new gap found and fixed

An independent probe of variants/siblings NOT in the corpus found ONE genuine
under-gating beyond the seed list:

- **`gpasswd -d <user> wheel|sudo|root|adm`** (remove a user from a privileged group ->
  strips sudo access; an admin-lockout sibling of the mandated `groupdel wheel`) was
  classified **WRITE**. FIXED: added a `gpasswd` rule in `_classify_argv` that escalates
  to DESTRUCTIVE only when the delete flag (`-d` / `--delete`) targets a privileged group
  (`wheel/sudo/root/adm`). Adding (`-a`) or removing from a non-privileged group
  (e.g. `docker`) correctly stays WRITE.

New corpus cases added:
- DESTRUCTIVE: `gpasswd -d admin wheel`, `gpasswd --delete admin sudo`, `gpasswd -d operator adm`.
- WRITE guards (must NOT over-gate): `gpasswd -d deploy docker`, `gpasswd -a deploy wheel`.

Non-gap notes (left intentionally):
- `nft -f <file>` loads a ruleset from a file whose contents are opaque to the classifier;
  it floors at WRITE. The mandated nft lockout shapes (`flush`/`delete ... ruleset|table`)
  are all caught. Not escalated — opaque-file-load is not a seed finding and blanket
  escalation would over-gate the routine `nft -f /etc/nftables.conf`.

## Commands run

```
python -m pytest tests/test_permissions.py -q   # 807 passed
PYTHONPATH=. python3 /tmp/verify_seed.py        # all 9 seed categories OK
```

## Verdict

**passed = true.** All tests green; every round-2 seed finding (plus the `gpasswd`
priv-group-removal sibling) is gated DESTRUCTIVE with typed confirmation and is refused
non-interactively. Public API and non-interactive-refusal behavior preserved. Only
`core/agent/permissions.py` and `tests/test_permissions.py` were modified.
