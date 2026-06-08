# Detailed Architecture: Facts-Only Mutual Fund RAG Chatbot

## 1) Goal and Boundary

Build a small Retrieval-Augmented Generation (RAG) chatbot that answers factual questions about selected mutual fund schemes from the provided Groww scheme pages (HTML sources only, no PDFs currently).

Core boundaries:

- Facts-only responses
- No advice/opinion/recommendation/comparison/return calculations
- Exactly one source link in every answer
- Maximum 3 sentences per answer
- Strictly grounded in retrieved source content

## 2) Scope Definition

### 2.1 Business Scope

- Use the following in-scope scheme URLs:
  - `https://groww.in/mutual-funds/motilal-oswal-most-focused-midcap-30-fund-direct-growth`
  - `https://groww.in/mutual-funds/motilal-oswal-bse-enhanced-value-index-fund-direct-growth`
  - `https://groww.in/mutual-funds/motilal-oswal-large-and-midcap-fund-direct-growth`
  - `https://groww.in/mutual-funds/motilal-oswal-nifty-india-defence-index-fund-direct-growth`
  - `https://groww.in/mutual-funds/motilal-oswal-gold-and-silver-passive-fof-direct-growth`
  - `https://groww.in/mutual-funds/motilal-oswal-small-cap-fund-direct-growth`
  - `https://groww.in/mutual-funds/motilal-oswal-nifty-500-momentum-50-index-fund-direct-growth`
- Current document-type scope: HTML webpages only (no PDFs provided at this stage).

### 2.2 Question Scope

Supported factual query types:

- Expense ratio
- Exit load
- Minimum SIP / minimum investment
- ELSS lock-in period
- Riskometer
- Benchmark
- Process questions (capital gains statement, account/tax statement access from official workflow pages)

Out-of-scope queries:

- Advice ("Should I invest?")
- Recommendation/comparison ("Which is better?")
- Return/performance projections or calculations

## 3) High-Level Architecture

```text
                   +-------------------------------+
                   |     In-Scope Source Pages      |
                   |   (Groww scheme pages, HTML)   |
                   +---------------+---------------+
                                   |
                                   v
                      +--------------------------+
                      | Ingestion & Normalizer   |
                      | URL validator + parser   |
                      +------------+-------------+
                                   |
                                   v
                      +--------------------------+
                      | Chunking + Metadata      |
                      | scheme/field/date/source |
                      +------------+-------------+
                                   |
                                   v
                      +--------------------------+
                      | Embeddings Generator     |
                      +------------+-------------+
                                   |
                                   v
                      +--------------------------+
                      | Vector DB (Chroma Cloud) |
                      +------------+-------------+
                                   |
           +-----------------------+------------------------+
           |                                                |
           v                                                v
+--------------------------+                    +---------------------------+
| Query Classifier         |                    | Retrieval Engine          |
| fact vs refusal          |                    | top-k + metadata filter   |
+------------+-------------+                    +-------------+-------------+
             |                                                    |
             | refusal path                                       |
             v                                                    v
+--------------------------+                    +---------------------------+
| Refusal Response Builder |                    | Context Assembler         |
| fixed policy + one link  |                    | dedupe + rank + compress  |
+------------+-------------+                    +-------------+-------------+
             |                                                    |
             +---------------------------+------------------------+
                                         v
                           +----------------------------+
                           | LLM Answer Generator       |
                           | strict prompt + constraints|
                           +-------------+--------------+
                                         |
                                         v
                           +----------------------------+
                           | Output Guardrail Layer     |
                           | 3-sentence + 1 link check  |
                           +-------------+--------------+
                                         |
                                         v
                           +----------------------------+
                           | UI/API Response            |
                           +----------------------------+
```

## 4) Component Design

## 4.1 Source Registry and Governance

Purpose: enforce "in-scope URLs only."

Input:

- Fixed manual source list (the 7 provided Groww URLs)

Validation rules:

- Allowlist domains only:
  - `groww.in`
- Reject out-of-scope domains.
- Record source type: scheme page (HTML).

Output:

- `sources.csv` or `sources.md` with:
  - URL
  - Domain
  - Source type
  - Scheme tag(s)
  - Last crawled timestamp

## 4.2 Ingestion Pipeline

Responsibilities:

- Fetch HTML
- Extract clean text
- Preserve source metadata
- Refresh data from all in-scope links on schedule

Suggested stack:

