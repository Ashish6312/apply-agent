"""Deterministic compatibility scoring.

Design choice (see README "Scoring"): the LLM must never invent a match
percentage. Arithmetic is more reliable, reproducible and testable when
computed in code, so this module has zero LLM calls and is pure functions
over lists of strings.

Formula:
    required_skill_score = matched_required / total_required * 100   (100 if no required skills listed)
    preferred_skill_score = matched_preferred / total_preferred * 100 (100 if no preferred skills listed)
    overall_score = required_skill_score * 0.8 + preferred_skill_score * 0.2

Required skills are weighted higher (80%) because failing to meet a
"required" qualification is a stronger negative signal for an application
than missing a "nice-to-have".
"""
from app.schemas.analysis import ScoreBreakdown

REQUIRED_WEIGHT = 0.8
PREFERRED_WEIGHT = 0.2


def _percentage(matched_count: int, total_count: int) -> int:
    if total_count == 0:
        # No requirements stated in this category -> treat as fully satisfied
        # rather than penalizing the candidate for something the job never asked for.
        return 100
    return round(matched_count / total_count * 100)


def calculate_score(
    matched_required: list[str],
    missing_required: list[str],
    matched_preferred: list[str],
    missing_preferred: list[str],
) -> ScoreBreakdown:
    """Compute a transparent, reproducible compatibility score from already-matched
    skill lists (see services/skill_matcher.py for the matching step itself).

    Kept as pure arithmetic over lists - no LLM, no I/O - so it is trivially
    unit-testable and reproducible for the same inputs.
    """
    total_required = len(matched_required) + len(missing_required)
    total_preferred = len(matched_preferred) + len(missing_preferred)

    required_score = _percentage(len(matched_required), total_required)
    preferred_score = _percentage(len(matched_preferred), total_preferred)
    overall = round(required_score * REQUIRED_WEIGHT + preferred_score * PREFERRED_WEIGHT)

    return ScoreBreakdown(
        overall_score=overall,
        required_skill_score=required_score,
        preferred_skill_score=preferred_score,
        matched_required=matched_required,
        missing_required=missing_required,
        matched_preferred=matched_preferred,
        missing_preferred=missing_preferred,
    )


def decision_bucket(overall_score: int) -> str:
    """Map score -> decision category. Pure threshold logic, unit-testable."""
    if overall_score >= 80:
        return "STRONG_APPLY"
    if overall_score >= 65:
        return "APPLY_REVIEW_GAPS"
    if overall_score >= 50:
        return "CONSIDER"
    return "LOW_MATCH"
