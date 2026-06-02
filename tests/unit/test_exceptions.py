"""Unit tests for refchecker.core.exceptions module."""

import pytest

from refchecker.core.exceptions import (
    AdapterError,
    ConfigurationError,
    ExportError,
    ParserError,
    RateLimitError,
    RefCheckerError,
    VerificationError,
)


class TestRefCheckerError:
    """Tests for the base RefCheckerError."""

    def test_message(self) -> None:
        """Exception stores message."""
        err = RefCheckerError("something failed")
        assert str(err) == "something failed"

    def test_details(self) -> None:
        """Exception stores optional details."""
        err = RefCheckerError("failed", details="extra context")
        assert err.details == "extra context"

    def test_no_details(self) -> None:
        """Details defaults to None."""
        err = RefCheckerError("failed")
        assert err.details is None


class TestParserError:
    """Tests for ParserError."""

    def test_inherits_from_base(self) -> None:
        """ParserError is a RefCheckerError."""
        assert issubclass(ParserError, RefCheckerError)

    def test_caught_by_base(self) -> None:
        """ParserError is caught by except RefCheckerError."""
        with pytest.raises(RefCheckerError):
            raise ParserError("bad bib")


class TestAdapterError:
    """Tests for AdapterError."""

    def test_inherits_from_base(self) -> None:
        """AdapterError is a RefCheckerError."""
        assert issubclass(AdapterError, RefCheckerError)

    def test_adapter_name(self) -> None:
        """AdapterError stores adapter_name."""
        err = AdapterError("timeout", adapter_name="s2")
        assert err.adapter_name == "s2"

    def test_no_adapter_name(self) -> None:
        """adapter_name defaults to None."""
        err = AdapterError("error")
        assert err.adapter_name is None


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_inherits_from_adapter_error(self) -> None:
        """RateLimitError is an AdapterError."""
        assert issubclass(RateLimitError, AdapterError)

    def test_retry_after(self) -> None:
        """RateLimitError stores retry_after."""
        err = RateLimitError("rate limited", adapter_name="s2", retry_after=5.0)
        assert err.retry_after == 5.0
        assert err.adapter_name == "s2"

    def test_no_retry_after(self) -> None:
        """retry_after defaults to None."""
        err = RateLimitError("limited")
        assert err.retry_after is None


class TestVerificationError:
    """Tests for VerificationError."""

    def test_inherits_from_base(self) -> None:
        assert issubclass(VerificationError, RefCheckerError)


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_inherits_from_base(self) -> None:
        assert issubclass(ConfigurationError, RefCheckerError)


class TestExportError:
    """Tests for ExportError."""

    def test_inherits_from_base(self) -> None:
        assert issubclass(ExportError, RefCheckerError)


class TestExceptionHierarchy:
    """Tests for the full exception hierarchy."""

    def test_all_are_refchecker_errors(self) -> None:
        """All custom exceptions are subclasses of RefCheckerError."""
        for exc_cls in [ParserError, AdapterError, RateLimitError,
                        VerificationError, ConfigurationError, ExportError]:
            assert issubclass(exc_cls, RefCheckerError), f"{exc_cls.__name__} should inherit RefCheckerError"

    def test_rate_limit_is_adapter_error(self) -> None:
        """RateLimitError inherits from AdapterError."""
        assert issubclass(RateLimitError, AdapterError)

    def test_catch_all_with_base(self) -> None:
        """All exceptions are caught by RefCheckerError handler."""
        exceptions = [
            ParserError("p"),
            AdapterError("a"),
            RateLimitError("r"),
            VerificationError("v"),
            ConfigurationError("c"),
            ExportError("e"),
        ]
        for exc in exceptions:
            with pytest.raises(RefCheckerError):
                raise exc
