"""Chat service behavior tests."""

from backend.chat_service import chat


def test_greeting_returns_friendly_response_without_retrieval():
    result = chat("hello")

    assert result["response_type"] == "greeting"
    assert "hello" in result["answer"].lower()
    assert result["source_link"] is None
    assert result["last_updated_from_sources"] is None


def test_greeting_handles_punctuation_and_case():
    result = chat("Hi!")

    assert result["response_type"] == "greeting"
