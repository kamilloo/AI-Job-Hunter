from enum import Enum
from pydantic import BaseModel, Field, HttpUrl

class Eligibility(str, Enum):
    eligible = "eligible"
    review = "review"
    rejected = "rejected"

class JobAnalysis(BaseModel):
    reasons: list[str]
    concerns: list[str]

    ai_transition_score: int = Field(ge=0, le=100)

    location_eligibility: Eligibility
    location_evidence: str

    recommendation: str


class Job(BaseModel):
    provider: str
    board: str
    external_id: str
    company: str
    title: str
    location: str = "Unknown"
    description: str = ""
    url: HttpUrl
    apply_url: HttpUrl | None = None
    remote: bool | None = None
    salary_text: str | None = None
    updated_at: str | None = None
    verified_live: bool = False
    verified_at: str | None = None
    @property
    def key(self) -> str:
        return f"{self.provider}:{self.board}:{self.external_id}"

class Match(BaseModel):
    key: str
    eligibility: Eligibility
    score: int = Field(ge=0, le=100)
    ai_transition_score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    ai_analyzed: bool = False

class JobHunter(BaseModel):
    job: Job
    eligibility: Eligibility
    match: Match


