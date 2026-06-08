"""Phase 3: Post-Deploy Smoke Tests

Quick validation that the RAG pipeline is functioning correctly after a refresh.
Tests the full pipeline: health check, factual queries, refusal queries, guardrails.

Exit codes:
  0 = all smoke tests passed
  1 = one or more tests failed

Usage:
    python phase_3_operational/smoke_tests.py
    python phase_3_operational/smoke_tests.py --api-base http://myserver:5000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)


@dataclass
class SmokeTestResult:
    name: str
    passed: bool
    detail: str = ""
    latency_ms: float = 0.0


SMOKE_QUERIES: list[dict[str, str]] = [
    {
        "query": "What is the expense ratio of Motilal Oswal Small Cap Fund?",
        "expected_type": "factual",
        "description": "Factual: expense ratio",
    },
    {
        "query": "What is the minimum SIP amount?",
        "expected_type": "factual",
        "description": "Factual: min SIP",
    },
    {
        "query": "Should I invest in this fund?",
        "expected_type": "refusal",
        "description": "Refusal: advice",
    },
    {
        "query": "Which fund is better?",
        "expected_type": "refusal",
        "description": "Refusal: comparison",
    },
]


def check_health(api_base: str) -> SmokeTestResult:
    """Check API health endpoint."""
    try:
        start = time.time()
        resp = requests.get(f"{api_base}/health", timeout=10)
        latency = (time.time() - start) * 1000

        if resp.status_code == 200 and resp.json().get("status") == "ok":
            return SmokeTestResult("health", True, "API healthy", latency)
        return SmokeTestResult("health", False, f"Unexpected response: {resp.text}", latency)
    except Exception as e:
        return SmokeTestResult("health", False, f"Health check failed: {e}")


def check_chat(api_base: str, test_case: dict[str, str]) -> SmokeTestResult:
    """Test a single chat query."""
    desc = test_case["description"]
    try:
        start = time.time()
        resp = requests.post(
            f"{api_base}/chat",
            json={"query": test_case["query"]},
            timeout=30,
        )
        latency = (time.time() - start) * 1000

        if resp.status_code != 200:
            return SmokeTestResult(desc, False, f"HTTP {resp.status_code}", latency)

        data = resp.json()

        # Check response type
        actual_type = data.get("response_type", "")
        expected_type = test_case["expected_type"]
        if actual_type != expected_type:
            return SmokeTestResult(
                desc, False,
                f"Expected type={expected_type}, got={actual_type}",
                latency,
            )

        # Check guardrails
        answer = data.get("answer", "")
        source_link = data.get("source_link", "")
        last_updated = data.get("last_updated_from_sources", "")

        if not answer:
            return SmokeTestResult(desc, False, "Empty answer", latency)

        if not source_link:
            return SmokeTestResult(desc, False, "Missing source_link", latency)

        if "groww.in" not in source_link:
            return SmokeTestResult(desc, False, f"Invalid source domain: {source_link}", latency)

        if not last_updated:
            return SmokeTestResult(desc, False, "Missing last_updated", latency)

        # Check answer doesn't contain URLs
        if "http" in answer:
            return SmokeTestResult(desc, False, "Answer contains URL", latency)

        # Check sentence count (rough)
        sentences = [s for s in answer.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        if len(sentences) > 3:
            return SmokeTestResult(desc, False, f"Too many sentences: {len(sentences)}", latency)

        return SmokeTestResult(desc, True, "OK", latency)

    except Exception as e:
        return SmokeTestResult(desc, False, f"Request failed: {e}")


def run_smoke_tests(api_base: str) -> list[SmokeTestResult]:
    """Run all smoke tests and return results."""
    results: list[SmokeTestResult] = []

    # Health check first
    results.append(check_health(api_base))
    if not results[-1].passed:
        return results  # No point testing further if API is down

    # Chat queries
    for test_case in SMOKE_QUERIES:
        results.append(check_chat(api_base, test_case))

    return results


def main():
    parser = argparse.ArgumentParser(description="Post-deploy smoke tests")
    parser.add_argument(
        "--api-base",
        default="http://localhost:5000",
        help="Base URL of the API (default: http://localhost:5000)",
    )
    args = parser.parse_args()

    print(f"Running smoke tests against: {args.api_base}")
    print("-" * 50)

    results = run_smoke_tests(args.api_base)

    passed = 0
    failed = 0
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}: {r.detail} ({r.latency_ms:.0f}ms)")
        if r.passed:
            passed += 1
        else:
            failed += 1

    print("-" * 50)
    print(f"Results: {passed} passed, {failed} failed, {len(results)} total")

    if failed > 0:
        print("SMOKE TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL SMOKE TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
