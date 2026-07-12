"""Regression tests for local JSON retrieval."""

from backend.retriever import retrieve


def test_expense_ratio_keeps_requested_small_cap_scheme():
    result = retrieve("What is the expense ratio of Motilal Oswal Small Cap Fund?")

    assert result.chunks
    assert result.chunks[0].scheme_name == "Motilal Oswal Small Cap Fund Direct Growth"
    assert "Expense Ratio: 0.81%" in result.chunks[0].text


def test_exit_load_keeps_requested_large_and_midcap_scheme():
    result = retrieve("What is the exit load of Motilal Oswal Large and Midcap Fund?")

    assert result.chunks
    assert all(
        chunk.scheme_name == "Motilal Oswal Large and Midcap Fund Direct Growth"
        for chunk in result.chunks
    )
    assert "large-and-midcap" in result.citation_urls[0]


def test_mo_midcap_alias_targets_midcap_not_large_and_midcap():
    result = retrieve("What is the 3Y return of MO Midcap Fund?")

    assert result.chunks
    assert result.chunks[0].scheme_name == "Motilal Oswal Midcap Fund Direct Growth"
    assert "returns" in result.chunks[0].text.lower()


def test_unknown_named_scheme_returns_no_chunks():
    result = retrieve("Top holdings of Motilal Oswal Flexi Cap?")

    assert result.chunks == []
    assert result.top_similarity == 0.0
    assert result.citation_urls == []