- HTML: `requests` + `BeautifulSoup` (or equivalent loader)
- Optional: retry + timeout + user-agent

Normalization:

- Remove boilerplate/navigation noise where possible
- Keep key tables/sections for factual fields
- Preserve section headings

Failure handling:

- Track inaccessible URLs
- Retry transient failures
- Log parse confidence (high/medium/low)

Scraping service behavior:

- Service name: `scraping_service`
- Input: fixed in-scope URL list (7 Groww links)
- Steps per run:
  1. Fetch each URL and parse the relevant scheme sections.
  2. Normalize extracted text and attach `crawl_date` and source metadata.
  3. Detect changed content using a page-content hash.
  4. Re-chunk and re-embed only changed pages (incremental update).
  5. Upsert chunks in vector store and mark old chunk versions inactive.
- Output artifacts:
  - Updated chunk store/vector index
  - `scrape_run_log` with run timestamp, URL status, and change flags

## 4.3 Chunking and Metadata

Chunking strategy:

- Chunk size: 500 to 900 characters (or ~150 to 250 tokens)
- Overlap: 80 to 120 characters
- Table-aware chunking when possible for scheme detail sections

Per-chunk metadata:

- `source_url`
- `source_domain`
- `document_type` (scheme_page_html)
- `scheme_name` (if applicable)
- `field_type` (expense_ratio / exit_load / min_sip / lock_in / riskometer / benchmark / statement_process / other)
- `last_updated_text` (if extracted)
- `crawl_date`

Rationale:

- Metadata enables accurate retrieval filtering and reliable citation extraction.

## 4.4 Embeddings and Vector Store

Embeddings:

- Model: **BAAI/bge-large-en-v1.5** via `sentence-transformers` (local inference, no API key)
- Dimension: 1024
- L2-normalize all document vectors; enables cosine similarity via inner product
- Query-time instruction prefix: `"Represent this question for searching relevant passages: {query}"`
- Batch size: 32; incremental — re-embed only chunks whose `content_hash` changed
- Model version pinned in `config.py` as `EMBED_MODEL`; full corpus re-embedded only on upgrade

Vector DB:

- **Chroma Cloud** (https://www.trychroma.com) — fully managed, hosted vector store; no local disk index
- Client: `chromadb.CloudClient(tenant, database, api_key)` — connects to `api.trychroma.com` over HTTPS
- Collection name: `mutual_fund_chunks`; distance metric: cosine
- Native metadata filtering on `scheme_name`, `field_type`, `section_name`, `crawl_date` via `where=` clauses
- No local `data/vector_store/` directory required; all vector data lives in the cloud collection

Indexing:

- Batch embedding generation (Stage E in chunking/embedding pipeline)
- Upsert chunks into Chroma Cloud collection by `chunk_id` after each run (Stage F)
- Chroma Cloud stores text, embedding vector, and metadata together per document
- `chunk_id` (UUID v5) used as document ID for idempotent upserts and citation enforcement
- Upsert is incremental: only changed slugs (from Stage E) are sent to the cloud

Required environment secrets (set in Replit Secrets):

- `CHROMA_API_KEY` — API key from Chroma Cloud console (https://app.trychroma.com)
- `CHROMA_TENANT` — tenant ID shown in Chroma Cloud console
- `CHROMA_DATABASE` — database name created in Chroma Cloud console
- `MODEL_NAME` — embedding model override (default: `BAAI/bge-large-en-v1.5`)

## 4.5 Retrieval Layer

Retrieval process:

1. Pre-process query (normalize scheme names, synonyms like SIP vs systematic investment plan).
2. Metadata-aware retrieval:
  - Prefer chunks with matching `scheme_name`
  - Prefer chunks with matching `field_type` inferred from query intent
3. Retrieve top-k (recommended k=4 to 6)
4. Re-rank by:
  - Query-term coverage
  - Metadata match score
  - Source freshness (if available)

Output:

- Compact context packet with 2 to 4 best chunks
- Candidate citation URL list (ranked)

## 4.6 Query Classification and Policy Guardrail

Classifier objective:

- `FACTUAL_ALLOWED`
- `REFUSAL_REQUIRED`
- `OUT_OF_SCOPE_OR_UNKNOWN`

Methods:

- Rule-first classifier with keyword patterns
- Optional LLM fallback classifier for ambiguous queries

Examples:

- Advice intent: "should", "best fund", "worth investing", "recommend"
- Comparison intent: "better than", "which is better"
- Calculation intent: "returns", "CAGR", "how much will I get"

Policy behavior:

- If `REFUSAL_REQUIRED`, bypass retrieval generation path and send refusal template + one educational official link.
- If `FACTUAL_ALLOWED`, continue retrieval and answering.

## 4.7 LLM Generation Layer

Prompt contract:

- "Answer ONLY from provided context."
- "If answer is missing, say you do not know."
- "Do not provide advice."
- "Maximum 3 sentences."
- "Include exactly one source link."
- "Include: Last updated from sources: "

Input to LLM:

- User query
- Curated retrieved context
- Required output format schema

Output schema (structured):

- `answer_text`
- `source_url`
- `last_updated_line`

## 4.8 Post-Processing Guardrails (Critical)

Post-processing checks before returning response:

1. Sentence count <= 3
2. Exactly one URL present
3. URL belongs to official allowlist
4. If refusal query, exact refusal message used
5. If non-refusal query and confidence too low, respond:
  - "I don't know based on the available official sources."
  - Include one official source URL
6. Ensure "Last updated from sources: <...>" line always present

If check fails:

- Auto-rewrite with deterministic formatter (not another free-form generation) to enforce constraints.

## 4.9 API Layer

Recommended minimal endpoints:

- `POST /chat`
  - Input: `query`, optional `session_id`
  - Output:
    - `answer`
    - `source_link`
    - `last_updated_from_sources`
    - `response_type` (`factual`, `refusal`, `unknown`)
- `GET /health`
- `GET /sources` (optional debug/admin)

Internal service modules:

- `query_classifier.py`
- `retriever.py`
- `generator.py`
- `policy.py`
- `response_formatter.py`
- `scraping_service.py`
- `github_actions_trigger.py` (optional script entrypoint for scheduled workflow)

## 4.10 UI Layer (Minimal)

Frontend requirements:

- Welcome text:
  - "Ask me factual questions about mutual funds. Facts-only. No investment advice."
- 3 example queries
- Text input and response panel
- Source link displayed as single clickable URL
- Last-updated line visible under each answer

Suggested implementation:

- Streamlit single-page app
- Stateless or lightweight session memory (for convenience only; no PII)

## 4.11 Security, Privacy, and Compliance

Controls:

- No PII collection fields
- Do not log raw sensitive user text if avoidable; if logging, redact obvious personal patterns
- Enforce official-domain allowlist for citations
- Disable any tool/function that computes return projections

Compliance behavior:

- No hallucinated figures; unknown fallback required when evidence absent
- Traceable citation from selected chunk to output link

## 5) Data Model

## 5.1 Source Record

- `source_id`
- `url`
- `domain`
- `source_type`
- `scheme_tags[]`
- `is_official` (boolean)
- `crawl_timestamp`

## 5.2 Chunk Record

- `chunk_id`
- `source_id`
- `text`
- `embedding`
- `scheme_name`
- `field_type`
- `last_updated_text`

## 5.3 Interaction Log (Non-PII)

- `interaction_id`
- `timestamp`
- `query_hash` (optional)
- `classification`
- `retrieved_chunk_ids[]`
- `final_source_url`
- `guardrail_pass` (boolean)

## 6) End-to-End Runtime Flows

## 6.1 Factual Query Flow

1. User asks factual question.
2. Classifier returns `FACTUAL_ALLOWED`.
3. Retriever fetches top-k chunks with metadata preference.
4. LLM generates concise answer from context.
5. Guardrail enforces 3 sentences + exactly one official link + last-updated line.
6. UI displays response.

## 6.2 Refusal Query Flow

1. User asks advice/comparison/returns question.
2. Classifier returns `REFUSAL_REQUIRED`.
3. System returns fixed refusal text and one official educational link.
4. UI displays refusal response.

## 6.3 Unknown/Insufficient Evidence Flow

1. Query is factual but not found in indexed sources.
2. System returns "I don't know based on available official sources."
3. Include one official link and last-updated line.

## 7) Suggested Project Structure

```text
project/
  app.py                      # Streamlit UI
  backend/
    chat_service.py
    query_classifier.py
    retriever.py
    generator.py
    policy.py
    formatter.py
  ingestion/
    source_registry.py
    crawl_and_parse.py
    chunk_and_embed.py
  data/
    sources.csv
    vector_store/
  prompts/
    answer_prompt.txt
    refusal_prompt.txt
  tests/
    test_classifier.py
    test_guardrails.py
    test_citation_rules.py
    test_refusals.py
  README.md
  sample_qa.md
```

## 8) Guardrail Rules (Deterministic)

Rule set:

- `R1`: If query class in {advice, comparison, performance_calc} => refusal template.
- `R2`: Final response must contain exactly 1 URL.
- `R3`: URL domain must be `groww.in`.
- `R4`: Final response max 3 sentences (excluding URL line and last-updated line if implemented as separate lines).
- `R5`: Must include last-updated line.
- `R6`: If confidence < threshold, return unknown template.

Confidence signals:

- Top-1 retrieval similarity
- Number of chunks agreeing on fact
- Presence of exact numeric/entity match

## 9) Observability and QA

Metrics:

- Refusal precision (how often prohibited queries are correctly refused)
- Citation validity rate (must be 100%)
- Single-link compliance rate (must be 100%)
- Hallucination audit failure rate (target 0)
- Unknown response rate
- Median response latency

Test suite:

- Unit tests for classifier categories
- Unit tests for formatter (sentence/URL constraints)
- Integration tests from query -> retrieval -> final response
- Regression tests with 5 to 10 sample Q&A

Manual evaluation checklist:

- Every answer includes exactly one official source link
- Advice/comparison/returns prompts always refused
- No answer without retrieval evidence

## 10) Deployment Blueprint

Environment:

- Python runtime
- Vector index persisted on disk
- Streamlit app + backend module in same service (small prototype)

Config via environment variables:

- `ALLOWED_DOMAINS`
- `TOP_K`
- `SIMILARITY_THRESHOLD`
- `MODEL_NAME`
- `VECTOR_DB_PATH`
- `SCRAPE_SCHEDULE_CRON` (default: `20 9 * * *`)
- `TIMEZONE` (default: `Asia/Kolkata`)
- `GITHUB_ACTIONS` (runtime flag for CI environment)

Release process:

1. Refresh sources
2. Rebuild embeddings/index
3. Run tests
4. Deploy app
5. Run post-deploy smoke tests for known factual and refusal prompts

Scheduler runtime (production):

- Scheduler platform: GitHub Actions (`.github/workflows/daily-refresh.yml`).
- Daily schedule: run at `9:20 AM` every day.
- Cron expression: `20 9 * * *` (configured in workflow schedule; evaluate against repository timezone strategy, typically UTC conversion).
- Trigger chain: `GitHub Actions schedule -> scraping_service -> incremental index update`.
- Workflow job stages:
  1. Checkout code and install dependencies.
  2. Run scraping + change-detection pipeline.
  3. Re-chunk/re-embed changed pages.
  4. Validate index and run guardrail smoke checks.
  5. Publish updated index artifacts (or commit/push updated index store, based on repo policy).
- On failure:
  - Retry once after 10 minutes.
  - If retry fails, keep last successful index active and raise alert.
- On success:
  - Update latest crawl timestamp in source registry.
  - Make refreshed data available for retrieval immediately after index swap.

## 11) Risks and Mitigations

- Source format changes (HTML layout drift)
  - Mitigation: parser fallback + manual source QA
- Wrong citation from chunk mismatch
  - Mitigation: strict `chunk -> source_url` mapping and response validator
- Advice leakage through generative phrasing
  - Mitigation: hard refusal path before generation
- Stale facts
  - Mitigation: recrawl schedule + visible "last updated" info

## 12) Implementation Phases

Phase 1 (MVP):

- Source allowlist + ingestion for 15 to 25 URLs
- Basic retrieval + QA guardrails + Streamlit UI
- Deterministic refusal and one-link enforcement

Phase 2 (Hardening):

- Better table parsing
- Re-ranking improvements
- Expanded test coverage and offline evaluation harness

Phase 3 (Operational):

- Daily scheduled refresh at 9:20 with automated incremental re-indexing
- Monitoring dashboard and error analytics

## 13) Acceptance Mapping to Requirements

- Facts-only chatbot: covered by classifier + policy guardrail.
- In-scope source pages only: strict URL/domain allowlist + source registry.
- Exactly one source link: formatter + validator rule `R2`.
- <=3 sentences: formatter rule `R4`.
- Refusal behavior: deterministic template route.
- RAG stack: loader, chunking, embeddings, vector DB, retriever, LLM.
- Minimal UI: welcome text + examples + input/output view.

This architecture is designed to be directly implementable for a working prototype while preserving strict compliance with your constraints._v1.5