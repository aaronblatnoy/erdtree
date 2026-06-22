# rag/LICENSES.md — Per-source redistribution verdict

Maintained alongside ``rag/build_corpus.py``.  Review before bundling any
corpus data in an ISO image (Phase 11 packaging concern; see plan Q3).

## Default Posture

**Ship the firstboot BUILD RECIPE, not the raw corpus.**

The Arch wiki (CC-BY-SA-3.0) and Stack Overflow (CC-BY-SA-4.0) sources carry
share-alike licensing that complicates ISO bundling and imposes per-post
attribution requirements on SO.  The man-page content is redistributable
(GPL-2.0) but the filtered SO subset is uncertain on a per-post basis.  The
safe default for v0.1 is to ship the recipe (``rag/build_corpus.py``) and have
the firstboot helper run it once on the installed system where the source
material already exists locally.

## Per-Source Verdict

| Source | License | Can bundle in ISO? | Notes |
|--------|---------|-------------------|-------|
| man pages (`/usr/share/man`) | GPL-2.0 (man-pages project; varies per page — util-linux GPL-2.0+, kernel docs GPL-2.0) | YES — freely redistributable | Rendered plain text only; groff rendering is our own work |
| Rocky/RHEL docs (`/usr/share/doc`) | CC-BY-SA-4.0 (Red Hat / Rocky Linux) | YES with attribution | Attribution: Red Hat, Inc. and Rocky Linux contributors |
| Arch wiki dump | CC-BY-SA-3.0 (Arch Linux wiki) | RECIPE ONLY for v0.1 | Share-alike; requires attribution; dump not bundled |
| Stack Overflow sysadmin export | CC-BY-SA-4.0 | RECIPE ONLY | Per-post attribution required; URL recorded in `source` field |
| CVE summaries (NVD) | Public domain (NIST / NVD) | YES | NVD data is US government work, not subject to copyright |

## Index Bundling Note

The built vector index (a sqlite-vec `.db` file) contains the chunk TEXT
extracted from these sources.  Bundling the index in an ISO is equivalent to
bundling the corpus text.  The same per-source verdict applies to the index.

For v0.1: bundle the index ONLY for sources cleared above (man pages + RHEL
docs + CVE); ship a firstboot recipe to rebuild from Arch wiki + SO.

## Full Corpus Embed: DEFERRED-TO-MOSSAD

Running ``build_corpus.py`` over all source trees and then embedding the
resulting millions of chunks (``rag/embed.py`` backend="st") requires the
mossad GPU host and the source corpora.  This step is environment-blocked on
the dev host.  See plan §13 D2.

What ships on the dev host (and in the v0.1 ISO):
  * ``rag/build_corpus.py`` — the recipe (this file covers its licensing).
  * ``rag/fixtures/corpus.jsonl`` — a hand-curated 12-chunk subset (GPL-2.0 /
    CC-BY-SA-4.0 / LGPL-2.1 / BSD; all redistributable; see chunk ``license``
    fields).
  * ``rag/fixtures/mini_index.db`` — the prebuilt sqlite-vec index over the
    fixture corpus (same license as the fixture corpus).

## Firstboot Recipe

```sh
# Run once after installation to populate the full corpus.
# Pre-download Arch wiki dump and SO export to:
#   /var/lib/erdtree/arch-wiki-dump/
#   /var/lib/erdtree/so-sysadmin/
python3 /opt/erdtree/rag/build_corpus.py \
    --man-dir /usr/share/man \
    --rhel-dir /usr/share/doc \
    --arch-dir /var/lib/erdtree/arch-wiki-dump \
    --so-dir  /var/lib/erdtree/so-sysadmin \
    --cve-dir /var/lib/erdtree/cve-corpus \
    --output  /var/lib/erdtree/corpus.jsonl

python3 /opt/erdtree/rag/embed.py \
    --backend st \
    --model   all-MiniLM-L6-v2 \
    --input   /var/lib/erdtree/corpus.jsonl \
    --output  /var/lib/erdtree/corpus_index.db
```

See ``rag/build_corpus.py`` for full parameter documentation.
