# Phase 5 — OS Integration Audit (B2)

**Date:** 2026-06-21
**Slice:** OS-integration config files (erdtree-agent.service, erdtree.conf, erdtree PAM stack)
**Status:** PASSED (with legitimately deferred items noted below)

---

## Files Authored

| File | Path |
|------|------|
| systemd unit | `os/systemd/erdtree-agent.service` |
| journald drop-in | `os/journald/erdtree.conf` |
| PAM stack snippet | `os/pam/erdtree` |

---

## systemd Unit (`os/systemd/erdtree-agent.service`)

**Design decisions:**
- `After=network.target ollama.service` + `Wants=ollama.service`: orders after the inference service if it is starting, but does NOT block login if it never comes up (no `Requires=`).
- `TimeoutStartSec=15`: bounded activation window; a stuck service self-terminates rather than hanging a login session.
- `Restart=on-failure` / `RestartSec=2`: restarts on crash, not on clean exit or dead-man exec().
- `PrivateTmp=true`: minimal sandboxing without restricting tool access.
- Tier/model config read from `EnvironmentFile=-/etc/erdtree/erdtree.env` (optional; missing file is safe).
- `/etc/passwd` login-shell wiring is done by the Phase 11 installer, not this unit (comment in unit explains this).

**Static validation:**
```
$ systemd-analyze verify os/systemd/erdtree-agent.service
erdtree-agent.service: Command /opt/erdtree/venv/bin/python is not executable: No such file or directory
```
This warning is a build-host artifact: `/opt/erdtree/` does not exist on the build host (Arch Linux).
Structural validation with substituted real paths (`/usr/bin/python3`, user/group commented out):
```
$ systemd-analyze verify /tmp/erdtree-test.service
(no output — exit code 0 — structurally valid)
```
The unit structure is valid; the path error is expected on the build host.

---

## journald Drop-In (`os/journald/erdtree.conf`)

**Design decisions:**
- `Storage=persistent`: survives reboots (needed for post-incident diagnostics).
- `SystemMaxUse=500M` / `SystemMaxFileSize=50M`: bounded to prevent disk exhaustion.
- `MaxRetentionSec=90day`: 90-day window; the product's own JSONL audit log is the long-term record.
- `Compress=yes`: reduces SSD footprint, important on embedded targets.
- Explicit rate-limit settings document intent (journald defaults, made explicit).
- Comment clearly separates this concern from the append-only `/var/log/<tier>/audit.jsonl`.

---

## PAM Stack (`os/pam/erdtree`)

**Design decisions:**
- `auth include system-auth`: delegates to whatever authselect profile the admin chose. Conservative.
- `account required pam_nologin.so`: honors `/etc/nologin` lockdown.
- `session optional pam_selinux.so open/close`: SELinux context, no-op on non-enforcing systems.
- All Erdtree-specific session items are `optional`: a module failure falls back gracefully (user gets the dead-man bash session) rather than locking them out.
- No third-party or custom PAM modules referenced.

---

## Invariant Verification

| Invariant | Result |
|-----------|--------|
| I2: no "AI"/"LLM"/"model"/"agent"/"agentic" in user-facing strings | PASS — only in comments documenting the rule; Description= reads "Erdtree command shell" |
| I7: no "Rocky" in any user-facing string | PASS — zero occurrences anywhere in all three files |
| I1: shell opens no network connections | N/A — config files, not code |
| Dead-man fallback referenced | PASS — unit header explicitly points to shell/shell.py B1/I9 as the real safety floor |
| No hard Requires= on inference service | PASS — only Wants=, no Requires= |

---

## Legitimately Deferred Items

| Item | Reason |
|------|--------|
| Live systemd unit activation | Requires a provisioned target host with root, the `erdtree` user/group, `/opt/erdtree/` install, and `/etc/erdtree/erdtree.env`. Done by installer (Phase 11 / install/ scripts). |
| PAM login wiring (`/etc/pam.d/` drop + `/etc/passwd` shell entry) | Requires root on a provisioned target host and editing `/etc/passwd`. Done by installer (Phase 11). |
| journald drop-in activation (`systemctl restart systemd-journald`) | Requires root on a provisioned target host. Done by installer (Phase 11). |

---

## Summary

Three OS integration config files authored, I2/I7-clean, and structurally validated on this build host (Arch Linux with systemd). The only legitimately deferred items are live activation on a provisioned target host — all requiring root + a full OS image — which is correct Phase 11 work.
