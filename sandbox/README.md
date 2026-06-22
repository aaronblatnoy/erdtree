# Erdtree tier sandbox

A throwaway Rocky 9 container for exercising the Erdtree tiers safely. Destructive
operations (`rm -rf`, `mkfs`, `userdel`, ...) hit a disposable container overlay —
never the host. Inference is delegated to the host's GPU-backed Ollama.

## Why a container (and not a VM)

mossad's BIOS currently has AMD-V (SVM) disabled, so KVM can't load and a hardware
VM isn't available without a reboot into UEFI. A rootless podman container gives the
isolation that actually matters here — the filesystem/process boundary that contains
destructive ops — today, with no reboot. (If you later enable SVM in the BIOS, a
proper Rocky 9 KVM VM becomes the higher-fidelity option.)

## Usage

```bash
sandbox/build.sh                 # build the image once (pulls Rocky 9 base)
sandbox/run.sh marika            # 3B tier   — gold prompt
sandbox/run.sh radagon           # 7B tier   — red prompt   (PRIMARY)
sandbox/run.sh radagon 14b       # Radagon at the top of its 7B-14B range
```

You land in the tier's NL prompt. Type plain English; `!cmd` runs one bash command;
`!!` toggles permanently between NL and BASH mode.

## Tiers

| Tier    | Prompt color | Model (in this sandbox) |
|---------|--------------|-------------------------|
| marika  | gold         | `qwen2.5:3b`            |
| radagon | red          | `qwen2.5:7b` (7B–14B range; pass `14b` for the high end) |
| radahn  | scarlet      | massive / dedicated-infra — **not** a 14B; not runnable here |

## How it's wired

- **Repo** is mounted **read-only** at `/opt/erdtree`, so a destructive op can't
  mutate the source. The running tree is always the current checkout.
- **Inference** uses `--network=host`, so `localhost:11434` inside the container is
  the host's Ollama. The core client's localhost-only assertion (I1) still holds.
- **Audit log** and any writes land in the container's ephemeral overlay and vanish
  on exit (`--rm`).
- **Rootless**: container-root maps to your unprivileged host uid; host block
  devices aren't present (private tmpfs `/dev`).

## Containment verified

- repo mount is read-only (writes refused)
- host block devices (`/dev/sda`, ...) are not present in the container
- container runs in an unprivileged user namespace (root → host uid 1000)
- all mutations are confined to the disposable overlay; nothing leaks to the host

## Limitations

- Not a full systemd boot — `systemctl`/`journalctl` are limited inside a
  non-systemd container. The permission gate, dispatch, and audit still exercise
  fully; only the live system-service surface is reduced.
- For the full bootable-OS experience (login-shell wiring, dead-man during a real
  firstboot model pull), enable SVM in the BIOS and use a KVM VM, or wait for the
  Phase 11 installer.
