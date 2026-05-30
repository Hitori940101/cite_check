"""Citation parsers for BibTeX and GBT 7714 formats.

Parses citation references from .bib files or plain text into
structured ReferenceItem objects used by the verification pipeline.
"""

import re
from pathlib import Path
from typing import Union

import bibtexparser

from refchecker.core.exceptions import ParserError
from refchecker.core.logging import get_logger
from refchecker.core.models import ReferenceItem

logger = get_logger(__name__)

# --- BibTeX field mapping to ReferenceItem fields ---
_BIBTEX_FIELD_MAP: dict[str, str] = {
    "title": "title",
    "author": "authors",
    "year": "year",
    "journal": "journal",
    "booktitle": "journal",
    "doi": "doi",
    "volume": "volume",
    "number": "issue",
    "pages": "pages",
    "publisher": "publisher",
}

# --- GBT 7714 patterns ---
# GBT 7714-2015 common formats:
# [1] AUTHOR. Title[J]. Journal, Year, Vol(Issue): Pages.
# [2] AUTHOR. Title[M]. City: Publisher, Year.
# [3] AUTHOR. Title[C]//Conference. City: Publisher, Year: Pages.

_GBT_JOURNAL = re.compile(
    r"""
    ^\[(?P<num>\d+)\]\s*
    (?P<authors>[^\.]+?)\.\s*
    (?P<title>[^\[]+?)\s*
    \[J\]\.\s*
    (?P<journal>[^,]+?),\s*
    (?P<year>\d{4}),\s*
    (?P<volume>\d+)
    (?:\((?P<issue>\d+)\))?
    (?::\s*(?P<pages>[\d\-]+))?
    \.?\s*$
    """,
    re.VERBOSE,
)

_GBT_BOOK = re.compile(
    r"""
    ^\[(?P<num>\d+)\]\s*
    (?P<authors>[^\.]+?)\.\s*
    (?P<title>[^\[]+?)\s*
    \[M\]\.\s*
    (?:(?P<city>[^:]+?):\s*)?
    (?P<publisher>[^,]+?),\s*
    (?P<year>\d{4})\.?\s*$
    """,
    re.VERBOSE,
)

_GBT_CONFERENCE = re.compile(
    r"""
    ^\[(?P<num>\d+)\]\s*
    (?P<authors>[^\.]+?)\.\s*
    (?P<title>[^\[]+?)\s*
    \[C\]//(?P<journal>[^,]+?)(?:,\s*)?
    (?:(?P<city>[^:]+?):\s*)?
    (?:(?P<publisher>[^,]+?),\s*)?
    (?P<year>\d{4})
    (?:\s*:\s*(?P<pages>[\d\-]+))?
    \.?\s*$
    """,
    re.VERBOSE,
)


def _split_bibtex_authors(author_str: str) -> list[str]:
    """Split a BibTeX author string into a list of individual author names.

    Handles common delimiters: 'and', commas, semicolons.
    Strips whitespace and removes surrounding braces.

    Args:
        author_str: Raw author string from BibTeX field.

    Returns:
        List of cleaned author name strings.
    """
    if not author_str or not author_str.strip():
        return []

    cleaned = author_str.strip()
    # Remove surrounding braces
    cleaned = re.sub(r"[{}]", "", cleaned)

    # Try splitting by ' and ' first (standard BibTeX delimiter)
    if " and " in cleaned:
        parts = re.split(r"\s+and\s+", cleaned, flags=re.IGNORECASE)
    elif ";" in cleaned:
        parts = cleaned.split(";")
    else:
        # Comma-separated — but be careful: "Last, First" is ONE author
        # Heuristic: if there are more commas after splitting by ' and ',
        # treat each "Last, First" as one author
        parts = _split_comma_authors(cleaned)

    return [p.strip() for p in parts if p.strip()]


