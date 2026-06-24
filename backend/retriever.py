from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import chromadb
import numpy as np

from .config import (
    CHROMA_API_KEY,
    CHROMA_COLLECTION,
    CHROMA_DATABASE,
    CHROMA_TENANT,
    EMBED_MODEL,
    EMBED_QUERY_PREFIX,
    RERANK_TOP_N,
    SIMILARITY_THRESHOLD,
    TOP_K,
)

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as _STType

_model: "_STType | None" = None
_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None


# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

def _get_model() -> "_STType":
    global _model

    if _model is None:
        print("========== LOADING MODEL ==========", flush=True)

        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

        print("========== MODEL LOADED ==========", flush=True)

    return _model


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is None:
        _client = chromadb.CloudClient(
            tenant=CHROMA_TENANT,
            database=CHROMA_DATABASE,
            api_key=CHROMA_API_KEY,
        )
        _collection = _client.get_collection(
            name=CHROMA_COLLECTION,
        )
    return _collection


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Query pre-processing
# ---------------------------------------------------------------------------

_SYNONYMS = {
    "systematic investment plan": "sip",
    "systematic investment": "sip",
    "net asset value": "nav",
    "assets under management": "aum",
    "fund size": "aum",
}

_FIELD_TYPE_HINTS: list[tuple[str, list[str]]] = [
    ("expense_ratio", ["expense ratio", "expense", "ter"]),
    ("exit_load", ["exit load", "exit", "load"]),
    ("min_sip", ["minimum sip", "min sip", "sip amount", "minimum investment"]),
    ("riskometer", ["riskometer", "risk level", "risk"]),
    ("benchmark", ["benchmark"]),
    ("statement_process", ["capital gains", "tax statement", "statement", "how to get"]),
]


def _normalize_query(query: str) -> str:
    q = query.lower().strip()
    for long, short in _SYNONYMS.items():
        q = q.replace(long, short)
    return q


def _infer_field_type(query: str) -> str | None:
    q = query.lower()
    for field_type, keywords in _FIELD_TYPE_HINTS:
        for kw in keywords:
            if kw in q:
                return field_type
    return None


def _infer_scheme_name(query: str, known_schemes: list[str]) -> str | None:
    q = query.lower()
    best_scheme = None
    best_score = 0
    for scheme in known_schemes:
        words = scheme.lower().split()
        # Count matching significant words (length > 2)
        matches = sum(1 for w in words if len(w) > 2 and w in q)
        if matches > best_score and matches >= 2:
            best_score = matches
            best_scheme = scheme
    return best_scheme


# ---------------------------------------------------------------------------
# Re-ranking
# ---------------------------------------------------------------------------

def _rerank(
    chunks: list[RetrievedChunk],
    query: str,
    target_field: str | None,
    target_scheme: str | None,
) -> list[RetrievedChunk]:
    q_terms = set(re.findall(r"\w+", query.lower()))

    for chunk in chunks:
        score = chunk.similarity * 2.0  # base similarity weight

        # Query-term coverage bonus
        chunk_terms = set(re.findall(r"\w+", chunk.text.lower()))
        if q_terms:
            coverage = len(q_terms & chunk_terms) / len(q_terms)
            score += coverage * 0.5

        # Metadata match bonuses
        if target_field and chunk.field_type == target_field:
            score += 1.0
        if target_scheme and chunk.scheme_name.lower() == target_scheme.lower():
            score += 0.8

        chunk.rank_score = score

    chunks.sort(key=lambda c: c.rank_score, reverse=True)
    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve(query: str) -> RetrievalResult:
    """Retrieve the most relevant chunks for a user query."""
    collection = _get_collection()
    model = _get_model()

    normalized = _normalize_query(query)
    target_field = _infer_field_type(query)

    # Get known scheme names from a quick peek at the collection
    peek = collection.peek(limit=100)
    known_schemes = list({
        m.get("scheme_name", "")
        for m in (peek.get("metadatas") or [])
        if m.get("scheme_name")
    })
    target_scheme = _infer_scheme_name(query, known_schemes)

    # Embed the query with BGE query prefix
    query_text = EMBED_QUERY_PREFIX + normalized
    vec = model.encode(
        [query_text],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).tolist()

    # Build optional where filter
    where_filter = None
    if target_scheme:
        where_filter = {"scheme_name": target_scheme}

    results = collection.query(
        query_embeddings=vec,
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
        where=where_filter,
    )

    # If scheme filter returned too few results, retry without filter
    docs = results.get("documents", [[]])[0]
    if len(docs) < 2 and where_filter:
        results = collection.query(
            query_embeddings=vec,
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"],
        )

    chunks: list[RetrievedChunk] = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        sim = 1.0 - dist  # cosine distance -> similarity
        chunks.append(RetrievedChunk(
            chunk_id=meta.get("content_hash", ""),
            text=doc,
            source_url=meta.get("source_url", ""),
            scheme_name=meta.get("scheme_name", ""),
            section_name=meta.get("section_name", ""),
            field_type=meta.get("field_type", ""),
            crawl_date=meta.get("crawl_date", ""),
            similarity=sim,
        ))

    # Re-rank
    chunks = _rerank(chunks, query, target_field, target_scheme)

    # Take top N after re-ranking
    top_chunks = chunks[:RERANK_TOP_N]

    # Filter by similarity threshold
    top_chunks = [c for c in top_chunks if c.similarity >= SIMILARITY_THRESHOLD]

    # Deduplicate citation URLs (preserve order)
    seen_urls: set[str] = set()
    citation_urls: list[str] = []
    for c in top_chunks:
        if c.source_url and c.source_url not in seen_urls:
            seen_urls.add(c.source_url)
            citation_urls.append(c.source_url)

    top_sim = top_chunks[0].similarity if top_chunks else 0.0

    return RetrievalResult(
        chunks=top_chunks,
        top_similarity=top_sim,
        citation_urls=citation_urls,
    )
