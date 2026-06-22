# Reference Index Build — Reproducible Runbook

**Decision refs:** [0003 — Local Vector Index Backend (FROZEN)](decisions/0003-vector-index.md) |
[0004 — Corpus License Posture](decisions/0004-corpus-license-posture.md) (pending owner gate)

---

## Overview

The reference index is a single `corpus.db` file (sqlite-vec) that backs the
`docs.retrieve` tool. The tool is controlled entirely by the environment variable
`ERDTREE_CORPUS_INDEX` — if unset, retrieval degrades silently to an empty-but-valid
result (I9); if set to a valid `corpus.db`, it returns grounded passages.

Build pipeline (all offline, no network — I1):

```
stage sources  ->  build_corpus()  ->  embed_texts()  ->  build_index()  ->  corpus.db
```

---

## Measured Numbers — Pilot Index (this host, 2026-06-22)

All measurements taken under `.venv/bin/python` (required — see FOOTGUN below).

| Metric | Value |
|--------|-------|
| Total chunks | 5,600 |
| man page chunks (60 pages, sections 1/5/8) | 2,100 |
| Rocky/RHEL doc chunks (132 admin files) | 3,500 |
| On-disk size (corpus.db) | 9.23 MiB |
| Build time (60 man pages + 132 Rocky files) | ~2.5 s |
| p50 query latency — per-call index open (as docs tool does) | 68.8 ms |
| p50 query latency — persistent connection, KNN-only | 29.6 ms |

**Latency note:** The docs tool opens the index per call by design (stateless, I9-safe).
The 68.8 ms p50 is the real end-to-end cost including that open. The 29.6 ms
persistent-connection number (KNN-only, no open overhead) shows the sqlite-vec query
itself on 5,600 chunks is fast; the dominant cost on this development host is the
`sqlite.connect()` + extension load. For reference, the 0003 fixture baseline was
~0.215 ms KNN-only on 12 chunks; the per-query open cost scales with OS file system
overhead, not chunk count. A future persistent-connection optimization can slot in
behind the frozen `retrieve()` boundary if interactive latency requires it.

---

## Projection to Full Coverage

Linear fit from 0003: **fixed overhead ≈ 40 KiB, marginal ≈ 1,159 bytes/chunk** (includes
the 1,024-byte float32 vector at dim=256 plus text/metadata).

Man pages on this host: section 1 = 2,711 | section 5 = 352 | section 8 = 1,308 = **4,371 total**.
Measured yield: **35 chunks/man page** (60 pages → 2,100 chunks).
Rocky docs: 475 English `.md` files, measured yield **26.5 chunks/file** (132 → 3,500).

| Scenario | Man chunks | Rocky chunks | Total chunks | Size (256-d) | Size (384-d st) |
|----------|-----------|--------------|-------------|-------------|-----------------|
| Pilot (60 man, 132 Rocky) | 2,100 | 3,500 | 5,600 | 9.2 MiB | ~14 MiB |
| Full man sections 1+5+8 + admin Rocky (132) | 152,985 | 3,500 | 156,485 | ~172 MiB | ~249 MiB |
| Full man + full Rocky (475) | 152,985 | 12,594 | 165,579 | ~183 MiB | ~264 MiB |

All scenarios are comfortably inside the **3–5 GB SSD budget** from 0003.
The entire doc corpus at full coverage is under 300 MiB even with the production
sentence-transformer embedder (384-d). Budget headroom is substantial.

---

## FOOTGUN: Use the Project Venv

**CRITICAL — the #1 build failure mode:**

```bash
# WRONG — system python3 has NO sqlite_vec; produces no index, no error
python3 -m rag.build_index_prod ...

# RIGHT
/home/aaron/erdtree/.venv/bin/python -m rag.build_index_prod ...
```

System python3 does not have `sqlite_vec` installed. `build_index()` will raise
`RuntimeError("sqlite-vec backend not installed")` if run under the wrong interpreter.
This is not a code bug — re-run under `.venv/bin/python`.

