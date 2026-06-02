"""CLI interface for RefChecker.

Provides command-line access to citation parsing, verification, and
API key management.

Usage:
    refchecker parse <file> [--format json|table]
    refchecker verify <file> [--adapters crossref,s2,openalex] [--output results.csv]
    refchecker set-key <adapter> <api-key>
    refchecker get-key <adapter>
    refchecker delete-key <adapter>
    refchecker list-keys
"""

import asyncio
import csv
import io
import json
import sys
from pathlib import Path
from typing import Optional

import click

from refchecker import __version__
from refchecker.adapters.aminer_adapter import AMinerAdapter
from refchecker.adapters.baidu_adapter import BaiduAdapter
from refchecker.adapters.cnki_adapter import CNKIAdapter
from refchecker.adapters.crossref_adapter import CrossrefAdapter
from refchecker.adapters.openalex_adapter import OpenAlexAdapter
from refchecker.adapters.s2_adapter import S2Adapter
from refchecker.config import load_config
from refchecker.core.logging import configure_logging, get_logger
from refchecker.core.models import VerificationStatus
from refchecker.core.parser import parse_file
from refchecker.engine import VerificationEngine

logger = get_logger(__name__)

_ADAPTER_REGISTRY = {
    "crossref": CrossrefAdapter,
    "s2": S2Adapter,
    "openalex": OpenAlexAdapter,
    "aminer": AMinerAdapter,
    "baidu": BaiduAdapter,
    "cnki": CNKIAdapter,
}

_STATUS_COLORS = {
    VerificationStatus.VERIFIED: "green",
    VerificationStatus.SUSPICIOUS: "yellow",
    VerificationStatus.LIKELY_FABRICATED: "red",
    VerificationStatus.UNABLE_TO_VERIFY: "blue",
    VerificationStatus.PENDING: "white",
}


def _format_table(items: list) -> str:
    """Format parsed references as a human-readable table."""
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


def _format_results_table(results: list) -> str:
    """Format verification results as a colored status table."""
    if not results:
        return "No results."

    lines = []
    lines.append(f"{'#':<4} {'Status':<6} {'Score':<7} {'Title':<50} {'Best Source'}")
    lines.append("-" * 85)

    for i, r in enumerate(results, 1):
        status = r.status.symbol
        score = f"{r.best_score:.2f}"
        title = r.reference.title[:49]
        best_source = ""
        for m in r.matches:
            if m.found and m.composite_score == r.best_score:
                best_source = m.adapter_name
                break
        lines.append(f"{i:<4} {status}    {score:<7} {title:<50} {best_source}")

    # Summary
    verified = sum(1 for r in results if r.status == VerificationStatus.VERIFIED)
    suspicious = sum(1 for r in results if r.status == VerificationStatus.SUSPICIOUS)
    fabricated = sum(1 for r in results if r.status == VerificationStatus.LIKELY_FABRICATED)
    unable = sum(1 for r in results if r.status == VerificationStatus.UNABLE_TO_VERIFY)

    lines.append(f"\nSummary: {verified} verified, {suspicious} suspicious, {fabricated} fabricated, {unable} unable to verify")
    return "\n".join(lines)


def _results_to_dicts(results: list) -> list[dict]:
    """Convert verification results to JSON-serializable dicts."""
    out = []
    for r in results:
        d = {
            "title": r.reference.title,
            "authors": r.reference.authors,
            "year": r.reference.year,
            "doi": r.reference.doi,
            "status": r.status.value,
            "best_score": round(r.best_score, 3),
            "matches": [],
        }
        for m in r.matches:
            d["matches"].append({
                "adapter": m.adapter_name,
                "found": m.found,
                "composite_score": round(m.composite_score, 3),
                "matched_title": m.matched_title,
                "error": m.error,
            })
        out.append(d)
    return out


