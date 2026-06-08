"""Stage B batch runner: Field-Aware Chunking

Reads every segmented JSON from ``data/segmented_pages/`` alongside the
matching processed JSON (for metrics and source metadata), runs the chunker,
and writes one JSONL file per fund to ``data/chunks/``.

One line per chunk; each line is a valid JSON object.

Incremental behaviour:
    A page is re-chunked only if its ``page_hash`` has changed since the
    last chunking run (tracked in ``data/state/chunk_state.json``).
    Pass ``--force`` to re-chunk all pages regardless.

Usage:
    python -m ingestion.run_chunking          # incremental
    python -m ingestion.run_chunking --force   # force full re-chunk
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .chunker import build_chunks
from .config import (
    CHUNK_LOG_PATH,
    CHUNKS_DIR,
    PROCESSED_DIR,
    SEGMENTED_DIR,
    STATE_DIR,
)

_CHUNK_STATE_PATH = STATE_DIR / "chunk_state.json"


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_chunk_state() -> dict[str, str]:
    if not _CHUNK_STATE_PATH.exists():
        return {}
    try:
        return json.loads(_CHUNK_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_chunk_state(state: dict[str, str]) -> None:
    _CHUNK_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Per-page chunking
# ---------------------------------------------------------------------------

def _chunk_one(
    slug: str,
    force: bool,
    state: dict[str, str],
) -> dict:
    segmented_path = SEGMENTED_DIR / f"{slug}.json"
    processed_path = PROCESSED_DIR / f"{slug}.json"

    if not segmented_path.exists():
        return {"slug": slug, "status": "skipped", "reason": "no_segmented_file"}
    if not processed_path.exists():
        return {"slug": slug, "status": "skipped", "reason": "no_processed_file"}

    segmented = json.loads(segmented_path.read_text(encoding="utf-8"))
    processed = json.loads(processed_path.read_text(encoding="utf-8"))

    page_hash = processed.get("page_hash", "")
    if not force and state.get(slug) == page_hash:
        return {"slug": slug, "status": "skipped", "reason": "page_hash_unchanged"}

    segments: list[dict] = segmented.get("segments", [])
    if not segments:
        return {"slug": slug, "status": "skipped", "reason": "no_segments"}

    chunks = build_chunks(segments, processed)

    out_path = CHUNKS_DIR / f"{slug}.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk.to_dict(), ensure_ascii=True))
            fh.write("\n")

    # Build a quick field_type distribution for reporting.
    field_dist: dict[str, int] = {}
    for c in chunks:
        field_dist[c.field_type] = field_dist.get(c.field_type, 0) + 1

    state[slug] = page_hash
    return {
        "slug": slug,
        "status": "chunked",
        "chunk_count": len(chunks),
        "field_type_dist": field_dist,
    }


# ---------------------------------------------------------------------------
# Reporting helper
# ---------------------------------------------------------------------------

def _print_chunk_preview(slug: str) -> None:
    """Print a brief summary of each chunk in the output JSONL."""
    path = CHUNKS_DIR / f"{slug}.jsonl"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            c = json.loads(line)
            preview = c["text"][:80].replace("\n", " ")
            size_flag = ""
            if c["char_count"] < 350:
                size_flag = " [small]"
            elif c["char_count"] > 1000:
                size_flag = " [OVER-MAX]"
            print(
                f"    chunk {i+1:02d}  [{c['section_name']:<22}]"
                f"  ft={c['field_type']:<18}  {c['char_count']:>4}ch{size_flag}"
                f"  '{preview}...'"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(force: bool = False) -> dict:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CHUNK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    state = _load_chunk_state()
    slugs = sorted(p.stem for p in SEGMENTED_DIR.glob("*.json"))

    if not slugs:
        print("No segmented pages found. Run segmentation first.")
        return {"status": "no_input"}

    run_timestamp = datetime.now(timezone.utc).isoformat()
    results = []

    for slug in slugs:
        try:
            result = _chunk_one(slug, force=force, state=state)
        except Exception as exc:  # noqa: BLE001
            result = {"slug": slug, "status": "failed", "error": str(exc)}
        results.append(result)

        status = result["status"]
        if status == "chunked":
            dist = result["field_type_dist"]
            print(
                f"  [chunked]  {slug}\n"
                f"             {result['chunk_count']} chunks  field_types={dist}"
            )
            _print_chunk_preview(slug)
        elif status == "skipped":
            print(f"  [skipped]  {slug}  ({result.get('reason', '')})")
        else:
            print(f"  [FAILED]   {slug}  {result.get('error', '')}", file=sys.stderr)

    _save_chunk_state(state)

    summary = {
        "run_timestamp": run_timestamp,
        "total": len(results),
        "chunked": sum(1 for r in results if r["status"] == "chunked"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }

    with CHUNK_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=True))
        fh.write("\n")

    print(
        f"\nDone — {summary['chunked']} chunked, "
        f"{summary['skipped']} skipped, {summary['failed']} failed."
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage B: Field-Aware Chunking")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-chunk all pages even if page_hash is unchanged.",
    )
    args = parser.parse_args()
    run(force=args.force)


if __name__ == "__main__":
    main()
