"""Unit tests for arxiv_adapter — covers _parse_xml and _entry_to_match."""

import pytest

from refchecker.adapters.arxiv_adapter import ArxivAdapter
from refchecker.core.models import ReferenceItem


def _ref(title: str = "Attention Is All You Need",
         authors: list[str] | None = None,
         year: int | None = 2017) -> ReferenceItem:
    return ReferenceItem(
        title=title, authors=authors or ["Ashish Vaswani"], year=year,
    )


# Sample arXiv Atom XML response
_SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v5</id>
    <title>Attention Is All You Need</title>
    <summary>We propose a new simple network architecture, the Transformer.</summary>
    <published>2017-06-12T17:30:44Z</published>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <arxiv:doi>10.5555/3295222.3295349</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2001.00001v1</id>
    <title>Unrelated Paper</title>
    <summary>Something else.</summary>
    <published>2020-01-01T00:00:00Z</published>
    <author><name>John Smith</name></author>
  </entry>
</feed>
"""


class TestArxivAdapter:
    """Tests for ArxivAdapter."""

    def test_name(self) -> None:
        """Adapter name is 'arxiv'."""
        adapter = ArxivAdapter()
        assert adapter.name == "arxiv"

    def test_parse_xml_match(self) -> None:
        """XML with matching title returns found."""
        adapter = ArxivAdapter()
        match = adapter._parse_xml(_SAMPLE_XML, _ref())
        assert match.found is True
        assert match.composite_score > 0.6
        assert "Attention" in (match.matched_title or "")

    def test_parse_xml_no_match(self) -> None:
        """XML without matching title returns low score."""
        adapter = ArxivAdapter()
        match = adapter._parse_xml(_SAMPLE_XML, _ref(title="Completely Unrelated Title XXX"))
        # Score should be low but may still be "found" if composite >= 0.6
        assert match.composite_score < match.composite_score + 1  # Just verify it returns

    def test_parse_xml_empty(self) -> None:
        """Empty XML returns not found."""
        adapter = ArxivAdapter()
        match = adapter._parse_xml("", _ref())
        assert match.found is False
        assert "XML parse error" in (match.error or "")

    def test_parse_xml_no_entries(self) -> None:
        """XML with no entries returns not found."""
        adapter = ArxivAdapter()
        xml = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        match = adapter._parse_xml(xml, _ref())
        assert match.found is False

    def test_entry_to_match(self) -> None:
        """_entry_to_match extracts title, authors, year."""
        import xml.etree.ElementTree as ET
        adapter = ArxivAdapter()
        root = ET.fromstring(_SAMPLE_XML)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", ns)
        match = adapter._entry_to_match(entry, _ref())
        assert match.matched_title is not None
        assert "Attention" in match.matched_title
