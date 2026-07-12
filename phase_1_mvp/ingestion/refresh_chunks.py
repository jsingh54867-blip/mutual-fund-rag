from __future__ import annotations

import json

from .run_chunking import run as run_chunking
from .run_segmentation import run as run_segmentation
from .scraping_service import ScrapingService


def refresh(force: bool = True) -> dict:
    """Refresh local retrieval chunks from the registered live source URLs."""
    scrape_summary = ScrapingService().run()
    segment_summary = run_segmentation(force=force)
    chunk_summary = run_chunking(force=force)

    return {
        "scrape": scrape_summary,
        "segmentation": segment_summary,
        "chunking": chunk_summary,
    }


def main() -> None:
    print(json.dumps(refresh(force=True), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
