from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


SOURCE_URLS = [
    "https://groww.in/mutual-funds/motilal-oswal-most-focused-midcap-30-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-bse-enhanced-value-index-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-large-and-midcap-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-nifty-india-defence-index-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-gold-and-silver-passive-fof-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-small-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-nifty-500-momentum-50-index-fund-direct-growth",
]

ALLOWED_DOMAIN = "groww.in"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 2
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw_pages"
PROCESSED_DIR = DATA_DIR / "processed_pages"
LOGS_DIR = DATA_DIR / "logs"
STATE_DIR = DATA_DIR / "state"

SOURCES_CSV_PATH = DATA_DIR / "sources.csv"
SCRAPE_LOG_PATH = LOGS_DIR / "scrape_run_log.jsonl"
STATE_FILE_PATH = STATE_DIR / "page_state.json"

SEGMENTED_DIR = DATA_DIR / "segmented_pages"
SEGMENT_LOG_PATH = LOGS_DIR / "segmentation_run_log.jsonl"

CHUNKS_DIR = DATA_DIR / "chunks"
CHUNK_LOG_PATH = LOGS_DIR / "chunking_run_log.jsonl"

# Stage B chunk size policy (characters)
CHUNK_TARGET = 650
CHUNK_MIN = 350
CHUNK_MAX = 1000
CHUNK_OVERLAP = 100

# Stage E: embedding model (BAAI/bge-large-en-v1.5 via sentence-transformers)
EMBED_MODEL = "BAAI/bge-large-en-v1.5"
EMBED_DIM = 1024
EMBED_BATCH_SIZE = 32
# BGE query-time instruction prefix (applied at retrieval, not during ingestion)
EMBED_QUERY_PREFIX = "Represent this question for searching relevant passages: "

EMBEDDINGS_DIR = DATA_DIR / "embeddings"
EMBED_STATE_PATH = STATE_DIR / "embed_state.json"
EMBED_LOG_PATH = LOGS_DIR / "embedding_run_log.jsonl"

# Stage F: Chroma Cloud vector store (https://www.trychroma.com)
# Credentials are read from environment variables — never hardcoded.
# Set CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE in Replit Secrets.
import os as _os

CHROMA_COLLECTION = "mutual_fund_chunks"
CHROMA_API_KEY  = _os.environ.get("CHROMA_API_KEY", "")
CHROMA_TENANT   = _os.environ.get("CHROMA_TENANT", "")
CHROMA_DATABASE = _os.environ.get("CHROMA_DATABASE", "")
