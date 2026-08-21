"""Request/response models for the FastAPI layer, separate from the domain
schemas in resume.py/job.py/analysis.py so API shape can evolve independently
of the internal agent state."""
from pydantic import BaseModel

from app.schemas.analysis import AnalysisResult


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    model_name: str


class AnalyzeResponse(BaseModel):
    result: AnalysisResult
