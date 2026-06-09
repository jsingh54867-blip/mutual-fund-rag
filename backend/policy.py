from __future__ import annotations

from .config import ALLOWED_DOMAIN, SOURCE_URLS

# -- Refusal templates --

REFUSAL_ADVICE = (
    "I can only provide factual information about mutual fund schemes. "
    "I cannot offer investment advice, recommendations, or opinions."
)

REFUSAL_COMPARISON = (
    "I can only provide factual information about individual mutual fund schemes. "
    "I cannot compare funds or suggest which is better."
)

REFUSAL_CALCULATION = (
    "I can only provide factual information from official scheme pages. "
    "I cannot calculate or project returns."
)

UNKNOWN_ANSWER = (
    "I don't know based on the available official sources."
)

OUT_OF_SCOPE_ANSWER = (
    "I can only answer questions about Motilal Oswal Mutual Funds. "
    "Please ask about fund performance, NAV, holdings, or related topics."
)

DEFAULT_SOURCE_URL = SOURCE_URLS[0] if SOURCE_URLS else f"https://{ALLOWED_DOMAIN}"

REFUSAL_RESPONSE = {
    "answer": REFUSAL_ADVICE,
    "source_link": None,
    "last_updated_from_sources": None,
    "response_type": "refusal",
}

UNKNOWN_RESPONSE = {
    "answer": UNKNOWN_ANSWER,
    "source_link": None,
    "last_updated_from_sources": None,
    "response_type": "unknown",
}

OUT_OF_SCOPE_RESPONSE = {
    "answer": OUT_OF_SCOPE_ANSWER,
    "source_link": None,
    "last_updated_from_sources": None,
    "response_type": "out_of_scope",
}
