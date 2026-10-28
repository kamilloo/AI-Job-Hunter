from typing import List

from pydantic import BaseModel, Field


class CandidateExperience(BaseModel):
    technology: str
    context: str
    production: bool | None = None
    years: float | None = Field(default=None, ge=0)


class CandidateProfile(BaseModel):
    core_skills: list[str] = Field(default_factory=list)
    skill_experiences: list[CandidateExperience] = Field(
        default_factory=list
    )
