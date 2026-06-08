from __future__ import annotations

import json

from .incremental_pipeline import export_changed_urls_for_next_stages
from .index_upsert import upsert_embeddings
from .run_chunking import run as run_chunking
from .run_embedding import run as run_embedding
from .run_segmentation import run as run_segmentation
from .scraping_service import ScrapingService


def main() -> None:
    # ── Ingestion: fetch, parse, change-detect, store processed JSON ──────────
    summary = ScrapingService().run()
    changed_urls_path = export_changed_urls_for_next_stages(summary)
    summary["changed_urls_artifact"] = str(changed_urls_path)

    # ── Stage A: Structural Segmentation (incremental) ────────────────────────
    seg_summary = run_segmentation(force=False)
    summary["segmentation"] = seg_summary

    # ── Stage B: Field-Aware Chunking (incremental) ───────────────────────────
    chunk_summary = run_chunking(force=False)
    summary["chunking"] = chunk_summary

    # ── Stage E: Embedding Generation — bge-large-en-v1.5 (incremental) ──────
    embed_summary = run_embedding(force=False)
    summary["embedding"] = embed_summary

    # ── Stage F: ChromaDB Upsert (upsert only changed slugs) ─────────────────
    changed_slugs = embed_summary.get("changed_slugs", [])
    if changed_slugs:
        index_summary = upsert_embeddings(slug_filter=changed_slugs)
        summary["index"] = index_summary
    else:
        summary["index"] = {"skipped": True, "reason": "no embedding changes"}

    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
