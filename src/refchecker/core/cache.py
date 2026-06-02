"""Result caching layer for RefChecker.

Provides in-memory and optional file-based caching of verification results
to avoid re-verifying the same citations across sessions.

Cache key is derived from normalized (title, first_author, year).
File cache uses JSON with timestamps for TTL enforcement.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from refchecker.core.logging import get_logger
from refchecker.core.models import ReferenceItem, VerificationResult

logger = get_logger(__name__)

_DEFAULT_CACHE_DIR = Path.home() / ".refchecker" / "cache"


class ResultCache:
    """In-memory + optional file cache for verification results.

    Args:
        cache_dir: Directory for persistent file cache.
            Defaults to ~/.refchecker/cache/.
        ttl_days: Time-to-live in days for cached entries.
            Set to 0 to disable TTL. Defaults to 7.
    """

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        ttl_days: int = 7,
    ) -> None:
        self._cache_dir = cache_dir or _DEFAULT_CACHE_DIR
        self._ttl_days = ttl_days
        self._memory: dict[str, VerificationResult] = {}
        self._file_cache_loaded = False

    @staticmethod
    def _make_key(reference: ReferenceItem) -> str:
        """Generate a deterministic cache key from a reference.

        Normalizes title (lowercase, strip), first author, and year
        to ensure the same citation always maps to the same key.

        Args:
            reference: The reference item to key on.

        Returns:
            Hex digest string (SHA-256).
        """
        title_norm = reference.title.lower().strip()
        first_author = (reference.authors[0].strip().lower()
                        if reference.authors else "")
        year = str(reference.year or "")
        raw = f"{title_norm}|{first_author}|{year}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, reference: ReferenceItem) -> VerificationResult | None:
        """Look up a cached verification result.

        Checks in-memory cache first, then file cache.
        Expired file entries are silently removed.

        Args:
            reference: The reference to look up.

        Returns:
            Cached VerificationResult, or None if not found or expired.
        """
        key = self._make_key(reference)

        # Check memory cache
        if key in self._memory:
            return self._memory[key]

        # Check file cache
        return self._get_from_file(key)

    def put(
        self,
        reference: ReferenceItem,
        result: VerificationResult,
    ) -> None:
        """Store a verification result in cache.

        Writes to both in-memory and file cache.

        Args:
            reference: The reference that was verified.
            result: The verification result to cache.
        """
        key = self._make_key(reference)
        self._memory[key] = result
        self._write_to_file(key, result)

    def clear(self) -> None:
        """Clear all cached entries (memory and files)."""
        self._memory.clear()
        if self._cache_dir.exists():
            for f in self._cache_dir.glob("*.json"):
                f.unlink(missing_ok=True)
            logger.info("cache_cleared", dir=str(self._cache_dir))

    def _get_from_file(self, key: str) -> VerificationResult | None:
        """Load a result from the file cache, respecting TTL."""
        import time

        path = self._cache_dir / f"{key}.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            timestamp = data.get("timestamp", 0)

            # TTL check
            if self._ttl_days > 0:
                age_days = (time.time() - timestamp) / 86400
                if age_days > self._ttl_days:
                    path.unlink(missing_ok=True)
                    return None

            return VerificationResult.model_validate(data["result"])
        except Exception as exc:
            logger.debug("cache_read_error", key=key, error=str(exc))
            return None

    def _write_to_file(self, key: str, result: VerificationResult) -> None:
        """Persist a result to the file cache."""
        import time

        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "timestamp": time.time(),
                "result": result.model_dump(),
            }
            path = self._cache_dir / f"{key}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
        except Exception as exc:
            logger.debug("cache_write_error", key=key, error=str(exc))