def _results_to_csv(results: list) -> str:
    """Convert verification results to CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["#", "Title", "Year", "DOI", "Status", "Best Score", "Best Source"])
    for i, r in enumerate(results, 1):
        best_source = ""
        for m in r.matches:
            if m.found and m.composite_score == r.best_score:
                best_source = m.adapter_name
                break
        writer.writerow([
            i,
            r.reference.title,
            r.reference.year,
            r.reference.doi,
            r.status.value,
            f"{r.best_score:.3f}",
            best_source,
        ])
    return buf.getvalue()


def _build_adapters(adapter_names: list[str]) -> list:
    """Build adapter instances from names.

    Args:
        adapter_names: List of adapter names.

    Returns:
        List of VerificationAdapter instances.
    """
    config = load_config()
    adapters = []
    for name in adapter_names:
        name = name.strip().lower()
        if name not in _ADAPTER_REGISTRY:
            click.echo(f"Warning: Unknown adapter '{name}', skipping.", err=True)
            continue
        adapter_config = config.get_adapter_config(name)
        adapter_cls = _ADAPTER_REGISTRY[name]
        adapters.append(adapter_cls(**adapter_config))
    return adapters


async def _run_verify(file: str, adapter_names: list[str], output_format: str, output_path: Optional[str]) -> None:
    """Async verify implementation."""
    items = parse_file(file)
    if not items:
        click.echo("No references found in file.")
        return

    click.echo(f"Parsed {len(items)} references from {file}")
    click.echo(f"Using adapters: {', '.join(adapter_names)}")
    click.echo()

    adapters = _build_adapters(adapter_names)
    if not adapters:
        click.echo("Error: No valid adapters specified.", err=True)
        sys.exit(1)

    engine = VerificationEngine(adapters)

    with click.progressbar(length=len(items), label="Verifying") as bar:
        def on_progress(idx: int, result: object) -> None:
            bar.update(1)

        results = await engine.verify_batch(items, progress_callback=on_progress)

    click.echo()

    # Output
    if output_format == "json":
        text = json.dumps(_results_to_dicts(results), indent=2, ensure_ascii=False)
    elif output_format == "csv":
        text = _results_to_csv(results)
    else:
        text = _format_results_table(results)

    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        click.echo(f"Results written to {output_path}")
    else:
        click.echo(text)


@click.group()
@click.version_option(version=__version__, prog_name="refchecker")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose (DEBUG) logging.")
def cli(verbose: bool) -> None:
    """RefChecker — Citation verification for academic papers."""
    level = "DEBUG" if verbose else "INFO"
    configure_logging(level=level)


# --- API Key Management Commands ---

_ADAPTER_TO_KEY_NAME = {
    "s2": "s2_api_key",
    "openalex": "openalex_api_key",
    "aminer": "aminer_api_key",
}


@cli.command("set-key")
@click.argument("adapter", type=click.Choice(list(_ADAPTER_TO_KEY_NAME.keys())))
@click.argument("api_key")
def set_key(adapter: str, api_key: str) -> None:
    """Store an API key for an adapter (encrypted).

    The key is saved in the OS-native credential store (Keychain on macOS,
    Secret Service on Linux, Windows Credential Manager on Windows).

    \b
    Supported adapters: s2, openalex, aminer
    """
    try:
        from refchecker.core.key_store import store_key
    except ImportError:
        click.echo("Error: 'keyring' package is required for encrypted key storage.", err=True)
        click.echo("Install it with: pip install keyring", err=True)
        sys.exit(1)

    key_name = _ADAPTER_TO_KEY_NAME[adapter]
    try:
        store_key(key_name, api_key)
        click.echo(f"✅ API key for '{adapter}' stored securely.")
    except Exception as exc:
        click.echo(f"Error storing key: {exc}", err=True)
        sys.exit(1)


@cli.command("get-key")
@click.argument("adapter", type=click.Choice(list(_ADAPTER_TO_KEY_NAME.keys())))
def get_key(adapter: str) -> None:
    """Check whether an API key is stored for an adapter.

    For security, the key value is NOT displayed — only its presence.
    """
    try:
        from refchecker.core.key_store import load_key
    except ImportError:
        click.echo("Error: 'keyring' package is required.", err=True)
        sys.exit(1)

    key_name = _ADAPTER_TO_KEY_NAME[adapter]
    value = load_key(key_name)
    if value is not None:
        masked = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
        click.echo(f"🔑 Key for '{adapter}': {masked} (stored)")
    else:
        click.echo(f"ℹ️  No key stored for '{adapter}'.")


@cli.command("delete-key")
@click.argument("adapter", type=click.Choice(list(_ADAPTER_TO_KEY_NAME.keys())))
def delete_key(adapter: str) -> None:
    """Remove a stored API key for an adapter."""
    try:
        from refchecker.core.key_store import delete_key as _delete_key
    except ImportError:
        click.echo("Error: 'keyring' package is required.", err=True)
        sys.exit(1)

    key_name = _ADAPTER_TO_KEY_NAME[adapter]
    deleted = _delete_key(key_name)
    if deleted:
        click.echo(f"🗑️  Key for '{adapter}' deleted.")
    else:
        click.echo(f"ℹ️  No key to delete for '{adapter}'.")


@cli.command("list-keys")
def list_keys() -> None:
    """List all adapters and their key storage status."""
    try:
        from refchecker.core.key_store import list_keys as _list_keys
    except ImportError:
        click.echo("Error: 'keyring' package is required.", err=True)
        sys.exit(1)

    keys = _list_keys()
    click.echo("Adapter Key Status:")
    click.echo("-" * 40)
    for entry in keys:
        status = "🔑 stored" if entry.has_key else "—  none"
        click.echo(f"  {entry.adapter_name:<12} {status}")
    click.echo()
    click.echo("Use 'refchecker set-key <adapter> <key>' to store a key.")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
def parse(file: str, output_format: str) -> None:
    """Parse citations from a .bib or text file."""
    try:
        items = parse_file(file)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(json.dumps(
            [{"title": i.title, "authors": i.authors, "year": i.year, "doi": i.doi, "journal": i.journal, "citation_key": i.citation_key} for i in items],
            indent=2, ensure_ascii=False,
        ))
    else:
        click.echo(_format_table(items))


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--adapters", default="crossref,s2,openalex", help="Comma-separated adapters.")
@click.option("--format", "output_format", type=click.Choice(["table", "json", "csv"]), default="table")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path.")
def verify(file: str, adapters: str, output_format: str, output: Optional[str]) -> None:
    """Verify citations from a .bib or text file."""
    adapter_names = [a.strip() for a in adapters.split(",")]
    asyncio.run(_run_verify(file, adapter_names, output_format, output))


if __name__ == "__main__":
    cli()
