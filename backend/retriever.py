from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import RERANK_TOP_N, SIMILARITY_THRESHOLD, TOP_K


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_DIR = PROJECT_ROOT / "phase_1_mvp" / "data" / "chunks"

_chunks_cache: list["RetrievedChunk"] | None = None


def clear_chunk_cache() -> None:
    global _chunks_cache
    _chunks_cache = None


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    source_url: str
    scheme_name: str
    section_name: str
    field_type: str
    crawl_date: str
    similarity: float
    rank_score: float = 0.0


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    top_similarity: float = 0.0
    citation_urls: list[str] = field(default_factory=list)


_SYNONYMS = {
    "systematic investment plan": "sip",
    "systematic investment": "sip",
    "net asset value": "nav",
    "assets under management": "aum",
    "fund size": "aum",
    "minimum investment": "minimum sip",
    "3y": "3 year",
    "mo ": "motilal oswal ",
}

_SCHEME_ALIASES: list[tuple[str, str]] = [
    (
        "large and midcap",
        "Motilal Oswal Large and Midcap Fund Direct Growth",
    ),
    (
        "large midcap",
        "Motilal Oswal Large and Midcap Fund Direct Growth",
    ),
    (
        "large & midcap",
        "Motilal Oswal Large and Midcap Fund Direct Growth",
    ),
    (
        "bse enhanced value",
        "Motilal Oswal BSE Enhanced Value Index Fund Direct Growth",
    ),
    (
        "enhanced value",
        "Motilal Oswal BSE Enhanced Value Index Fund Direct Growth",
    ),
    (
        "gold and silver",
        "Motilal Oswal Gold and Silver Passive FoF Direct Growth",
    ),
    (
        "gold silver",
        "Motilal Oswal Gold and Silver Passive FoF Direct Growth",
    ),
    (
        "india defence",
        "Motilal Oswal Nifty India Defence Index Fund Direct Growth",
    ),
    (
        "defence",
        "Motilal Oswal Nifty India Defence Index Fund Direct Growth",
    ),
    (
        "momentum 50",
        "Motilal Oswal Nifty 500 Momentum 50 Index Fund Direct Growth",
    ),
    (
        "nifty 500 momentum",
        "Motilal Oswal Nifty 500 Momentum 50 Index Fund Direct Growth",
    ),
    (
        "small cap",
        "Motilal Oswal Small Cap Fund Direct Growth",
    ),
    (
        "midcap",
        "Motilal Oswal Midcap Fund Direct Growth",
    ),
    (
        "mid cap",
        "Motilal Oswal Midcap Fund Direct Growth",
    ),
]

_FIELD_TYPE_HINTS: list[tuple[str, list[str]]] = [
    ("expense_ratio", ["expense ratio", "expense", "ter"]),
    ("exit_load", ["exit load", "exit", "load"]),
    ("min_sip", ["minimum sip", "min sip", "sip amount", "minimum investment"]),
    ("riskometer", ["riskometer", "risk level", "risk"]),
    ("benchmark", ["benchmark"]),
    ("nav", ["nav", "net asset value"]),
    ("aum", ["aum", "assets under management", "fund size"]),
    ("holdings", ["holdings", "holding", "portfolio", "stocks"]),
    ("returns", ["returns", "return", "performance", "1 year", "3 year", "5 year"]),
    ("statement_process", ["capital gains", "tax statement", "statement"]),
]

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "can",
    "do",
    "does",
    "for",
    "from",
    "give",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "please",
    "tell",
    "the",
    "to",
    "what",
    "which",
    "with",
    "you",
}

_GENERIC_SCHEME_WORDS = {
    "direct",
    "fund",
    "growth",
    "index",
    "motilal",
    "oswal",
    "plan",
}


def _normalize_query(query: str) -> str:
    normalized = query.lower().strip()

    for long_form, short_form in _SYNONYMS.items():
        normalized = normalized.replace(long_form, short_form)

    return normalized


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if word not in _STOP_WORDS and len(word) > 1}


def _infer_field_type(query: str) -> str | None:
    query_lower = query.lower()

    for field_type, keywords in _FIELD_TYPE_HINTS:
        if any(keyword in query_lower for keyword in keywords):
            return field_type

    return None


def _infer_scheme_name(query: str, known_schemes: list[str]) -> str | None:
    query_tokens = _tokens(_normalize_query(query))
    normalized_query = _normalize_query(query)
    known_scheme_set = set(known_schemes)

    for alias, scheme_name in _SCHEME_ALIASES:
        if alias in normalized_query and scheme_name in known_scheme_set:
            return scheme_name

    best_scheme: str | None = None
    best_matches = 0

    for scheme_name in known_schemes:
        scheme_tokens = _tokens(scheme_name) - _GENERIC_SCHEME_WORDS
        matches = len(query_tokens & scheme_tokens)
        compact_scheme = _compact(scheme_name)
        compact_query = _compact(normalized_query)

        if compact_scheme and compact_scheme in compact_query:
            return scheme_name

        if matches > best_matches:
            best_matches = matches
            best_scheme = scheme_name

    if best_matches >= 2:
        return best_scheme

    return None


def _mentions_unmatched_scheme(query: str) -> bool:
    normalized_query = _normalize_query(query)
    query_terms = _tokens(normalized_query)

    if not ({"motilal", "oswal"} & query_terms):
        return False

    scheme_terms = {
        "bse",
        "defence",
        "enhanced",
        "flexi",
        "fof",
        "gold",
        "large",
        "mid",
        "midcap",
        "momentum",
        "nifty",
        "passive",
        "silver",
        "small",
        "value",
    }

    return bool(query_terms & scheme_terms)


