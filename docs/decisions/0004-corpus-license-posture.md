# 0004 — Corpus License Posture (SHIP: bundle vs recipe)

- Status: **DRAFT — AWAITING OWNER APPROVAL** (NOT accepted)
- Date drafted: 2026-06-22
- Owner decision: ________________________ (pending)
- Phase: RAG production ingest orchestrator, Phase 4 (the license-posture GATE)
- Decides: plan §0 SC4 / §10 Q1 — how the grounded-lookup index reaches the
  installed machine: **shipped inside the ISO (Branch A)** or **built once on
  firstboot from sources already on the box (Branch B)**.
- Cross-links: **docs/decisions/0003-vector-index.md** (the FROZEN index/engine
  contract — sqlite-vec single `.db`, `retrieve()` signature, on-disk format).
  This decision is ADDITIVE and does NOT edit 0003.
- Scope of the gate: **only the CC-BY-SA-4.0 Rocky/RHEL docs and the index that
  embeds their text.** man pages (GPL-2.0) are bundleable under EITHER branch
  (see below). Arch wiki / Stack Overflow / CVE remain RECIPE_ONLY and out of
  pilot scope — they are not part of this gate.

---

## Why there is a gate at all

The production index is a single sqlite-vec `.db` (per 0003). It stores not just
vectors but the **chunk text itself** (the `chunks` table). For the pilot that
text is two sources:

- **man pages** rendered to plain text from `/usr/share/man` (GPL-2.0; the
  man-pages project. Our groff rendering is our own work, but the underlying
  page text is GPL-2.0).
- **Rocky/RHEL docs** from the rocky-docs content under `/usr/share/doc`
  (CC-BY-SA-4.0 — Red Hat, Inc. and Rocky Linux contributors).

Bundling the `.db` inside the ISO is therefore **a redistribution of that source
text** (rag/LICENSES.md already states this). GPL-2.0 man text is freely
redistributable. The **CC-BY-SA-4.0 Rocky text is the load-bearing question**:
share-alike + attribution duties attach to redistributing it. That is the only
thing this gate decides.

### Pilot facts the owner is deciding against (measured, Phase 2)

- Pilot index: **5,600 passages, 9.2 MB** on disk (hashed embedder, dim 256).
- Per-source split: man = 4,924 chunks, Rocky docs = 676 chunks.
- Build is fully **offline** (I1) and **deterministic** (stable chunk_ids).
- Pilot build time: ~1 s for this capped set (full uncapped man set is minutes,
  still offline — see 0003 projection / Phase 5).
- The production 384-d st-embedder build is DEFERRED-TO-MOSSAD; it does not
  change the license posture (more bytes, same source text, same verdict).

---

## BRANCH A — Bundle-the-index-with-attribution

**Ship `corpus.db` inside the ISO image.** Grounded lookup is live the instant
the system boots; the user's box never runs a build step.

What this REQUIRES (mechanical, if the owner picks A):

1. A **NOTICE / attribution file** shipped alongside the index, crediting:
   - **Red Hat, Inc. and the Rocky Linux contributors** for the Rocky/RHEL docs
     content, under **CC-BY-SA-4.0**, with a link to the license text and a
     statement that the index contains adapted/extracted excerpts.
   - **The man-pages project** for the man content, under **GPL-2.0**.
2. **Share-alike compliance** for the CC-BY-SA-4.0 portion: the redistributed
   excerpts (and adaptations thereof, i.e. the embedded chunk text) carry the
   same-or-compatible license forward; the NOTICE makes the license and
   attribution available to the recipient.
3. The packaging hook (downstream — Phase 11 / parent plan) places `corpus.db`
   plus the NOTICE file into the ISO payload and points `ERDTREE_CORPUS_INDEX`
   at the installed path. **0004 records the posture; it does not build the ISO.**

**Pro**

- Instant grounded lookup on firstboot — zero build step on the user's machine,
  no firstboot latency, no dependency on the source trees being present.
- Reproducible, audited artifact: the exact index we measured is the one that
  ships.

**Con**

- The ISO image itself **carries CC-BY-SA-4.0 text**, so share-alike +
  attribution duties travel with every ISO we distribute.
- The index **grows the ISO** (pilot 9.2 MB; full-coverage projection per 0003
  scales with chunk count — still inside the ~3–5 GB SSD budget but non-trivial
  image weight).
- Asymmetric with the existing RECIPE_ONLY sources (Arch/SO), which are
  deliberately NOT bundled — Branch A treats Rocky docs differently from the
  other share-alike source.

---

## BRANCH B — Recipe-only (firstboot build) — RECOMMENDED

**Ship the orchestrator + the staging recipe, NOT the `.db`.** Build
`corpus.db` **once on firstboot** from sources already present on the installed
Rocky base:

