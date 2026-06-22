# Terminal Output Spec

This is the contract for what the product prints to the terminal. The marketing
site's demo terminals were hand-authored to this format; the real CLI output
should match it. If the product's output looks worse than the site demos, this
file is the target to converge on.

The whole point: **it should not read like a chatbot.** No preamble, no "I'll
help you with that," no mention of AI/models/agents. Just a terminal that reads
the system, states what it found, asks before it changes anything, and reports
what it did.

---

## The flow

Every interaction follows the same four beats. Not every beat appears every
time (a pure read has no confirm/execute), but the order never changes:

1. **Read** — dim lines showing what the system is inspecting (context, logs,
   config). Prefixed with `→`.
2. **Find** — a blank line, then the findings in plain text. Key terms or
   problems are highlighted.
3. **Confirm** — before any write or destructive action, a prompt ending in
   `[y/N]`. Destructive/irreversible actions get a `⚠` warning line.
4. **Execute** — `✓` lines, one per completed step.

---

## Line types

| Type | Prefix | Color | Used for |
|------|--------|-------|----------|
| Prompt | `$ ` | accent (per-tier color) | The echoed user input |
| Read / context | `→ ` | dim gray | What it's reading, scanning, planning |
| Finding | *(none)* | normal gray | Plain-text results and recommendations |
| Highlight | *(inline)* | amber/yellow | Key terms, config keys, the thing that's wrong |
| Critical value | *(inline)* | red | A dangerous number or hard failure |
| Confirm prompt | *(none)* | dim gray | Ends in `[y/N]` |
| Warning | `⚠  ` | amber/yellow | Precedes a confirm for destructive/irreversible ops |
| Success | `✓ ` | green | A completed step |

Blank line between the "read" block and the "find" block, and between separate
operations.

---

## Rules

- **No AI language.** Never print "AI", "LLM", "model", "agent", "assistant",
  "I", or "I'll". The system acts; it does not converse.
- **No filler.** No "Sure!", "Here's what I found:", "Let me help." Go straight
  to the `→` read lines.
- **Reads run silently and immediately.** No confirm for read-only ops.
- **Writes always confirm.** Anything that changes the system ends in `[y/N]`
  before it runs.
- **Destructive ops get a `⚠` line** spelling out the consequence ("This locks
  out password-based SSH") before the confirm.
- **State the system context you used**, briefly, in the read lines — it proves
  the system knew the environment without the user explaining it.
- **One `✓` per step**, past tense, concrete ("nginx.service started — active,
  running" not "Done!").
- Use `·` as an inline separator in context lines, `→` for the read prefix.

---

## Reference transcripts

These are the exact demos from the marketing site. Match this shape.

### Diagnosis → fix (read, find, confirm, execute)

```
$ why is nginx not starting
→ Reading system context — Rocky 9 · 32GB RAM · nginx 1.24
→ Scanning journal: nginx.service (last 200 lines)

Port conflict — apache2.service is bound to :80
nginx.service failed: exit 1 — Address already in use

Stop apache2 and start nginx? [y/N]
$ y
✓ apache2.service stopped
✓ nginx.service started — active, running
```

`Port conflict` is highlighted (amber). The two `✓` lines are green.

### Install / setup (plan, confirm, execute)

```
$ set up nextcloud for personal use
→ System: Rocky 9 · 16GB RAM · 2TB /data mounted
→ Plan: nextcloud + mariadb + nginx + php-fpm. Install 4 packages, write 3 configs.
Continue? [y/N]
$ y
✓ mariadb installed and secured
✓ nextcloud 28 deployed at /var/www/nextcloud
✓ nginx configured · TLS ready → http://localhost
```

### Diagnosis with a dangerous value (highlight + critical red)

```
$ why is postgres consuming 90% memory
→ System: 64GB RAM · PostgreSQL 15 · 142 active connections
→ Reading pg_stat_activity, shared_buffers, work_mem...

shared_buffers = 32GB (50% RAM — within spec)
work_mem = 256MB × 142 connections = 36GB potential
Recommend: reduce work_mem to 64MB. Reloads without restart. Apply? [y/N]
```

`shared_buffers` and `work_mem` are highlighted (amber). `36GB potential` is red
(the critical value).

### Destructive op (⚠ warning before confirm)

```
$ harden this server against ssh brute force
→ Reading: sshd_config, firewalld zones, fail2ban status
Plan: enable fail2ban, MaxAuthTries=3, disable password auth, move SSH to :2222
⚠  This locks out password-based SSH. Key auth only after this point. Confirm? [y/N]
```

The `⚠` line is amber. No `✓` lines shown because the action is destructive and
gated — they'd only print after confirmation.

---

## ANSI color reference (for a real terminal)

The site used hex; the equivalent terminal colors:

| Role | Site hex | Terminal |
|------|----------|----------|
| Prompt `$` | per-tier accent | 256-color amber (e.g. `\e[38;5;179m`) |
| Read `→` | `#444` | bright black / gray (`\e[90m`) |
| Finding | `#888` | default fg, slightly dim |
| Highlight | `#fbbf24` | yellow (`\e[33m`) |
| Critical | `#f87171` | red (`\e[31m`) |
| Success `✓` | `#4ade80` | green (`\e[32m`) |
| Warning `⚠` | `#fbbf24` | yellow (`\e[33m`) |

Per-tier prompt accent: Marika = pale gold, Radagon = deep red (auburn),
Radahn = orange-red. The accent only colors the `$` prompt; everything else is
shared across tiers.
