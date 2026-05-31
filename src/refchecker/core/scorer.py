"""Fuzzy matching scorer for citation verification.

Uses RapidFuzz to compute similarity scores between a reference item
and a matched result from a verification source.

Scoring weights (per ADR-4):
- Title: 0.5
- Author: 0.3
- Year: 0.1
- Venue: 0.1

Thresholds:
- ≥0.85: Verified
- 0.60–0.84: Suspicious
- <0.60: Likely Fabricated
"""

from rapidfuzz import fuzz

from refchecker.core.models import ReferenceItem

# Scoring weights
_WEIGHT_TITLE = 0.5
_WEIGHT_AUTHOR = 0.3
_WEIGHT_YEAR = 0.1
_WEIGHT_VENUE = 0.1

# Year tolerance: exact match or ±1 year
_YEAR_TOLERANCE = 1


def compute_title_score(query: str, candidate: str) -> float:
    """Compute title similarity score.

    Uses a combination of ratio and token_sort_ratio to handle
    word reordering and minor spelling differences.

    Args:
        query: Title from the original reference.
        candidate: Title from the verification source.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    if not query or not candidate:
        return 0.0

    q = query.lower().strip()
    c = candidate.lower().strip()

    if q == c:
        return 1.0

    # Combine exact ratio with token-sorted ratio
    ratio = fuzz.ratio(q, c) / 100.0
    token_sort = fuzz.token_sort_ratio(q, c) / 100.0
    token_set = fuzz.token_set_ratio(q, c) / 100.0

    # Weight: prefer token_set (handles subset/superset), then token_sort
    return max(ratio, token_sort, token_set)


def compute_author_score(query_authors: list[str], candidate_authors: list[str]) -> float:
    """Compute author similarity score.

    Uses token_set_ratio to handle subset/superset author lists.
    Compares the full author strings as well as individual matching.

    Args:
        query_authors: Authors from the original reference.
        candidate_authors: Authors from the verification source.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    if not query_authors or not candidate_authors:
        return 0.0

    q_str = " ".join(a.lower().strip() for a in query_authors)
    c_str = " ".join(a.lower().strip() for a in candidate_authors)

    if q_str == c_str:
        return 1.0

    token_set = fuzz.token_set_ratio(q_str, c_str) / 100.0
    token_sort = fuzz.token_sort_ratio(q_str, c_str) / 100.0

    return max(token_set, token_sort)


def compute_year_score(query_year: int | None, candidate_year: int | None) -> float:
    """Compute year match score.

    Exact match = 1.0, within ±1 year = 0.8, otherwise 0.0.

    Args:
        query_year: Year from the original reference.
        candidate_year: Year from the verification source.

    Returns:
        Match score between 0.0 and 1.0.
    """
    if query_year is None or candidate_year is None:
        # If year is missing in either, don't penalize
        return 0.5

    if query_year == candidate_year:
        return 1.0

    if abs(query_year - candidate_year) <= _YEAR_TOLERANCE:
        return 0.8

    return 0.0


def compute_venue_score(query_venue: str | None, candidate_venue: str | None) -> float:
    """Compute venue/journal similarity score.

    Uses token_set_ratio for fuzzy journal name matching.

    Args:
        query_venue: Journal/venue from the original reference.
        candidate_venue: Journal/venue from the verification source.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    if not query_venue or not candidate_venue:
        # Missing venue in either: don't penalize
        return 0.5

    q = query_venue.lower().strip()
    c = candidate_venue.lower().strip()

    if q == c:
        return 1.0

    token_set = fuzz.token_set_ratio(q, c) / 100.0
    return token_set


def compute_composite_score(
    *,
    title_score: float,
    author_score: float,
    year_score: float,
    venue_score: float,
) -> float:
    """Compute the weighted composite verification score.

    Weights: title=0.5, author=0.3, year=0.1, venue=0.1.

    Args:
        title_score: Title similarity (0.0–1.0).
        author_score: Author similarity (0.0–1.0).
        year_score: Year match (0.0–1.0).
        venue_score: Venue similarity (0.0–1.0).

    Returns:
        Weighted composite score between 0.0 and 1.0.
    """
    return (
        _WEIGHT_TITLE * title_score
        + _WEIGHT_AUTHOR * author_score
        + _WEIGHT_YEAR * year_score
        + _WEIGHT_VENUE * venue_score
    )


def score_match(
    reference: ReferenceItem,
    *,
    matched_title: str | None = None,
    matched_authors: list[str] | None = None,
    matched_year: int | None = None,
    matched_journal: str | None = None,
) -> tuple[float, float, float, float, float]:
    """Score a candidate match against a reference item.

    Args:
        reference: The original reference item.
        matched_title: Title from the verification source.
        matched_authors: Authors from the verification source.
        matched_year: Year from the verification source.
        matched_journal: Journal/venue from the verification source.

    Returns:
        Tuple of (title_score, author_score, year_score, venue_score, composite).
    """
    t_score = compute_title_score(
        reference.title,
        matched_title or "",
    )
    a_score = compute_author_score(
        reference.authors,
        matched_authors or [],
    )
    y_score = compute_year_score(
        reference.year,
        matched_year,
    )
    v_score = compute_venue_score(
        reference.journal,
        matched_journal,
    )
    composite = compute_composite_score(
        title_score=t_score,
        author_score=a_score,
        year_score=y_score,
        venue_score=v_score,
    )
    return t_score, a_score, y_score, v_score, composite
