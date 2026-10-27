from functools import partial

from pydantic import BaseModel, Field
from enum import Enum

from job_hunter.models import Eligibility
from job_hunter.validation.evidence import EvidenceValidation


class RequirementStatus(str, Enum):
    met = "met"
    unmet = "unmet"
    unknown = "unknown"

class TechnicalFit(str, Enum):
    strong = "strong"
    partial = "partial"
    weak = "weak"

class TechnicalRequirement(BaseModel):
    name: str
    mandatory: bool
    status: RequirementStatus

    job_evidence: str
    evidence_validation: EvidenceValidation | None = None
    candidate_evidence: str

    explanation: str

class TechnicalAssessment(BaseModel):
    requirements: list[TechnicalRequirement]

    summary: str
    confidence: float = Field(ge=0, le=1)
    technical_fit: TechnicalFit | None = None


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

class MatchingAssessment(BaseModel):
    technical_fit: TechnicalFit | None = None
    requirement_verification: Eligibility
    final_eligibility: Eligibility