def _split_comma_authors(text: str) -> list[str]:
    """Split comma-separated authors, respecting 'Last, First' pairs.

    Examples:
        "Smith, John, Doe, Jane" → ["Smith, John", "Doe, Jane"]
        "Smith J, Doe J" → ["Smith J", "Doe J"]

    Args:
        text: Comma-separated author string.

    Returns:
        List of author name strings.
    """
    tokens = [t.strip() for t in text.split(",") if t.strip()]

    # If we have an even number of tokens, pair them as "Last, First"
    if len(tokens) >= 2 and len(tokens) % 2 == 0:
        pairs = []
        for i in range(0, len(tokens), 2):
            pairs.append(f"{tokens[i]}, {tokens[i + 1]}")
        return pairs

    # Otherwise treat each token as a separate author
    return tokens


def parse_bibtex(content: str, *, source_file: str | None = None) -> list[ReferenceItem]:
    """Parse a BibTeX string into a list of ReferenceItem objects.

    Args:
        content: BibTeX file content as a string.
        source_file: Optional filename for tracing the source.

    Returns:
        List of parsed ReferenceItem objects.

    Raises:
        ParserError: If the BibTeX content cannot be parsed.
    """
    try:
        library = bibtexparser.parse_string(content)
    except Exception as exc:
        raise ParserError(
            f"Failed to parse BibTeX content: {exc}",
            details=str(exc),
        ) from exc

    if library.failed_blocks:
        logger.warning(
            "bibtex_parse_warnings",
            failed_count=len(library.failed_blocks),
            source=source_file,
        )

    items: list[ReferenceItem] = []
    for entry in library.entries:
        item = _entry_to_reference(entry, source_file=source_file)
        if item is not None:
            items.append(item)

    logger.info(
        "bibtex_parsed",
        total_entries=len(library.entries),
        parsed_items=len(items),
        failed_blocks=len(library.failed_blocks),
        source=source_file,
    )
    return items


def parse_bibtex_file(file_path: Union[str, Path]) -> list[ReferenceItem]:
    """Parse a .bib file into a list of ReferenceItem objects.

    Args:
        file_path: Path to the .bib file.

    Returns:
        List of parsed ReferenceItem objects.

    Raises:
        ParserError: If the file cannot be read or parsed.
    """
    path = Path(file_path)
    if not path.exists():
        raise ParserError(f"File not found: {path}", details=str(path))
    if not path.suffix.lower() == ".bib":
        raise ParserError(
            f"Expected .bib file, got: {path.suffix}",
            details=str(path),
        )

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    except Exception as exc:
        raise ParserError(
            f"Failed to read file: {path}",
            details=str(exc),
        ) from exc

    return parse_bibtex(content, source_file=str(path))


def parse_gbt7714(content: str, *, source_file: str | None = None) -> list[ReferenceItem]:
    """Parse GBT 7714 formatted citation text into ReferenceItem objects.

    Supports common GBT 7714-2015 formats:
    - Journal articles [J]
    - Books [M]
    - Conference papers [C]

    Args:
        content: Plain text with GBT 7714 formatted references.
        source_file: Optional filename for tracing the source.

    Returns:
        List of parsed ReferenceItem objects.
    """
    items: list[ReferenceItem] = []
    lines = content.strip().splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        item = _parse_gbt_line(line, source_file=source_file)
        if item is not None:
            items.append(item)

    logger.info(
        "gbt7714_parsed",
        total_lines=len(lines),
        parsed_items=len(items),
        source=source_file,
    )
    return items


def parse_gbt7714_file(file_path: Union[str, Path]) -> list[ReferenceItem]:
    """Parse a text file with GBT 7714 formatted references.

    Args:
        file_path: Path to the text file.

    Returns:
        List of parsed ReferenceItem objects.

    Raises:
        ParserError: If the file cannot be read or parsed.
    """
    path = Path(file_path)
    if not path.exists():
        raise ParserError(f"File not found: {path}", details=str(path))

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    except Exception as exc:
        raise ParserError(
            f"Failed to read file: {path}",
            details=str(exc),
        ) from exc

    return parse_gbt7714(content, source_file=str(path))


def detect_format(content: str) -> str:
    """Detect whether the content is BibTeX or GBT 7714 format.

    Args:
        content: File content string.

    Returns:
        'bibtex' or 'gbt7714' or 'unknown'.
    """
    stripped = content.strip()
    if stripped.startswith("@") or "@article" in stripped.lower() or "@book" in stripped.lower():
        return "bibtex"
    if re.search(r"\[\d+\]", stripped):
        return "gbt7714"
    return "unknown"


