"""Phase 2: Unit Tests for Query Classifier"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from backend.query_classifier import classify, FACTUAL_ALLOWED, REFUSAL_REQUIRED, OUT_OF_SCOPE


class TestFactualClassification:
    """Tests that factual queries are correctly classified."""

    @pytest.mark.parametrize("query", [
        "What is the expense ratio of Motilal Oswal Small Cap Fund?",
        "What is the exit load?",
        "Tell me the minimum SIP amount",
        "What is the riskometer reading?",
        "What is the benchmark index?",
        "What is the NAV?",
        "How to get capital gains statement?",
        "What is the ELSS lock-in period?",
        "What is the fund size?",
        "What is the minimum investment amount?",
    ])
    def test_factual_queries(self, query):
        assert classify(query) == FACTUAL_ALLOWED

    def test_plain_question(self):
        assert classify("When was this fund launched?") == FACTUAL_ALLOWED

    def test_empty_query(self):
        assert classify("") == OUT_OF_SCOPE

    def test_whitespace_only(self):
        assert classify("   ") == OUT_OF_SCOPE


class TestRefusalClassification:
    """Tests that advice/comparison/calculation queries trigger refusal."""

    @pytest.mark.parametrize("query", [
        "Should I invest in this fund?",
        "Is it worth investing in Motilal Oswal?",
        "Can you recommend a good fund?",
        "Which fund is better?",
        "Compare these two funds",
        "What returns will I get?",
        "Calculate my CAGR",
        "How much will I get after 5 years?",
        "Is it a good fund to invest in?",
        "Suggest me the best mutual fund",
    ])
    def test_refusal_queries(self, query):
        assert classify(query) == REFUSAL_REQUIRED


class TestEdgeCases:
    """Edge cases and boundary queries."""

    def test_mixed_intent(self):
        """Query with both factual and advice elements should refuse."""
        result = classify("Should I invest based on the expense ratio?")
        assert result == REFUSAL_REQUIRED

    def test_case_insensitive(self):
        assert classify("SHOULD I INVEST?") == REFUSAL_REQUIRED
        assert classify("what is the EXPENSE RATIO?") == FACTUAL_ALLOWED

    def test_partial_keyword_no_false_positive(self):
        """'Returns' alone in a factual context should not refuse."""
        # "What are the historic returns?" is factual
        result = classify("What are the historic returns?")
        assert result == FACTUAL_ALLOWED

    def test_comparison_keyword(self):
        assert classify("Fund A vs Fund B") == REFUSAL_REQUIRED
        assert classify("which is better for me") == REFUSAL_REQUIRED
