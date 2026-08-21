"""Deterministic skill matching between a candidate's skills and a job's
requirements - exact/substring string comparison, no LLM involved.

Kept as its own module (not part of scoring.py) so the "tool" that compares
resume skills against job requirements is a separately-callable, separately-
testable function - see docs/architecture.md.
"""
import re


def _normalize(skill: str) -> str:
    """Lowercase and strip punctuation/whitespace so 'REST APIs' and 'rest-api'
    are comparable. Kept simple on purpose - a full synonym/alias system is
    out of scope for a 24h prototype."""
    return re.sub(r"[^a-z0-9+#]", "", skill.lower())


def match_skills(candidate_skills: list[str], job_skills: list[str]) -> tuple[list[str], list[str]]:
    """Compare candidate skills against one list of job skills (required or preferred).

    Returns (matched, missing), both using the *original* job-skill wording
    so the UI displays human-readable labels (e.g. "REST APIs") rather than
    the normalized form.

    A job skill counts as matched if it normalizes to an exact match with a
    candidate skill, OR one normalized string contains the other as a whole
    token-boundary substring (handles cases like "Python" matching
    "Python 3" or "React" matching "React.js").
    """
    normalized_candidate = {_normalize(s): s for s in candidate_skills}

    matched: list[str] = []
    missing: list[str] = []

    for job_skill in job_skills:
        norm_job = _normalize(job_skill)
        if not norm_job:
            continue

        is_match = norm_job in normalized_candidate or any(
            norm_job in norm_cand or norm_cand in norm_job for norm_cand in normalized_candidate
        )

        if is_match:
            matched.append(job_skill)
        else:
            missing.append(job_skill)

    return matched, missing
