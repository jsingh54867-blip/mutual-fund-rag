"""Stage A batch runner: Structural Segmentation

Reads every processed JSON from ``data/processed_pages/``, runs the
segmenter, and writes the result to ``data/segmented_pages/``.

Incremental behaviour:
    A page is re-segmented only if its ``page_hash`` has changed since the
    last segmentation run (tracked in ``data/state/segment_state.json``).
    Pass ``--force`` to re-segment all pages regardless.

Usage:
    python -m ingestion.run_segmentation          # incremental
    python -m ingestion.run_segmentation --force   # re-segment everything
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    PROCESSED_DIR,
    SEGMENT_LOG_PATH,
    SEGMENTED_DIR,
    STATE_DIR,
)
from .segmenter import merge_small_segments, segment_text

_SEGMENT_STATE_PATH = STATE_DIR / "segment_state.json"


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def _load_segment_state() -> dict[str, str]:
    """Load the mapping of slug -> page_hash from the last segmentation run."""
    if not _SEGMENT_STATE_PATH.exists():
        return {}
    try:
        return json.loads(_SEGMENT_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_segment_state(state: dict[str, str]) -> None:
    _SEGMENT_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Per-page segmentation
# ---------------------------------------------------------------------------


def _segment_one(processed_path: Path, force: bool, state: dict[str, str]) -> dict:
    """Segment a single processed JSON file.

    Returns a result dict describing what happened.
    """
    slug = processed_path.stem
    processed = json.loads(processed_path.read_text(encoding="utf-8"))

    page_hash = processed.get("page_hash", "")
    last_hash = state.get(slug, "")

    if not force and page_hash == last_hash:
        return {"slug": slug, "status": "skipped", "reason": "page_hash_unchanged"}

    text = processed.get("text", "")
    if not text.strip():
        return {"slug": slug, "status": "skipped", "reason": "empty_text"}

    raw_segments = segment_text(text)
    segments = merge_small_segments(raw_segments)

    # Build per-block summary for quick inspection.
    block_summary: dict[str, int] = {}
    for seg in segments:
        block_summary[seg.block_type] = block_summary.get(seg.block_type, 0) + 1

    output = {
        "source_url": processed.get("source_url", ""),
        "scheme_name": processed.get("scheme_name", ""),
        "crawl_date": processed.get("crawl_date", ""),
        "page_hash": page_hash,
        "segmented_at": datetime.now(timezone.utc).isoformat(),
        "segment_count": len(segments),
        "block_summary": block_summary,
        "segments": [seg.to_dict() for seg in segments],
    }

    out_path = SEGMENTED_DIR / f"{slug}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")

    state[slug] = page_hash
    return {
        "slug": slug,
        "status": "segmented",
        "segment_count": len(segments),
        "block_summary": block_summary,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(force: bool = False) -> dict:
    SEGMENTED_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    state = _load_segment_state()
    processed_files = sorted(PROCESSED_DIR.glob("*.json"))

    if not processed_files:
        print("No processed pages found. Run the ingestion pipeline first.")
        return {"status": "no_input"}

    run_timestamp = datetime.now(timezone.utc).isoformat()
    results = []

    for path in processed_files:
        try:
            result = _segment_one(path, force=force, state=state)
        except Exception as exc:  # noqa: BLE001
            result = {"slug": path.stem, "status": "failed", "error": str(exc)}
        results.append(result)
        status = result["status"]
        slug = result["slug"]
        if status == "segmented":
            segs = result["segment_count"]
            blocks = result["block_summary"]
            print(f"  [segmented]  {slug}  ->  {segs} segments  {blocks}")
        elif status == "skipped":
            print(f"  [skipped]    {slug}  ({result.get('reason', '')})")
        else:
            print(f"  [FAILED]     {slug}  {result.get('error', '')}", file=sys.stderr)

    _save_segment_state(state)

    summary = {
        "run_timestamp": run_timestamp,
        "total": len(results),
        "segmented": sum(1 for r in results if r["status"] == "segmented"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }

    with SEGMENT_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=True))
        fh.write("\n")

    print(
        f"\nDone — {summary['segmented']} segmented, "
        f"{summary['skipped']} skipped, {summary['failed']} failed."
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage A: Structural Segmentation")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-segment all pages even if page_hash is unchanged.",
    )
    args = parser.parse_args()
    run(force=args.force)


if __name__ == "__main__":
    main()
