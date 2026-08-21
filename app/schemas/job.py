"""Structured representation of a job posting, extracted from a job description."""
from pydantic import BaseModel, Field


class JobRequirements(BaseModel):
    role: str | None = Field(default=None, description="Job title / role name")
    company: str | None = Field(
        default=None, description="Hiring company/organization name, if stated in the posting"
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Skills/technologies explicitly described as required, must-have, or "
        "essential in the job description.",
    )
    preferred_skills: list[str] = Field(
        default_factory=list,
        description="Skills described as preferred, nice-to-have, or a bonus in the job description.",
    )
    responsibilities: list[str] = Field(
        default_factory=list,
        description="Key responsibilities / day-to-day duties listed in the job description.",
    )
    experience_requirements: str | None = Field(
        default=None,
        description="Stated experience requirement, e.g. '2+ years backend development'. Null if not mentioned.",
    )
