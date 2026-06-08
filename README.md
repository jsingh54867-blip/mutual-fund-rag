# Mutual Fund RAG Prototype

This project is organized by implementation phase from `RAG_MutualFund_Chatbot_Architecture.md`.

## Folders

- `phase_1_mvp/` - MVP implementation (includes `4.2 Ingestion Pipeline`)
- `phase_2_hardening/` - hardening placeholders (table parsing, reranking, test expansion)
- `phase_3_operational/` - operational placeholders (scheduler, monitoring)

## Current Status

Implemented: `phase_1_mvp/ingestion` with:

- source registry for 7 in-scope Groww URLs
- HTML fetch + parse + normalization
- content hash change detection
- scrape run log generation
- crawl timestamp updates for sources