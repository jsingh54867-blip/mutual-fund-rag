"""Phase 2: Cross-Encoder Reranker

Improved retrieval reranking using a cross-encoder model for more accurate
semantic matching between queries and retrieved chunks.

Falls back to the Phase 1 heuristic reranker when the cross-encoder model
is unavailable (e.g., on first cold start or memory-constrained environments).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.retriever import RetrievedChunk

logger = logging.getLogger(__name__)

# Cross-encoder model (lazy-loaded)
_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_reranker = None


def _get_reranker():
    """Lazy-load the cross-encoder model."""
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder(_RERANKER_MODEL)
            logger.info("Cross-encoder reranker loaded: %s", _RERANKER_MODEL)
        except Exception as e:
            logger.warning("Failed to load cross-encoder reranker: %s", e)
            return None
    return _reranker


@dataclass
class RerankedChunk:
    """A chunk with its reranking score."""
    chunk: "RetrievedChunk"
    rerank_score: float
    combined_score: float


def rerank_with_cross_encoder(
    query: str,
    chunks: list["RetrievedChunk"],
    top_n: int = 4,
    similarity_weight: float = 0.4,
    rerank_weight: float = 0.6,
) -> list["RetrievedChunk"]:
    """Rerank chunks using a cross-encoder model combined with similarity scores.

    Args:
        query: The user's query.
        chunks: List of retrieved chunks from the vector store.
        top_n: Number of top chunks to return after reranking.
        similarity_weight: Weight for the original similarity score.
        rerank_weight: Weight for the cross-encoder score.

    Returns:
        Reranked list of chunks, limited to top_n.
    """
    if not chunks:
        return chunks

    reranker = _get_reranker()
    if reranker is None:
        logger.info("Cross-encoder unavailable, falling back to heuristic rerank")
        return _heuristic_fallback(query, chunks, top_n)

    # Build query-chunk pairs for cross-encoder scoring
    pairs = [(query, chunk.text) for chunk in chunks]

    try:
        scores = reranker.predict(pairs)
    except Exception as e:
        logger.warning("Cross-encoder prediction failed: %s", e)
        return _heuristic_fallback(query, chunks, top_n)

    # Normalize cross-encoder scores to [0, 1] range
    if hasattr(scores, 'tolist'):
        score_list = scores.tolist()
    else:
        score_list = list(scores)

    min_s = min(score_list) if score_list else 0.0
    max_s = max(score_list) if score_list else 1.0
    score_range = max_s - min_s if max_s > min_s else 1.0

    reranked: list[RerankedChunk] = []
    for chunk, raw_score in zip(chunks, score_list):
        normalized_rerank = (raw_score - min_s) / score_range
        combined = (
            similarity_weight * chunk.similarity
            + rerank_weight * normalized_rerank
        )
        chunk.rank_score = combined
        reranked.append(RerankedChunk(
            chunk=chunk,
            rerank_score=normalized_rerank,
            combined_score=combined,
        ))

    # Sort by combined score descending
    reranked.sort(key=lambda rc: rc.combined_score, reverse=True)

    return [rc.chunk for rc in reranked[:top_n]]


def _heuristic_fallback(
    query: str,
    chunks: list["RetrievedChunk"],
    top_n: int,
) -> list["RetrievedChunk"]:
    """Fallback reranking using term overlap heuristics (Phase 1 approach)."""
    import re
    q_terms = set(re.findall(r"\w+", query.lower()))

    for chunk in chunks:
        chunk_terms = set(re.findall(r"\w+", chunk.text.lower()))
        if q_terms:
            coverage = len(q_terms & chunk_terms) / len(q_terms)
        else:
            coverage = 0.0

        score = chunk.similarity * 2.0 + coverage * 0.5
        chunk.rank_score = score

    chunks.sort(key=lambda c: c.rank_score, reverse=True)
    return chunks[:top_n]