- `/usr/share/man` — present on the base; rendered with **groff** (present on
  the Rocky base).
- the **rocky-docs RPM** content under `/usr/share/doc` — present on the base.

This **mirrors the existing RECIPE_ONLY model** already used for Arch wiki +
Stack Overflow: ship the recipe, build locally from material that already lives
on the machine.

What this REQUIRES (mechanical, if the owner picks B):

1. Ship `rag/build_index_prod.py` (the orchestrator) + `rag/stage_sources.py`
   (the staging recipe) in the image — **code, not corpus text**.
2. A **firstboot unit** that runs the orchestrator once against `/usr/share/man`
   + `/usr/share/doc`, writes `corpus.db` to a durable path (e.g.
   `/var/lib/erdtree/corpus.db`), and points `ERDTREE_CORPUS_INDEX` at it.
3. Confirm firstboot prerequisites are on the base: **groff** (man rendering),
   the **rocky-docs** content under `/usr/share/doc`, and the `.venv`/sqlite-vec
   backend the orchestrator needs (packaging concern — Phase 11).

**Pro**

- **No CC-BY-SA-4.0 text in the ISO image itself** — the share-alike Rocky text
  is only ever materialized on the user's own installed machine from content
  Red Hat/Rocky already placed there. The redistribution-of-source-text duty
  that drives Branch A's NOTICE obligation does not attach to our image.
- **Symmetrical** with the existing RECIPE_ONLY sources (Arch/SO) — one
  consistent posture for all share-alike content.
- **Self-contained + offline (I1-clean):** the build reads only local
  `/usr/share/man` + `/usr/share/doc`; it opens no socket. Nothing is fetched.
- Image stays lean (no index payload).

**Con**

- **Firstboot build time.** Bounded — pilot is ~1 s for ~1.6k-style capped runs;
  the full uncapped man set is **minutes** (offline). First grounded lookup
  waits on that one-time build (or it runs in the background post-install).
- Depends on **groff** + the **rocky-docs** content being present at firstboot
  (both ship on the Rocky base — verify in the Phase 11 packaging step).

---

## man pages note (applies to BOTH branches)

man-page content is **GPL-2.0** and **freely redistributable**. It is bundleable
under EITHER branch — bundling the man portion of the index is not the gated
question. The gate is exclusively about the **CC-BY-SA-4.0 Rocky/RHEL docs** and
the index that embeds their text. (Per-post Stack Overflow attribution is NOT in
scope — SO is RECIPE_ONLY and out of the pilot.)

---

## Recommendation — lean **BRANCH B (recipe-only firstboot build)**

Rationale (one line): **B keeps the CC-BY-SA-4.0 share-alike text out of the ISO
image, is symmetrical with the existing arch/SO RECIPE_ONLY model, and is
self-contained + offline because the Rocky base already ships `/usr/share/doc`
+ groff — so the firstboot build needs nothing the box doesn't already have.**

The single real cost is a bounded, one-time, offline firstboot build (seconds to
minutes). Against that, B removes the share-alike + attribution redistribution
duties from every ISO we ship and avoids a second, inconsistent treatment of
share-alike content. Branch A is the right call **only if** instant-on-firstboot
grounded lookup is judged worth carrying CC-BY-SA text (and its NOTICE +
share-alike duties) in the image and accepting the index's contribution to ISO
size.

**This is the owner's call.** This document is a draft and a recommendation; it
is NOT accepted and the posture is NOT resolved until the owner records a
decision below.

---

## Decision

- **Status: DRAFT — AWAITING OWNER APPROVAL** (NOT ACCEPTED)
- **Owner decision: ____ (pending)** — owner selects **A** (bundle-with-
  attribution) or **B** (recipe-only firstboot); record the choice + date here.
- On acceptance, the chosen branch is mechanical to execute:
  - **If A:** add the NOTICE/attribution file + packaging hook (Phase 11);
    flip the rag/LICENSES.md "Index Bundling Note" to the bundle-with-NOTICE
    wording.
  - **If B:** wire the firstboot orchestrator unit (Phase 11); the
    rag/LICENSES.md "Index Bundling Note" already reflects the recipe posture.
- 0003 (the FROZEN index/engine contract) is **unaffected and unedited** by
  either outcome — this gate is about the SHIP posture, not the engine.

## Where the owner reviews / finalizes

This file (`docs/decisions/0004-corpus-license-posture.md`). To finalize: fill
in the "Owner decision" line with A or B + date, change Status to ACCEPTED, and
flip the single posture paragraph in `rag/LICENSES.md` "Index Bundling Note" to
match (a one-line edit either way — the rest of the manifest is already correct).