def parse_file(file_path: Union[str, Path]) -> list[ReferenceItem]:
    """Auto-detect format and parse a file into ReferenceItem objects.

    Args:
        file_path: Path to the .bib or text file.

    Returns:
        List of parsed ReferenceItem objects.

    Raises:
        ParserError: If the format cannot be detected or parsing fails.
    """
    path = Path(file_path)
    if not path.exists():
        raise ParserError(f"File not found: {path}", details=str(path))

    # Try by extension first
    if path.suffix.lower() == ".bib":
        return parse_bibtex_file(path)

    # Read and detect format
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")

    fmt = detect_format(content)
    if fmt == "bibtex":
        return parse_bibtex(content, source_file=str(path))
    if fmt == "gbt7714":
        return parse_gbt7714(content, source_file=str(path))

    raise ParserError(
        f"Cannot detect citation format in: {path}",
        details="Expected BibTeX (starts with @) or GBT 7714 (starts with [N]).",
    )


def _entry_to_reference(
    entry: bibtexparser.model.Entry,
    *,
    source_file: str | None = None,
) -> ReferenceItem | None:
    """Convert a bibtexparser Entry to a ReferenceItem.

    Args:
        entry: Parsed BibTeX entry.
        source_file: Optional source file path.

    Returns:
        ReferenceItem or None if the entry has no title.
    """
    fields: dict[str, str] = {f.key: f.value for f in entry.fields}

    title = fields.get("title", "").strip()
    if not title:
        logger.warning("skip_no_title", key=entry.key, source=source_file)
        return None

    author_str = fields.get("author", "")
    authors = _split_bibtex_authors(author_str)

    return ReferenceItem(
        title=title,
        authors=authors,
        year=fields.get("year"),
        journal=fields.get("journal") or fields.get("booktitle"),
        doi=fields.get("doi"),
        volume=fields.get("volume"),
        issue=fields.get("number"),
        pages=fields.get("pages"),
        publisher=fields.get("publisher"),
        entry_type=entry.entry_type,
        citation_key=entry.key,
        raw_text=None,
        source_file=source_file,
    )


def _parse_gbt_line(line: str, *, source_file: str | None = None) -> ReferenceItem | None:
    """Parse a single GBT 7714 formatted line into a ReferenceItem.

    Tries journal, book, and conference patterns in order.

    Args:
        line: A single citation line.
        source_file: Optional source file path.

    Returns:
        ReferenceItem or None if no pattern matches.
    """
    for pattern, entry_type in [
        (_GBT_JOURNAL, "article"),
        (_GBT_BOOK, "book"),
        (_GBT_CONFERENCE, "inproceedings"),
    ]:
        match = pattern.match(line)
        if match:
            return _gbt_match_to_reference(match, entry_type, source_file=source_file)

    logger.debug("gbt_no_match", line=line[:80])
    return None


def _gbt_match_to_reference(
    match: re.Match,
    entry_type: str,
    *,
    source_file: str | None = None,
) -> ReferenceItem:
    """Convert a GBT 7714 regex match to a ReferenceItem.

    Args:
        match: Regex match object with named groups.
        entry_type: BibTeX-style entry type.
        source_file: Optional source file path.

    Returns:
        A ReferenceItem.
    """
    groups = match.groupdict()
    authors_str = groups.get("authors", "")
    authors = [a.strip() for a in re.split(r"[;,，；]", authors_str) if a.strip()]

    return ReferenceItem(
        title=groups.get("title", "").strip(),
        authors=authors,
        year=groups.get("year"),
        journal=groups.get("journal", "").strip() or None,
        doi=None,
        volume=groups.get("volume"),
        issue=groups.get("issue"),
        pages=groups.get("pages"),
        publisher=groups.get("publisher", "").strip() or None,
        entry_type=entry_type,
        citation_key=groups.get("num"),
        raw_text=match.group(0),
        source_file=source_file,
    )
