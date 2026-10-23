from pydantic import BaseModel, Field

from job_hunter.models import Eligibility


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



