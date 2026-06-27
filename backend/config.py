from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# -- Chroma Cloud --
CHROMA_API_KEY = os.environ.get("CHROMA_API_KEY", "")
CHROMA_TENANT = os.environ.get("CHROMA_TENANT", "")
CHROMA_DATABASE = os.environ.get("CHROMA_DATABASE", "")
CHROMA_COLLECTION = "mutual_fund_chunks_minilm_v1"

# -- Embedding model (must match ingestion) --
# all-MiniLM-L6-v2: 384-dim, symmetric model, no query prefix needed
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
EMBED_QUERY_PREFIX = ""  # MiniLM is symmetric — no instruction prefix

# -- Groq LLM (OpenAI-compatible API) --
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
LLM_MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")

# -- Retrieval --
TOP_K = 6
RERANK_TOP_N = 4
SIMILARITY_THRESHOLD = 0.30

# -- Domain allowlist --
ALLOWED_DOMAIN = "groww.in"

SOURCE_URLS = [
    "https://groww.in/mutual-funds/motilal-oswal-most-focused-midcap-30-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-bse-enhanced-value-index-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-large-and-midcap-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-nifty-india-defence-index-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-gold-and-silver-passive-fof-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-small-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-nifty-500-momentum-50-index-fund-direct-growth",
    "https://groww.in/mutual-funds/motilal-oswal-most-focused-multicap-35-fund-direct-growth",
    "https://groww.in/etfs/motilal-oswal-mutual-fund-motilal-oswal-nasdaq-q-etf-nq",
    "https://groww.in/mutual-funds/motilal-oswal-gold-and-silver-passive-fof-direct-growth",
    
]
