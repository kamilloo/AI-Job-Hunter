import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceValidation:
    valid: bool
    reason: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def validate_candidate_evidence(
    contexts: list[str],
    evidence: str,
) -> EvidenceValidation:
    if not evidence or not evidence.strip():
        return EvidenceValidation(
            False,
            "Evidence is required",
        )

    normalized_evidence = normalize(evidence)
    if any(
        normalized_evidence in normalize(context)
        for context in contexts
    ):
        return EvidenceValidation(
            True,
            "Evidence found in candidate experience",
        )

    return EvidenceValidation(
        False,
        "Evidence not found in candidate experience",
    )