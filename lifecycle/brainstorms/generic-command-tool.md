# Brainstorm: The Generic Gated Command Tool (closing the closed-world gap)

**Status:** exploratory — design space + position, not a build plan.
**Date:** 2026-06-22
**Feeds:** a phase-plan-architect plan once the load-bearing question (§4) is resolved.

---

## 1. The problem, concretely

The natural-language agent can only act through an **enumerated, closed set of
tools**: 11 tools / 79 ops at time of writing.

```
disk(9) docs(1) files(11) firewall(10) hardware(7) logs(6)
network(8) packages(5) processes(6) services(8) users(8)   = 79 ops
```

There is **no general execution path**. When the model wants an operation the
menu does not cover, the router treats it as a MISS and re-asks, *handing the
model the valid-tool list to push it back into the menu*:

- `core/agent/router.py` → `reask_unknown_tool(name, valid_tools)` (~L78). The
  model emitting unknown tool names is not noise — it is the model reaching for
  operations the menu lacks.
- The `network.wifi` op added on 2026-06-22 is the symptom: "what wifi network
  am I on?" had no tool, so the model fell back to `ip -brief addr` (which
  cannot show an SSID). Adding `wifi` fixed *that* request. It does not fix the
  next thousand (`iwconfig`, `cron`, `lvm`, `sysctl`, `ip route`, `tmux`,
  `tcpdump`, `rsync`, …). Enumeration cannot reach the end of Linux.

### The two-worlds split (the real shape of the gap)

A raw escape hatch already exists — and is **deliberately outside the safety
layer**. `shell/passthrough.py`'s own docstring: *"this is the raw escape
hatch, **not** the tool layer that runs curated commands."*

|                         | NL agent (the product) | `!` passthrough |
|-------------------------|------------------------|-----------------|
| Coverage                | 79 ops, closed         | all of Linux    |
| Gated by `classify()`   | **yes**                | **no**          |
| Audited                 | **yes**                | **no**          |
| Input                   | English                | raw bash        |

So the NL surface — the entire pitch, "Type in English. Linux does it." — is
**strictly weaker than the shell it wraps**, and the only way to exceed it
drops the user into the *ungated, un-audited* path. Every load-bearing
invariant (gate-before-write, audit-everything) silently lapses the moment a
user needs something off-menu.

## 2. Why this is the priority

This is not a cosmetic gap. It directly contradicts the product promise in
`CLAUDE.md` ("natural language is the native interface to the OS") and quietly
defeats invariants #3 (no destructive op without confirmation) and #4 (audit
every operation) — because the workaround for the closed menu is the ungated
`!` path. The cwd/wifi fixes from earlier today were symptom-level; this is the
structural cause.

## 3. The key architectural insight

**Safety here does not come from the closed toolset. It comes from
`classify()`, which already reasons over arbitrary command _strings_.**

Evidence it is string-shaped, not tool-shaped:
- `core/agent/permissions.classify(cmd: str, ctx)` takes a command *string* and
  returns a Gate (ALLOW / CONFIRM / CONFIRM_TYPED / REFUSE).
- `core/agent/repl.synthesize_command()` exists *specifically* to turn a
  structured tool call back into a command string so the gate can read it
  (`network.show` → `"ip addr show"`, `network.bring_down` → `"ip link set
  <if> down"`, etc.). The structured call is already being collapsed to a
  string before the gate runs.

So the curated toolset is a *convenience layer over the string gate*, not the
thing that makes the system safe. That means a generic command tool is
architecturally native: the model emits a command string, the *same* gate
classifies it, the *same* audit spine records it.

## 4. THE load-bearing open question (resolve before building)

**Is `classify()` safe enough to be the _sole_ gate over arbitrary,
model-generated command strings?**

Today the classifier is exercised by a *finite, known* set of synthesized
strings (one shape per op). A generic tool makes it the gate for an *open* set
of inputs the model invents. The risk is not the ALLOW/CONFIRM/DESTRUCTIVE
ladder itself — it is **coverage and the unknown-command default**:

- Verified default today: an unknown binary (`iwgetid -r`) → `CONFIRM`. Good —
  fail-safe direction (a prompt, not silent execution).
- But: does the DESTRUCTIVE rule set catch every dangerous shape when the model
  is free to compose them? Examples to stress: `dd if=… of=/dev/sda`,
  `mkfs.*`, `> /dev/sda`, `chmod -R 000 /`, `:(){ :|:& };:`, `curl … | bash`
  (also an egress/I1 concern), command substitution `$(…)`, `;`/`&&`/pipes that
  smuggle a destructive tail past a read-looking head, here-docs, `eval`.
- This is the make-or-break audit. **Action: an adversarial pass over
  `permissions.py` (the `audit-duo` skill / `consensus-verification-duo`) that
  tries to find a destructive command the classifier waves through as
  ALLOW/auto.** If found, harden the classifier *first*. The frozen-classifier
  rule (I3) means hardening is additive, not a rewrite.

Position: **the generic tool is only as safe as this audit. Gate the build on
it. Do not ship generic exec on top of an unaudited classifier.**

## 5. Proposal (the design space)

### 5.1 The tool — `command` / `run` (READ-advisory, gate decides for real)

