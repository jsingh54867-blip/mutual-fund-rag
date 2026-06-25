from **future** import annotations

import re
from dataclasses import dataclass, field

import chromadb

from .config import (
CHROMA_API_KEY,
CHROMA_COLLECTION,
CHROMA_DATABASE,
CHROMA_TENANT,
RERANK_TOP_N,
SIMILARITY_THRESHOLD,
TOP_K,
)

_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None

# ---------------------------------------------------------------------------

# Lazy singletons

# ---------------------------------------------------------------------------

def _get_collection() -> chromadb.Collection:
global _client, _collection

```
if _collection is None:
    print("========== CONNECTING TO CHROMA ==========", flush=True)

    _client = chromadb.CloudClient(
        tenant=CHROMA_TENANT,
        database=CHROMA_DATABASE,
        api_key=CHROMA_API_KEY,
    )

    _collection = _client.get_collection(
        name=CHROMA_COLLECTION,
    )

    print("========== CHROMA CONNECTED ==========", flush=True)

return _collection
```

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

# Query preprocessing

# ---------------------------------------------------------------------------

_SYNONYMS = {
"systematic investment plan": "sip",
"systematic investment": "sip",
"net asset value": "nav",
"assets under management": "aum",
"fund size": "aum",
}

_FIELD_TYPE_HINTS = [
("expense_ratio", ["expense ratio", "expense", "ter"]),
("exit_load", ["exit load", "exit", "load"]),
("min_sip", ["minimum sip", "min sip", "sip amount"]),
("riskometer", ["riskometer", "risk level", "risk"]),
("benchmark", ["benchmark"]),
]

def _normalize_query(query: str) -> str:
q = query.lower().strip()

```
for long, short in _SYNONYMS.items():
    q = q.replace(long, short)

return q
```

def _infer_field_type(query: str) -> str | None:
q = query.lower()

```
for field_type, keywords in _FIELD_TYPE_HINTS:
    for kw in keywords:
        if kw in q:
            return field_type

return None
```

# ---------------------------------------------------------------------------

# Re-ranking

# ---------------------------------------------------------------------------

def _rerank(
chunks: list[RetrievedChunk],
query: str,
target_field: str | None,
) -> list[RetrievedChunk]:

```
q_terms = set(re.findall(r"\w+", query.lower()))

for chunk in chunks:
    score = chunk.similarity

    chunk_terms = set(re.findall(r"\w+", chunk.text.lower()))

    if q_terms:
        coverage = len(q_terms & chunk_terms) / len(q_terms)
        score += coverage

    if target_field and chunk.field_type == target_field:
        score += 1.0

    chunk.rank_score = score

chunks.sort(key=lambda x: x.rank_score, reverse=True)

return chunks
```

# ---------------------------------------------------------------------------

# Public API

# ---------------------------------------------------------------------------

def retrieve(query: str) -> RetrievalResult:

```
collection = _get_collection()

normalized = _normalize_query(query)
target_field = _infer_field_type(query)

print("========== QUERYING CHROMA ==========", flush=True)

results = collection.query(
    query_texts=[normalized],
    n_results=TOP_K,
    include=["documents", "metadatas", "distances"],
)

chunks: list[RetrievedChunk] = []

docs = results.get("documents", [[]])[0]
metas = results.get("metadatas", [[]])[0]
dists = results.get("distances", [[]])[0]

for doc, meta, dist in zip(docs, metas, dists):

    similarity = 1.0 - float(dist)

    chunks.append(
        RetrievedChunk(
            chunk_id=meta.get("content_hash", ""),
            text=doc,
            source_url=meta.get("source_url", ""),
            scheme_name=meta.get("scheme_name", ""),
            section_name=meta.get("section_name", ""),
            field_type=meta.get("field_type", ""),
            crawl_date=meta.get("crawl_date", ""),
            similarity=similarity,
        )
    )

chunks = _rerank(
    chunks=chunks,
    query=query,
    target_field=target_field,
)

top_chunks = chunks[:RERANK_TOP_N]

top_chunks = [
    c for c in top_chunks
    if c.similarity >= SIMILARITY_THRESHOLD
]

citation_urls: list[str] = []
seen: set[str] = set()

for chunk in top_chunks:
    if chunk.source_url and chunk.source_url not in seen:
        seen.add(chunk.source_url)
        citation_urls.append(chunk.source_url)

top_similarity = (
    top_chunks[0].similarity
    if top_chunks
    else 0.0
)

return RetrievalResult(
    chunks=top_chunks,
    top_similarity=top_similarity,
    citation_urls=citation_urls,
)
```
