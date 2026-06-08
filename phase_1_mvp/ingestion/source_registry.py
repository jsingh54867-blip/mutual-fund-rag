from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .config import ALLOWED_DOMAIN, SOURCES_CSV_PATH, SOURCE_URLS


@dataclass(frozen=True)
class SourceRecord:
    url: str
    domain: str
    source_type: str
    scheme_tag: str
    last_crawled_timestamp: str


def _scheme_tag_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.split("/")[-1] if path else "unknown-scheme"


def _validate_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if not host.endswith(ALLOWED_DOMAIN):
        raise ValueError(f"Out-of-scope URL domain: {url}")
    return host


def default_source_records() -> list[SourceRecord]:
    return [
        SourceRecord(
            url=url,
            domain=_validate_domain(url),
            source_type="scheme_page_html",
            scheme_tag=_scheme_tag_from_url(url),
            last_crawled_timestamp="",
        )
        for url in SOURCE_URLS
    ]


def ensure_source_registry(path: Path = SOURCES_CSV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "url",
                "domain",
                "source_type",
                "scheme_tag",
                "last_crawled_timestamp",
            ],
        )
        writer.writeheader()
        for record in default_source_records():
            writer.writerow(record.__dict__)


def load_source_registry(path: Path = SOURCES_CSV_PATH) -> list[dict[str, str]]:
    ensure_source_registry(path)
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def update_last_crawled_timestamps(
    crawled_urls: set[str],
    crawl_timestamp: str | None = None,
    path: Path = SOURCES_CSV_PATH,
) -> None:
    if not crawled_urls:
        return

    rows = load_source_registry(path)
    now = crawl_timestamp or datetime.now(timezone.utc).isoformat()

    for row in rows:
        if row["url"] in crawled_urls:
            row["last_crawled_timestamp"] = now

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
