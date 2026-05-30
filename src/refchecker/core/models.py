"""Pydantic data models for RefChecker.

Defines the core data structures used throughout the verification pipeline:
reference items, verification results, and adapter responses.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class VerificationStatus(str, Enum):
    """Verification status for a citation reference.

    Taxonomy:
        VERIFIED: Found in ≥1 source, composite score ≥0.85
        SUSPICIOUS: Partial match, score 0.60–0.84
        LIKELY_FABRICATED: Not found, score <0.60
        UNABLE_TO_VERIFY: Network error or source unavailable
        PENDING: Not yet checked
    """

    VERIFIED = "verified"
    SUSPICIOUS = "suspicious"
    LIKELY_FABRICATED = "likely_fabricated"
    UNABLE_TO_VERIFY = "unable_to_verify"
    PENDING = "pending"

    @property
    def symbol(self) -> str:
        """Return the status symbol for display."""
        symbols = {
            VerificationStatus.VERIFIED: "✅",
            VerificationStatus.SUSPICIOUS: "⚠️",
            VerificationStatus.LIKELY_FABRICATED: "❌",
            VerificationStatus.UNABLE_TO_VERIFY: "ℹ️",
            VerificationStatus.PENDING: "🔄",
        }
        return symbols[self]


class ReferenceItem(BaseModel):
    """A single citation reference extracted from a .bib or text file.

    Immutable (frozen=True) to prevent accidental mutation during
    the verification pipeline.
    """

    title: str = Field(description="Paper title")
    authors: list[str] = Field(default_factory=list, description="Author names")
    year: Optional[int] = Field(default=None, description="Publication year")
    journal: Optional[str] = Field(default=None, description="Journal or venue name")
    doi: Optional[str] = Field(default=None, description="Digital Object Identifier")
    volume: Optional[str] = Field(default=None, description="Journal volume")
    issue: Optional[str] = Field(default=None, description="Journal issue number")
    pages: Optional[str] = Field(default=None, description="Page range (e.g. '1-10')")
    publisher: Optional[str] = Field(default=None, description="Publisher name")
    entry_type: Optional[str] = Field(default=None, description="BibTeX entry type (article, book, etc.)")
    citation_key: Optional[str] = Field(default=None, description="BibTeX citation key")
    raw_text: Optional[str] = Field(default=None, description="Original raw text of the reference")
    source_file: Optional[str] = Field(default=None, description="Source file the reference was parsed from")

    model_config = {"frozen": True}

    @field_validator("year", mode="before")
    @classmethod
    def coerce_year(cls, v: object) -> Optional[int]:
        """Coerce year from string or other types to int."""
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            cleaned = v.strip()
            if not cleaned:
                return None
            try:
                return int(cleaned)
            except ValueError:
                return None
        return None

    @field_validator("doi", mode="before")
    @classmethod
    def normalize_doi(cls, v: Optional[str]) -> Optional[str]:
        """Normalize DOI by stripping whitespace and common URL prefixes."""
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break
        return cleaned

    @property
    def display_authors(self) -> str:
        """Return a formatted author string for display."""
        if not self.authors:
            return "Unknown"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."

    @property
    def has_doi(self) -> bool:
        """Check whether this reference has a DOI."""
        return self.doi is not None and len(self.doi) > 0


class AdapterMatch(BaseModel):
    """A match result from a single verification adapter.

    Contains the matched metadata and similarity scores for
    title, authors, year, and venue.
    """

    adapter_name: str = Field(description="Name of the verification adapter")
    found: bool = Field(description="Whether a match was found")
    matched_title: Optional[str] = Field(default=None, description="Title from the source")
    matched_authors: list[str] = Field(default_factory=list, description="Authors from the source")
    matched_year: Optional[int] = Field(default=None, description="Year from the source")
    matched_journal: Optional[str] = Field(default=None, description="Journal/venue from the source")
    matched_doi: Optional[str] = Field(default=None, description="DOI from the source")
    title_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Title similarity score")
    author_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Author similarity score")
    year_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Year match score")
    venue_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Venue similarity score")
    composite_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Weighted composite score")
    source_url: Optional[str] = Field(default=None, description="URL to the matched paper")
    error: Optional[str] = Field(default=None, description="Error message if verification failed")

    model_config = {"frozen": True}


class VerificationResult(BaseModel):
    """Complete verification result for a single reference.

    Aggregates matches from all adapters and determines the
    final verification status.
    """

    reference: ReferenceItem = Field(description="The original reference item")
    matches: list[AdapterMatch] = Field(default_factory=list, description="Matches from each adapter")
    best_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Best composite score across adapters")
    status: VerificationStatus = Field(
        default=VerificationStatus.PENDING,
        description="Final verification status",
    )

    model_config = {"frozen": True}

    def determine_status(self) -> "VerificationResult":
        """Return a new VerificationResult with updated status based on matches.

        Status logic:
        - If any adapter reported an error and no matches found: UNABLE_TO_VERIFY
        - If best composite score ≥ 0.85: VERIFIED
        - If best composite score 0.60–0.84: SUSPICIOUS
        - If best composite score < 0.60: LIKELY_FABRICATED
        - If no matches at all: LIKELY_FABRICATED
        """
        if not self.matches:
            return VerificationResult(
                reference=self.reference,
                matches=self.matches,
                best_score=0.0,
                status=VerificationStatus.LIKELY_FABRICATED,
            )

        found_matches = [m for m in self.matches if m.found]
        error_matches = [m for m in self.matches if m.error is not None]

        if not found_matches and error_matches:
            new_status = VerificationStatus.UNABLE_TO_VERIFY
        elif not found_matches:
            new_status = VerificationStatus.LIKELY_FABRICATED
        elif self.best_score >= 0.85:
            new_status = VerificationStatus.VERIFIED
        elif self.best_score >= 0.60:
            new_status = VerificationStatus.SUSPICIOUS
        else:
            new_status = VerificationStatus.LIKELY_FABRICATED

        return VerificationResult(
            reference=self.reference,
            matches=self.matches,
            best_score=self.best_score,
            status=new_status,
        )

    def with_match(self, match: AdapterMatch) -> "VerificationResult":
        """Return a new VerificationResult with an additional adapter match.

        Automatically updates the best score.
        """
        new_matches = [*self.matches, match]
        new_best = max(m.composite_score for m in new_matches if m.found) if any(
            m.found for m in new_matches
        ) else 0.0
        return VerificationResult(
            reference=self.reference,
            matches=new_matches,
            best_score=new_best,
            status=self.status,
        )
