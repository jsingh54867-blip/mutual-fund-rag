"""Stage A: Structural Segmentation

Splits cleaned page text into named semantic blocks before chunking.

Blocks defined by the architecture:
    header_block       – scheme name / category snapshot
    facts_block        – expense ratio, AUM, NAV-like factual fields and returns
    fees_block         – exit load, minimum investment / SIP, stamp duty
    risk_benchmark_block – riskometer, benchmark
    process_block      – capital gains / tax statement workflow references
    other_block        – residual useful content (holdings, fund managers, etc.)

Segmentation rules (from architecture doc §4 Stage A):
  - Use heading-based anchor keywords to trigger block transitions.
  - Non-anchor lines inherit the current block (sticky assignment).
  - Keep label-value pairs together through stickiness.
  - Drop repetitive boilerplate lines.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

BlockType = Literal[
    "header_block",
    "facts_block",
    "fees_block",
    "risk_benchmark_block",
    "process_block",
    "other_block",
]

# ---------------------------------------------------------------------------
# Anchor rules — checked in order; first matching rule wins for each line.
# Each tuple: (block_type, list_of_trigger_substrings_lowercased)
# ---------------------------------------------------------------------------
_ANCHOR_RULES: list[tuple[BlockType, list[str]]] = [
    (
        "facts_block",
        [
            "historic returns",
            "returns and rankings",
            "average of the yearly returns",
            "total return of a mutual fund",
            "annualised",
            "a fee payable to a mutual fund house for managing",
            "fund returns",
            "category average",
        ],
    ),
    (
        "fees_block",
        [
            "minimum investments",
            "exit load",
            "stamp duty",
            "minimum sip",
            "minimum lumpsum",
            "lumpsum",
            "a fee payable to a mutual fund house for exiting",
        ],
    ),
    (
        "process_block",
        [
            "a percentage of your capital gains",
            "a form of tax payable for the purchase",
            "capital gains",
            "tax implication",
            "lock-in",
            "lock in",
            "elss",
        ],
    ),
    (
        "risk_benchmark_block",
        [
            "riskometer",
            "benchmark",
            "very high risk",
            "moderate risk",
            "low to moderate",
            "high risk",
        ],
    ),
    (
        "other_block",
        [
            "holdings",
            "compare similar funds",
            "fund management",
            "investment objective",
            "fund house",
        ],
    ),
]

# ---------------------------------------------------------------------------
# Boilerplate lines to discard (exact lowercase match after strip).
# These are UI labels, navigation elements, or column headers that add no
# factual value for retrieval.
# ---------------------------------------------------------------------------
_BOILERPLATE_EXACT: frozenset[str] = frozenset(
    [
        "return calculator",
        "over the past",
        "total investment",
        "would've become",
        "understand terms",
        "compare",
        "name",
        "sector",
        "instruments",
        "assets",
        "view details",
        "monthly sip",
        "one time",
        "monthly investment",
        "1d",
        "1m",
        "6m",
        "1y",
        "3y",
        "5y",
        "10y",
        "all",
        "returns",
    ]
)

# Lines shorter than this with no keyword match are considered noise.
_MIN_LINE_LEN = 3


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Segment:
    """A contiguous group of lines belonging to the same semantic block."""

    block_type: BlockType
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "block_type": self.block_type,
            "text": self.text,
            "line_count": len(self.lines),
            "char_count": self.char_count,
            "content_hash": self.content_hash,
        }


# ---------------------------------------------------------------------------
# Core segmentation logic
# ---------------------------------------------------------------------------


def _is_boilerplate(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < _MIN_LINE_LEN:
        return True
    return stripped.lower() in _BOILERPLATE_EXACT


def _anchor_block(line: str) -> BlockType | None:
    """Return the block type triggered by this line's content, or None."""
    lowered = line.lower()
    for block_type, keywords in _ANCHOR_RULES:
        if any(kw in lowered for kw in keywords):
            return block_type
    return None


def segment_text(text: str) -> list[Segment]:
    """Segment cleaned page text into semantic blocks.

    Args:
        text: Newline-separated cleaned text from ``extract_clean_text``.

    Returns:
        Ordered list of :class:`Segment` objects. Each segment groups lines
        that belong to the same semantic block. The header_block always comes
        first (the scheme name line). Boilerplate lines are silently dropped.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    segments: list[Segment] = []
    current_type: BlockType = "header_block"
    current_lines: list[str] = []

    for idx, line in enumerate(lines):
        # The very first line (scheme name) is always kept in the header.
        if idx == 0:
            current_lines.append(line)
            continue

        if _is_boilerplate(line):
            continue

        triggered = _anchor_block(line)

        if triggered is not None and triggered != current_type:
            # Flush the current segment, then start a new one.
            if current_lines:
                segments.append(Segment(block_type=current_type, lines=current_lines))
            current_lines = []
            current_type = triggered

        current_lines.append(line)

    # Flush the final segment.
    if current_lines:
        segments.append(Segment(block_type=current_type, lines=current_lines))

    return segments


def merge_small_segments(
    segments: list[Segment],
    min_chars: int = 80,
) -> list[Segment]:
    """Merge segments that are too small into an adjacent same-type segment.

    Single-line definition paragraphs can cause many tiny segments. This pass
    absorbs any segment whose text is shorter than ``min_chars`` into the
    nearest preceding segment of the same type, or into the next segment if no
    predecessor exists.
    """
    if not segments:
        return segments

    result: list[Segment] = []
    for seg in segments:
        if result and seg.char_count < min_chars and result[-1].block_type == seg.block_type:
            result[-1].lines.extend(seg.lines)
        else:
            result.append(Segment(block_type=seg.block_type, lines=list(seg.lines)))
    return result
