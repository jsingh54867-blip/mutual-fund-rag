from __future__ import annotations

from .config import SIMILARITY_THRESHOLD
from .formatter import format_response
from .generator import generate
from .policy import REFUSAL_RESPONSE, UNKNOWN_RESPONSE
from .query_classifier import (
    FACTUAL_ALLOWED,
    OUT_OF_SCOPE,
    REFUSAL_REQUIRED,
    classify,
)
from .retriever import retrieve

GREETING_RESPONSE = {
    "answer": (
        "Hello! I can help with factual information about Motilal Oswal mutual "
        "funds, like NAV, expense ratio, AUM, holdings, and exit load."
    ),
    "source_link": None,
    "last_updated_from_sources": None,
    "response_type": "greeting",
}

_GREETING_QUERIES = {
    "hello",
    "hi",
    "hey",
    "hii",
    "helo",
    "good morning",
    "good afternoon",
    "good evening",
    "namaste",
}


def _is_greeting(query: str) -> bool:
    normalized = query.lower().strip(" .,!?\t\n")
    return normalized in _GREETING_QUERIES


def chat(query: str) -> dict:
    """End-to-end chat pipeline: classify -> retrieve -> generate -> format.

    Returns a dict with keys:
      answer, source_link, last_updated_from_sources, response_type
    """
    query = query.strip()
    if not query:
        return format_response(
            answer_text="Please ask a question about mutual funds.",
            source_url="",
            last_updated="N/A",
            response_type="unknown",
        )

    if _is_greeting(query):
        return dict(GREETING_RESPONSE)

    # -- Phase 4.6: Query Classification --
    classification = classify(query)

    if classification == REFUSAL_REQUIRED:
        return dict(REFUSAL_RESPONSE)

    # -- Phase 4.5: Retrieval --
    retrieval = retrieve(query)

    # -- R6: Low confidence -> unknown --
    if not retrieval.chunks or retrieval.top_similarity < SIMILARITY_THRESHOLD:
        return dict(UNKNOWN_RESPONSE)

    # -- Phase 4.7: LLM Generation --
    llm_result = generate(query, retrieval)

    # -- Phase 4.8: Post-Processing Guardrails --
    response = format_response(
        answer_text=llm_result["answer_text"],
        source_url=llm_result["source_url"],
        last_updated=llm_result["last_updated"],
        response_type="factual",
    )

    return response