def _chunk_matches_field(chunk: RetrievedChunk, target_field: str | None) -> bool:
    if not target_field:
        return True

    searchable_text = f"{chunk.field_type} {chunk.section_name} {chunk.text}".lower()

    if chunk.field_type == target_field:
        return True

    field_markers = {
        "nav": ["nav:"],
        "aum": ["aum", "fund size"],
        "expense_ratio": ["expense ratio"],
        "exit_load": ["exit load"],
        "min_sip": ["minimum sip", "minimum investments"],
        "holdings": ["holdings"],
        "returns": ["historic returns", "fund returns", "year"],
        "benchmark": ["benchmark"],
        "riskometer": ["riskometer", "risk level"],
        "statement_process": ["capital gains", "tax statement", "tax implication"],
    }

    return any(
        marker in searchable_text
        for marker in field_markers.get(target_field, [target_field.replace("_", " ")])
    )


def _load_chunks() -> list[RetrievedChunk]:
    global _chunks_cache

    if _chunks_cache is not None:
        return _chunks_cache

    if not CHUNKS_DIR.exists():
        raise RuntimeError(
            f"Chunk folder not found: {CHUNKS_DIR}. "
            "Make sure phase_1_mvp/data/chunks is committed to GitHub."
        )

    chunk_files = sorted(CHUNKS_DIR.glob("*.jsonl"))

    if not chunk_files:
        raise RuntimeError(
            f"No JSONL chunk files found in {CHUNKS_DIR}. "
            "Make sure the chunk data is committed to GitHub."
        )

    chunks: list[RetrievedChunk] = []

    for file_path in chunk_files:
        for line_number, line in enumerate(
            file_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            text = str(
                record.get("text")
                or record.get("chunk_text")
                or record.get("content")
                or ""
            ).strip()

            if not text:
                continue

            field_type = str(record.get("field_type") or "").strip()

            if not field_type:
                field_types = record.get("field_types", [])

                if isinstance(field_types, list) and field_types:
                    field_type = str(field_types[0])

                elif isinstance(field_types, str):
                    field_type = field_types

                else:
                    field_type = "other"

            chunks.append(
                RetrievedChunk(
                    chunk_id=str(
                        record.get("chunk_id")
                        or record.get("content_hash")
                        or f"{file_path.stem}-{line_number}"
                    ),
                    text=text,
                    source_url=str(record.get("source_url") or ""),
                    scheme_name=str(record.get("scheme_name") or file_path.stem),
                    section_name=str(record.get("section_name") or ""),
                    field_type=field_type,
                    crawl_date=str(record.get("crawl_date") or ""),
                    similarity=0.0,
                )
            )

    if not chunks:
        raise RuntimeError("Chunk files were found, but no readable chunks were loaded.")

    _chunks_cache = chunks
    return chunks


def _score_chunk(
    chunk: RetrievedChunk,
    query_terms: set[str],
    target_field: str | None,
    target_scheme: str | None,
) -> float:
    if target_scheme and chunk.scheme_name.lower() != target_scheme.lower():
        return 0.0

    searchable_text = " ".join(
        [
            chunk.scheme_name,
            chunk.section_name,
            chunk.field_type,
            chunk.text,
        ]
    )

    chunk_terms = _tokens(searchable_text)

    coverage = 0.0

    if query_terms:
        coverage = len(query_terms & chunk_terms) / len(query_terms)

    score = coverage * 0.60

    if target_field and _chunk_matches_field(chunk, target_field):
        score += 0.75

    if target_scheme and chunk.scheme_name.lower() == target_scheme.lower():
        score += 1.0

    if target_scheme:
        scheme_terms = _tokens(target_scheme) - _GENERIC_SCHEME_WORDS

        if scheme_terms and scheme_terms.issubset(_tokens(chunk.scheme_name)):
            score += 0.25

    return score


def retrieve(query: str) -> RetrievalResult:
    all_chunks = _load_chunks()

    normalized_query = _normalize_query(query)
    query_terms = _tokens(normalized_query)
    target_field = _infer_field_type(normalized_query)

    known_schemes = list(
        {
            chunk.scheme_name
            for chunk in all_chunks
            if chunk.scheme_name
        }
    )

    target_scheme = _infer_scheme_name(normalized_query, known_schemes)

    if target_scheme is None and _mentions_unmatched_scheme(normalized_query):
        return RetrievalResult()

    ranked_chunks: list[RetrievedChunk] = []

    for chunk in all_chunks:
        score = _score_chunk(
            chunk=chunk,
            query_terms=query_terms,
            target_field=target_field,
            target_scheme=target_scheme,
        )

        if score <= 0:
            continue

        chunk.similarity = score
        chunk.rank_score = score
        ranked_chunks.append(chunk)

    ranked_chunks.sort(key=lambda item: item.rank_score, reverse=True)

    candidate_chunks = ranked_chunks[:TOP_K]

    top_chunks = [
        chunk
        for chunk in candidate_chunks[:RERANK_TOP_N]
        if chunk.similarity >= SIMILARITY_THRESHOLD
    ]

    citation_urls: list[str] = []
    seen_urls: set[str] = set()

    for chunk in top_chunks:
        if chunk.source_url and chunk.source_url not in seen_urls:
            seen_urls.add(chunk.source_url)
            citation_urls.append(chunk.source_url)

    top_similarity = top_chunks[0].similarity if top_chunks else 0.0

    return RetrievalResult(
        chunks=top_chunks,
        top_similarity=top_similarity,
        citation_urls=citation_urls,
    )
