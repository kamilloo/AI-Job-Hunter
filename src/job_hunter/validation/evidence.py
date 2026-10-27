import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceValidation:
    valid: bool
    reason: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def validate_job_evidence(
    job_description: str,
    evidence: str,
) -> EvidenceValidation:
    if not evidence or not evidence.strip():
        return EvidenceValidation(
            False,
            "Evidence is required",
        )

    normalized_description = normalize(job_description)
    normalized_evidence = normalize(evidence)

    if normalized_evidence in normalized_description:
        return EvidenceValidation(
            True,
            "Evidence found in job description",
        )

    return EvidenceValidation(
        False,
        "Evidence not found in job description",
    )