One new tool: `{ command: "<raw string>" }`. It does **not** self-classify; it
hands the string to the existing gate (I3 — caller resolves the gate before
execute), runs via `run_subprocess`, writes the audit record. Identical contract
to every other tool — it is just the one whose "op" is the whole command.

- Curated tools **stay** as typed fast-paths: better arg validation, nicer
  summaries, stable audit shape for common ops. They are not deprecated.
- The generic tool is the **floor**: nothing on the box is unreachable from
  English. It turns the menu from a *ceiling* into a *fast-path*.
- Net safety **improves**: open-ended operations that today escape to the
  ungated `!` path now route *through* the gate + audit instead.

### 5.2 Router fallthrough

Two viable shapes:
- **(a) Explicit tool** the model selects when no curated tool fits. Simple;
  relies on the model choosing it. Pairs with prompt guidance (§5.3).
- **(b) Unknown-tool → generic fallthrough.** Instead of `reask_unknown_tool`
  bouncing the model back to the menu, a model attempt that is really "run this
  command" is *re-homed* onto the generic tool. Risk: turns a genuine
  malformed-call MISS into an execution attempt — must not bypass the gate, and
  must not mask the 0002 §5 re-ask contract for truly garbled output.

Lean **(a) first** (explicit, legible, minimal blast radius on the router's MISS
contract), consider (b) later as ergonomics. Keep the §5 re-ask path intact.

### 5.3 Prompt: curated vs generic

The model needs a rule for *when* to reach for the generic tool. Draft:
"Prefer a specific operation when one fits; use the general command operation
only when no specific one does, and emit the smallest single command that does
the job." This keeps fast-paths primary and the generic tool a deliberate
fallback, not the lazy default. Must pass the I2 filter.

### 5.4 Audit record shape

Curated ops audit `(tool, op, args)`. A free-form command audits the **raw
command string** as the translated command — which is arguably *more* honest
(the audit spine already stores `translated_command`). Decide: do we tag these
records (`source: generic`) so an operator can see which actions came from the
open path vs a typed fast-path? Recommendation: **yes**, cheap and valuable for
trust/forensics.

## 6. RHEL documentation as a knowledge input (offered by the operator)

The operator can supply RHEL documentation. This is directly load-bearing for a
generic tool, on two fronts — and the RAG plumbing already exists
(`core/tools/docs.py` → `retrieve`, the `rag/` index, `docs/decisions/0003`):

1. **Command synthesis quality.** A generic tool is only as good as the model's
   ability to emit a *correct* RHEL/dnf/systemd/SELinux command. RHEL docs
   (man pages, admin guides) in the retrieval index let the model ground a
   free-form command instead of guessing — exactly the Radagon (sysadmin) use
   case. This raises the floor on correctness, which matters *more* once the
   model composes commands freely.
2. **Classifier hardening (§4).** RHEL docs enumerate the dangerous verbs and
   shapes (mkfs, dd, lvremove, pvremove, `dnf remove` of critical pkgs, firewld
   panic, `systemctl mask`, SELinux relabels). They are a source for *test
   corpora* that the §4 adversarial audit runs against the classifier — "every
   destructive command RHEL warns about must not classify ALLOW."

So: **take the RHEL docs.** Best initial use is (a) seed/extend the retrieval
index for command-synthesis grounding, and (b) mine them for a
destructive-command test corpus that gates the §4 audit. (Keep ingestion local —
I1: no egress.)

## 7. Risks & honest unknowns

- **Small-model error rate (Marika 3B).** Free-form commands are more
  error-prone than menu selection. Mitigation: the gate makes the worst case a
  confirm-prompt, not damage; curated fast-paths still handle the common ops;
  RHEL grounding (§6) reduces malformed commands. Still — needs measurement on
  3B, not just 14B.
- **Egress via command (`curl … | bash`).** I1 says no external calls, ever.
  The classifier must treat outbound-network commands as at least CONFIRM, and
  arguably REFUSE for the data-exfil shapes. Part of the §4 audit.
- **Quoting/escaping** when the model's command string hits `run_subprocess`
  (argv vs shell). Today tools build argv vectors; a raw string needs a defined
  parse (shlex) or an explicit, gated shell=True path. Decide deliberately;
  `shell=True` widens the classifier's job (chained/substituted commands).
- **Re-ask contract erosion.** Don't let "unknown tool" fallthrough (§5.2b)
  swallow genuinely garbled output that the 0002 §5 path should re-ask.

## 8. Position

Build the generic gated `command` tool — it is the only thing that makes "Type
in English. Linux does it." true, and it *strengthens* the invariants by pulling
open-ended actions out of the ungated `!` path and through the gate + audit.

**But gate the build on the §4 classifier audit.** The sequence is:
1. Adversarial audit + harden `classify()` over an open command corpus (mine
   RHEL docs for the destructive-shape test set).
2. Ingest RHEL docs into the retrieval index for command-synthesis grounding.
3. Add the `command` tool (explicit-select, §5.1), prompt rule (§5.3), tagged
   audit (§5.4).
4. Measure malformed/incorrect-command rate on **Marika 3B**, not just Radagon.
5. Later: consider unknown-tool→generic fallthrough (§5.2b) for ergonomics.

Next artifact: a phase-plan-architect plan over steps 1–4, with step 1 as a hard
gate before step 3.
