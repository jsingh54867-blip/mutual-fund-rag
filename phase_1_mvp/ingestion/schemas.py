"""Shared data-model definitions for the chunking and embedding pipeline.

The Chunk is the core unit produced by Stage B and consumed by all
downstream stages (versioning, embedding, vector upsert).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Literal

FieldType = Literal[
    "expense_ratio",
    "exit_load",
    "min_sip",
    "lock_in",
    "riskometer",
    "benchmark",
    "statement_process",
    "other",
]


@dataclass
class Chunk:
    """One retrieval-ready text unit with full provenance metadata.

    Matches the Chunk Record schema from section 5.2 of the architecture doc.
    """

    # Provenance
    source_url: str
    source_domain: str
    document_type: str
    scheme_name: str
    crawl_date: str

    # Content
    text: str
    section_name: str           # block_type from Stage A (e.g. "fees_block")
    field_type: FieldType       # primary field classification
    field_types: list[str]      # all matched field types (may be multi)

    # Versioning
    chunk_version: str = "1"
    is_active: bool = True

    # Computed on init via __post_init__
    chunk_id: str = field(default="", init=False)
    content_hash: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.content_hash = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        # Stable UUID v5 — same text + url always produces same id.
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        seed = f"{self.source_url}::{self.text}"
        self.chunk_id = str(uuid.uuid5(namespace, seed))

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_url": self.source_url,
            "source_domain": self.source_domain,
            "document_type": self.document_type,
            "scheme_name": self.scheme_name,
            "crawl_date": self.crawl_date,
            "section_name": self.section_name,
            "field_type": self.field_type,
            "field_types": self.field_types,
            "chunk_version": self.chunk_version,
            "is_active": self.is_active,
            "content_hash": self.content_hash,
            "char_count": len(self.text),
            "text": self.text,
        }
