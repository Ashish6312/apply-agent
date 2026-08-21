"""FastAPI routes. Kept thin on purpose - all business logic lives in the
agent graph / services layer, this file only handles HTTP concerns
(validation, status codes, wiring the request into an AgentState)."""
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.graph import compiled_graph
from app.core.config import get_settings
from app.schemas.analysis import AnalysisResult
from app.schemas.api import AnalyzeResponse, HealthResponse
from app.services.llm_client import LLMConfigurationError

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB - generous for a text-based resume PDF


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", llm_provider=settings.llm_provider, model_name=settings.model_name)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    resume: UploadFile = File(..., description="Candidate resume, PDF format"),
    job_description: str = Form(..., description="Full job description text"),
    target_role: str | None = Form(default=None, description="Optional target role/preference hint"),
) -> AnalyzeResponse:
    if resume.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Resume must be a PDF file.")

    resume_bytes = await resume.read()
    if not resume_bytes:
        raise HTTPException(status_code=400, detail="Resume file is empty.")
    if len(resume_bytes) > MAX_RESUME_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Resume file exceeds 5MB limit.")

    if not job_description or not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    settings = get_settings()
    if not settings.active_api_key():
        raise HTTPException(
            status_code=400,
            detail=f"Missing API key for LLM_PROVIDER='{settings.llm_provider}'. Set it in .env and restart.",
        )

    initial_state = {
        "resume_bytes": resume_bytes,
        "job_description": job_description,
        "target_role": target_role,
        "execution_trace": [],
        "errors": [],
    }

    try:
        final_state = compiled_graph.invoke(initial_state)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent graph execution failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    result = AnalysisResult(
        candidate_profile=final_state["candidate_profile"],
        job_requirements=final_state["job_requirements"],
        score_breakdown=final_state["score_breakdown"],
        recommendation=final_state["recommendation"],
        resume_improvements=final_state.get("resume_improvements", []),
        cover_letter=final_state.get("cover_letter"),
        gap_analysis=final_state.get("gap_analysis"),
        interview_questions=final_state.get("interview_questions", []),
        execution_trace=final_state.get("execution_trace", []),
        errors=final_state.get("errors", []),
    )
    return AnalyzeResponse(result=result)
