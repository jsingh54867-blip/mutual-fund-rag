from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .config import EMBED_BATCH_SIZE, EMBED_DIM, EMBED_MODEL

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as _STType

_MODEL: "_STType | None" = None


def _get_model() -> "_STType":
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        print(f"  [embed] Loading model {EMBED_MODEL} ...", flush=True)
        _MODEL = SentenceTransformer(EMBED_MODEL)
    return _MODEL


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Embed a list of chunk dicts and return EmbeddingRecord dicts.

    Each output dict contains all chunk metadata plus:
      embedding_vector  : list[float] of length EMBED_DIM (1024)
      embedding_model   : str
      embedding_dim     : int
      embedded_at       : ISO-8601 UTC timestamp
    """
    if not chunks:
        return []

    model = _get_model()
    texts = [c["text"] for c in chunks]

    raw: np.ndarray = model.encode(
        texts,
        batch_size=EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    assert raw.shape == (len(chunks), EMBED_DIM), (
        f"Unexpected embedding shape {raw.shape}; expected ({len(chunks)}, {EMBED_DIM})"
    )

    now = datetime.datetime.utcnow().isoformat() + "Z"
    records: list[dict] = []

    for chunk, vec in zip(chunks, raw):
        rec = {
            "chunk_id": chunk["chunk_id"],
            "source_url": chunk["source_url"],
            "scheme_name": chunk["scheme_name"],
            "section_name": chunk["section_name"],
            "field_type": chunk["field_type"],
            "field_types": chunk["field_types"],
            "text": chunk["text"],
            "crawl_date": chunk.get("crawl_date", ""),
            "content_hash": chunk["content_hash"],
            "embedding_vector": vec.tolist(),
            "embedding_model": EMBED_MODEL,
            "embedding_dim": EMBED_DIM,
            "embedded_at": now,
        }
        records.append(rec)

    return records
