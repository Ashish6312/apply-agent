"""LLM-based structured extraction of JobRequirements from a job description.

Job descriptions are written in free-form, ambiguous language ("solid
experience with cloud platforms") - this is exactly the kind of semantic
understanding an LLM is good at and deterministic string matching is not,
which is why extraction (not matching/scoring) is the LLM's job here.
"""
import logging

from app.agents.prompts import JOB_EXTRACTION_PROMPT
from app.schemas.job import JobRequirements
from app.services.llm_client import get_chat_model, invoke_with_retry

logger = logging.getLogger(__name__)


def extract_job_requirements(job_description: str, target_role: str | None = None) -> JobRequirements:
    """Ask the LLM to extract structured requirements from a job description."""
    llm = get_chat_model().with_structured_output(JobRequirements)
    prompt = JOB_EXTRACTION_PROMPT.format(
        job_description=job_description,
        target_role_hint=target_role or "not specified",
    )
    return invoke_with_retry(llm, prompt)
