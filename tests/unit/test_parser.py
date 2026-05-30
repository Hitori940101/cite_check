"""Unit tests for the BibTeX and GBT 7714 parsers."""

from pathlib import Path

import pytest

from refchecker.core.exceptions import ParserError
from refchecker.core.models import ReferenceItem
from refchecker.core.parser import (
    _split_bibtex_authors,
    _split_comma_authors,
    detect_format,
    parse_bibtex,
    parse_bibtex_file,
    parse_file,
    parse_gbt7714,
    parse_gbt7714_file,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestSplitBibtexAuthors:
    """Tests for BibTeX author string splitting."""

    def test_and_delimiter(self) -> None:
        """Split on 'and' delimiter."""
        result = _split_bibtex_authors("Smith, John and Doe, Jane")
        assert result == ["Smith, John", "Doe, Jane"]

    def test_multiple_and(self) -> None:
        """Split multiple 'and'-separated authors."""
        result = _split_bibtex_authors("A and B and C")
        assert result == ["A", "B", "C"]

    def test_semicolon_delimiter(self) -> None:
        """Split on semicolon delimiter."""
        result = _split_bibtex_authors("Smith J; Doe J")
        assert result == ["Smith J", "Doe J"]

    def test_brace_removal(self) -> None:
        """Remove curly braces from names."""
        result = _split_bibtex_authors("{Smith, John}")
        assert result == ["Smith, John"]

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        assert _split_bibtex_authors("") == []

    def test_whitespace_only(self) -> None:
        """Whitespace-only string returns empty list."""
        assert _split_bibtex_authors("   ") == []


class TestSplitCommaAuthors:
    """Tests for comma-separated author splitting."""

    def test_even_pairs(self) -> None:
        """Even number of tokens → paired as Last, First."""
        result = _split_comma_authors("Smith, John, Doe, Jane")
        assert result == ["Smith, John", "Doe, Jane"]

    def test_odd_tokens(self) -> None:
        """Odd number of tokens → each is a separate author."""
        result = _split_comma_authors("Smith J, Doe J, Brown K")
        assert result == ["Smith J", "Doe J", "Brown K"]


class TestParseBibtex:
    """Tests for BibTeX parsing."""

    def test_parse_article(self) -> None:
        """Parse a standard article entry."""
        bib = """
        @article{test2023,
          title = {Test Paper},
          author = {Smith, John and Doe, Jane},
          journal = {Nature},
          year = {2023},
          volume = {1},
          doi = {10.1234/test}
        }
        """
        items = parse_bibtex(bib)
        assert len(items) == 1
        item = items[0]
        assert item.title == "Test Paper"
        assert item.authors == ["Smith, John", "Doe, Jane"]
        assert item.year == 2023
        assert item.journal == "Nature"
        assert item.doi == "10.1234/test"
        assert item.volume == "1"
        assert item.entry_type == "article"
        assert item.citation_key == "test2023"

    def test_parse_multiple_entries(self) -> None:
        """Parse multiple BibTeX entries."""
        bib = """
        @article{a1, title = {Paper One}, year = {2020}}
        @book{b1, title = {Book Two}, year = {2021}}
        """
        items = parse_bibtex(bib)
        assert len(items) == 2

    def test_parse_book_with_booktitle(self) -> None:
        """Book title maps to journal field."""
        bib = """
        @inproceedings{conf1,
          title = {Conference Paper},
          booktitle = {NeurIPS},
          year = {2023}
        }
        """
        items = parse_bibtex(bib)
        assert len(items) == 1
        assert items[0].journal == "NeurIPS"

    def test_parse_no_title_entry_skipped(self) -> None:
        """Entries without a title are skipped."""
        bib = """
        @article{notitle,
          author = {Smith, John},
          year = {2023}
        }
        """
        items = parse_bibtex(bib)
        assert len(items) == 0

    def test_parse_doi_normalization(self) -> None:
        """DOI is normalized during parsing."""
        bib = """
        @article{doi_test,
          title = {Test},
          doi = {https://doi.org/10.1234/test}
        }
        """
        items = parse_bibtex(bib)
        assert items[0].doi == "10.1234/test"

    def test_parse_malformed_bibtex_graceful(self) -> None:
        """Malformed BibTeX is handled gracefully (logged, not raised)."""
        # bibtexparser v2 logs failures in failed_blocks rather than raising
        items = parse_bibtex("@article{broken, title = {unclosed")
        assert isinstance(items, list)
        # The malformed entry produces no valid items
        assert len(items) == 0

    def test_source_file_propagation(self) -> None:
        """Source file is propagated to ReferenceItem."""
        bib = "@article{t, title = {T}}"
        items = parse_bibtex(bib, source_file="test.bib")
        assert items[0].source_file == "test.bib"


class TestParseBibtexFile:
    """Tests for BibTeX file parsing."""

    def test_parse_sample_file(self) -> None:
        """Parse the sample .bib fixture file."""
        items = parse_bibtex_file(FIXTURES / "sample.bib")
        assert len(items) == 5
        titles = {item.title for item in items}
        assert "Attention Is All You Need" in titles
        assert "Reinforcement Learning: An Introduction" in titles

    def test_file_not_found(self) -> None:
        """Missing file raises ParserError."""
        with pytest.raises(ParserError, match="File not found"):
            parse_bibtex_file("/nonexistent/path/test.bib")

    def test_wrong_extension(self) -> None:
        """Non-.bib file raises ParserError."""
        with pytest.raises(ParserError, match="Expected .bib"):
            parse_bibtex_file(FIXTURES / "sample_gbt.txt")


class TestParseGbt7714:
    """Tests for GBT 7714 parsing."""

    def test_journal_article(self) -> None:
        """Parse a journal article [J] format."""
        text = "[1] Zhang S, Li M. Deep Learning[J]. Nature, 2023, 10(2): 100-110."
        items = parse_gbt7714(text)
        assert len(items) == 1
        item = items[0]
        assert item.title == "Deep Learning"
        assert item.year == 2023
        assert item.journal == "Nature"
        assert item.volume == "10"
        assert item.issue == "2"
        assert item.pages == "100-110"
        assert item.entry_type == "article"

    def test_book(self) -> None:
        """Parse a book [M] format."""
        text = "[2] Goodfellow I, Bengio Y. Deep Learning[M]. MIT Press, 2016."
        items = parse_gbt7714(text)
        assert len(items) == 1
        item = items[0]
        assert item.title == "Deep Learning"
        assert item.publisher == "MIT Press"
        assert item.year == 2016
        assert item.entry_type == "book"

    def test_conference_paper(self) -> None:
        """Parse a conference paper [C] format."""
        text = "[3] Devlin J. BERT[C]//NAACL-HLT, 2019: 4171-4186."
        items = parse_gbt7714(text)
        assert len(items) == 1
        item = items[0]
        assert item.title == "BERT"
        assert item.year == 2019
        assert item.pages == "4171-4186"
        assert item.entry_type == "inproceedings"

    def test_multiple_references(self) -> None:
        """Parse multiple GBT 7714 references."""
        text = """[1] Author A. Title One[J]. Journal, 2020, 1.
[2] Author B. Title Two[M]. Publisher, 2021."""
        items = parse_gbt7714(text)
        assert len(items) == 2

    def test_empty_lines_ignored(self) -> None:
        """Empty lines are skipped."""
        text = "[1] A. Title[J]. J, 2020, 1.\n\n[2] B. Title[M]. P, 2021."
        items = parse_gbt7714(text)
        assert len(items) == 2

    def test_unrecognized_line_skipped(self) -> None:
        """Lines that don't match any pattern are skipped."""
        text = "This is not a citation"
        items = parse_gbt7714(text)
        assert len(items) == 0

    def test_raw_text_preserved(self) -> None:
        """The original line text is preserved in raw_text."""
        text = "[1] A. Title[J]. Journal, 2023, 1."
        items = parse_gbt7714(text)
        assert items[0].raw_text is not None

    def test_authors_split_by_semicolon(self) -> None:
        """GBT authors split on semicolons."""
        text = "[1] Zhang S; Li M. Title[J]. Journal, 2023, 1."
        items = parse_gbt7714(text)
        assert len(items[0].authors) == 2


class TestParseGbtFile:
    """Tests for GBT 7714 file parsing."""

    def test_parse_sample_file(self) -> None:
        """Parse the sample GBT fixture file."""
        items = parse_gbt7714_file(FIXTURES / "sample_gbt.txt")
        assert len(items) == 3

    def test_file_not_found(self) -> None:
        """Missing file raises ParserError."""
        with pytest.raises(ParserError, match="File not found"):
            parse_gbt7714_file("/nonexistent/path/gbt.txt")


class TestDetectFormat:
    """Tests for format detection."""

    def test_detect_bibtex(self) -> None:
        """Detect BibTeX format."""
        assert detect_format("@article{key, title={T}}") == "bibtex"

    def test_detect_gbt(self) -> None:
        """Detect GBT 7714 format."""
        assert detect_format("[1] Author. Title[J]. Journal, 2023.") == "gbt7714"

    def test_detect_unknown(self) -> None:
        """Unknown format detected."""
        assert detect_format("Some random text") == "unknown"


class TestParseFileAutoDetect:
    """Tests for auto-detect parse_file()."""

    def test_bib_extension(self) -> None:
        """File with .bib extension uses BibTeX parser."""
        items = parse_file(FIXTURES / "sample.bib")
        assert len(items) == 5

    def test_gbt_text_file(self) -> None:
        """Text file with GBT content uses GBT parser."""
        items = parse_file(FIXTURES / "sample_gbt.txt")
        assert len(items) == 3

    def test_file_not_found(self) -> None:
        """Missing file raises ParserError."""
        with pytest.raises(ParserError, match="File not found"):
            parse_file("/nonexistent/path/file.txt")

    def test_unknown_format(self) -> None:
        """File with unrecognized format raises ParserError."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("This is not a citation file.\nJust random text.")
            f.flush()
            with pytest.raises(ParserError, match="Cannot detect"):
                parse_file(f.name)
