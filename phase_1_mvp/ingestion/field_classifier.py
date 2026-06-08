"""Stage C: Field-Type Classifier (Metadata Enrichment)

Maps chunk text and block_type to a FieldType label using rule-based keyword
matching. Returns both a primary label and a full list of all matched types.

Field-type mapping per architecture doc §6 Stage C:

    expense ratio         -> expense_ratio
    exit load             -> exit_load
    minimum + sip         -> min_sip
    riskometer            -> riskometer
    benchmark             -> benchmark
    lock-in / lock in     -> lock_in
    capital gains / tax statement / statement -> statement_process
    (default)             -> other
"""

from __future__ import annotations

from .schemas import FieldType
from .segmenter import BlockType

# ---------------------------------------------------------------------------
# Keyword rules — (field_type, trigger_substrings_lowercased).
# Evaluated in order; ALL matches are collected, first match = primary.
# ---------------------------------------------------------------------------
_FIELD_RULES: list[tuple[FieldType, list[str]]] = [
    ("expense_ratio", ["expense ratio", "expense_ratio", "total expense ratio", "total expense"]),
    ("exit_load",     ["exit load", "exit_load", "redemption charge", "exit charge"]),
    ("min_sip",       ["minimum sip", "minimum investment", "min. for sip",
                       "minimum lumpsum", "minimum instalment", "minimum investments"]),
    ("lock_in",       ["lock-in", "lock in", "elss", "tax saving"]),
    ("riskometer",    ["riskometer", "risk-o-meter"]),
    ("benchmark",     ["benchmark", "nifty", "sensex", "bse", "crisil composite"]),
    ("statement_process", ["capital gains", "tax statement", "account statement",
                           "tax implication", "ltcg", "stcg", "stamp duty"]),
]

# Block-type fallback priority when no keyword matches
_BLOCK_DEFAULT: dict[BlockType, FieldType] = {
    "header_block":        "other",
    "facts_block":         "other",
    "fees_block":          "exit_load",   # fees section default
    "risk_benchmark_block": "riskometer",
    "process_block":       "statement_process",
    "other_block":         "other",
}


def classify(text: str, block_type: BlockType) -> tuple[FieldType, list[FieldType]]:
    """Return (primary_field_type, all_matched_field_types).

    Args:
        text:       The chunk text to classify.
        block_type: The segment block type from Stage A.

    Returns:
        primary:  The most specific matched FieldType.
        all_types: Every FieldType whose keywords appear in the text.
    """
    lowered = text.lower()
    matched: list[FieldType] = []

    for field_type, keywords in _FIELD_RULES:
        if any(kw in lowered for kw in keywords):
            matched.append(field_type)

    if not matched:
        primary = _BLOCK_DEFAULT.get(block_type, "other")
        return primary, [primary]

    return matched[0], matched
