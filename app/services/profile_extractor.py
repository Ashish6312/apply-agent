"""LLM-based structured extraction of a CandidateProfile from raw resume text.

Separated from resume_parser.py on purpose: resume_parser.py is pure
deterministic file handling (PDF -> text), this module is the one place
that asks the LLM to *read* that text and structure it. Keeping the two
apart makes the "deterministic vs LLM" split visible in the file layout,
not just in comments.
"""
import logging

from app.agents.prompts import RESUME_EXTRACTION_PROMPT
from app.schemas.resume import CandidateProfile
from app.services.llm_client import get_chat_model, invoke_with_retry

logger = logging.getLogger(__name__)


def extract_candidate_profile(resume_text: str) -> CandidateProfile:
    """Ask the LLM to extract a structured profile, grounded strictly in resume_text.

    The prompt instructs the model to only report skills/experience that are
    literally present in the text (see prompts.py) - this is the main
    anti-hallucination guard for resume parsing.
    """
    llm = get_chat_model().with_structured_output(CandidateProfile)
    prompt = RESUME_EXTRACTION_PROMPT.format(resume_text=resume_text)
    return invoke_with_retry(llm, prompt)  # already validated as CandidateProfile by with_structured_output
