"""Phase 3: Monitoring & Alerting Module

Tracks key metrics for the RAG chatbot and provides health check utilities.

Metrics tracked:
  - Response latency (p50, p95, p99)
  - Refusal rate
  - Unknown response rate
  - Citation validity rate
  - Error rate
  - Source freshness (days since last crawl)

Usage:
    from phase_3_operational.monitoring import MetricsCollector, HealthChecker

    collector = MetricsCollector()
    collector.record_response(response_type="factual", latency_ms=250, guardrail_pass=True)
    report = collector.get_report()
"""

from __future__ import annotations

import json
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class MetricEntry:
    """A single metric observation."""
    timestamp: str
    response_type: str
    latency_ms: float
    guardrail_pass: bool
    source_url: str
    error: str | None = None


class MetricsCollector:
    """Collects and aggregates RAG pipeline metrics."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        self._entries: list[MetricEntry] = []
        self._log_path = Path(log_path) if log_path else None

    def record_response(
        self,
        response_type: str,
        latency_ms: float,
        guardrail_pass: bool,
        source_url: str = "",
        error: str | None = None,
    ) -> None:
        """Record a single response metric."""
        entry = MetricEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            response_type=response_type,
            latency_ms=latency_ms,
            guardrail_pass=guardrail_pass,
            source_url=source_url,
            error=error,
        )
        self._entries.append(entry)

        # Append to log file if configured
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": entry.timestamp,
                    "response_type": entry.response_type,
                    "latency_ms": entry.latency_ms,
                    "guardrail_pass": entry.guardrail_pass,
                    "source_url": entry.source_url,
                    "error": entry.error,
                }))
                f.write("\n")

    def get_report(self) -> dict[str, Any]:
        """Generate a summary report from collected metrics."""
        if not self._entries:
            return {"status": "no_data", "total_requests": 0}

        latencies = [e.latency_ms for e in self._entries]
        latencies.sort()

        total = len(self._entries)
        type_counts = defaultdict(int)
        guardrail_failures = 0
        errors = 0

        for e in self._entries:
            type_counts[e.response_type] += 1
            if not e.guardrail_pass:
                guardrail_failures += 1
            if e.error:
                errors += 1

        return {
            "status": "ok",
            "total_requests": total,
            "latency": {
                "p50_ms": round(statistics.median(latencies), 1),
                "p95_ms": round(self._percentile(latencies, 95), 1),
                "p99_ms": round(self._percentile(latencies, 99), 1),
                "mean_ms": round(statistics.mean(latencies), 1),
            },
            "response_types": dict(type_counts),
            "refusal_rate": type_counts.get("refusal", 0) / total,
            "unknown_rate": type_counts.get("unknown", 0) / total,
            "guardrail_pass_rate": (total - guardrail_failures) / total,
            "citation_validity_rate": self._citation_validity_rate(),
            "error_rate": errors / total,
            "errors": [e.error for e in self._entries if e.error][:10],
        }

    def _citation_validity_rate(self) -> float:
        """Calculate the rate of responses with valid groww.in citations."""
        if not self._entries:
            return 1.0
        valid = sum(
            1 for e in self._entries
            if e.source_url and "groww.in" in e.source_url
        )
        return valid / len(self._entries)

    @staticmethod
    def _percentile(sorted_data: list[float], pct: float) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0
        k = (len(sorted_data) - 1) * (pct / 100)
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


class HealthChecker:
    """Health check utilities for the RAG pipeline."""

    def __init__(self, api_base: str = "http://localhost:5000") -> None:
        self.api_base = api_base

    def check_api_health(self) -> dict[str, Any]:
        """Check if the API is responding."""
        try:
            import requests
            resp = requests.get(f"{self.api_base}/health", timeout=5)
            return {
                "api_status": "ok" if resp.status_code == 200 else "degraded",
                "status_code": resp.status_code,
                "response_time_ms": resp.elapsed.total_seconds() * 1000,
            }
        except Exception as e:
            return {
                "api_status": "down",
                "error": str(e),
            }

    def check_sources_available(self) -> dict[str, Any]:
        """Check if source URLs are reachable."""
        try:
            import requests
            resp = requests.get(f"{self.api_base}/sources", timeout=5)
            sources = resp.json().get("sources", [])
        except Exception:
            return {"sources_status": "unavailable"}

        reachable = 0
        unreachable = 0
        for url in sources[:3]:  # Sample first 3
            try:
                r = requests.head(url, timeout=10, allow_redirects=True)
                if r.status_code < 400:
                    reachable += 1
                else:
                    unreachable += 1
            except Exception:
                unreachable += 1

        return {
            "sources_status": "ok" if unreachable == 0 else "degraded",
            "total_sources": len(sources),
            "sampled": reachable + unreachable,
            "reachable": reachable,
            "unreachable": unreachable,
        }

    def full_health_check(self) -> dict[str, Any]:
        """Run all health checks and return aggregate status."""
        api = self.check_api_health()
        sources = self.check_sources_available()

        overall = "ok"
        if api.get("api_status") == "down":
            overall = "critical"
        elif api.get("api_status") == "degraded" or sources.get("sources_status") == "degraded":
            overall = "degraded"

        return {
            "overall_status": overall,
            "api": api,
            "sources": sources,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


if __name__ == "__main__":
    checker = HealthChecker()
    report = checker.full_health_check()
    print(json.dumps(report, indent=2))
