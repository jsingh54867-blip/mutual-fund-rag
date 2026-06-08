from __future__ import annotations

"""Stage E: Embedding Generation (incremental).

Reads chunk JSONL files from CHUNKS_DIR, skips chunks whose content_hash
has not changed since last run (tracked in embed_state.json), embeds the
rest using BAAI/bge-large-en-v1.5, and writes EmbeddingRecord JSONL files
to EMBEDDINGS_DIR.
"""

import argparse
import json
from pathlib import Path

from .config import (
    CHUNKS_DIR,
    EMBED_DIM,
    EMBED_LOG_PATH,
    EMBED_MODEL,
    EMBED_STATE_PATH,
    EMBEDDINGS_DIR,
)
from .embed_pipeline import embed_chunks


def _load_state() -> dict[str, str]:
    if EMBED_STATE_PATH.exists():
        return json.loads(EMBED_STATE_PATH.read_text())
    return {}


def _save_state(state: dict[str, str]) -> None:
    EMBED_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EMBED_STATE_PATH.write_text(json.dumps(state, indent=2))


def run(force: bool = False) -> dict:
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

    state = {} if force else _load_state()

    total_embedded = 0
    total_skipped = 0
    total_failed = 0
    changed_slugs: list[str] = []

    chunk_files = sorted(CHUNKS_DIR.glob("*.jsonl"))
    if not chunk_files:
        print("  [embed] No chunk files found — run chunking first.")
        return {"embedded": 0, "skipped": 0, "failed": 0, "changed_slugs": []}

    for chunk_path in chunk_files:
        slug = chunk_path.stem
        try:
            all_chunks = [json.loads(l) for l in chunk_path.read_text().splitlines() if l.strip()]
        except Exception as exc:
            print(f"  [embed-err] {slug}: could not read chunks — {exc}")
            total_failed += 1
            continue

        new_chunks = [c for c in all_chunks if force or state.get(c["chunk_id"]) != c["content_hash"]]
        cached_chunks = [c for c in all_chunks if not force and state.get(c["chunk_id"]) == c["content_hash"]]

        out_path = EMBEDDINGS_DIR / f"{slug}.jsonl"

        if not new_chunks:
            total_skipped += len(all_chunks)
            print(f"  [skipped]  {slug}  (all {len(all_chunks)} chunks unchanged)")
            continue

        print(f"  [embed]    {slug}  embedding {len(new_chunks)} new/changed, {len(cached_chunks)} cached ...")

        try:
            new_records = embed_chunks(new_chunks)
        except Exception as exc:
            print(f"  [embed-err] {slug}: embedding failed — {exc}")
            total_failed += len(new_chunks)
            continue

        cached_records: list[dict] = []
        if cached_chunks and out_path.exists():
            old_by_id = {}
            for line in out_path.read_text().splitlines():
                if line.strip():
                    rec = json.loads(line)
                    old_by_id[rec["chunk_id"]] = rec
            for c in cached_chunks:
                if c["chunk_id"] in old_by_id:
                    cached_records.append(old_by_id[c["chunk_id"]])

        all_records_by_id = {r["chunk_id"]: r for r in cached_records}
        for r in new_records:
            all_records_by_id[r["chunk_id"]] = r

        ordered_records = [all_records_by_id[c["chunk_id"]] for c in all_chunks if c["chunk_id"] in all_records_by_id]

        out_path.write_text("\n".join(json.dumps(r) for r in ordered_records) + "\n")

        for r in new_records:
            state[r["chunk_id"]] = r["content_hash"]

        _save_state(state)
        total_embedded += len(new_records)
        total_skipped += len(cached_chunks)
        changed_slugs.append(slug)

        print(f"           -> wrote {len(ordered_records)} embedding records to {out_path.name}")

    print(f"\nDone — {total_embedded} embedded, {total_skipped} skipped, {total_failed} failed.")
    return {
        "embedded": total_embedded,
        "skipped": total_skipped,
        "failed": total_failed,
        "changed_slugs": changed_slugs,
        "model": EMBED_MODEL,
        "dim": EMBED_DIM,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage E: embed chunks with bge-large-en-v1.5")
    parser.add_argument("--force", action="store_true", help="Re-embed all chunks regardless of hash")
    args = parser.parse_args()
    run(force=args.force)


if __name__ == "__main__":
    main()
