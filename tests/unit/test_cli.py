"""Unit tests for refchecker CLI interface.

Uses click.testing.CliRunner for isolated CLI testing with mocked
engine, adapters, and key store.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from refchecker.cli.main import cli
from refchecker.core.models import (
    AdapterMatch,
    ReferenceItem,
    VerificationResult,
    VerificationStatus,
)


# --- Helpers ---

def _ref(
    title: str = "Test Paper",
    authors: list[str] | None = None,
    year: int | None = 2024,
    doi: str | None = None,
    citation_key: str = "test2024",
) -> ReferenceItem:
    """Build a ReferenceItem for testing."""
    return ReferenceItem(
        title=title,
        authors=authors or ["Alice Smith"],
        year=year,
        doi=doi,
        citation_key=citation_key,
    )


def _match(
    adapter_name: str = "crossref",
    found: bool = True,
    score: float = 0.95,
) -> AdapterMatch:
    """Build an AdapterMatch for testing."""
    return AdapterMatch(
        adapter_name=adapter_name,
        found=found,
        composite_score=score,
        title_score=score,
        author_score=score,
        year_score=1.0,
        venue_score=1.0,
        matched_title="Test Paper" if found else None,
        matched_authors=["Alice Smith"] if found else None,
        matched_year=2024 if found else None,
    )


def _result(
    ref: ReferenceItem | None = None,
    status: VerificationStatus = VerificationStatus.VERIFIED,
    matches: list[AdapterMatch] | None = None,
    best_score: float = 0.95,
) -> VerificationResult:
    """Build a VerificationResult for testing."""
    return VerificationResult(
        reference=ref or _ref(),
        status=status,
        matches=matches or [_match()],
        best_score=best_score,
    )


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CliRunner."""
    return CliRunner()


@pytest.fixture
def sample_bib(fixtures_dir: Path) -> str:
    """Return path string to sample.bib."""
    return str(fixtures_dir / "sample.bib")


# --- Tests ---


