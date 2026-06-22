"""
stage_sources.py — Stage Rocky Linux documentation into a durable, filtered tree.

PURPOSE
-------
Copies English-only, optionally admin-relevant Rocky docs from an ephemeral source
clone into a durable location, so the corpus build is reproducible without hitting
/tmp or the network.

HOW THE SOURCE CLONE IS OBTAINED (reproducing the source without scraping)
--------------------------------------------------------------------------
  Dev host (one-time):
    git clone https://github.com/rocky-linux/documentation /tmp/rocky-docs
    # The docs/ subdirectory contains the Markdown source for docs.rockylinux.org.
    # Licensed CC-BY-SA-4.0 (see /tmp/rocky-docs/LICENSE.md).

  Firstboot / target variant:
    On the installed Rocky Linux base, the rocky-docs RPM places the same
    documentation tree under /usr/share/doc/rocky-docs (or equivalent), so the
    staging helper can be pointed at that path without requiring a git clone:
      python -m rag.stage_sources --src /usr/share/doc/rocky-docs --dest /var/lib/erdtree/rocky-docs

  Either way the helper is pointed at the root of the clone (the directory that
  contains the docs/ subdirectory), not at docs/ itself.

WHAT IT DOES
------------
1. Walks <src>/docs recursively, selecting only *.md files.
2. Drops translation files (regex \\.[a-z][a-z]\\.md$ — e.g. index.fr.md).
3. Optionally intersects an ADMIN_ALLOWLIST of keyword patterns in the file path,
   keeping only guides relevant to network/SELinux/firewall/dnf/systemd/users/
   disk/ssh/services. Full-English mode (all 475 files) is one flag away.
4. Copies each selected file into <dest>/, preserving a minimal path segment
   (guide category / filename) to keep filenames unique across subdirectories.
5. Idempotent: re-running with the same --src and --dest produces an identical
   file set (existing files are overwritten in-place; no stale files accumulate
   on a clean re-run because the dest is purged before copy).

USAGE
-----
  # Admin-relevance filter (default, ~83 files):
  .venv/bin/python -m rag.stage_sources \\
      --src /tmp/rocky-docs \\
      --dest /home/aaron/erdtree/runtime/rag/sources/rocky-docs

  # Full English set (~475 files):
  .venv/bin/python -m rag.stage_sources \\
      --src /tmp/rocky-docs \\
      --dest /home/aaron/erdtree/runtime/rag/sources/rocky-docs \\
      --all-english

DURABLE LOCATIONS
-----------------
  Dev host:  <repo>/runtime/rag/sources/rocky-docs/  (gitignored; CC-BY-SA content)
  Target:    /var/lib/erdtree/rocky-docs/
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Admin-relevance allowlist
# Each pattern is matched (case-insensitive) against the FULL relative path of
# the candidate file within the docs/ tree. A file passes if ANY pattern matches.
# Edit this list to broaden or narrow the admin-relevant pilot set.
# Pass --all-english to bypass it entirely and stage the full English corpus.
# ---------------------------------------------------------------------------
ADMIN_ALLOWLIST: list[str] = [
    r"firewall",
    r"selinux",
    r"network",
    r"dnf",
    r"systemd",
    r"user",
    r"group",
    r"disk",
    r"ssh",
    r"service",
    r"security",
    r"package",
    r"storage",
    r"backup",
    r"cron",
    r"kernel",
    r"nfs",
    r"samba",
    r"fail2ban",
    r"sudo",
    r"permission",
    r"mount",
    r"lvm",
    r"raid",
    r"nginx",
    r"apache",
    r"httpd",
    r"postgresql",
    r"mysql",
    r"mariadb",
    r"rsync",
    r"audit",
    r"log",
    r"journal",
]

# Regex that identifies translation files.
# Covers:  *.xx.md      (e.g. index.fr.md, guide.zh.md)
#          *.xx-YY.md   (e.g. guide.pt-BR.md, doc.zh-CN.md)
_TRANSLATION_RE = re.compile(r'\.[a-z]{2}(-[A-Za-z]{2,4})?\.md$')


def _is_translation(path: Path) -> bool:
    """Return True if path looks like a translated variant (*.xx.md)."""
    return bool(_TRANSLATION_RE.search(path.name))


def _is_admin_relevant(rel_path: str, allowlist: list[str]) -> bool:
    """Return True if rel_path matches any admin-allowlist pattern."""
    lower = rel_path.lower()
    return any(re.search(pat, lower) for pat in allowlist)


def _collect(src_docs: Path, all_english: bool) -> list[tuple[Path, str]]:
    """
    Walk src_docs, apply filters, return a sorted list of (abs_path, unique_name).

    unique_name is built from the relative path within docs/ with path separators
    replaced by '__' so that guides/security/firewalld.md becomes
    guides__security__firewalld.md — unique across the tree and human-readable.
    """
    candidates: list[tuple[Path, str]] = []
    for md_path in sorted(src_docs.rglob("*.md")):
        if _is_translation(md_path):
            continue
        rel = md_path.relative_to(src_docs)
        rel_str = str(rel)
        if not all_english and not _is_admin_relevant(rel_str, ADMIN_ALLOWLIST):
            continue
        unique_name = rel_str.replace("/", "__")
        candidates.append((md_path, unique_name))
    return candidates


def stage(
    src: str | Path,
    dest: str | Path,
    all_english: bool = False,
    verbose: bool = True,
) -> int:
    """
    Stage Rocky docs from src into dest.

    Parameters
    ----------
    src        : Root of the rocky-linux/documentation clone (contains docs/).
    dest       : Durable destination directory. Created if it does not exist.
    all_english: If True, skip the admin allowlist and stage all English .md files.
    verbose    : Print progress summary to stdout.

    Returns
    -------
    Number of files staged.

    Raises
    ------
    SystemExit(1) if the source is missing (with a clear clone instruction).
    """
    src = Path(src)
    dest = Path(dest)

    src_docs = src / "docs"
    if not src_docs.is_dir():
        print(
            f"ERROR: source not found; clone rocky-linux/documentation to {src}\n"
            f"  git clone https://github.com/rocky-linux/documentation {src}",
            file=sys.stderr,
        )
        sys.exit(1)

    candidates = _collect(src_docs, all_english)
    if not candidates:
        print(
            f"ERROR: no English .md files found under {src_docs}. "
            "Check that the clone is complete.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Purge dest before writing so re-runs produce an identical set (idempotent +
    # deterministic: no stale files from a previous wider filter accumulate).
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    staged = 0
    for abs_path, unique_name in candidates:
        shutil.copy2(abs_path, dest / unique_name)
        staged += 1

    if verbose:
        mode = "full English" if all_english else "admin-relevant"
        print(f"Staged {staged} {mode} Rocky docs to {dest}")

    return staged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage Rocky Linux docs from a git clone into a durable filtered tree.",
    )
    parser.add_argument(
        "--src",
        default="/tmp/rocky-docs",
        help="Root of the rocky-linux/documentation clone (default: /tmp/rocky-docs)",
    )
    parser.add_argument(
        "--dest",
        required=True,
        help="Durable destination directory.",
    )
    parser.add_argument(
        "--all-english",
        action="store_true",
        default=False,
        help="Stage all English .md files instead of only admin-relevant ones.",
    )
    args = parser.parse_args()
    stage(src=args.src, dest=args.dest, all_english=args.all_english)


if __name__ == "__main__":
    main()
