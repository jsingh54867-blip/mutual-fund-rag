from __future__ import annotations

import re

# Classification labels
FACTUAL_ALLOWED = "factual"
REFUSAL_REQUIRED = "refusal"
OUT_OF_SCOPE = "unknown"

# -- Keyword patterns for refusal detection --

_ADVICE_PATTERNS = [
    r"\bshould\s+i\b",
    r"\bworth\s+investing\b",
    r"\brecommend\b",
    r"\bsugg?est\b",
    r"\bbest\s+fund\b",
    r"\bgood\s+fund\b",
    r"\bis\s+it\s+good\b",
    r"\bis\s+it\s+safe\b",
    r"\bis\s+it\s+worth\b",
    r"\binvest\s+in\b",
    r"\bwhere\s+should\b",
]

_COMPARISON_PATTERNS = [
    r"\bbetter\s+than\b",
    r"\bwhich\s+is\s+better\b",
    r"\bwhich\b.*\bbetter\b",
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bvs\.?\b",
    r"\bversus\b",
]

_CALCULATION_PATTERNS = [
    r"\breturns?\b.*\bcalculat\w*\b",
    r"\bcalculat\w*\b.*\breturns?\b",
    r"\breturns?\b.*\bwill\b",
    r"\breturns?\b.*\bget\b",
    r"\bcagr\b",
    r"\bhow\s+much\s+will\s+(i|you)\s+get\b",
    r"\bprofit\b",
    r"\bfuture\s+value\b",
    r"\bproject(ion|ed)?\b",
    r"\bhow\s+much\s+(can|will)\b",
    r"\bestimate\s+returns?\b",
]

_COMPILED_REFUSAL: list[re.Pattern] = []
for _pat_list in (_ADVICE_PATTERNS, _COMPARISON_PATTERNS, _CALCULATION_PATTERNS):
    for _p in _pat_list:
        _COMPILED_REFUSAL.append(re.compile(_p, re.IGNORECASE))

# -- Factual intent keywords --
_FACTUAL_KEYWORDS = [
    "expense ratio", "exit load", "minimum sip", "min sip",
    "minimum investment", "lock-in", "lock in", "lockin",
    "riskometer", "risk level", "benchmark", "nav",
    "fund size", "aum", "fund manager", "stamp duty",
    "capital gains", "tax statement", "elss",
    "what is", "what are", "how to get", "how do i",
    "tell me", "scheme name", "category",
]


def classify(query: str) -> str:
    """Classify a user query into factual / refusal / unknown."""
    q = query.strip()
    if not q:
        return OUT_OF_SCOPE

    # Check refusal patterns first
    for pat in _COMPILED_REFUSAL:
        if pat.search(q):
            return REFUSAL_REQUIRED

    # Check factual keywords
    q_lower = q.lower()
    for kw in _FACTUAL_KEYWORDS:
        if kw in q_lower:
            return FACTUAL_ALLOWED

    # If it looks like a question, assume factual
    if q.rstrip().endswith("?"):
        return FACTUAL_ALLOWED

    # Default: treat as factual (let the retriever decide confidence)
    return FACTUAL_ALLOWED