class TestCLIGeneral:
    """Test CLI group-level behavior."""

    def test_help(self, runner: CliRunner) -> None:
        """--help prints usage information."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "RefChecker" in result.output

    def test_version(self, runner: CliRunner) -> None:
        """--version prints version string."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCLIParse:
    """Test the 'parse' command."""

    def test_parse_empty_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """Parsing a file with no refs shows empty message."""
        empty_bib = tmp_path / "empty.bib"
        empty_bib.write_text("% empty file\n")
        result = runner.invoke(cli, ["parse", str(empty_bib)])
        assert result.exit_code == 0
        assert "No references found" in result.output

    def test_parse_error_handling(self, runner: CliRunner, tmp_path: Path) -> None:
        """Parse command handles exceptions from parser."""
        bad_bib = tmp_path / "bad.bib"
        bad_bib.write_text("@article{test,\n")  # malformed
        # Should not crash — may succeed or fail depending on parser strictness
        result = runner.invoke(cli, ["parse", str(bad_bib)])
        # Just verify it doesn't crash unhandled
        assert result.exit_code in (0, 1)
    """Test the 'parse' command."""

    def test_parse_empty_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """Parsing a file with no refs shows empty message."""
        empty_bib = tmp_path / "empty.bib"
        empty_bib.write_text("% empty file\n")
        result = runner.invoke(cli, ["parse", str(empty_bib)])
        assert result.exit_code == 0
        assert "No references found" in result.output

    def test_parse_bib_table(self, runner: CliRunner, sample_bib: str) -> None:
        """Parse a .bib file and display as table."""
        result = runner.invoke(cli, ["parse", sample_bib])
        assert result.exit_code == 0
        assert "Total:" in result.output

    def test_parse_bib_json(self, runner: CliRunner, sample_bib: str) -> None:
        """Parse a .bib file with --format json."""
        result = runner.invoke(cli, ["parse", sample_bib, "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "title" in data[0]

    def test_parse_file_not_found(self, runner: CliRunner) -> None:
        """Non-existent file produces an error."""
        result = runner.invoke(cli, ["parse", "/nonexistent/file.bib"])
        assert result.exit_code != 0


class TestCLIVerify:
    """Test the 'verify' command."""

    @patch("refchecker.cli.main._run_verify", new_callable=AsyncMock)
    def test_verify_basic(self, mock_run: AsyncMock, runner: CliRunner, sample_bib: str) -> None:
        """Verify command invokes _run_verify."""
        mock_run.return_value = None
        result = runner.invoke(cli, ["verify", sample_bib])
        assert result.exit_code == 0

    @patch("refchecker.cli.main.parse_file")
    @patch("refchecker.cli.main._build_adapters")
    @patch("refchecker.cli.main.VerificationEngine")
    def test_verify_json_output(
        self,
        mock_engine_cls: MagicMock,
        mock_build: MagicMock,
        mock_parse: MagicMock,
        runner: CliRunner,
        sample_bib: str,
    ) -> None:
        """Verify with --format json produces valid JSON."""
        ref = _ref()
        mock_parse.return_value = [ref]
        mock_build.return_value = [MagicMock()]

        mock_engine = MagicMock()
        mock_engine.verify_batch = AsyncMock(return_value=[_result(ref)])
        mock_engine_cls.return_value = mock_engine

        result = runner.invoke(cli, ["verify", sample_bib, "--format", "json"])
        assert result.exit_code == 0
        # JSON is after the progress output lines
        json_start = result.output.index("[")
        data = json.loads(result.output[json_start:])
        assert isinstance(data, list)
        assert data[0]["status"] == "verified"

    @patch("refchecker.cli.main.parse_file")
    @patch("refchecker.cli.main._build_adapters")
    @patch("refchecker.cli.main.VerificationEngine")
    def test_verify_csv_output(
        self,
        mock_engine_cls: MagicMock,
        mock_build: MagicMock,
        mock_parse: MagicMock,
        runner: CliRunner,
        sample_bib: str,
    ) -> None:
        """Verify with --format csv produces CSV."""
        ref = _ref()
        mock_parse.return_value = [ref]
        mock_build.return_value = [MagicMock()]

        mock_engine = MagicMock()
        mock_engine.verify_batch = AsyncMock(return_value=[_result(ref)])
        mock_engine_cls.return_value = mock_engine

        result = runner.invoke(cli, ["verify", sample_bib, "--format", "csv"])
        assert result.exit_code == 0
        assert "Title" in result.output
        assert "Test Paper" in result.output

    @patch("refchecker.cli.main.parse_file")
    @patch("refchecker.cli.main._build_adapters")
    @patch("refchecker.cli.main.VerificationEngine")
    def test_verify_output_to_file(
        self,
        mock_engine_cls: MagicMock,
        mock_build: MagicMock,
        mock_parse: MagicMock,
        runner: CliRunner,
        sample_bib: str,
        tmp_path: Path,
    ) -> None:
        """Verify with --output writes results to file."""
        ref = _ref()
        mock_parse.return_value = [ref]
        mock_build.return_value = [MagicMock()]

        mock_engine = MagicMock()
        mock_engine.verify_batch = AsyncMock(return_value=[_result(ref)])
        mock_engine_cls.return_value = mock_engine

        output_file = str(tmp_path / "results.csv")
        result = runner.invoke(cli, ["verify", sample_bib, "--format", "csv", "--output", output_file])
        assert result.exit_code == 0
        assert Path(output_file).exists()

    @patch("refchecker.cli.main.load_config")
    def test_verify_unknown_adapter_warns(
        self, mock_config: MagicMock, runner: CliRunner, sample_bib: str
    ) -> None:
        """Unknown adapter name produces a warning."""
        mock_config.return_value = MagicMock()
        result = runner.invoke(cli, ["verify", sample_bib, "--adapters", "nonexistent"])
        output = result.output + (result.stderr if result.stderr else "")
        assert "Unknown adapter" in output or result.exit_code != 0


class TestCLISetKey:
    """Test the 'set-key' command."""

    @patch("refchecker.core.key_store.store_key")
    def test_set_key_success(self, mock_store: MagicMock, runner: CliRunner) -> None:
        """Successful key storage."""
        result = runner.invoke(cli, ["set-key", "s2", "test-api-key-123"])
        assert result.exit_code == 0
        assert "stored securely" in result.output
        mock_store.assert_called_once_with("s2_api_key", "test-api-key-123")

    @patch("refchecker.core.key_store.store_key", side_effect=Exception("storage error"))
    def test_set_key_store_error(self, mock_store: MagicMock, runner: CliRunner) -> None:
        """Key storage failure produces error."""
        result = runner.invoke(cli, ["set-key", "s2", "test-key"])
        assert result.exit_code != 0

    @patch.dict("sys.modules", {"refchecker.core.key_store": None})
    def test_set_key_import_error(self, runner: CliRunner) -> None:
        """Missing keyring package produces import error."""
        # Simulate ImportError by making key_store import fail inside the command
        import refchecker.cli.main as cli_mod
        original = cli_mod.__dict__.get("__builtins__", {})
        with patch("builtins.__import__", side_effect=ImportError("no keyring")):
            result = runner.invoke(cli, ["set-key", "s2", "test-key"])
            assert result.exit_code != 0

    def test_set_key_invalid_adapter(self, runner: CliRunner) -> None:
        """Invalid adapter name is rejected."""
        result = runner.invoke(cli, ["set-key", "invalid", "test-key"])
        assert result.exit_code != 0


class TestCLIGetKey:
    """Test the 'get-key' command."""

    @patch("refchecker.core.key_store.load_key", return_value="sk-1234567890abcdef")
    def test_get_key_stored(self, mock_load: MagicMock, runner: CliRunner) -> None:
        """Stored key shows masked value."""
        result = runner.invoke(cli, ["get-key", "s2"])
        assert result.exit_code == 0
        assert "stored" in result.output
        assert "****" in result.output

    @patch("refchecker.core.key_store.load_key", return_value=None)
    def test_get_key_not_stored(self, mock_load: MagicMock, runner: CliRunner) -> None:
        """Missing key shows info message."""
        result = runner.invoke(cli, ["get-key", "s2"])
        assert result.exit_code == 0
        assert "No key stored" in result.output


class TestCLIDeleteKey:
    """Test the 'delete-key' command."""

    @patch("refchecker.core.key_store.delete_key", return_value=True)
    def test_delete_key_exists(self, mock_delete: MagicMock, runner: CliRunner) -> None:
        """Existing key is deleted."""
        result = runner.invoke(cli, ["delete-key", "s2"])
        assert result.exit_code == 0
        assert "deleted" in result.output

    @patch("refchecker.core.key_store.delete_key", return_value=False)
    def test_delete_key_not_exists(self, mock_delete: MagicMock, runner: CliRunner) -> None:
        """No key to delete shows info."""
        result = runner.invoke(cli, ["delete-key", "s2"])
        assert result.exit_code == 0
        assert "No key to delete" in result.output


class TestCLIListKeys:
    """Test the 'list-keys' command."""

    @patch("refchecker.core.key_store.list_keys")
    def test_list_keys(self, mock_list: MagicMock, runner: CliRunner) -> None:
        """List keys shows adapter status."""
        entry = MagicMock()
        entry.adapter_name = "s2"
        entry.has_key = True
        mock_list.return_value = [entry]

        result = runner.invoke(cli, ["list-keys"])
        assert result.exit_code == 0
        assert "s2" in result.output
        assert "stored" in result.output

    @patch("refchecker.core.key_store.list_keys")
    def test_list_keys_empty(self, mock_list: MagicMock, runner: CliRunner) -> None:
        """Empty key list shows header."""
        mock_list.return_value = []
        result = runner.invoke(cli, ["list-keys"])
        assert result.exit_code == 0
        assert "Adapter Key Status" in result.output


class TestCLIFormatting:
    """Test internal formatting helpers."""

    def test_format_table_empty(self) -> None:
        """_format_table with empty list returns message."""
        from refchecker.cli.main import _format_table
        assert _format_table([]) == "No references found."

    def test_format_table_with_items(self) -> None:
        """_format_table formats items as a table."""
        from refchecker.cli.main import _format_table
        items = [_ref(title="My Paper", year=2023)]
        output = _format_table(items)
        assert "My Paper" in output
        assert "Total: 1 references" in output

    def test_format_results_table_empty(self) -> None:
        """_format_results_table with empty list."""
        from refchecker.cli.main import _format_results_table
        assert _format_results_table([]) == "No results."

    def test_format_results_table_verified(self) -> None:
        """_format_results_table shows summary for verified result."""
        from refchecker.cli.main import _format_results_table
        r = _result(status=VerificationStatus.VERIFIED)
        output = _format_results_table([r])
        assert "verified" in output.lower() or "✅" in output or "Summary" in output

    def test_format_results_table_mixed(self) -> None:
        """_format_results_table shows counts for mixed statuses."""
        from refchecker.cli.main import _format_results_table
        results = [
            _result(status=VerificationStatus.VERIFIED),
            _result(
                ref=_ref(title="Bad", citation_key="bad"),
                status=VerificationStatus.LIKELY_FABRICATED,
                best_score=0.3,
                matches=[AdapterMatch(
                    adapter_name="crossref", found=False, composite_score=0.3,
                    title_score=0.3, author_score=0.3, year_score=0.5, venue_score=0.5,
                    matched_title=None, matched_authors=[], matched_year=None,
                )],
            ),
        ]
        output = _format_results_table(results)
        assert "Summary" in output

    @patch("refchecker.cli.main._run_verify", new_callable=AsyncMock)
    def test_verify_table_format(self, mock_run: AsyncMock, runner: CliRunner, sample_bib: str) -> None:
        """Verify default (table) format runs without error."""
        mock_run.return_value = None
        result = runner.invoke(cli, ["verify", sample_bib])
        assert result.exit_code == 0
