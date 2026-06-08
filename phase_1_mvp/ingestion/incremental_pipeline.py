from __future__ import annotations

import json
from pathlib import Path

from .config import DATA_DIR


def export_changed_urls_for_next_stages(summary: dict) -> Path:
    """
    Creates an artifact consumed by chunking/embedding steps.
    """
    changed_urls = [
        item["url"]
        for item in summary.get("results", [])
        if item.get("status") == "success" and item.get("changed") is True
    ]

    output_path = DATA_DIR / "changed_urls.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "run_timestamp": summary.get("run_timestamp"),
                "changed_urls": changed_urls,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output_path
