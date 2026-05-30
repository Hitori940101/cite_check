"""Custom exception hierarchy for RefChecker.

All application-specific exceptions inherit from RefCheckerError,
allowing callers to catch broadly or narrowly as needed.
"""


class RefCheckerError(Exception):
    """Base exception for all RefChecker errors."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        self.details = details
        super().__init__(message)


class ParserError(RefCheckerError):
    """Raised when citation parsing fails.

    Examples: malformed BibTeX, unsupported format, encoding issues.
    """


class AdapterError(RefCheckerError):
    """Raised when a verification adapter encounters an error.

    Examples: API rate limit, network timeout, invalid response.
    """

    def __init__(
        self,
        message: str,
        *,
        adapter_name: str | None = None,
        details: str | None = None,
    ) -> None:
        self.adapter_name = adapter_name
        super().__init__(message, details=details)


class RateLimitError(AdapterError):
    """Raised when an API rate limit is hit.

    Contains retry-after information for exponential backoff.
    """

    def __init__(
        self,
        message: str,
        *,
        adapter_name: str | None = None,
        retry_after: float | None = None,
        details: str | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, adapter_name=adapter_name, details=details)


class VerificationError(RefCheckerError):
    """Raised when the verification pipeline fails.

    Examples: all adapters failed, internal scoring error.
    """


class ConfigurationError(RefCheckerError):
    """Raised when configuration is invalid or missing.

    Examples: missing required setting, invalid API key format.
    """


class ExportError(RefCheckerError):
    """Raised when exporting results fails.

    Examples: file write permission, unsupported export format.
    """
