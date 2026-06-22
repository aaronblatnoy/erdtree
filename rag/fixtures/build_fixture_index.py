"""Build the tiny fixture index from rag/fixtures/corpus.jsonl, fully offline.

Run: python3 -m rag.fixtures.build_fixture_index
Produces rag/fixtures/mini_index.db so test_rag_retrieve runs with no GPU and
no network. Uses the pure-stdlib hashed embedder (rag.embed backend="hashed").
"""

from __future__ import annotations

import json
from pathlib import Path

from rag import embed as _embed
from rag import index as _index

FIXTURE_DIR = Path(__file__).resolve().parent
CORPUS = FIXTURE_DIR / "corpus.jsonl"
INDEX = FIXTURE_DIR / "mini_index.db"


def load_corpus() -> list[_index.CorpusChunk]:
    chunks: list[_index.CorpusChunk] = []
    with CORPUS.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            chunks.append(
                _index.CorpusChunk(
                    chunk_id=rec["chunk_id"],
                    source=rec["source"],
                    license=rec["license"],
                    text=rec["text"],
                )
            )
    return chunks


def build() -> Path:
    chunks = load_corpus()
    vectors = _embed.embed_texts(
        [c.text for c in chunks], backend="hashed", dim=_embed.DEFAULT_DIM
    )
    _index.build_index(
        INDEX,
        chunks,
        vectors,
        dim=_embed.DEFAULT_DIM,
        embed_backend="hashed",
        embed_model="",
    )
    return INDEX


if __name__ == "__main__":
    path = build()
    print(f"built fixture index: {path} ({path.stat().st_size} bytes)")
