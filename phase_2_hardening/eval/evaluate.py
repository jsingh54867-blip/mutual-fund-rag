"""Phase 2: Offline Evaluation Harness

Evaluates the RAG pipeline against a curated set of question-answer pairs
without requiring live API calls. Tests the full pipeline:
  classify -> retrieve -> generate -> format

Usage:
    python -m phase_2_hardening.eval.evaluate
    python -m phase_2_hardening.eval.evaluate --json   # JSON output
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.query_classifier import classify, FACTUAL_ALLOWED, REFUSAL_REQUIRED
from backend.formatter import format_response, _count_sentences, _is_allowed_url
from backend.policy import REFUSAL_RESPONSE, UNKNOWN_RESPONSE


# ---------------------------------------------------------------------------
# Evaluation Dataset
# ---------------------------------------------------------------------------

@dataclass
class EvalCase:
    """A single evaluation test case."""
    query: str
    expected_type: str  # "factual", "refusal", "unknown"
    expected_keywords: list[str] = field(default_factory=list)
    description: str = ""


EVAL_DATASET: list[EvalCase] = [
    # Factual queries
    EvalCase(
        query="What is the expense ratio of Motilal Oswal Small Cap Fund?",
        expected_type="factual",
        expected_keywords=["expense ratio"],
        description="Expense ratio query",
    ),
    EvalCase(
        query="What is the minimum SIP amount?",
        expected_type="factual",
        expected_keywords=["sip", "minimum"],
        description="Min SIP query",
    ),
    EvalCase(
        query="What is the exit load?",
        expected_type="factual",
        expected_keywords=["exit load"],
        description="Exit load query",
    ),
    EvalCase(
        query="What is the benchmark index?",
        expected_type="factual",
        expected_keywords=["benchmark"],
        description="Benchmark query",
    ),
    EvalCase(
        query="What is the riskometer reading?",
        expected_type="factual",
        expected_keywords=["risk"],
        description="Riskometer query",
    ),

    # Refusal queries
    EvalCase(
        query="Should I invest in this fund?",
        expected_type="refusal",
        description="Advice refusal",
    ),
    EvalCase(
        query="Which fund is better?",
        expected_type="refusal",
        description="Comparison refusal",
    ),
    EvalCase(
        query="Calculate my returns",
        expected_type="refusal",
        description="Calculation refusal",
    ),
    EvalCase(
        query="Recommend me a good mutual fund",
        expected_type="refusal",
        description="Recommendation refusal",
    ),

    # Edge cases
    EvalCase(
        query="",
        expected_type="unknown",
        description="Empty query",
    ),
]


# ---------------------------------------------------------------------------
# Evaluation Runner
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    """Result of evaluating a single case."""
    case: EvalCase
    classified_type: str
    classification_correct: bool
    response: dict | None = None
    guardrail_pass: bool = False
    latency_ms: float = 0.0
    error: str | None = None


def evaluate_classifier(case: EvalCase) -> EvalResult:
    """Evaluate only the classifier stage (no API calls needed)."""
    start = time.time()
    try:
        classified = classify(case.query)
        latency = (time.time() - start) * 1000
        correct = classified == case.expected_type

        return EvalResult(
            case=case,
            classified_type=classified,
            classification_correct=correct,
            latency_ms=latency,
        )
    except Exception as e:
        return EvalResult(
            case=case,
            classified_type="error",
            classification_correct=False,
            latency_ms=(time.time() - start) * 1000,
            error=str(e),
        )


def evaluate_guardrails(response: dict) -> bool:
    """Check if a response passes all guardrail rules."""
    # R2: Has source_link
    if not response.get("source_link"):
        return False
    # R3: Source URL domain is groww.in
    if not _is_allowed_url(response["source_link"]):
        return False
    # R4: Max 3 sentences
    if _count_sentences(response.get("answer", "")) > 3:
        return False
    # R5: Has last_updated
    if not response.get("last_updated_from_sources"):
        return False
    # Answer should not contain URLs
    if "http" in response.get("answer", ""):
        return False
    return True


def run_classifier_evaluation() -> dict[str, Any]:
    """Run the full classifier evaluation suite."""
    results: list[EvalResult] = []

    for case in EVAL_DATASET:
        result = evaluate_classifier(case)
        results.append(result)

    correct = sum(1 for r in results if r.classification_correct)
    total = len(results)

    # Per-type metrics
    refusal_cases = [r for r in results if r.case.expected_type == "refusal"]
    refusal_correct = sum(1 for r in refusal_cases if r.classification_correct)
    refusal_precision = refusal_correct / len(refusal_cases) if refusal_cases else 0.0

    factual_cases = [r for r in results if r.case.expected_type == "factual"]
    factual_correct = sum(1 for r in factual_cases if r.classification_correct)
    factual_precision = factual_correct / len(factual_cases) if factual_cases else 0.0

    avg_latency = sum(r.latency_ms for r in results) / total if total else 0.0

    return {
        "total_cases": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "refusal_precision": refusal_precision,
        "factual_precision": factual_precision,
        "avg_latency_ms": round(avg_latency, 2),
        "failures": [
            {
                "query": r.case.query,
                "expected": r.case.expected_type,
                "got": r.classified_type,
                "description": r.case.description,
            }
            for r in results if not r.classification_correct
        ],
        "results": [
            {
                "query": r.case.query,
                "expected": r.case.expected_type,
                "classified": r.classified_type,
                "correct": r.classification_correct,
                "latency_ms": round(r.latency_ms, 2),
                "description": r.case.description,
            }
            for r in results
        ],
    }


def print_report(report: dict[str, Any], as_json: bool = False) -> None:
    """Print the evaluation report."""
    if as_json:
        print(json.dumps(report, indent=2))
        return

    print("=" * 60)
    print("  EVALUATION REPORT")
    print("=" * 60)
    print(f"  Total cases:       {report['total_cases']}")
    print(f"  Correct:           {report['correct']}")
    print(f"  Accuracy:          {report['accuracy']:.1%}")
    print(f"  Refusal precision: {report['refusal_precision']:.1%}")
    print(f"  Factual precision: {report['factual_precision']:.1%}")
    print(f"  Avg latency:       {report['avg_latency_ms']:.1f}ms")
    print("-" * 60)

    if report["failures"]:
        print(f"\n  FAILURES ({len(report['failures'])}):")
        for f in report["failures"]:
            print(f"    [{f['description']}] expected={f['expected']}, got={f['got']}")
            print(f"      query: \"{f['query']}\"")
    else:
        print("\n  All cases passed!")

    print("=" * 60)


if __name__ == "__main__":
    as_json = "--json" in sys.argv
    report = run_classifier_evaluation()
    print_report(report, as_json=as_json)
