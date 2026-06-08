"""Phase 2: Unit Tests for Output Guardrails (Formatter)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from backend.formatter import format_response, _count_sentences, _is_allowed_url


class TestSentenceLimit:
    """R4: Max 3 sentences in answer."""

    def test_short_answer_unchanged(self):
        result = format_response(
            answer_text="The expense ratio is 0.85%. It is competitive.",
            source_url="https://groww.in/mutual-funds/test",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert _count_sentences(result["answer"]) <= 3

    def test_long_answer_truncated(self):
        long_answer = (
            "First sentence. Second sentence. "
            "Third sentence. Fourth sentence. Fifth sentence."
        )
        result = format_response(
            answer_text=long_answer,
            source_url="https://groww.in/mutual-funds/test",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert _count_sentences(result["answer"]) <= 3

    def test_sentence_counter(self):
        assert _count_sentences("One. Two. Three.") == 3
        assert _count_sentences("Hello!") == 1
        assert _count_sentences("") == 0
        assert _count_sentences("No punctuation") == 1


class TestSingleLinkRule:
    """R2: Exactly one URL in response."""

    def test_urls_stripped_from_answer(self):
        result = format_response(
            answer_text="The NAV is ₹100. See https://groww.in/mutual-funds/test for details.",
            source_url="https://groww.in/mutual-funds/test",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert "https://" not in result["answer"]
        assert result["source_link"] == "https://groww.in/mutual-funds/test"


class TestDomainAllowlist:
    """R3: URL domain must be groww.in."""

    def test_allowed_domain(self):
        assert _is_allowed_url("https://groww.in/mutual-funds/test") is True
        assert _is_allowed_url("https://www.groww.in/test") is True

    def test_disallowed_domain(self):
        assert _is_allowed_url("https://example.com/test") is False
        assert _is_allowed_url("https://moneycontrol.com/fund") is False

    def test_fallback_to_default_on_bad_url(self):
        result = format_response(
            answer_text="The expense ratio is 0.85%.",
            source_url="https://evil.com/test",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert _is_allowed_url(result["source_link"])


class TestLastUpdatedLine:
    """R5: Must include last_updated line."""

    def test_last_updated_present(self):
        result = format_response(
            answer_text="The NAV is ₹100.",
            source_url="https://groww.in/mutual-funds/test",
            last_updated="2025-06-01",
            response_type="factual",
        )
        assert result["last_updated_from_sources"] == "2025-06-01"

    def test_last_updated_fallback(self):
        result = format_response(
            answer_text="The NAV is ₹100.",
            source_url="https://groww.in/mutual-funds/test",
            last_updated="",
            response_type="factual",
        )
        assert result["last_updated_from_sources"] == "N/A"

    def test_last_updated_none(self):
        result = format_response(
            answer_text="The NAV is ₹100.",
            source_url="https://groww.in/mutual-funds/test",
            last_updated=None,
            response_type="factual",
        )
        assert result["last_updated_from_sources"] == "N/A"


class TestResponseStructure:
    """Ensure the response dict has all required keys."""

    def test_all_keys_present(self):
        result = format_response(
            answer_text="Test answer.",
            source_url="https://groww.in/test",
            last_updated="2025-01-01",
            response_type="factual",
        )
        assert "answer" in result
        assert "source_link" in result
        assert "last_updated_from_sources" in result
        assert "response_type" in result

    def test_response_type_preserved(self):
        for rtype in ("factual", "refusal", "unknown"):
            result = format_response(
                answer_text="Test.",
                source_url="https://groww.in/test",
                last_updated="2025-01-01",
                response_type=rtype,
            )
            assert result["response_type"] == rtype
