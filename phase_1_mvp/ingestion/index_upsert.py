from __future__ import annotations

"""Stage F: Chroma Cloud vector store upsert.

Reads EmbeddingRecord JSONL files from EMBEDDINGS_DIR and upserts them
into a Chroma Cloud collection using pre-computed bge-large-en-v1.5 vectors.

Collection design (per architecture §9):
  - Store      : Chroma Cloud  (api.trychroma.com)
  - Client     : chromadb.CloudClient(tenant, database, api_key)
  - Collection : "mutual_fund_chunks"
  - Distance   : cosine
  - Document ID: chunk_id (UUID v5 — stable, idempotent upsert key)
  - Embedding  : 1024-dim L2-normalised float32 vector
  - Document   : raw chunk text (for context assembly)
  - Metadata   : source_url, scheme_name, section_name, field_type,
                 crawl_date, content_hash, embedding_model, embedded_at

Credentials are read from environment variables (set in Replit Secrets):
  CHROMA_API_KEY   — API key from https://app.trychroma.com
  CHROMA_TENANT    — Tenant ID from Chroma Cloud console
  CHROMA_DATABASE  — Database name from Chroma Cloud console

Upsert is idempotent: re-running on unchanged chunk IDs is a no-op.
Only embeddings from changed slugs (reported by Stage E) need to be sent.
"""

import json

import chromadb

from .config import (
    CHROMA_API_KEY,
    CHROMA_COLLECTION,
    CHROMA_DATABASE,
    CHROMA_TENANT,
    EMBEDDINGS_DIR,
    EMBED_QUERY_PREFIX,
)

_METADATA_FIELDS = (
    "source_url",
    "scheme_name",
    "section_name",
    "field_type",
    "crawl_date",
    "content_hash",
    "embedding_model",
    "embedded_at",
)


def _require_credentials() -> None:
    missing = [
        name for name, val in [
            ("CHROMA_API_KEY", CHROMA_API_KEY),
            ("CHROMA_TENANT",  CHROMA_TENANT),
            ("CHROMA_DATABASE", CHROMA_DATABASE),
        ]
        if not val
    ]
    if missing:
        raise EnvironmentError(
            f"Chroma Cloud credentials missing from environment: {', '.join(missing)}. "
            "Add them to Replit Secrets: CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE."
        )


def _get_client() -> chromadb.ClientAPI:
    _require_credentials()
    return chromadb.CloudClient(
        tenant=CHROMA_TENANT,
        database=CHROMA_DATABASE,
        api_key=CHROMA_API_KEY,
    )


def _get_collection(client: chromadb.ClientAPI) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_embeddings(slug_filter: list[str] | None = None) -> dict:
    """Upsert embedding records into Chroma Cloud.

    Args:
        slug_filter: if provided, only upsert records from these fund slugs.
                     Pass None to upsert all embedding files.

    Returns:
        dict with 'upserted', 'files', 'collection_count', 'collection'.
    """
    embedding_files = sorted(EMBEDDINGS_DIR.glob("*.jsonl"))
    if not embedding_files:
        print("  [chroma] No embedding files found — run embedding stage first.")
        return {"upserted": 0, "files": 0, "collection_count": 0}

    if slug_filter is not None:
        embedding_files = [p for p in embedding_files if p.stem in slug_filter]

    print(f"  [chroma] Connecting to Chroma Cloud "
          f"(tenant={CHROMA_TENANT!r}, database={CHROMA_DATABASE!r}) …")
    client = _get_client()
    collection = _get_collection(client)
    print(f"  [chroma] Connected — collection '{CHROMA_COLLECTION}'")

    total_upserted = 0
    total_files = 0

    for path in embedding_files:
        records = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        if not records:
            continue

        ids        = [r["chunk_id"] for r in records]
        embeddings = [r["embedding_vector"] for r in records]
        documents  = [r["text"] for r in records]
        metadatas  = [
            {k: r.get(k, "") for k in _METADATA_FIELDS}
            for r in records
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        total_upserted += len(records)
        total_files += 1
        print(
            f"  [chroma] Upserted {len(records):>2} chunks "
            f"from {path.name} -> Chroma Cloud collection '{CHROMA_COLLECTION}'"
        )

    count = collection.count()
    print(f"  [chroma] Cloud collection total: {count} documents")

    _run_sanity_check(collection)

    return {
        "upserted": total_upserted,
        "files": total_files,
        "collection_count": count,
        "collection": CHROMA_COLLECTION,
        "tenant": CHROMA_TENANT,
        "database": CHROMA_DATABASE,
    }


def _run_sanity_check(collection: chromadb.Collection) -> None:
    from .embed_pipeline import _get_model

    probes = [
        ("What is the expense ratio?",      "expense_ratio"),
        ("What is the minimum SIP amount?", "min_sip"),
        ("What is the exit load?",          "exit_load"),
    ]

    model = _get_model()
    print("  [chroma] Sanity check — top-2 retrieval for probe queries:")

    for question, expected_field in probes:
        query_text = EMBED_QUERY_PREFIX + question
        vec = model.encode(
            [query_text],
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).tolist()

        results = collection.query(
            query_embeddings=vec,
            n_results=2,
            include=["documents", "metadatas", "distances"],
        )

        print(f"    Q: {question!r}")
        for rank, (doc, meta, dist) in enumerate(
            zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ),
            1,
        ):
            sim = 1.0 - dist
            snippet = doc[:70].replace("\n", " ").encode("ascii", "replace").decode("ascii")
            hit = "Y" if meta.get("field_type") == expected_field else "."
            print(
                f"      #{rank} {hit} sim={sim:.4f}  "
                f"[{meta.get('field_type')}] [{meta.get('scheme_name', '')[:30]}]  "
                f"{snippet!r}"
            )
