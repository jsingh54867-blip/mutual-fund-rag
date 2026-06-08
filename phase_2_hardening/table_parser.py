"""Phase 2: Table-Aware HTML Parser

Improved parser that extracts structured table data from Groww scheme pages.
Handles key-value tables, returns tables, and holdings tables with proper
row/column preservation for better retrieval quality.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag


@dataclass
class TableRow:
    """A single row from an HTML table."""
    cells: list[str]
    is_header: bool = False


@dataclass
class ParsedTable:
    """A structured representation of an HTML table."""
    headers: list[str] = field(default_factory=list)
    rows: list[TableRow] = field(default_factory=list)
    caption: str = ""
    table_type: str = "generic"  # returns | holdings | fees | generic

    def to_text(self) -> str:
        """Serialize the table into retrieval-friendly plain text."""
        lines: list[str] = []
        if self.caption:
            lines.append(f"Table: {self.caption}")

        if self.headers:
            lines.append(" | ".join(self.headers))
            lines.append("-" * (len(" | ".join(self.headers))))

        for row in self.rows:
            if self.headers and len(row.cells) == len(self.headers):
                pairs = [
                    f"{h}: {c}" for h, c in zip(self.headers, row.cells) if c.strip()
                ]
                lines.append(" | ".join(pairs) if pairs else " | ".join(row.cells))
            else:
                lines.append(" | ".join(row.cells))

        return "\n".join(lines)


def _classify_table(table: Tag, preceding_text: str = "") -> str:
    """Classify a table by its content and context."""
    text = (table.get_text(" ", strip=True) + " " + preceding_text).lower()

    if any(kw in text for kw in ["1y", "3y", "5y", "returns", "annualised", "cagr"]):
        return "returns"
    if any(kw in text for kw in ["holding", "top stocks", "sector", "allocation"]):
        return "holdings"
    if any(kw in text for kw in ["exit load", "expense ratio", "stamp duty", "fee"]):
        return "fees"
    return "generic"


def _clean_cell(cell: Tag) -> str:
    """Extract clean text from a table cell, handling nested elements."""
    # Remove script/style tags inside cells
    for tag in cell(["script", "style", "svg"]):
        tag.decompose()

    text = cell.get_text(" ", strip=True)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _infer_caption(table: Tag) -> str:
    """Try to find a caption for the table from surrounding context."""
    # Check <caption> element first
    caption_el = table.find("caption")
    if caption_el:
        return _clean_cell(caption_el)

    # Check preceding sibling heading
    prev = table.find_previous_sibling(["h1", "h2", "h3", "h4", "h5"])
    if prev:
        return _clean_cell(prev)

    return ""


def extract_tables(html: str) -> list[ParsedTable]:
    """Extract all meaningful tables from an HTML page.

    Returns a list of ParsedTable objects with structured row/column data.
    """
    soup = BeautifulSoup(html, "html.parser")
    tables: list[ParsedTable] = []

    for table_el in soup.find_all("table"):
        parsed = _parse_single_table(table_el)
        if parsed and (parsed.headers or parsed.rows):
            tables.append(parsed)

    return tables


def _parse_single_table(table_el: Tag) -> ParsedTable | None:
    """Parse a single <table> element into a ParsedTable."""
    caption = _infer_caption(table_el)

    # Extract header row
    headers: list[str] = []
    thead = table_el.find("thead")
    if thead:
        header_row = thead.find("tr")
        if header_row:
            headers = [_clean_cell(th) for th in header_row.find_all(["th", "td"])]

    # If no thead, check first row for <th> elements
    if not headers:
        first_row = table_el.find("tr")
        if first_row:
            ths = first_row.find_all("th")
            if ths:
                headers = [_clean_cell(th) for th in ths]

    # Extract body rows
    rows: list[TableRow] = []
    tbody = table_el.find("tbody") or table_el
    for tr in tbody.find_all("tr"):
        # Skip rows that are purely header rows (already captured)
        cells_td = tr.find_all("td")
        cells_th = tr.find_all("th")

        if cells_td:
            cells = [_clean_cell(td) for td in cells_td]
            # Include any th cells in the row as leading cells
            if cells_th:
                th_texts = [_clean_cell(th) for th in cells_th]
                cells = th_texts + cells
            rows.append(TableRow(cells=cells))
        elif cells_th and not headers:
            # All-th row used as header
            headers = [_clean_cell(th) for th in cells_th]

    if not rows and not headers:
        return None

    # Filter out empty rows
    rows = [r for r in rows if any(c.strip() for c in r.cells)]

    table_type = _classify_table(table_el, caption)

    return ParsedTable(
        headers=headers,
        rows=rows,
        caption=caption,
        table_type=table_type,
    )


def tables_to_text(tables: list[ParsedTable]) -> str:
    """Convert a list of parsed tables into a single text block for chunking."""
    blocks: list[str] = []
    for table in tables:
        text = table.to_text()
        if text.strip():
            blocks.append(text)
    return "\n\n".join(blocks)


def extract_clean_text_v2(html: str) -> str:
    """Enhanced clean text extraction that includes structured table data.

    Improvements over Phase 1:
    - Tables are extracted separately and serialized as structured text
    - Table rows are preserved as key-value pairs when headers are available
    - Boilerplate table cells (empty, navigation) are filtered out
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "noscript", "svg", "footer", "nav"]):
        tag.decompose()

    lines: list[str] = []

    # Extract non-table content
    for element in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        # Skip elements inside tables (handled separately)
        if element.find_parent("table"):
            continue
        value = re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip()
        if value:
            lines.append(value)

    # Extract and append structured table data
    tables = extract_tables(html)
    if tables:
        lines.append("")  # separator
        lines.append(tables_to_text(tables))

    # Deduplicate
    deduped: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(line)

    return "\n".join(deduped)
