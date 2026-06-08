from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from .config import (
    MAX_RETRIES,
    PROCESSED_DIR,
    RAW_DIR,
    RETRY_BACKOFF_SECONDS,
    SCRAPE_LOG_PATH,
    STATE_FILE_PATH,
    USER_AGENT,
    REQUEST_TIMEOUT_SECONDS,
)
from .html_parser import (
    extract_clean_text,
    extract_key_metrics,
    extract_scheme_name,
    infer_field_tags,
    infer_parse_confidence,
)
from .source_registry import load_source_registry, update_last_crawled_timestamps


@dataclass
class ScrapeResult:
    url: str
    status: str
    changed: bool
    page_hash: str | None
    parse_confidence: str | None
    scheme_name: str | None
    field_tags: list[str]
    metrics: dict
    error: str | None


class ScrapingService:
    def __init__(self) -> None:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        SCRAPE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    def run(self) -> dict[str, Any]:
        source_rows = load_source_registry()
        state = self._load_state()
        run_timestamp = datetime.now(timezone.utc).isoformat()

        results: list[ScrapeResult] = []
        crawled_urls: set[str] = set()

        for row in source_rows:
            url = row["url"]
            try:
                html = self._fetch_with_retries(url)
                clean_text, scheme_name, parse_confidence = self._parse(html)
                metrics = extract_key_metrics(html)
                page_hash = self._hash_text(clean_text)
                old_hash = state.get(url, {}).get("page_hash")
                changed = page_hash != old_hash

                self._write_raw_html(url, html)
                self._write_processed_document(
                    url=url,
                    clean_text=clean_text,
                    scheme_name=scheme_name,
                    parse_confidence=parse_confidence,
                    page_hash=page_hash,
                    crawl_date=run_timestamp,
                    metrics=metrics,
                )
                state[url] = {
                    "page_hash": page_hash,
                    "last_crawl": run_timestamp,
                }

                field_tags = infer_field_tags(clean_text)
                results.append(
                    ScrapeResult(
                        url=url,
                        status="success",
                        changed=changed,
                        page_hash=page_hash,
                        parse_confidence=parse_confidence,
                        scheme_name=scheme_name,
                        field_tags=field_tags,
                        metrics=metrics,
                        error=None,
                    )
                )
                crawled_urls.add(url)
            except Exception as exc:  # noqa: BLE001 - include non-network parse failures
                results.append(
                    ScrapeResult(
                        url=url,
                        status="failed",
                        changed=False,
                        page_hash=None,
                        parse_confidence=None,
                        scheme_name=None,
                        field_tags=[],
                        metrics={},
                        error=str(exc),
                    )
                )

        self._save_state(state)
        update_last_crawled_timestamps(crawled_urls, run_timestamp)
        summary = self._build_summary(run_timestamp, results)
        self._append_run_log(summary)
        return summary

    def _fetch_with_retries(self, url: str) -> str:
        headers = {"User-Agent": USER_AGENT}
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                return response.text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= MAX_RETRIES:
                    break
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

        raise RuntimeError(f"Failed to fetch URL: {url}; error: {last_error}") from last_error

    def _parse(self, html: str) -> tuple[str, str, str]:
        soup = BeautifulSoup(html, "html.parser")
        clean_text = extract_clean_text(html)
        scheme_name = extract_scheme_name(soup)
        parse_confidence = infer_parse_confidence(clean_text)
        return clean_text, scheme_name, parse_confidence

    def _url_slug(self, url: str) -> str:
        return url.rstrip("/").split("/")[-1]

    def _write_raw_html(self, url: str, html: str) -> None:
        slug = self._url_slug(url)
        path = RAW_DIR / f"{slug}.html"
        path.write_text(html, encoding="utf-8")

    def _write_processed_document(
        self,
        *,
        url: str,
        clean_text: str,
        scheme_name: str,
        parse_confidence: str,
        page_hash: str,
        crawl_date: str,
        metrics: dict,
    ) -> None:
        slug = self._url_slug(url)
        payload = {
            "source_url": url,
            "source_domain": "groww.in",
            "document_type": "scheme_page_html",
            "scheme_name": scheme_name,
            "parse_confidence": parse_confidence,
            "crawl_date": crawl_date,
            "page_hash": page_hash,
            "metrics": {
                "nav": metrics.get("nav"),
                "nav_date": metrics.get("nav_date"),
                "min_sip": metrics.get("min_sip"),
                "fund_size_cr": metrics.get("fund_size_cr"),
                "expense_ratio": metrics.get("expense_ratio"),
                "rating": metrics.get("rating"),
            },
            "text": clean_text,
        }
        (PROCESSED_DIR / f"{slug}.json").write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _load_state(self) -> dict[str, dict[str, str]]:
        if not STATE_FILE_PATH.exists():
            return {}
        try:
            return json.loads(STATE_FILE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_state(self, state: dict[str, dict[str, str]]) -> None:
        STATE_FILE_PATH.write_text(
            json.dumps(state, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _build_summary(self, run_timestamp: str, results: list[ScrapeResult]) -> dict[str, Any]:
        success_results = [result for result in results if result.status == "success"]
        changed_count = sum(1 for result in success_results if result.changed)
        failed_results = [result for result in results if result.status == "failed"]

        return {
            "run_timestamp": run_timestamp,
            "total_urls": len(results),
            "success_count": len(success_results),
            "failed_count": len(failed_results),
            "changed_count": changed_count,
            "results": [result.__dict__ for result in results],
        }

    def _append_run_log(self, summary: dict[str, Any]) -> None:
        with SCRAPE_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(json.dumps(summary, ensure_ascii=True))
            file.write("\n")
