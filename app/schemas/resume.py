"""Structured representation of a candidate, extracted from resume text.

Using a Pydantic model (instead of parsing free-form LLM text later) means
every downstream node gets a typed, validated object instead of guessing
at string formats.
"""
from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    name: str | None = Field(default=None, description="Candidate's full name, if present in resume")
    email: str | None = Field(default=None, description="Contact email, if present in resume")
    phone: str | None = Field(default=None, description="Contact phone number, if present in resume")
    location: str | None = Field(default=None, description="City/region, if present in resume")
    skills: list[str] = Field(
        default_factory=list,
        description="Skills explicitly stated in the resume (tools, languages, frameworks). "
        "Never invent skills that are not written in the resume text.",
    )
    experience: list[str] = Field(
        default_factory=list,
        description="Short summaries of work experience entries, taken directly from the resume "
        "(e.g. 'Backend Intern at Acme Corp - built REST APIs in Django'). One string per role.",
    )
    projects: list[str] = Field(
        default_factory=list,
        description="Short summaries of projects mentioned in the resume.",
    )
    education: list[str] = Field(
        default_factory=list,
        description="Education entries as written in the resume (degree, institution, year).",
    )
    years_of_experience: float | None = Field(
        default=None,
        description="Approximate total professional years of experience, only if it can be "
        "reasonably inferred from dates in the resume. Otherwise null.",
    )
