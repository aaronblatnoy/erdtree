# Phase 1 — Permission Seam Hardening (Round 3) — Audit Evidence

**File audited:** `core/agent/permissions.py` (safety keystone)
**Tests:** `tests/test_permissions.py`
**Date:** 2026-06-21
**Verdict:** PASS — all tests green AND every seed finding gated DESTRUCTIVE (typed confirmation), never write.

## Test result (real, not fabricated)

```
$ python -m pytest tests/test_permissions.py -q
807 passed in 0.37s
```

## Root-cause fix confirmed in place

The classifier is TOKENIZED and FLAG-NORMALIZED (no longer regex-on-raw-string for flag detection):

- `_tokenize` uses `shlex.split` to build argv.
- `_strip_env_prefix` peels `sudo`/`doas`/`env`/`nice`/`ionice`/`timeout`/`xargs`/`watch`/`stdbuf`/VAR=val
  prefixes (consuming their option-args and positionals) so the real wrapped verb is seen.
- `_split_subcommands` splits on `| ; & && ||`; each sub-command is classified and the MOST SEVERE wins.
- `_flag_letters` normalizes combined/split/uppercase forms: `-rf == -fr == -r -f == -Rf == -fR == -f -R == --recursive --force`.
- `_classify_argv` is the authoritative DESTRUCTIVE escalation layer; a secondary whole-string regex net
  (`_DESTRUCTIVE_PATTERNS`) catches redirections / fork bombs the tokenizer cannot represent.
- DEFAULT-DENY preserved: unknown shape floors at WRITE, never silent ALLOW; destructive-shaped unknowns escalate.
- Public API (`classify`, `Decision`, `ExecContext`, `Gate`, `OpClass`, `confirms_destructive`,
  `is_auto_confirmable`, `DESTRUCTIVE_CONFIRM_WORD`) unchanged.
- Non-interactive refusal preserved: every destructive op => `Gate.REFUSE` when `interactive=False`;
  `Gate.CONFIRM_TYPED` when interactive. Verified directly.

## Every seed finding — now DESTRUCTIVE (independently re-verified, not just via corpus)

| Finding (was WRITE / dead-code) | Example | Now |
|---|---|---|
| iptables/ip6tables flush | `iptables -F`, `iptables --flush`, `ip6tables -F`, `iptables -F INPUT` | DESTRUCTIVE |
| iptables-legacy/-nft flush | `iptables-legacy -F`, `ip6tables-nft --flush` | DESTRUCTIVE |
| default-DROP policy | `iptables -P INPUT DROP` | DESTRUCTIVE |
| nft named table flush/delete | `nft flush table inet filter`, `nft delete table ip6 nat`, bridge/arp/netdev fams | DESTRUCTIVE |
| mass kill (word-boundary dead code) | `kill -9 -1`, `killall -9 -1`, `kill -KILL -1`, `pkill -9 -1`, `kill -s KILL -1` | DESTRUCTIVE |
| rm split/uppercase/separate flags | `rm -r -f /etc`, `rm -fR /home`, `rm -Rf /etc`, `rm -f -R /etc`, `rm --recursive --force /data` | DESTRUCTIVE |
| recursive delete of system path (no force) | `rm -r /etc`, `rm -R /home` | DESTRUCTIVE |
| forced delete of critical file | `rm -f /etc/fstab`, `rm /etc/shadow`, `rm /etc/ssh/sshd_config` | DESTRUCTIVE |
| sshd_config clobber (not just `>`) | `tee`, `cp /dev/null`, `mv`, `dd`, `install` over `/etc/ssh/sshd_config` | DESTRUCTIVE |
| other critical-file clobber | cp/tee/mv/dd over `/etc/fstab`,`/etc/passwd`,`/etc/shadow`,`/etc/sudoers` | DESTRUCTIVE |
| admin/root lockout | `chpasswd`, `usermod -p "" root`, `usermod -L root`, `deluser admin`, `userdel admin` | DESTRUCTIVE |
| privileged-group removal | `gpasswd -d admin wheel`, `gpasswd --delete admin sudo` | DESTRUCTIVE |
| remote reboot/poweroff/halt | `dbus-send … login1 … Reboot`, `busctl call … Reboot`, `gdbus … PowerOff`, `systemctl reboot/poweroff/halt` | DESTRUCTIVE |
| write to block device | `truncate -s 0 /dev/sdb`, `dd if=/dev/zero of=/dev/sda`, `mkfs.xfs /dev/sdb1` | DESTRUCTIVE |

All confirmed: each → `Gate.CONFIRM_TYPED` (interactive) and `Gate.REFUSE` (non-interactive), `auto_ok=False`.

## Non-regression (no over-gating)

Legitimate writes stay WRITE (not escalated): `usermod -l newname oldname`, `usermod -aG docker deploy`,
`rm -f /tmp/scratch`, `iptables -A INPUT … -j ACCEPT`, `truncate -s 100M /tmp/disk.img`,
`dd … of=/tmp/disk.img`, `groupdel testers`, `passwd deploy`, `gpasswd -d deploy docker`,
`gpasswd -a deploy wheel`, `cp a.conf b.conf`, `mv /tmp/a /tmp/b`. Reads stay READ.

## Corpus coverage

`DESTRUCTIVE_CORPUS` in `tests/test_permissions.py` includes every seed finding plus split/uppercase/clobber/
wrapper-evasion variants, so CI catches regressions; existing READ/WRITE corpora remain green.

**passed = true**
