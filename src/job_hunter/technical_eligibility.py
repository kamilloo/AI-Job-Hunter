from job_hunter.model.RequirementAssessment import TechnicalAssessment, RequirementStatus
from job_hunter.models import Eligibility
from job_hunter.model.CandidateExperience import CandidateProfile
from job_hunter.validation.evidence import validate_job_evidence
from job_hunter.validation.validate_candidate_evidence import validate_candidate_evidence

def technical_eligibility(
    assessment: TechnicalAssessment,
) -> Eligibility:

    mandatory = [
        requirement
        for requirement in assessment.requirements
        if requirement.mandatory
    ]

    if any(
        requirement.status == RequirementStatus.unmet
        for requirement in mandatory
    ):
        return Eligibility.review

    if any(
        requirement.status == RequirementStatus.unknown
        for requirement in mandatory
    ):
        return Eligibility.review

    return Eligibility.eligible


def grounded_technical_eligibility(
    assessment: TechnicalAssessment,
    candidate_profile: dict,
    job_description: str,
) -> Eligibility:
    """Apply the same quotation and uncertainty policy in CLI and evaluations.

    Quotation provenance does not establish semantic sufficiency. Missing or
    unsupported evidence requires review, never a confirmed rejection.
    """
    candidate = CandidateProfile.model_validate(candidate_profile)
    contexts = [experience.context for experience in candidate.skill_experiences if experience.context.strip()]
    if not assessment.requirements or not any(r.mandatory for r in assessment.requirements):
        return Eligibility.review
    grounded = True
    for requirement in assessment.requirements:
        requirement.evidence_validation = validate_job_evidence(job_description, requirement.job_evidence)
        if not requirement.evidence_validation.valid:
            grounded = False
        if requirement.status != RequirementStatus.unknown and not validate_candidate_evidence(contexts, requirement.candidate_evidence).valid:
            grounded = False
    return technical_eligibility(assessment) if grounded else Eligibility.review
