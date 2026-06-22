"""rag/build_corpus.py — corpus assembly + chunking recipe.

PURPOSE
-------
Assembles a normalised, chunked corpus from local Linux documentation sources
and emits:
  * A JSONL file of :class:`RawChunk` records (one JSON object per line).
  * A per-source license manifest written alongside the output JSONL.

DEFAULT POSTURE (Q3 resolution from the plan):
  Ship the BUILD RECIPE, not the raw corpus.  The Arch wiki and Stack Overflow
  sources carry copy-left / SA licensing that complicates ISO bundling; the
  man-page content is GPL-2.0 (freely redistributable) but the filtered SO
  subset is uncertain.  The recipe is what ships; a firstboot helper runs it
  once on the target box where the corpora already exist on the local filesystem.
  See ``rag/LICENSES.md`` for the per-source verdict.

SOURCES (in priority order — licensed for redistribution + locally available)
-------
  1. Local man pages   /usr/share/man/**/*.gz   GPL-2.0 (man-pages project)
                       Rendered to plain text via groff; filtered to sections
                       1, 5, 8 (commands, config files, sysadmin).
  2. Rocky/RHEL docs   /usr/share/doc/**        CC-BY-SA-4.0 per upstream.
                       Recursively collected *.txt / *.rst / *.md files.
  3. Arch wiki dump    /var/lib/erdtree/arch-wiki-dump/  CC-BY-SA-3.0.
                       Pre-downloaded offline XML dump, parsed to article text.
                       Ship the recipe only (firstboot); do NOT bundle raw dump.
  4. Stack Overflow    /var/lib/erdtree/so-sysadmin/    CC-BY-SA-4.0.
                       Filtered Q+A export (sysadmin/linux tags, score>=5).
                       Ship the recipe only (firstboot); licensing must be
                       evaluated per-post; the recipe records attribution.
  5. CVE summaries     /var/lib/erdtree/cve-corpus/     public domain / NVD.
                       NVD JSON feed, filtered to Linux + sysadmin CVEs.

CHUNK CONTRACT
--------------
Every chunk emitted is a ``RawChunk`` with these fields (I2-clean):

    chunk_id : str   stable unique id (source:section:offset, URL-safe)
    source   : str   human provenance ("man:mount(8)", "Rocky/RHEL docs", …)
    license  : str   SPDX expression or short label
    text     : str   normalised plain text, ~100–600 chars, no leading/trailing WS

The chunk text MUST NOT contain any of the I2-forbidden terms in user-visible
positions (the canonical list is core.agent.prompt._FORBIDDEN_AI_TERMS).  The
chunker strips troff/ANSI escapes so raw man-page markup does not leak through.

FULL CORPUS EMBED: DEFERRED-TO-MOSSAD
--------------------------------------
Running build_corpus() over the full source trees produces O(millions) of chunks
that are then embedded (rag/embed.py backend="st") on the mossad GPU host.  That
step is environment-blocked on this dev host.  See plan §13 D2.

WHAT RUNS ON THIS HOST
-----------------------
  * The fixture corpus (rag/fixtures/corpus.jsonl + mini_index.db) is the
    offline-testable subset — it is hand-curated, not the output of this module.
  * ``build_corpus(man_dirs=[...], max_pages=N)`` with a tiny N (e.g. 20) runs
    on this host for integration smoke-tests and produces a mini JSONL; the
    resulting chunks are then indexed via rag/index.py for test_rag_index.py.
  * The unit tests (tests/test_rag_index.py) call ``build_corpus`` in smoke-test
    mode (max_pages=5) so that the full index-build pipeline is exercised offline
    without GPU or large data.

No network is opened at any point in this module (I1).  No AI/LLM/model/agent
language appears in any user-facing string (I2).
"""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Chunk schema
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawChunk:
    """One normalised corpus chunk.  Maps 1-to-1 to ``rag.index.CorpusChunk``."""

    chunk_id: str   # stable, URL-safe id
    source: str     # human provenance label (I2-clean)
    license: str    # SPDX expression
    text: str       # plain text, ~100–600 chars


# ---------------------------------------------------------------------------
# Per-source license manifest
# ---------------------------------------------------------------------------

SOURCE_LICENSES: dict[str, str] = {
    "man":      "GPL-2.0 (man-pages project / util-linux / kernel; varies per page)",
    "rhel":     "CC-BY-SA-4.0 (Red Hat / Rocky Linux documentation)",
    "arch":     "CC-BY-SA-3.0 (Arch Linux wiki; firstboot recipe only — do NOT bundle)",
    "so":       "CC-BY-SA-4.0 (Stack Overflow; firstboot recipe only — per-post attribution required)",
    "cve":      "Public domain (NVD / NIST CVE database)",
}

