"""CLI interface for RefChecker.

Provides command-line access to citation parsing and verification.

Usage:
    refchecker parse <file> [--format json|table]
    refchecker verify <file> [--adapters crossref,s2,openalex] [--output results.csv]
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click

from refchecker import __version__
from refchecker.core.logging import configure_logging, get_logger
from refchecker.core.parser import parse_file

logger = get_logger(__name__)


def _format_table(items: list) -> str:
    """Format parsed references as a human-readable table.

    Args:
        items: List of ReferenceItem objects.

    Returns:
        Formatted table string.
    """
    if not items:
        return "No references found."

    lines = []
    header = f"{'#':<4} {'Key':<25} {'Title':<50} {'Year':<6} {'Authors'}"
    lines.append(header)
    lines.append("-" * len(header))

    for i, item in enumerate(items, 1):
        key = (item.citation_key or "")[:24]
        title = item.title[:49]
        year = str(item.year or "")
        authors = item.display_authors[:30]
        lines.append(f"{i:<4} {key:<25} {title:<50} {year:<6} {authors}")

    lines.append(f"\nTotal: {len(items)} references")
    return "\n".join(lines)


def _items_to_dicts(items: list) -> list[dict]:
    """Convert ReferenceItem objects to JSON-serializable dicts.

    Args:
        items: List of ReferenceItem objects.

    Returns:
        List of dictionaries.
    """
    return [
        {
            "title": item.title,
            "authors": item.authors,
            "year": item.year,
            "journal": item.journal,
            "doi": item.doi,
            "volume": item.volume,
            "issue": item.issue,
            "pages": item.pages,
            "publisher": item.publisher,
            "entry_type": item.entry_type,
            "citation_key": item.citation_key,
        }
        for item in items
    ]


@click.group()
@click.version_option(version=__version__, prog_name="refchecker")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose (DEBUG) logging.")
def cli(verbose: bool) -> None:
    """RefChecker — Citation verification for academic papers.

    Parse and verify references from .bib files or GBT 7714 text.
    """
    level = "DEBUG" if verbose else "INFO"
    configure_logging(level=level)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format.",
)
def parse(file: str, output_format: str) -> None:
    """Parse citations from a .bib or text file.

    FILE is the path to a BibTeX (.bib) or GBT 7714 text file.
    """
    try:
        items = parse_file(file)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(json.dumps(_items_to_dicts(items), indent=2, ensure_ascii=False))
    else:
        click.echo(_format_table(items))


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--adapters",
    default="crossref,s2,openalex",
    help="Comma-separated list of verification adapters to use.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file path (CSV or Excel).",
)
def verify(file: str, adapters: str, output: Optional[str]) -> None:
    """Verify citations from a .bib or text file.

    FILE is the path to a BibTeX (.bib) or GBT 7714 text file.

    Note: Verification engine is not yet implemented.
    This command currently parses the file only.
    """
    try:
        items = parse_file(file)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Parsed {len(items)} references from {file}")
    click.echo(f"Requested adapters: {adapters}")
    click.echo("Verification engine: not yet implemented (Phase 2)")
    click.echo()

    for i, item in enumerate(items, 1):
        click.echo(f"  [{i}] {item.title} ({item.year or '?'}) — {item.display_authors}")


if __name__ == "__main__":
    cli()
