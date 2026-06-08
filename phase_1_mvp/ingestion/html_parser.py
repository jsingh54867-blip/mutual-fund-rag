from __future__ import annotations

import re
from bs4 import BeautifulSoup


SECTION_KEYWORDS = {
    "expense ratio": "expense_ratio",
    "exit load": "exit_load",
    "sip": "min_sip",
    "minimum": "min_sip",
    "lock-in": "lock_in",
    "lock in": "lock_in",
    "riskometer": "riskometer",
    "benchmark": "benchmark",
    "capital gains": "statement_process",
    "tax statement": "statement_process",
}

# Matches the stats block that Groww renders for every scheme page:
# "NAV: 15 Apr '26 ₹105.96 Min. for SIP ₹500 Fund size (AUM) ₹31,046.66 Cr
#  Expense ratio 0.85% Rating 3"
_METRICS_PATTERN = re.compile(
    r"NAV:\s*(?P<nav_date>[^₹\n]+?)\s*₹(?P<nav>[\d,\.]+)"
    r".*?Min\.\s*for\s*SIP\s*₹(?P<min_sip>[\d,\.]+)"
    r".*?Fund size \(AUM\)\s*₹(?P<fund_size>[\d,\.]+)\s*Cr"
    r".*?Expense ratio\s*(?P<expense_ratio>[\d\.]+%|--)"
    r".*?Rating\s*(?P<rating>\d+|--)",
    re.DOTALL,
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_scheme_name(soup: BeautifulSoup) -> str:
    title = soup.title.string if soup.title and soup.title.string else ""
    h1 = soup.find("h1")
    h1_text = h1.get_text(" ", strip=True) if h1 else ""
    candidate = h1_text or title
    return normalize_whitespace(candidate) or "unknown-scheme"


def infer_parse_confidence(text: str) -> str:
    if len(text) > 4000:
        return "high"
    if len(text) > 1500:
        return "medium"
    return "low"


def infer_field_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = {tag for keyword, tag in SECTION_KEYWORDS.items() if keyword in lowered}
    return sorted(tags) if tags else ["other"]


def extract_key_metrics(html: str) -> dict[str, str | None]:
    """Extract NAV, Min. for SIP, Fund Size, Expense Ratio, and Rating.

    Returns a dict with keys:
        nav              – e.g. "105.96"
        nav_date         – e.g. "15 Apr '26"
        min_sip          – e.g. "500"
        fund_size_cr     – e.g. "31,046.66"
        expense_ratio    – e.g. "0.85%"
        rating           – e.g. "3"  or None when "--"
    All values are strings (or None when the page doesn't carry that data).
    """
    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize_whitespace(soup.get_text(" ", strip=True))

    match = _METRICS_PATTERN.search(page_text)
    if not match:
        return {
            "nav": None,
            "nav_date": None,
            "min_sip": None,
            "fund_size_cr": None,
            "expense_ratio": None,
            "rating": None,
        }

    g = match.groupdict()
    return {
        "nav": g["nav"],
        "nav_date": g["nav_date"].strip(),
        "min_sip": g["min_sip"],
        "fund_size_cr": g["fund_size"],
        "expense_ratio": g["expense_ratio"] if g["expense_ratio"] != "--" else None,
        "rating": g["rating"] if g["rating"] != "--" else None,
    }


def extract_clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "footer", "nav"]):
        tag.decompose()

    lines: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th"]):
        value = normalize_whitespace(element.get_text(" ", strip=True))
        if value:
            lines.append(value)

    # Preserve heading/value flow while removing near-duplicate lines.
    deduped: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)

    return "\n".join(deduped)
