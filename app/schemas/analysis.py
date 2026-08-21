"""Output models for the deterministic scoring step and the final API response.

Kept separate from resume.py/job.py because these describe *analysis results*
(score, recommendation, generated content), not raw extracted entities.
"""
from pydantic import BaseModel, Field

from app.schemas.job import JobRequirements
from app.schemas.resume import CandidateProfile


class ScoreBreakdown(BaseModel):
    """Result of the deterministic scoring function. No LLM involved here -
    every number is computed from set overlap so it is reproducible and testable."""

    overall_score: int
    required_skill_score: int
    preferred_skill_score: int
    matched_required: list[str]
    missing_required: list[str]
    matched_preferred: list[str]
    missing_preferred: list[str]


class Recommendation(BaseModel):
    """LLM-generated explanation of the decision. The LLM only *explains* -
    it does not choose the score or the decision bucket, those are deterministic."""

    decision: str = Field(description="One of: STRONG_APPLY, APPLY_REVIEW_GAPS, CONSIDER, LOW_MATCH")
    confidence: str = Field(description="One of: high, medium, low")
    reasons: list[str] = Field(description="Evidence-grounded reasons supporting the decision")
    risks: list[str] = Field(
        default_factory=list,
        description="Risks or gaps to be aware of, e.g. a required skill with no resume evidence. "
        "Use 'Insufficient evidence' phrasing rather than assuming a skill is present.",
    )
    next_actions: list[str] = Field(default_factory=list, description="Concrete next steps for the candidate")


class InterviewQuestion(BaseModel):
    category: str = Field(description="One of: technical, behavioral, gap_related")
    question: str


class InterviewQuestionSet(BaseModel):
    """Wrapper so the LLM's structured output is a single Pydantic object (a list of
    questions on its own is not a valid structured-output schema for most providers)."""

    questions: list[InterviewQuestion]


class ResumeImprovementSet(BaseModel):
    """Wrapper around resume improvement suggestions, same reasoning as InterviewQuestionSet."""

    improvements: list[str] = Field(
        description="Concrete, evidence-grounded resume improvement suggestions. "
        "Any suggestion that requires information not present in the resume must "
        "end with the literal phrase 'Verify before adding.'"
    )


class AnalysisResult(BaseModel):
    """Full result returned by the API / shown in the UI. Aggregates every
    field produced across the LangGraph run."""

    candidate_profile: CandidateProfile
    job_requirements: JobRequirements
    score_breakdown: ScoreBreakdown
    recommendation: Recommendation
    resume_improvements: list[str]
    cover_letter: str | None = None
    gap_analysis: str | None = None
    interview_questions: list[InterviewQuestion]
    execution_trace: list[str]
    errors: list[str] = Field(default_factory=list)
