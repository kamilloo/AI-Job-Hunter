from pydantic import BaseModel, Field
from enum import Enum

from job_hunter.models import Eligibility

class RequirementStatus(str, Enum):
    met = "met"
    unmet = "unmet"
    unknown = "unknown"

class TechnicalRequirement(BaseModel):
    name: str
    mandatory: bool
    status: RequirementStatus

    job_evidence: str
    candidate_evidence: str

    explanation: str

class TechnicalAssessment(BaseModel):
    requirements: list[TechnicalRequirement]

    summary: str
    confidence: float = Field(ge=0, le=1)


class RequirementAssessment(BaseModel):
    requirement: str
    mandatory: bool
    candidate_evidence: str | None = None
    status: str # met,unmet, unknown

class AIRequirementAssessment(BaseModel):
    requirements: list[RequirementAssessment]
    eligibility: Eligibility
    explanation: str
    confidence: float = Field(ge=0, le=1)