On the production Rocky 9 target, set up a venv equivalently and install from
`rag/requirements.txt` before running the orchestrator.

---

## Stage 1: Stage Rocky Docs (dev host)

The Rocky Linux documentation is CC-BY-SA-4.0 content cloned separately:

```bash
# Clone once (out-of-band; not automated — no scraping, no network at build time)
git clone https://github.com/rocky-linux/documentation /tmp/rocky-docs

# Stage into the durable repo location (excludes *.xx.md translations; idempotent)
/home/aaron/erdtree/.venv/bin/python /home/aaron/erdtree/rag/stage_sources.py \
    --src /tmp/rocky-docs \
    --dest /home/aaron/erdtree/runtime/rag/sources/rocky-docs
```

`runtime/` is gitignored — the CC-BY-SA source tree is not repo-tracked.
Man pages need no staging; they live at `/usr/share/man` on every box.

**On the Rocky 9 target (BRANCH B — firstboot recipe):** the rocky-docs RPM places
content under `/usr/share/doc/rocky-docs/`; point `--src` there. groff is present
on every Rocky install, so man rendering works without extra packages.

---

## Stage 2: Build the Reference Index

```bash
# Dev host (with admin-allowlist Rocky docs, capped man pages)
/home/aaron/erdtree/.venv/bin/python -m rag.build_index_prod \
    --man-dir /usr/share/man \
    --rocky-dir /home/aaron/erdtree/runtime/rag/sources/rocky-docs \
    --output-index /home/aaron/erdtree/runtime/rag/corpus.db \
    --output-jsonl /home/aaron/erdtree/runtime/rag/corpus.jsonl \
    --max-man-pages 60

# Full coverage (uncapped; ~2-5 minutes on a dev box, fully offline)
/home/aaron/erdtree/.venv/bin/python -m rag.build_index_prod \
    --man-dir /usr/share/man \
    --rocky-dir /home/aaron/erdtree/runtime/rag/sources/rocky-docs \
    --output-index /home/aaron/erdtree/runtime/rag/corpus.db \
    --output-jsonl /home/aaron/erdtree/runtime/rag/corpus.jsonl
    # (omit --max-man-pages for uncapped; add --max-rocky-files N to cap Rocky)
```

The orchestrator prints an operator-facing summary on completion:
```
Built reference index: 5600 passages, 9.2 MB.
```

`corpus.db` is overwrite-safe — a re-run with the same inputs produces an identical
chunk count (deterministic chunk IDs; `build_index` unlinks the existing file before
writing).

---

## Stage 3: Wire the Docs Tool

```bash
# Point the docs tool at the index
export ERDTREE_CORPUS_INDEX=/home/aaron/erdtree/runtime/rag/corpus.db
```

Or set in the process environment before launching the agent. The agent reads this
at module load time from `core/tools/docs.py`. On the production target:

```bash
# /etc/erdtree/erdtree.conf  (or systemd unit Environment=)
ERDTREE_CORPUS_INDEX=/var/lib/erdtree/corpus.db
```

**Dev default:** `runtime/rag/corpus.db` (gitignored, produced by Stage 2).
**Target default:** `/var/lib/erdtree/corpus.db` (built at firstboot under BRANCH B).

### Verify the wiring

```python
# In a Python shell, with ERDTREE_CORPUS_INDEX set BEFORE this import
import os
os.environ['ERDTREE_CORPUS_INDEX'] = '/home/aaron/erdtree/runtime/rag/corpus.db'
from core.tools import docs
result = docs._op_retrieve({"query": "how do I open a firewall port"})
print(result)
# Expected: "[Rocky/RHEL docs (guides__security__firewalld-beginners.md)]\n..."
# Summary line: "Retrieved N reference passages."  (N >= 1)
```

### Rollback

