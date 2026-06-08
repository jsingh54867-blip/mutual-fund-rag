"""Stage B: Field-Aware Chunking

Converts Stage A segments into retrieval-ready Chunk objects.

Strategy (from architecture doc §5):
  1. Process segments in document order.
  2. Accumulate consecutive same-type segments into a running buffer.
     Flush buffer when block_type changes or the buffer would exceed
     CHUNK_MAX characters.
  3. If a flushed buffer still exceeds CHUNK_MAX (i.e. a single segment is
     already over the cap), split it with CHUNK_OVERLAP character overlap.
  4. Enrich chunk text with structured metrics wherever they are relevant,
     so label-value pairs are always present in the chunk (§5.3, §5.4).
  5. Attach full metadata via the field classifier (Stage C inline).

Size policy (configurable in config.py):
  Target  : 650 chars
  Min     : 350 chars  (guideline; small factual chunks kept, not discarded)
  Max cap : 1000 chars
  Overlap : 100 chars  (applied only on large-segment splits)
"""

from __future__ import annotations

from .config import CHUNK_MAX, CHUNK_OVERLAP
from .field_classifier import classify
from .schemas import Chunk
from .segmenter import BlockType

# ---------------------------------------------------------------------------
# Metrics enrichment
# ---------------------------------------------------------------------------

def _fmt_inr(value: str | None) -> str:
    """Format a raw metric value with a rupee symbol, or 'N/A'."""
    return f"\u20b9{value}" if value else "N/A"


def _build_header_enrichment(metrics: dict) -> str:
    """Build a structured key-facts block for the header chunk.

    This is the primary factual summary chunk and should be the top
    retrieval target for any general question about the fund.
    """
    lines = []
    if metrics.get("nav"):
        date_str = f" (as of {metrics['nav_date']})" if metrics.get("nav_date") else ""
        lines.append(f"NAV: {_fmt_inr(metrics['nav'])}{date_str}")
    if metrics.get("min_sip"):
        lines.append(f"Minimum SIP: {_fmt_inr(metrics['min_sip'])}")
    if metrics.get("fund_size_cr"):
        lines.append(f"Fund Size (AUM): \u20b9{metrics['fund_size_cr']} Cr")
    if metrics.get("expense_ratio"):
        lines.append(f"Expense Ratio: {metrics['expense_ratio']}")
    if metrics.get("rating"):
        lines.append(f"Rating: {metrics['rating']}")
    return "\n".join(lines)


def _metrics_lines_for_block(block_type: BlockType, chunk_text: str, metrics: dict) -> str:
    """Return metric injection lines relevant to this block and chunk content.

    Only injects values that are (a) available and (b) contextually relevant
    to avoid polluting unrelated chunks.
    """
    lowered = chunk_text.lower()
    lines: list[str] = []

    if block_type == "fees_block":
        if "minimum" in lowered and metrics.get("min_sip"):
            lines.append(f"Minimum SIP: {_fmt_inr(metrics['min_sip'])}")

    if block_type == "facts_block":
        expense_signals = (
            "expense ratio" in lowered
            or "fee payable to a mutual fund house for managing" in lowered
        )
        if expense_signals and metrics.get("expense_ratio"):
            lines.append(f"Expense Ratio: {metrics['expense_ratio']}")
        if ("rating" in lowered or "rank" in lowered) and metrics.get("rating"):
            lines.append(f"Rating: {metrics['rating']}")
        if ("fund size" in lowered or "aum" in lowered) and metrics.get("fund_size_cr"):
            lines.append(f"Fund Size (AUM): \u20b9{metrics['fund_size_cr']} Cr")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Text splitting (for over-max segments only)
# ---------------------------------------------------------------------------

