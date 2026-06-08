"""Phase 2: Unit Tests for Citation Rules"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from backend.formatter import format_response, _is_allowed_url, _extract_urls


class TestCitationValidity:
    """Ensure citations always point to official groww.in URLs."""

    def test_valid_source_link_preserved(self):
        result = format_response(
            answer_text="The expense ratio is 0.85%.",
            source_url="https://groww.in/mutual-funds/motilal-oswal-small-cap-fund",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert result["source_link"] == "https://groww.in/mutual-funds/motilal-oswal-small-cap-fund"

    def test_invalid_link_replaced_with_default(self):
        result = format_response(
            answer_text="The expense ratio is 0.85%.",
            source_url="https://malicious.com/fake",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert _is_allowed_url(result["source_link"])

    def test_empty_link_gets_default(self):
        result = format_response(
            answer_text="The expense ratio is 0.85%.",
            source_url="",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert _is_allowed_url(result["source_link"])

    def test_url_extracted_from_answer_text(self):
        """If source_url is invalid but answer contains a groww.in URL, use it."""
        result = format_response(
            answer_text="See https://groww.in/mutual-funds/test for more info.",
            source_url="https://bad-domain.com",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert "groww.in" in result["source_link"]


class TestUrlExtraction:
    """Test the URL extraction helper."""

    def test_extract_single_url(self):
        urls = _extract_urls("Visit https://groww.in/test for details.")
        assert len(urls) == 1
        assert urls[0] == "https://groww.in/test"

    def test_extract_multiple_urls(self):
        urls = _extract_urls("See https://groww.in/a and https://groww.in/b")
        assert len(urls) == 2

    def test_extract_no_urls(self):
        urls = _extract_urls("No URLs here.")
        assert len(urls) == 0


class TestSingleUrlEnforcement:
    """R2: Final response must contain exactly one URL (in source_link field)."""

    def test_answer_has_no_embedded_urls(self):
        result = format_response(
            answer_text="The NAV is ₹100. Check https://groww.in/test and https://groww.in/test2.",
            source_url="https://groww.in/test",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert "http" not in result["answer"]

    def test_source_link_is_single_url(self):
        result = format_response(
            answer_text="Test.",
            source_url="https://groww.in/mutual-funds/test",
            last_updated="2025-01-01",
            response_type="factual",
        )
        # source_link should be a single URL string
        assert isinstance(result["source_link"], str)
        assert result["source_link"].startswith("https://")
