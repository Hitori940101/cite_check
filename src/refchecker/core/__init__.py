"""Core verification engine — data models, parsing, scoring, orchestration."""

from refchecker.core.exceptions import (
    AdapterError,
    ConfigurationError,
    ExportError,
    ParserError,
    RateLimitError,
    RefCheckerError,
    VerificationError,
)
from refchecker.core.models import (
    AdapterMatch,
    ReferenceItem,
    VerificationResult,
    VerificationStatus,
)

__all__ = [
    # Exceptions
    "AdapterError",
    "ConfigurationError",
    "ExportError",
    "ParserError",
    "RateLimitError",
    "RefCheckerError",
    "VerificationError",
    # Models
    "AdapterMatch",
    "ReferenceItem",
    "VerificationResult",
    "VerificationStatus",
]
