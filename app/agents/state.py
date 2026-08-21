"""Typed state passed between LangGraph nodes.

Using a single TypedDict (rather than each node returning ad-hoc dicts)
means every node's inputs/outputs are explicit and IDE/type-checkable, and
the whole run can be serialized straight into the API response.
"""
from typing import TypedDict

from app.schemas.analysis import InterviewQuestion, Recommendation, ScoreBreakdown
from app.schemas.job import JobRequirements
from app.schemas.resume import CandidateProfile


class AgentState(TypedDict, total=False):
    # --- inputs (set before the graph runs) ---
    resume_bytes: bytes  # raw uploaded PDF, consumed by parse_resume
    job_description: str  # raw job posting text, consumed by analyze_job
    target_role: str | None  # optional user-provided hint (e.g. "Backend Intern")

    # --- parse_resume node output ---
    resume_text: str  # deterministic PyMuPDF extraction, kept for transparency/debugging
    candidate_profile: CandidateProfile  # LLM-structured extraction, grounded in resume_text
    resume_extraction_failed: bool  # True if the LLM call failed - candidate_profile is an empty stub, not real data

    # --- analyze_job node output ---
    job_requirements: JobRequirements  # LLM-structured extraction from job_description
    job_extraction_failed: bool  # True if the LLM call failed - job_requirements is an empty stub, not real data

    # --- match_skills node output ---
    matched_required: list[str]
    missing_required: list[str]
    matched_preferred: list[str]
    missing_preferred: list[str]

    # --- calculate_score node output ---
    score_breakdown: ScoreBreakdown  # deterministic, see services/scoring.py

    # --- decision node output ---
    decision_bucket: str  # STRONG_APPLY / APPLY_REVIEW_GAPS / CONSIDER / LOW_MATCH (deterministic)
    route: str  # "apply" or "gap_analysis" - which branch the conditional edge takes
    recommendation: Recommendation  # LLM explanation grounded in the evidence above

    # --- generate_application / generate_gap_analysis node output ---
    resume_improvements: list[str]
    cover_letter: str | None  # only populated on the "apply" route
    gap_analysis: str | None  # only populated on the "gap_analysis" route

    # --- generate_interview_prep node output ---
    interview_questions: list[InterviewQuestion]

    # --- cross-cutting ---
    execution_trace: list[str]  # human-readable log of what the agent did, shown in the UI
    errors: list[str]  # non-fatal errors surfaced to the user instead of raising
