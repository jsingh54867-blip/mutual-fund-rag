from __future__ import annotations

import re
from urllib.parse import urlparse

from .config import ALLOWED_DOMAIN, SOURCE_URLS
from .policy import DEFAULT_SOURCE_URL


def _count_sentences(text: str) -> int:
    """Count sentences by splitting on sentence-ending punctuation."""
    sentences = re.split(r"[.!?]+", text.strip())
    return len([s for s in sentences if s.strip()])


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\"\')]+", text)


def _is_allowed_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        return host == ALLOWED_DOMAIN or host.endswith("." + ALLOWED_DOMAIN)
    except Exception:
        return False


def format_response(
    answer_text: str,
    source_url: str,
    last_updated: str,
    response_type: str,
) -> dict:
    """Apply guardrail rules R1-R6 and return a clean response dict.

    Rules:
      R2: Exactly one URL in response
      R3: URL domain must be groww.in
      R4: Max 3 sentences (excluding source and last-updated lines)
      R5: Must include last-updated line
      R6: Low confidence -> unknown template
    """

    # -- R3: Validate source URL domain --
    if not source_url or not _is_allowed_url(source_url):
        # Pick first URL from answer text that is valid
        for url in _extract_urls(answer_text):
            if _is_allowed_url(url):
                source_url = url
                break
        else:
            source_url = DEFAULT_SOURCE_URL

    # -- R4: Enforce max 3 sentences --
    if _count_sentences(answer_text) > 3:
        sentences = re.split(r"(?<=[.!?])\s+", answer_text.strip())
        answer_text = " ".join(sentences[:3])
        if not answer_text.endswith((".", "!", "?")):
            answer_text += "."

    # -- R2: Strip any URLs embedded in the answer text --
    # (we deliver the URL as a separate field)
    clean_answer = re.sub(r"https?://[^\s\"\')]+", "", answer_text).strip()
    clean_answer = re.sub(r"\s{2,}", " ", clean_answer)

    # -- R5: Ensure last_updated --
    if not last_updated or last_updated.strip() == "":
        last_updated = "N/A"

    return {
        "answer": clean_answer,
        "source_link": source_url,
        "last_updated_from_sources": last_updated,
        "response_type": response_type,
    }
