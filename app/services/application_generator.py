"""LLM-generated content for the "what should the candidate do about it" stage:
recommendation explanation, resume improvements, cover letter, gap analysis,
and interview prep questions.

Every function here takes deterministic evidence (scores, matched/missing
skill lists, extracted profile) as input and asks the LLM to reason over
that evidence - never to compute or invent facts. See prompts.py for the
exact anti-hallucination wording used in each call.
"""
import logging
from datetime import date

from app.agents.prompts import (
    COVER_LETTER_PROMPT,
    GAP_ANALYSIS_PROMPT,
    INTERVIEW_PREP_PROMPT,
    RECOMMENDATION_PROMPT,
    RESUME_IMPROVEMENT_PROMPT,
)
from app.schemas.analysis import (
    InterviewQuestion,
    InterviewQuestionSet,
    Recommendation,
    ResumeImprovementSet,
)
from app.schemas.job import JobRequirements
from app.schemas.resume import CandidateProfile
from app.services.llm_client import get_chat_model, invoke_with_retry

logger = logging.getLogger(__name__)


def _candidate_summary(profile: CandidateProfile) -> str:
    """Render the candidate profile as plain text for prompt context."""
    lines = [
        f"Skills: {', '.join(profile.skills) or 'none listed'}",
        f"Experience: {'; '.join(profile.experience) or 'none listed'}",
        f"Projects: {'; '.join(profile.projects) or 'none listed'}",
        f"Education: {'; '.join(profile.education) or 'none listed'}",
    ]
    return "\n".join(lines)


def generate_recommendation(
    profile: CandidateProfile,
    decision_bucket: str,
    overall_score: int,
    matched_required: list[str],
    missing_required: list[str],
    matched_preferred: list[str],
    missing_preferred: list[str],
    experience_requirement: str | None,
) -> Recommendation:
    """Ask the LLM to explain the (already-decided) recommendation with evidence-grounded reasoning."""
    llm = get_chat_model().with_structured_output(Recommendation)
    prompt = RECOMMENDATION_PROMPT.format(
        decision_bucket=decision_bucket,
        overall_score=overall_score,
        candidate_skills=", ".join(profile.skills) or "none listed",
        matched_required=", ".join(matched_required) or "none",
        missing_required=", ".join(missing_required) or "none",
        matched_preferred=", ".join(matched_preferred) or "none",
        missing_preferred=", ".join(missing_preferred) or "none",
        years_of_experience=profile.years_of_experience or "unknown",
        experience_requirement=experience_requirement or "not specified",
    )
    result = invoke_with_retry(llm, prompt)
    # The decision bucket is deterministic - enforce it even if the LLM drifted.
    result.decision = decision_bucket
    return result


def generate_resume_improvements(
    profile: CandidateProfile, missing_required: list[str], missing_preferred: list[str]
) -> list[str]:
    # json_mode instead of forced function-calling: this prompt's long, prose-friendly
    # nature made some models skip the forced tool call entirely (observed live on
    # openai/gpt-oss-120b via Groq). json_mode asks for plain JSON, which the same
    # models follow far more reliably - see prompts.RESUME_IMPROVEMENT_PROMPT for the
    # matching explicit-shape instruction json_mode requires.
    llm = get_chat_model().with_structured_output(ResumeImprovementSet, method="json_mode")
    prompt = RESUME_IMPROVEMENT_PROMPT.format(
        candidate_summary=_candidate_summary(profile),
        missing_required=", ".join(missing_required) or "none",
        missing_preferred=", ".join(missing_preferred) or "none",
    )
    result = invoke_with_retry(llm, prompt)
    return result.improvements


def generate_cover_letter(
    profile: CandidateProfile, job: JobRequirements, matched_required: list[str]
) -> str:
    """Return a complete, ready-to-copy-paste cover letter.

    Only the three body paragraphs are LLM-generated (grounded in resume/job
    evidence, per COVER_LETTER_PROMPT). The date, greeting, and signature
    block are assembled here deterministically from data already extracted
    from the resume/job posting - the candidate's real name, email, phone,
    and the company name - so the user never has to fill their own details
    back in by hand, and the signature can't be hallucinated by the model.
    """
    llm = get_chat_model()
    prompt = COVER_LETTER_PROMPT.format(
        role=job.role or "the advertised role",
        company=job.company or "the company",
        candidate_summary=_candidate_summary(profile),
        matched_required=", ".join(matched_required) or "none",
        responsibilities="; ".join(job.responsibilities) or "not specified",
    )
    response = invoke_with_retry(llm, prompt)
    body = response.content.strip()

    today = date.today().strftime("%B %d, %Y")
    greeting = f"Dear {job.company} Hiring Team," if job.company else "Dear Hiring Manager,"

    signature = [profile.name or "[Your Name]"]
    contact_bits = [bit for bit in (profile.email, profile.phone, profile.location) if bit]
    if contact_bits:
        signature.append(" | ".join(contact_bits))

    return "\n\n".join([today, greeting, body, "Sincerely,", "\n".join(signature)])


def generate_gap_analysis(
    profile: CandidateProfile,
    overall_score: int,
    missing_required: list[str],
    missing_preferred: list[str],
) -> str:
    llm = get_chat_model()
    prompt = GAP_ANALYSIS_PROMPT.format(
        overall_score=overall_score,
        missing_required=", ".join(missing_required) or "none",
        missing_preferred=", ".join(missing_preferred) or "none",
        candidate_summary=_candidate_summary(profile),
    )
    response = invoke_with_retry(llm, prompt)
    return response.content.strip()


def generate_interview_questions(
    job: JobRequirements, matched_required: list[str], missing_required: list[str]
) -> list[InterviewQuestion]:
    llm = get_chat_model().with_structured_output(InterviewQuestionSet)
    prompt = INTERVIEW_PREP_PROMPT.format(
        role=job.role or "the advertised role",
        matched_required=", ".join(matched_required) or "none",
        missing_required=", ".join(missing_required) or "none",
        responsibilities="; ".join(job.responsibilities) or "not specified",
    )
    result = invoke_with_retry(llm, prompt)
    return result.questions
