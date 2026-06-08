from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# -- Chroma Cloud --
CHROMA_API_KEY = os.environ.get("CHROMA_API_KEY", "")
CHROMA_TENANT = os.environ.get("CHROMA_TENANT", "")
CHROMA_DATABASE = os.environ.get("CHROMA_DATABASE", "")
CHROMA_COLLECTION = "mutual_fund_chunks"

# -- Embedding model (must match ingestion) --
EMBED_MODEL = "BAAI/bge-large-en-v1.5"
EMBED_DIM = 1024
EMBED_QUERY_PREFIX = "Represent this question for searching relevant passages: "

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
]
