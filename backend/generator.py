from __future__ import annotations

import json

from openai import OpenAI

from .config import GROQ_API_KEY, GROQ_BASE_URL, LLM_MODEL
from .retriever import RetrievalResult

_client: OpenAI | None = None

SYSTEM_PROMPT = """\
You are a facts-only mutual fund information assistant.

STRICT RULES:
1. Answer ONLY from the provided context below. Never use outside knowledge.
2. If the answer is not in the context, respond: "I don't know based on the available official sources."
3. Do NOT provide investment advice, opinions, or recommendations.
4. Maximum 3 sentences in your answer.
5. Include exactly one source URL from the context.
6. End with a line: "Last updated from sources: <crawl_date>"

OUTPUT FORMAT (respond in valid JSON only):
{
  "answer_text": "Your factual answer here (max 3 sentences).",
  "source_url": "https://groww.in/...",
  "last_updated": "the crawl_date from the most relevant chunk"
}
"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    return _client


def _build_context(result: RetrievalResult) -> str:
    parts: list[str] = []
    for i, chunk in enumerate(result.chunks, 1):
        parts.append(
            f"[Chunk {i}]\n"
            f"Scheme: {chunk.scheme_name}\n"
            f"Section: {chunk.section_name}\n"
            f"Field type: {chunk.field_type}\n"
            f"Source URL: {chunk.source_url}\n"
            f"Crawl date: {chunk.crawl_date}\n"
            f"Text:\n{chunk.text}\n"
        )
    return "\n---\n".join(parts)


def generate(query: str, retrieval: RetrievalResult) -> dict:
    """Call the LLM to generate a factual answer from retrieved context.

    Returns dict with keys: answer_text, source_url, last_updated.
    """
    if not retrieval.chunks:
        return {
            "answer_text": "I don't know based on the available official sources.",
            "source_url": retrieval.citation_urls[0] if retrieval.citation_urls else "",
            "last_updated": "N/A",
        }

    context = _build_context(retrieval)
    user_message = (
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        f"Respond in valid JSON only."
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,
        max_tokens=300,
    )

    raw = response.choices[0].message.content or ""

    # Parse JSON response from LLM
    try:
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        return {
            "answer_text": parsed.get("answer_text", raw),
            "source_url": parsed.get("source_url", ""),
            "last_updated": parsed.get("last_updated", "N/A"),
        }
    except (json.JSONDecodeError, KeyError):
        # Fallback: use raw text as answer
        fallback_url = retrieval.citation_urls[0] if retrieval.citation_urls else ""
        crawl = retrieval.chunks[0].crawl_date if retrieval.chunks else "N/A"
        return {
            "answer_text": raw.strip(),
            "source_url": fallback_url,
            "last_updated": crawl,
        }