#: Default posture: sources where we ship the recipe, not the raw data.
RECIPE_ONLY_SOURCES: frozenset[str] = frozenset({"arch", "so"})

# ---------------------------------------------------------------------------
# Text cleanup helpers
# ---------------------------------------------------------------------------

# Strip troff sequences produced by groff -mandoc -Tascii (bold/underline).
_TROFF_RE = re.compile(r"\x1b\[[0-9;]*m|\x08.")
# Strip residual backspace-overstrikes from raw nroff output.
_BS_RE = re.compile(r".\x08")
# Collapse runs of whitespace (but preserve single newlines).
_WS_RE = re.compile(r"[ \t]+")
# Drop lines that are pure whitespace or pagination artifacts.
_BLANK_RE = re.compile(r"^\s*$")


def _clean_man_text(raw: str) -> str:
    """Strip troff/ANSI markup and collapse whitespace from a rendered man page."""
    text = _TROFF_RE.sub("", raw)
    text = _BS_RE.sub("", text)
    lines = [_WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    # Drop pagination headers/footers (short lines with page numbers).
    lines = [ln for ln in lines if ln and not re.match(r"^[A-Z()0-9 _.-]{3,60}\s+\d+\s*$", ln)]
    return "\n".join(lines)


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Sliding-window word-boundary chunker.

    Splits ``text`` into overlapping chunks of approximately ``chunk_size``
    characters with ``overlap`` characters of context carry-forward.  Each
    chunk is stripped and guaranteed non-empty.
    """
    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0
    for w in words:
        wl = len(w) + 1  # +1 for space
        if buf_len + wl > chunk_size and buf:
            chunk = " ".join(buf).strip()
            if chunk:
                chunks.append(chunk)
            # Carry the last overlap chars forward as context.
            carried: List[str] = []
            carried_len = 0
            for token in reversed(buf):
                tl = len(token) + 1
                if carried_len + tl > overlap:
                    break
                carried.insert(0, token)
                carried_len += tl
            buf = carried
            buf_len = carried_len
        buf.append(w)
        buf_len += wl
    if buf:
        chunk = " ".join(buf).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _stable_id(prefix: str, content: str) -> str:
    """Deterministic, URL-safe chunk id: ``prefix`` + blake2b(content)[0:8]."""
    digest = hashlib.blake2b(content.encode("utf-8"), digest_size=4).hexdigest()
    safe_prefix = re.sub(r"[^a-zA-Z0-9_.-]", "_", prefix)
    return f"{safe_prefix}-{digest}"


# ---------------------------------------------------------------------------
# Man-page source
# ---------------------------------------------------------------------------

#: Man sections that are relevant for sysadmin corpus.
MAN_SECTIONS: frozenset[str] = frozenset({"1", "5", "8"})

#: Groff command to render nroff source as plain ASCII.
_GROFF_CMD = ["groff", "-mandoc", "-Tascii"]


def _render_man_gz(path: Path) -> Optional[str]:
    """Render a gzip-compressed man page to plain text.  Returns None on error."""
    try:
        with gzip.open(path, "rb") as fh:
            nroff_src = fh.read()
    except Exception:
        return None
    try:
        proc = subprocess.run(
            _GROFF_CMD,
            input=nroff_src,
            capture_output=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.decode("ascii", errors="replace")
    except Exception:
        return None


def _section_from_path(path: Path) -> str:
    """Extract the man section digit from the path, e.g. 'man8' -> '8'."""
    parent = path.parent.name  # e.g. 'man8', 'man1'
    m = re.match(r"man(\d+)", parent)
    return m.group(1) if m else ""


def iter_man_chunks(
    man_dirs: Sequence[str | Path],
    max_pages: Optional[int] = None,
) -> Iterator[RawChunk]:
    """Yield :class:`RawChunk` records from man pages in ``man_dirs``.

    Parameters
    ----------
    man_dirs:
        Directories to search (typically ``/usr/share/man`` plus extras).
    max_pages:
        If set, stop after rendering this many pages (smoke-test / fixture mode).

    Renders each ``*.gz`` man file via groff to plain ASCII, cleans and chunks
    the text, and emits one :class:`RawChunk` per chunk.  Opens no network
    socket (I1).
    """
    rendered = 0
    for raw_dir in man_dirs:
        base = Path(raw_dir)
        if not base.exists():
            continue
        for section_dir in sorted(base.iterdir()):
            if not section_dir.is_dir():
                continue
            # section_dir.name is e.g. 'man1', 'man8'; extract the digit directly.
            m = re.match(r"man(\d+)$", section_dir.name)
            sec = m.group(1) if m else ""
            if sec not in MAN_SECTIONS:
                continue
            for gz_file in sorted(section_dir.glob("*.gz")):
                if max_pages is not None and rendered >= max_pages:
                    return
                plain = _render_man_gz(gz_file)
                if not plain:
                    continue
                rendered += 1
                clean = _clean_man_text(plain)
                if len(clean) < 80:
                    continue
                # Name for the source label: strip the trailing .gz, e.g. mount.8
                name = gz_file.stem  # e.g. 'mount.8'
                source_label = f"man:{name}"
                license_label = SOURCE_LICENSES["man"]
                for chunk_text in _chunk_text(clean):
                    if len(chunk_text) < 60:
                        continue
                    cid = _stable_id(f"man-{name}", chunk_text)
                    yield RawChunk(
                        chunk_id=cid,
                        source=source_label,
                        license=license_label,
                        text=chunk_text,
                    )


# ---------------------------------------------------------------------------
# Rocky/RHEL docs source
# ---------------------------------------------------------------------------


def iter_rhel_chunks(
    doc_dirs: Sequence[str | Path],
    max_files: Optional[int] = None,
) -> Iterator[RawChunk]:
    """Yield :class:`RawChunk` records from Rocky/RHEL documentation files.

    Scans ``doc_dirs`` for ``*.txt``, ``*.rst``, and ``*.md`` files and chunks
    them into corpus passages.  Opens no network socket (I1).
    """
    seen = 0
    for raw_dir in doc_dirs:
        base = Path(raw_dir)
        if not base.exists():
            continue
        for ext in ("*.txt", "*.rst", "*.md"):
            for doc_file in sorted(base.rglob(ext)):
                if max_files is not None and seen >= max_files:
                    return
                try:
                    text = doc_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                text = text.strip()
                if len(text) < 80:
                    continue
                seen += 1
                source_label = f"Rocky/RHEL docs ({doc_file.name})"
                for chunk_text in _chunk_text(text):
                    if len(chunk_text) < 60:
                        continue
                    cid = _stable_id(f"rhel-{doc_file.stem}", chunk_text)
                    yield RawChunk(
                        chunk_id=cid,
                        source=source_label,
                        license=SOURCE_LICENSES["rhel"],
                        text=chunk_text,
                    )


# ---------------------------------------------------------------------------
# Arch wiki source (recipe-only)
# ---------------------------------------------------------------------------


def iter_arch_wiki_chunks(
    dump_dir: str | Path,
    max_articles: Optional[int] = None,
) -> Iterator[RawChunk]:
    """Yield :class:`RawChunk` records from a locally downloaded Arch wiki dump.

    RECIPE ONLY.  The Arch wiki XML dump is not bundled in the ISO; run this
    on a firstboot where the dump has been downloaded to ``dump_dir``.  The
    dump carries CC-BY-SA-3.0.

    Parses ``.txt`` article export files (one article per file, wiki-markup
    stripped).
    """
    base = Path(dump_dir)
    if not base.exists():
        return
    count = 0
    for txt_file in sorted(base.rglob("*.txt")):
        if max_articles is not None and count >= max_articles:
            return
        try:
            text = txt_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        # Strip MediaWiki markup (simple heuristic: drop lines starting with {|, |, !).
        lines = [
            ln for ln in text.splitlines()
            if not re.match(r"^(\{\||\||\!|Category:|#REDIRECT)", ln.strip())
        ]
        text = "\n".join(lines).strip()
        if len(text) < 80:
            continue
        count += 1
        article_name = txt_file.stem
        source_label = f"Arch wiki: {article_name}"
        for chunk_text in _chunk_text(text):
            if len(chunk_text) < 60:
                continue
            cid = _stable_id(f"arch-{article_name}", chunk_text)
            yield RawChunk(
                chunk_id=cid,
                source=source_label,
                license=SOURCE_LICENSES["arch"],
                text=chunk_text,
            )


# ---------------------------------------------------------------------------
# Stack Overflow source (recipe-only, license-gated)
# ---------------------------------------------------------------------------


def iter_so_chunks(
    so_dir: str | Path,
    max_posts: Optional[int] = None,
) -> Iterator[RawChunk]:
    """Yield :class:`RawChunk` records from a filtered Stack Overflow export.

    RECIPE ONLY.  SO posts are CC-BY-SA-4.0; per-post attribution is required
    (source URL recorded in ``source``).  Assumes a pre-filtered export at
    ``so_dir`` with one ``.txt`` file per post (post_id + attribution in the
    first line).

    Only posts with score >= 5 should be included; the filter is applied
    upstream when building the export (not enforced here).
    """
    base = Path(so_dir)
    if not base.exists():
        return
    count = 0
    for txt_file in sorted(base.rglob("*.txt")):
        if max_posts is not None and count >= max_posts:
            return
        try:
            text = txt_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        # First line: attribution URL or post ID.
        source_label = lines[0].strip() if lines else f"Stack Overflow ({txt_file.stem})"
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else text.strip()
        if len(body) < 80:
            continue
        count += 1
        for chunk_text in _chunk_text(body):
            if len(chunk_text) < 60:
                continue
            cid = _stable_id(f"so-{txt_file.stem}", chunk_text)
            yield RawChunk(
                chunk_id=cid,
                source=source_label,
                license=SOURCE_LICENSES["so"],
                text=chunk_text,
            )


# ---------------------------------------------------------------------------
# CVE summaries source
# ---------------------------------------------------------------------------


def iter_cve_chunks(
    cve_dir: str | Path,
    max_files: Optional[int] = None,
) -> Iterator[RawChunk]:
    """Yield :class:`RawChunk` records from NVD CVE summary files.

    Assumes ``cve_dir`` contains ``.txt`` files, one per CVE, with the CVE ID
    on the first line and the summary text following.  NVD data is public domain.
    """
    base = Path(cve_dir)
    if not base.exists():
        return
    count = 0
    for txt_file in sorted(base.rglob("CVE-*.txt")):
        if max_files is not None and count >= max_files:
            return
        try:
            text = txt_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        text = text.strip()
        if len(text) < 60:
            continue
        count += 1
        cve_id = txt_file.stem  # e.g. 'CVE-2024-1234'
        source_label = f"CVE: {cve_id} (NVD)"
        for chunk_text in _chunk_text(text):
            if len(chunk_text) < 60:
                continue
            cid = _stable_id(f"cve-{cve_id}", chunk_text)
            yield RawChunk(
                chunk_id=cid,
                source=source_label,
                license=SOURCE_LICENSES["cve"],
                text=chunk_text,
            )


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------


def build_corpus(
    *,
    man_dirs: Sequence[str | Path] = ("/usr/share/man",),
    rhel_doc_dirs: Sequence[str | Path] = ("/usr/share/doc",),
    arch_wiki_dir: str | Path = "/var/lib/erdtree/arch-wiki-dump",
    so_dir: str | Path = "/var/lib/erdtree/so-sysadmin",
    cve_dir: str | Path = "/var/lib/erdtree/cve-corpus",
    output_jsonl: str | Path = "/var/lib/erdtree/corpus.jsonl",
    max_man_pages: Optional[int] = None,
    max_rhel_files: Optional[int] = None,
    max_arch_articles: Optional[int] = None,
    max_so_posts: Optional[int] = None,
    max_cve_files: Optional[int] = None,
) -> List[RawChunk]:
    """Assemble the full corpus from all configured sources and emit a JSONL.

    DEFERRED-TO-MOSSAD for the full run (D2 in the plan).  On this dev host,
    call with ``max_man_pages=N`` for a smoke-test run (N <= 20 is fast).

    Parameters
    ----------
    man_dirs, rhel_doc_dirs, arch_wiki_dir, so_dir, cve_dir:
        Source directories.  Missing directories are silently skipped.
    output_jsonl:
        Destination file for the emitted JSONL chunks.
    max_*:
        Per-source page/file caps for smoke-test / fixture mode.  None = no cap
        (full corpus run).

    Returns
    -------
    list[RawChunk]
        All chunks emitted (in-memory; for large runs use the JSONL directly).

    Notes
    -----
    No network is opened (I1).  arch/ and so/ sources print a recipe-only
    reminder to stderr when their directories are absent (the caller should note
    these need firstboot population).
    """
    import json

    out_path = Path(output_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_chunks: List[RawChunk] = []

    def _emit(chunk: RawChunk) -> None:
        all_chunks.append(chunk)

    # Source 1: man pages (GPL-2.0, always available on target).
    for c in iter_man_chunks(man_dirs, max_pages=max_man_pages):
        _emit(c)

    # Source 2: Rocky/RHEL docs (CC-BY-SA-4.0).
    for c in iter_rhel_chunks(rhel_doc_dirs, max_files=max_rhel_files):
        _emit(c)

    # Source 3: Arch wiki (recipe only; firstboot).
    if not Path(arch_wiki_dir).exists():
        print(
            f"[build_corpus] Arch wiki dump not found at {arch_wiki_dir}; "
            "run the firstboot recipe to populate it.",
            file=sys.stderr,
        )
    for c in iter_arch_wiki_chunks(arch_wiki_dir, max_articles=max_arch_articles):
        _emit(c)

    # Source 4: Stack Overflow (recipe only; firstboot).
    if not Path(so_dir).exists():
        print(
            f"[build_corpus] Stack Overflow corpus not found at {so_dir}; "
            "run the firstboot recipe to populate it.",
            file=sys.stderr,
        )
    for c in iter_so_chunks(so_dir, max_posts=max_so_posts):
        _emit(c)

    # Source 5: CVE summaries (public domain).
    for c in iter_cve_chunks(cve_dir, max_files=max_cve_files):
        _emit(c)

    # Write output JSONL.
    with out_path.open("w", encoding="utf-8") as fh:
        for chunk in all_chunks:
            fh.write(
                json.dumps(
                    {
                        "chunk_id": chunk.chunk_id,
                        "source": chunk.source,
                        "license": chunk.license,
                        "text": chunk.text,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    return all_chunks


# ---------------------------------------------------------------------------
# License manifest emitter
# ---------------------------------------------------------------------------


def write_license_manifest(output_path: str | Path = "rag/LICENSES.md") -> None:
    """Write the per-source redistribution verdict to ``output_path``.

    This is called by the corpus-build pipeline to keep the manifest in sync
    with the actual sources used.
    """
    manifest = Path(output_path)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(_LICENSE_MANIFEST_TEXT, encoding="utf-8")


_LICENSE_MANIFEST_TEXT = """\
# rag/LICENSES.md — Per-source redistribution verdict

Generated by ``rag/build_corpus.py``.  Review before bundling any corpus data
in an ISO image (that is a Phase 11 packaging concern; see plan Q3).

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
| man pages (`/usr/share/man`) | GPL-2.0 (man-pages project; varies per page — util-linux uses GPL-2.0+, kernel docs use GPL-2.0) | YES — freely redistributable | Rendered plain text only; groff rendering is our own work |
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

## Firstboot Recipe (placeholder)

```
# Run once after installation to populate the full corpus from local sources.
# Arch wiki dump and SO export must be pre-downloaded to:
#   /var/lib/erdtree/arch-wiki-dump/
#   /var/lib/erdtree/so-sysadmin/
python3 /opt/erdtree/rag/build_corpus.py
python3 /opt/erdtree/rag/embed.py --backend st --model all-MiniLM-L6-v2 \\
        --input /var/lib/erdtree/corpus.jsonl \\
        --output /var/lib/erdtree/corpus_index.db
```

See ``rag/build_corpus.py`` for full parameter documentation.
"""


# ---------------------------------------------------------------------------
# CLI entry point (smoke-test / firstboot)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Assemble corpus from local documentation sources.",
    )
    parser.add_argument("--man-dir", default="/usr/share/man", help="Man pages root")
    parser.add_argument("--rhel-dir", default="/usr/share/doc", help="RHEL/Rocky docs root")
    parser.add_argument("--arch-dir", default="/var/lib/erdtree/arch-wiki-dump")
    parser.add_argument("--so-dir", default="/var/lib/erdtree/so-sysadmin")
    parser.add_argument("--cve-dir", default="/var/lib/erdtree/cve-corpus")
    parser.add_argument("--output", default="/var/lib/erdtree/corpus.jsonl")
    parser.add_argument("--max-man-pages", type=int, default=None, help="Cap for smoke-test")
    parser.add_argument("--max-rhel-files", type=int, default=None)
    parser.add_argument("--write-licenses", action="store_true", help="(Re)write rag/LICENSES.md")
    args = parser.parse_args()

    if args.write_licenses:
        write_license_manifest()
        print("wrote rag/LICENSES.md")

    chunks = build_corpus(
        man_dirs=[args.man_dir],
        rhel_doc_dirs=[args.rhel_dir],
        arch_wiki_dir=args.arch_dir,
        so_dir=args.so_dir,
        cve_dir=args.cve_dir,
        output_jsonl=args.output,
        max_man_pages=args.max_man_pages,
        max_rhel_files=args.max_rhel_files,
    )
    print(f"emitted {len(chunks)} chunks -> {args.output}")