```bash
unset ERDTREE_CORPUS_INDEX
# or set it to a nonexistent path — the tool degrades to "Retrieved 0 reference passages."
```

The agent keeps running; it just loses grounded retrieval. The index is a single file;
deleting it is the rollback.

---

## License Posture

See [docs/decisions/0004-corpus-license-posture.md](decisions/0004-corpus-license-posture.md)
(pending owner gate, Phase 4). Two branches are scoped:

**BRANCH A — Bundle-with-attribution:** ship `corpus.db` inside the ISO.
Requires a NOTICE/attribution file crediting Red Hat, Inc. + Rocky Linux contributors
(CC-BY-SA-4.0) and the man-pages project (GPL-2.0). Pro: instant retrieval on
firstboot. Con: ISO carries CC-BY-SA text → share-alike + attribution duties.

**BRANCH B — Recipe-only (firstboot build):** ship the orchestrator + staging recipe;
build `corpus.db` on firstboot from `/usr/share/man` + the rocky-docs content already
present on the installed base. Pro: no CC-BY-SA text in the ISO image itself;
symmetrical with the existing RECIPE_ONLY arch/SO/CVE model. Con: firstboot build
time (pilot: ~2.5 s for 5,600 chunks; full man+Rocky: ~2-5 minutes, still offline).

Man pages (GPL-2.0) are bundleable under either branch.

---

## Production Embedder (DEFERRED-TO-MOSSAD)

The pilot uses the stdlib hashed embedder (`backend="hashed"`, dim=256). It is
offline, zero-dependency, and sufficient for the pilot retrieval quality demonstrated
(firewall query → correct firewalld passage, top result).

The production sentence-transformer embedder (`backend="st"`, dim=384) is
**DEFERRED-TO-MOSSAD** — it requires cached sentence-transformers weights and a GPU
host. The orchestrator is embedder-agnostic: swapping backends needs only two flags:

```bash
/home/aaron/erdtree/.venv/bin/python -m rag.build_index_prod \
    ... \
    --backend st \
    --dim 384
```

No code change. The `embed_backend` and `dim` are recorded in the index `meta` table;
`retrieve()` reads them back and embeds queries with the same backend/dim automatically.
A re-run with `backend=st` rebuilds the index in-place and the docs tool picks it up
on next call.

---

## Chosen Production Caps

| Parameter | Pilot cap | Full-coverage recommendation |
|-----------|-----------|------------------------------|
| `--max-man-pages` | 60 | Omit (uncapped) — all 4,371 sections 1+5+8 fit in ~183 MiB |
| `--max-rocky-files` | None (all 132 staged admin docs) | Omit (uncapped all 475 English) |

**Recommendation:** ship uncapped for both. The full index is ~183 MiB (256-d) or
~264 MiB (384-d) — well inside the 3–5 GB SSD budget. Build time at full coverage
is estimated at 2-5 minutes on a dev box (man rendering is the slow step), acceptable
for a firstboot one-time build under BRANCH B.

---

## Follow-On: Command Synthesis + Classifier Corpus

This index is a prerequisite for two downstream plans:

**1. Generic gated `command` tool** (`lifecycle/brainstorms/generic-command-tool.md`)
The corpus.db built here is the grounding corpus that lets a small local model emit
correct RHEL/dnf/systemd/SELinux commands in response to natural-language requests.
The `docs.retrieve` tool fetches grounded passages before the model synthesizes a
command — without this index, the command tool operates blind.

**2. Classifier adversarial audit corpus** (Phase 6 / D4 — not built here)
The Rocky docs in this index enumerate dangerous operations (mkfs, dd, lvremove,
`firewall-cmd --panic`, `systemctl mask`, SELinux relabels, etc.). These are mined
into a destructive-command test set for the adversarial `classify()` audit that gates
the command tool build. This index is the mining source; the classifier build is the
next plan.

Sequence: **this plan (index built) → classify() adversarial audit (Phase 6) → generic
command tool (new plan after Phase 6 passes).**
