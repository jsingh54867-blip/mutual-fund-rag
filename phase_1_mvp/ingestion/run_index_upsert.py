from __future__ import annotations

"""CLI runner for Stage F: ChromaDB upsert."""

import argparse

from .index_upsert import upsert_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage F: upsert embeddings into ChromaDB collection"
    )
    parser.add_argument(
        "--slugs",
        nargs="*",
        metavar="SLUG",
        help="Only upsert specific fund slugs (default: all)",
    )
    args = parser.parse_args()

    result = upsert_embeddings(slug_filter=args.slugs)
    print(
        f"\nDone — {result['upserted']} chunks upserted across "
        f"{result['files']} files. "
        f"Collection '{result['collection']}' now has "
        f"{result['collection_count']} documents."
    )


if __name__ == "__main__":
    main()