def _split_text_with_overlap(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split text into sub-chunks of at most max_chars with character overlap.

    Splits on line boundaries where possible to avoid cutting mid-sentence.
    """
    lines = text.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > max_chars and current:
            chunk_text = "\n".join(current)
            chunks.append(chunk_text)
            # Start next chunk with the last `overlap` chars from the tail.
            tail = chunk_text[-overlap:]
            # Find the first newline in tail to start cleanly on a line boundary.
            nl_idx = tail.find("\n")
            seed = tail[nl_idx + 1:] if nl_idx != -1 else tail
            current = [seed, line] if seed.strip() else [line]
            current_len = len(seed) + line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Main chunking function
# ---------------------------------------------------------------------------

def build_chunks(
    segments: list[dict],
    source_doc: dict,
) -> list[Chunk]:
    """Build a list of Chunk objects from Stage A segments + the processed doc.

    Args:
        segments:   List of segment dicts from the segmented JSON.
                    Each has keys: block_type, text, line_count, char_count.
        source_doc: The processed JSON dict for the page.
                    Must contain: source_url, scheme_name, crawl_date,
                    page_hash, metrics, source_domain, document_type.

    Returns:
        Ordered list of Chunk objects ready for versioning and embedding.
    """
    metrics: dict = source_doc.get("metrics") or {}
    scheme_name: str = source_doc.get("scheme_name", "unknown-scheme")
    source_url: str = source_doc.get("source_url", "")
    source_domain: str = source_doc.get("source_domain", "groww.in")
    document_type: str = source_doc.get("document_type", "scheme_page_html")
    crawl_date: str = source_doc.get("crawl_date", "")

    chunks: list[Chunk] = []

    # -------------------------------------------------------------------
    # Special case: build the header enrichment chunk first.
    # The header_block segment is always the first segment and contains
    # only the scheme name. We inject the full metrics summary here.
    # -------------------------------------------------------------------
    header_seg = next((s for s in segments if s["block_type"] == "header_block"), None)
    if header_seg:
        enrichment = _build_header_enrichment(metrics)
        header_text = header_seg["text"]
        if enrichment:
            header_text = header_text + "\n" + enrichment
        field_type, field_types = classify(header_text, "header_block")
        chunks.append(
            Chunk(
                source_url=source_url,
                source_domain=source_domain,
                document_type=document_type,
                scheme_name=scheme_name,
                crawl_date=crawl_date,
                text=header_text,
                section_name="header_block",
                field_type=field_type,
                field_types=field_types,
            )
        )

    # -------------------------------------------------------------------
    # Process remaining segments with greedy same-type accumulation.
    # -------------------------------------------------------------------
    non_header = [s for s in segments if s["block_type"] != "header_block"]

    buffer_type: str | None = None
    buffer_lines: list[str] = []

    def _flush_buffer() -> None:
        if not buffer_lines:
            return
        raw_text = "\n".join(buffer_lines)
        block_type: BlockType = buffer_type  # type: ignore[assignment]

        # Inject relevant metric values into the chunk text.
        injection = _metrics_lines_for_block(block_type, raw_text, metrics)
        if injection:
            raw_text = raw_text + "\n" + injection

        # If the text exceeds the hard cap, split it.
        if len(raw_text) > CHUNK_MAX:
            sub_texts = _split_text_with_overlap(raw_text, CHUNK_MAX, CHUNK_OVERLAP)
        else:
            sub_texts = [raw_text]

        for sub_text in sub_texts:
            if not sub_text.strip():
                continue
            ft, fts = classify(sub_text, block_type)
            chunks.append(
                Chunk(
                    source_url=source_url,
                    source_domain=source_domain,
                    document_type=document_type,
                    scheme_name=scheme_name,
                    crawl_date=crawl_date,
                    text=sub_text,
                    section_name=block_type,
                    field_type=ft,
                    field_types=fts,
                )
            )

    for seg in non_header:
        seg_type = seg["block_type"]
        seg_lines = seg["text"].splitlines()

        if buffer_type is None:
            buffer_type = seg_type
            buffer_lines = seg_lines

        elif seg_type == buffer_type:
            # Same type: try to merge.
            candidate_len = len("\n".join(buffer_lines)) + 1 + len(seg["text"])
            if candidate_len <= CHUNK_MAX:
                buffer_lines.extend(seg_lines)
            else:
                # Would exceed max — flush and start fresh.
                _flush_buffer()
                buffer_type = seg_type
                buffer_lines = seg_lines

        else:
            # Different type: flush current buffer, start new one.
            _flush_buffer()
            buffer_type = seg_type
            buffer_lines = seg_lines

    _flush_buffer()  # flush the last buffer

    return chunks
