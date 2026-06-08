"""Phase 2: Unit Tests for Refusal Responses"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from backend.policy import (
    REFUSAL_RESPONSE,
    UNKNOWN_RESPONSE,
    REFUSAL_ADVICE,
    REFUSAL_COMPARISON,
    REFUSAL_CALCULATION,
    UNKNOWN_ANSWER,
    DEFAULT_SOURCE_URL,
)
from backend.formatter import _is_allowed_url


class TestRefusalTemplates:
    """Verify refusal templates are well-formed."""

    def test_refusal_response_structure(self):
        assert "answer" in REFUSAL_RESPONSE
        assert "source_link" in REFUSAL_RESPONSE
        assert "last_updated_from_sources" in REFUSAL_RESPONSE
        assert "response_type" in REFUSAL_RESPONSE
        assert REFUSAL_RESPONSE["response_type"] == "refusal"

    def test_refusal_response_has_valid_source(self):
        assert _is_allowed_url(REFUSAL_RESPONSE["source_link"])

    def test_refusal_advice_text(self):
        assert "factual" in REFUSAL_ADVICE.lower()
        assert "advice" in REFUSAL_ADVICE.lower() or "recommendation" in REFUSAL_ADVICE.lower()

    def test_refusal_comparison_text(self):
        assert "compare" in REFUSAL_COMPARISON.lower() or "comparison" in REFUSAL_COMPARISON.lower()

    def test_refusal_calculation_text(self):
        assert "calculat" in REFUSAL_CALCULATION.lower() or "project" in REFUSAL_CALCULATION.lower()


class TestUnknownResponse:
    """Verify the unknown/low-confidence response template."""

    def test_unknown_response_structure(self):
        assert "answer" in UNKNOWN_RESPONSE
        assert "source_link" in UNKNOWN_RESPONSE
        assert "last_updated_from_sources" in UNKNOWN_RESPONSE
        assert "response_type" in UNKNOWN_RESPONSE
        assert UNKNOWN_RESPONSE["response_type"] == "unknown"

    def test_unknown_response_has_valid_source(self):
        assert _is_allowed_url(UNKNOWN_RESPONSE["source_link"])

    def test_unknown_answer_text(self):
        assert "don't know" in UNKNOWN_ANSWER.lower() or "do not know" in UNKNOWN_ANSWER.lower()

    def test_unknown_last_updated_is_na(self):
        assert UNKNOWN_RESPONSE["last_updated_from_sources"] == "N/A"


class TestDefaultSourceUrl:
    """Verify the fallback source URL."""

    def test_default_source_is_groww(self):
        assert _is_allowed_url(DEFAULT_SOURCE_URL)

    def test_default_source_is_string(self):
        assert isinstance(DEFAULT_SOURCE_URL, str)
        assert DEFAULT_SOURCE_URL.startswith("https://")


class TestRefusalDeterminism:
    """Refusal responses must be deterministic (same template every time)."""

    def test_refusal_is_deterministic(self):
        r1 = dict(REFUSAL_RESPONSE)
        r2 = dict(REFUSAL_RESPONSE)
        assert r1 == r2

    def test_unknown_is_deterministic(self):
        r1 = dict(UNKNOWN_RESPONSE)
        r2 = dict(UNKNOWN_RESPONSE)
        assert r1 == r2

    def test_refusal_does_not_contain_user_query(self):
        """Refusal templates must never echo user query text."""
        assert "expense ratio" not in REFUSAL_ADVICE.lower()
        assert "sip" not in REFUSAL_ADVICE.lower()
