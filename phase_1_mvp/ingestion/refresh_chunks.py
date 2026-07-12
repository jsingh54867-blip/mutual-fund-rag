from __future__ import annotations

import json

from .run_chunking import run as run_chunking
from .run_segmentation import run as run_segmentation
from .scraping_service import ScrapingService


def refresh(force: bool = True) -> dict:
    """Refresh local retrieval chunks from the registered live source URLs."""
    scrape_summary = ScrapingService().run()

    failed_count = int(scrape_summary.get("failed_count", 0))
    success_count = int(scrape_summary.get("success_count", 0))
    total_urls = int(scrape_summary.get("total_urls", 0))

    if failed_count or success_count != total_urls:
        failed_urls = [
            {
                "url": item.get("url"),
                "error": item.get("error"),
            }
            for item in scrape_summary.get("results", [])
            if item.get("status") == "failed"
        ]
        raise RuntimeError(
            "Live source refresh failed; refusing to rebuild chunks from stale data. "
            f"success_count={success_count}, total_urls={total_urls}, "
            f"failed_urls={failed_urls}"
        )

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
