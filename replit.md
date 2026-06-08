# Mutual Fund RAG Prototype

## Overview
A Python-based Retrieval-Augmented Generation (RAG) data ingestion pipeline for mutual fund scheme information. It scrapes mutual fund pages from Groww, normalizes the content, detects changes via SHA-256 hashing, and stores structured JSON output for downstream chunking and embedding.

## Project Structure
- `phase_1_mvp/` - Active MVP implementation
  - `ingestion/` - Core pipeline: scraping, parsing, change detection, source registry
  - `requirements.txt` - Python dependencies (beautifulsoup4, requests)
- `phase_2_hardening/` - Placeholder for table parsing, reranking, testing
- `phase_3_operational/` - Placeholder for scheduling and monitoring

## Running the Pipeline
```bash
cd phase_1_mvp && python -m ingestion.run_ingestion
```

## Architecture
1. Loads URLs from `sources.csv` (7 Groww mutual fund scheme pages)
2. Fetches HTML with retry logic
3. Parses and normalizes content using BeautifulSoup4
4. Extracts structured key metrics: NAV, Min. for SIP, Fund Size (AUM in Cr), Expense Ratio, Rating
5. Detects changes via SHA-256 hash comparison against `page_state.json`
6. Saves raw HTML to `data/raw_pages/` and cleaned JSON to `data/processed_pages/`
7. Generates `changed_urls.json` for incremental downstream processing

## Processed JSON Structure (`data/processed_pages/`)
Each file contains:
- `scheme_name`, `source_url`, `crawl_date`, `page_hash`, `parse_confidence`
- `metrics` block with:
  - `nav` — current NAV value (e.g. "105.96")
  - `nav_date` — date of the NAV (e.g. "15 Apr '26")
  - `min_sip` — minimum SIP amount in ₹ (e.g. "500")
  - `fund_size_cr` — AUM in crores (e.g. "31,046.66")
  - `expense_ratio` — as a percentage string (e.g. "0.85%")
  - `rating` — numeric rating as string, or null if unrated
- `text` — full normalized page text for RAG chunking

## Stage A: Structural Segmentation (`data/segmented_pages/`)
Module: `ingestion/segmenter.py` | Runner: `ingestion/run_segmentation.py`

Each processed JSON is split into named semantic blocks before chunking:
- `header_block` — scheme name
- `facts_block` — returns history, returns rankings, expense ratio description
- `fees_block` — minimum investments, exit load, stamp duty details
- `process_block` — capital gains/LTCG/STCG tax descriptions, tax implication
- `risk_benchmark_block` — riskometer, benchmark (when present)
- `other_block` — holdings table, compare similar funds, fund management

Rules: keyword-anchored transitions, sticky assignment for non-anchor lines,
boilerplate removal (UI labels, column headers, nav elements).
Incremental: re-segments only pages whose `page_hash` changed since last run.

Run standalone: `python -m ingestion.run_segmentation [--force]`
Integrated: runs automatically after every ingestion via `run_ingestion.py`

## Stage B: Field-Aware Chunking (`data/chunks/`)
Modules: `ingestion/chunker.py`, `ingestion/field_classifier.py`, `ingestion/schemas.py`
Runner: `ingestion/run_chunking.py`

Each fund's segments are converted into `Chunk` objects (one JSONL file per fund):

**Chunk size policy**: target 650 chars, min 350, max cap 1000, overlap 100
**Greedy same-type accumulation**: consecutive same-block segments are merged
until the max cap would be exceeded; over-max single segments are split with
100-char overlap on line boundaries.

**Metrics enrichment** (label-value pairs kept together per §5.3):
- `header_block` chunk: full structured key-facts summary injected (NAV, min SIP,
  Fund Size, Expense Ratio, Rating)
- `facts_block` chunk: Expense Ratio/Rating/Fund Size injected when contextually present
- `fees_block` chunk: Minimum SIP value injected alongside "Minimum investments"

**Per-chunk metadata** (Chunk Record from §5.2):
- `chunk_id` — stable UUID v5 (deterministic from source_url + text)
- `source_url`, `source_domain`, `document_type`, `scheme_name`, `crawl_date`
- `section_name` — Stage A block type (e.g. "fees_block")
- `field_type` — primary field label (expense_ratio / exit_load / min_sip /
  riskometer / benchmark / lock_in / statement_process / other)
- `field_types` — all matched field labels
- `content_hash`, `chunk_version`, `is_active`

**Field-type classification** (`field_classifier.py`): rule-based keyword mapping,
checked in priority order; first match is primary.

Run standalone: `python -m ingestion.run_chunking [--force]`
Integrated: runs automatically after segmentation via `run_ingestion.py`

## Stage E: Embedding Generation (`data/embeddings/`)
Modules: `ingestion/embed_pipeline.py`
Runner: `ingestion/run_embedding.py`

**Model**: `BAAI/bge-large-en-v1.5` via `sentence-transformers` (local, no API key)
**Dimension**: 1024, L2-normalized (`normalize_embeddings=True`)
**Batch size**: 32
**Document prefix**: none (BGE v1.5 embeds document chunks without an instruction prefix)
**Query prefix at retrieval**: `"Represent this question for searching relevant passages: {query}"`

Incremental: tracks `chunk_id -> content_hash` in `data/state/embed_state.json`; skips chunks that haven't changed. On first run, downloads model (~1.34 GB, cached by HuggingFace Hub).

Output per fund: `data/embeddings/{slug}.jsonl` — one JSON line per chunk containing `embedding_vector` (len=1024), `embedding_model`, `embedding_dim`, `embedded_at`, plus all chunk metadata.

Run standalone: `python -m ingestion.run_embedding [--force]`

## Stage F: Chroma Cloud Vector Store
Modules: `ingestion/index_upsert.py`
Runner: `ingestion/run_index_upsert.py`

**Store**: Chroma Cloud (https://www.trychroma.com) — fully managed, hosted; `chromadb.CloudClient`
**Distance**: cosine (`hnsw:space = "cosine"`) — correct for L2-normalised bge-large vectors
**No local index files** — all vector data lives in the Chroma Cloud collection; no `data/vector_store/` directory needed at runtime
**Document ID**: `chunk_id` (UUID v5) — idempotent upsert key; re-running on unchanged chunks is a no-op
**Metadata stored per document**: `source_url`, `scheme_name`, `section_name`, `field_type`, `crawl_date`, `content_hash`, `embedding_model`, `embedded_at` — all filterable via `where=` at query time

**Required secrets** (set in Replit Secrets):
- `CHROMA_API_KEY` — API key from https://app.trychroma.com
- `CHROMA_TENANT` — tenant ID from Chroma Cloud console
- `CHROMA_DATABASE` — database name from Chroma Cloud console

Integrated into `run_ingestion.py` — only upserts slugs that changed in the current embedding run. Includes 3-probe sanity check after upsert (expense ratio / min SIP / exit load — all `✓` at rank #1 against Chroma Cloud).

Run standalone: `python -m ingestion.run_index_upsert [--slugs SLUG ...]`

## Dependencies
- Python 3.12
- beautifulsoup4
- requests
- sentence-transformers (installed via pip to .pythonlibs)
- chromadb (installed via pip to .pythonlibs)
- torch (CPU-only, installed via pip to .pythonlibs)

## Workflow
- **Start application**: Runs the ingestion pipeline as a one-shot console process
